"""Rate limiting for external API calls."""

import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 10.0
    burst_size: int = 20
    window_size: float = 60.0  # Time window in seconds


class TokenBucket:
    """Token bucket implementation for rate limiting."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.burst_size
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False if rate limited
        """
        async with self._lock:
            now = time.time()
            
            # Refill tokens based on time elapsed
            time_elapsed = now - self.last_refill
            tokens_to_add = time_elapsed * self.config.requests_per_second
            self.tokens = min(self.config.burst_size, self.tokens + tokens_to_add)
            self.last_refill = now
            
            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                logger.warning(f"Rate limit exceeded, tokens available: {self.tokens}, requested: {tokens}")
                return False
    
    async def wait_for_tokens(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Wait for tokens to become available.
        
        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if tokens were acquired, False if timeout
        """
        start_time = time.time()
        
        while True:
            if await self.acquire(tokens):
                return True
            
            if timeout and (time.time() - start_time) >= timeout:
                return False
            
            # Calculate wait time until next token is available
            wait_time = min(1.0 / self.config.requests_per_second, 1.0)
            await asyncio.sleep(wait_time)


class RateLimiter:
    """Rate limiter for external service calls."""
    
    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._configs: Dict[str, RateLimitConfig] = {}
        self._setup_default_configs()
    
    def _setup_default_configs(self):
        """Setup default rate limiting configurations."""
        # HTTP API services
        self._configs["http_api"] = RateLimitConfig(
            requests_per_second=10.0,
            burst_size=20,
            window_size=60.0
        )
        
        # Google Cloud services (more conservative)
        self._configs["gcp"] = RateLimitConfig(
            requests_per_second=5.0,
            burst_size=10,
            window_size=60.0
        )
        
        # Background tasks
        self._configs["background_task"] = RateLimitConfig(
            requests_per_second=2.0,
            burst_size=5,
            window_size=60.0
        )
    
    def get_bucket(self, service_name: str, service_type: str = "http_api") -> TokenBucket:
        """Get or create a token bucket for a service."""
        if service_name not in self._buckets:
            config = self._configs.get(service_type, self._configs["http_api"])
            self._buckets[service_name] = TokenBucket(config)
            logger.info(f"Created rate limiter for service '{service_name}' with {config.requests_per_second} req/s")
        
        return self._buckets[service_name]
    
    async def acquire(self, service_name: str, service_type: str = "http_api", tokens: int = 1) -> bool:
        """Acquire tokens for a service call."""
        bucket = self.get_bucket(service_name, service_type)
        return await bucket.acquire(tokens)
    
    async def wait_for_tokens(
        self, 
        service_name: str, 
        service_type: str = "http_api", 
        tokens: int = 1,
        timeout: Optional[float] = None
    ) -> bool:
        """Wait for tokens to become available for a service call."""
        bucket = self.get_bucket(service_name, service_type)
        return await bucket.wait_for_tokens(tokens, timeout)
    
    def set_config(self, service_type: str, config: RateLimitConfig):
        """Set rate limiting configuration for a service type."""
        self._configs[service_type] = config
        # Clear existing buckets for this service type to pick up new config
        buckets_to_remove = []
        for service_name, bucket in self._buckets.items():
            # This is a simplified approach - in practice you might want to track service types per bucket
            buckets_to_remove.append(service_name)
        
        for service_name in buckets_to_remove:
            del self._buckets[service_name]
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get rate limiter statistics."""
        stats = {}
        for service_name, bucket in self._buckets.items():
            stats[service_name] = {
                "available_tokens": bucket.tokens,
                "max_tokens": bucket.config.burst_size,
                "requests_per_second": bucket.config.requests_per_second,
                "last_refill": bucket.last_refill
            }
        return stats


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def rate_limited_call(
    func,
    service_name: str,
    service_type: str = "http_api",
    tokens: int = 1,
    timeout: Optional[float] = None,
    *args,
    **kwargs
):
    """
    Execute a function with rate limiting.
    
    Args:
        func: Function to execute
        service_name: Name of the service for rate limiting
        service_type: Type of service (http_api, gcp, background_task)
        tokens: Number of tokens to consume
        timeout: Maximum time to wait for tokens
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function call
        
    Raises:
        Exception: If rate limit timeout is exceeded or function fails
    """
    rate_limiter = get_rate_limiter()
    
    # Wait for tokens
    if not await rate_limiter.wait_for_tokens(service_name, service_type, tokens, timeout):
        raise Exception(f"Rate limit timeout exceeded for service '{service_name}'")
    
    # Execute the function
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return func(*args, **kwargs)