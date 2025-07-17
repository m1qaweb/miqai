"""Circuit breaker implementation for external service calls."""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Union
from dataclasses import dataclass
import logging

from .exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests due to failures
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: float = 30.0  # Seconds before trying half-open
    success_threshold: int = 3  # Successful calls needed to close from half-open
    timeout_window: float = 60.0  # Time window for counting failures
    

class CircuitBreaker:
    """
    Circuit breaker implementation for protecting external service calls.
    
    The circuit breaker prevents cascading failures by:
    - Tracking failures over time
    - Opening the circuit when failure threshold is exceeded
    - Allowing limited testing when in half-open state
    - Closing the circuit when service recovers
    """
    
    def __init__(self, service_name: str, config: Optional[CircuitBreakerConfig] = None):
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()
        
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._state_change_time = time.time()
        self._lock = asyncio.Lock()
        
        logger.info(f"Circuit breaker initialized for service '{service_name}'")
    
    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self._state
    
    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The result of the function call
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception raised by the function
        """
        async with self._lock:
            await self._update_state()
            
            if self._state == CircuitBreakerState.OPEN:
                logger.warning(
                    f"Circuit breaker OPEN for service '{self.service_name}', "
                    f"blocking request after {self._failure_count} failures"
                )
                raise CircuitBreakerOpenError(self.service_name, self._failure_count)
            
            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.info(f"Circuit breaker HALF_OPEN for service '{self.service_name}', testing recovery")
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Record success
            await self._record_success()
            return result
            
        except Exception as e:
            # Record failure
            await self._record_failure()
            raise e
    
    async def _update_state(self) -> None:
        """Update circuit breaker state based on current conditions."""
        current_time = time.time()
        
        if self._state == CircuitBreakerState.OPEN:
            # Check if we should transition to half-open
            if current_time - self._state_change_time >= self.config.recovery_timeout:
                await self._transition_to_half_open()
        
        elif self._state == CircuitBreakerState.CLOSED:
            # Reset failure count if timeout window has passed
            if (current_time - self._last_failure_time >= self.config.timeout_window and 
                self._failure_count > 0):
                logger.debug(f"Resetting failure count for service '{self.service_name}'")
                self._failure_count = 0
    
    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                logger.debug(
                    f"Success recorded for service '{self.service_name}' "
                    f"({self._success_count}/{self.config.success_threshold})"
                )
                
                if self._success_count >= self.config.success_threshold:
                    await self._transition_to_closed()
            
            elif self._state == CircuitBreakerState.CLOSED:
                # Reset failure count on success
                if self._failure_count > 0:
                    logger.debug(f"Resetting failure count for service '{self.service_name}' after success")
                    self._failure_count = 0
    
    async def _record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            logger.warning(
                f"Failure recorded for service '{self.service_name}' "
                f"({self._failure_count}/{self.config.failure_threshold})"
            )
            
            if self._state == CircuitBreakerState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    await self._transition_to_open()
            
            elif self._state == CircuitBreakerState.HALF_OPEN:
                # Any failure in half-open state transitions back to open
                await self._transition_to_open()
    
    async def _transition_to_open(self) -> None:
        """Transition circuit breaker to OPEN state."""
        self._state = CircuitBreakerState.OPEN
        self._state_change_time = time.time()
        self._success_count = 0
        
        logger.error(
            f"Circuit breaker OPENED for service '{self.service_name}' "
            f"after {self._failure_count} failures"
        )
    
    async def _transition_to_half_open(self) -> None:
        """Transition circuit breaker to HALF_OPEN state."""
        self._state = CircuitBreakerState.HALF_OPEN
        self._state_change_time = time.time()
        self._success_count = 0
        
        logger.info(f"Circuit breaker transitioned to HALF_OPEN for service '{self.service_name}'")
    
    async def _transition_to_closed(self) -> None:
        """Transition circuit breaker to CLOSED state."""
        self._state = CircuitBreakerState.CLOSED
        self._state_change_time = time.time()
        self._failure_count = 0
        self._success_count = 0
        
        logger.info(f"Circuit breaker CLOSED for service '{self.service_name}' - service recovered")
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "service_name": self.service_name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "state_change_time": self._state_change_time,
            "last_failure_time": self._last_failure_time,
        }