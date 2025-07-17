"""Decorators for applying resilience patterns to functions."""

import asyncio
import functools
from typing import Any, Callable, Optional, TypeVar, Dict
import logging

from .circuit_breaker import CircuitBreaker
from .retry import RetryManager
from .timeout import TimeoutManager
from .config import resilience_config_manager, ResilienceConfig
from .rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Global registry for circuit breakers (one per service)
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def resilient(
    service_name: str,
    service_type: str = "http_api",
    config: Optional[ResilienceConfig] = None,
    fallback: Optional[Callable] = None
):
    """
    Decorator that applies full resilience patterns (circuit breaker, retry, timeout).
    
    Args:
        service_name: Name of the service for logging and circuit breaker identification
        service_type: Type of service (http_api, gcp, background_task, database)
        config: Custom resilience configuration (optional)
        fallback: Fallback function to call if all attempts fail (optional)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Get configuration
        resilience_config = config or resilience_config_manager.get_config(service_type)
        
        # Get or create circuit breaker for this service
        if service_name not in _circuit_breakers:
            _circuit_breakers[service_name] = CircuitBreaker(
                service_name, resilience_config.circuit_breaker
            )
        circuit_breaker = _circuit_breakers[service_name]
        
        # Create managers
        retry_manager = RetryManager(service_name, resilience_config.retry)
        timeout_manager = TimeoutManager(service_name, resilience_config.timeout)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                # Get rate limiter
                rate_limiter = get_rate_limiter()
                
                # Apply rate limiting first
                if not await rate_limiter.wait_for_tokens(
                    service_name, 
                    service_type, 
                    tokens=1, 
                    timeout=10.0
                ):
                    raise Exception(f"Rate limit timeout exceeded for service '{service_name}'")
                
                # Apply circuit breaker -> retry -> timeout -> function
                async def resilient_call():
                    return await retry_manager.execute(
                        lambda: timeout_manager.execute(func, *args, **kwargs)
                    )
                
                return await circuit_breaker.call(resilient_call)
                
            except Exception as e:
                logger.error(f"All resilience patterns failed for service '{service_name}': {e}")
                
                # Try fallback if available
                if fallback:
                    logger.info(f"Attempting fallback for service '{service_name}'")
                    try:
                        if hasattr(fallback, '__call__'):
                            return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
                    except Exception as fallback_error:
                        logger.error(f"Fallback failed for service '{service_name}': {fallback_error}")
                
                raise e
        
        return wrapper
    return decorator


def http_resilient(
    service_name: str,
    fallback: Optional[Callable] = None
):
    """
    Decorator specifically for HTTP API services with appropriate defaults.
    
    Args:
        service_name: Name of the HTTP service
        fallback: Fallback function to call if all attempts fail (optional)
    """
    return resilient(service_name, "http_api", fallback=fallback)


def gcp_resilient(
    service_name: str,
    fallback: Optional[Callable] = None
):
    """
    Decorator specifically for Google Cloud services with appropriate defaults.
    
    Args:
        service_name: Name of the GCP service
        fallback: Fallback function to call if all attempts fail (optional)
    """
    return resilient(service_name, "gcp", fallback=fallback)


def background_task_resilient(
    service_name: str,
    fallback: Optional[Callable] = None
):
    """
    Decorator specifically for background tasks with appropriate defaults.
    
    Args:
        service_name: Name of the background task
        fallback: Fallback function to call if all attempts fail (optional)
    """
    return resilient(service_name, "background_task", fallback=fallback)


def database_resilient(
    service_name: str,
    fallback: Optional[Callable] = None
):
    """
    Decorator specifically for database operations with appropriate defaults.
    
    Args:
        service_name: Name of the database operation
        fallback: Fallback function to call if all attempts fail (optional)
    """
    return resilient(service_name, "database", fallback=fallback)


def get_circuit_breaker_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all circuit breakers."""
    return {
        name: breaker.get_stats() 
        for name, breaker in _circuit_breakers.items()
    }


def reset_circuit_breaker(service_name: str) -> bool:
    """
    Manually reset a circuit breaker to closed state.
    
    Args:
        service_name: Name of the service
        
    Returns:
        True if circuit breaker was reset, False if not found
    """
    if service_name in _circuit_breakers:
        circuit_breaker = _circuit_breakers[service_name]
        # Reset to closed state
        from .circuit_breaker import CircuitBreakerState
        circuit_breaker._state = CircuitBreakerState.CLOSED
        circuit_breaker._failure_count = 0
        circuit_breaker._success_count = 0
        logger.info(f"Circuit breaker manually reset for service '{service_name}'")
        return True
    return False