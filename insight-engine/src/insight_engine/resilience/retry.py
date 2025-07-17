"""Retry logic with exponential backoff and jitter."""

import asyncio
import random
import time
from typing import Any, Callable, Optional, Set, Type, TypeVar, Union
from dataclasses import dataclass
import logging

from .exceptions import RetryExhaustedError

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Exponential backoff multiplier
    jitter: bool = True  # Add random jitter to prevent thundering herd
    retryable_exceptions: Optional[Set[Type[Exception]]] = None
    
    def __post_init__(self):
        if self.retryable_exceptions is None:
            # Default retryable exceptions for HTTP and network errors
            self.retryable_exceptions = {
                ConnectionError,
                TimeoutError,
                OSError,
            }


class RetryManager:
    """Manages retry logic with exponential backoff."""
    
    def __init__(self, service_name: str, config: Optional[RetryConfig] = None):
        self.service_name = service_name
        self.config = config or RetryConfig()
        
    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function with retry logic.
        
        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The result of the function call
            
        Raises:
            RetryExhaustedError: If all retry attempts are exhausted
            Exception: The last exception if not retryable
        """
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(
                    f"Attempting call to service '{self.service_name}' "
                    f"(attempt {attempt}/{self.config.max_attempts})"
                )
                
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                if attempt > 1:
                    logger.info(
                        f"Service '{self.service_name}' call succeeded on attempt {attempt}"
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if this exception is retryable
                if not self._is_retryable_exception(e):
                    logger.debug(
                        f"Non-retryable exception for service '{self.service_name}': {type(e).__name__}"
                    )
                    raise e
                
                # Don't sleep after the last attempt
                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Service '{self.service_name}' call failed on attempt {attempt}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Service '{self.service_name}' call failed on final attempt {attempt}: {e}"
                    )
        
        # All attempts exhausted
        raise RetryExhaustedError(self.service_name, self.config.max_attempts, last_exception)
    
    def _is_retryable_exception(self, exception: Exception) -> bool:
        """Check if an exception is retryable."""
        # Check if the exception type is in the retryable set
        for retryable_type in self.config.retryable_exceptions:
            if isinstance(exception, retryable_type):
                return True
        
        # Check for HTTP status codes (if using httpx or requests)
        if hasattr(exception, 'response'):
            response = exception.response
            if hasattr(response, 'status_code'):
                # Retry on 5xx server errors and some 4xx errors
                status_code = response.status_code
                if 500 <= status_code < 600:  # Server errors
                    return True
                if status_code in [408, 429]:  # Request timeout, too many requests
                    return True
        
        # Check for Google Cloud transient errors
        if hasattr(exception, 'code'):
            # Google Cloud error codes that are typically transient
            transient_codes = [
                'DEADLINE_EXCEEDED',
                'UNAVAILABLE', 
                'RESOURCE_EXHAUSTED',
                'ABORTED',
                'INTERNAL',
            ]
            if str(exception.code) in transient_codes:
                return True
        
        return False
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number."""
        # Exponential backoff: base_delay * (exponential_base ^ (attempt - 1))
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        
        # Cap at max_delay
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            # Add random jitter up to 25% of the delay
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure delay is not negative
        
        return delay


async def retry_with_backoff(
    func: Callable[..., T],
    service_name: str,
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> T:
    """
    Convenience function to execute a function with retry logic.
    
    Args:
        func: The function to execute
        service_name: Name of the service for logging
        config: Retry configuration
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        The result of the function call
    """
    retry_manager = RetryManager(service_name, config)
    return await retry_manager.execute(func, *args, **kwargs)