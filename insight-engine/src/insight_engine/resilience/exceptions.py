"""Custom exceptions for resilience patterns."""

from typing import Optional


class ResilienceError(Exception):
    """Base exception for resilience-related errors."""
    
    def __init__(self, message: str, service_name: Optional[str] = None):
        super().__init__(message)
        self.service_name = service_name


class CircuitBreakerOpenError(ResilienceError):
    """Raised when circuit breaker is open and blocking requests."""
    
    def __init__(self, service_name: str, failure_count: int):
        message = f"Circuit breaker is OPEN for service '{service_name}' after {failure_count} failures"
        super().__init__(message, service_name)
        self.failure_count = failure_count


class RetryExhaustedError(ResilienceError):
    """Raised when all retry attempts have been exhausted."""
    
    def __init__(self, service_name: str, attempts: int, last_exception: Exception):
        message = f"Retry exhausted for service '{service_name}' after {attempts} attempts"
        super().__init__(message, service_name)
        self.attempts = attempts
        self.last_exception = last_exception


class TimeoutError(ResilienceError):
    """Raised when an operation times out."""
    
    def __init__(self, service_name: str, timeout_seconds: float):
        message = f"Operation timed out for service '{service_name}' after {timeout_seconds}s"
        super().__init__(message, service_name)
        self.timeout_seconds = timeout_seconds