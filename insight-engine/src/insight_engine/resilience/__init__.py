"""
Resilience patterns for external service calls.

This module provides circuit breaker, retry logic, timeout handling,
rate limiting, and fallback mechanisms for external service integrations.
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerState
from .retry import RetryConfig, retry_with_backoff
from .timeout import TimeoutConfig, with_timeout
from .rate_limiter import RateLimitConfig, get_rate_limiter, rate_limited_call
from .decorators import (
    resilient, 
    http_resilient, 
    gcp_resilient, 
    background_task_resilient,
    database_resilient
)
from .exceptions import (
    ResilienceError,
    CircuitBreakerOpenError,
    RetryExhaustedError,
    TimeoutError,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerState", 
    "RetryConfig",
    "retry_with_backoff",
    "TimeoutConfig",
    "with_timeout",
    "RateLimitConfig",
    "get_rate_limiter",
    "rate_limited_call",
    "resilient",
    "http_resilient",
    "gcp_resilient",
    "background_task_resilient",
    "database_resilient",
    "ResilienceError",
    "CircuitBreakerOpenError",
    "RetryExhaustedError",
    "TimeoutError",
]