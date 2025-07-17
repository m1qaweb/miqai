"""Timeout management for external service calls."""

import asyncio
from typing import Any, Callable, Optional, TypeVar
from dataclasses import dataclass
import logging

from .exceptions import TimeoutError as ResilienceTimeoutError

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior."""
    connect_timeout: float = 10.0  # Connection timeout in seconds
    read_timeout: float = 30.0     # Read timeout in seconds
    total_timeout: float = 60.0    # Total operation timeout in seconds


class TimeoutManager:
    """Manages timeouts for external service calls."""
    
    def __init__(self, service_name: str, config: Optional[TimeoutConfig] = None):
        self.service_name = service_name
        self.config = config or TimeoutConfig()
    
    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function with timeout protection.
        
        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The result of the function call
            
        Raises:
            TimeoutError: If the operation times out
            Exception: Any exception raised by the function
        """
        try:
            logger.debug(
                f"Executing call to service '{self.service_name}' "
                f"with timeout {self.config.total_timeout}s"
            )
            
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.total_timeout
                )
            else:
                # For sync functions, run in thread pool with timeout
                result = await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=self.config.total_timeout
                )
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(
                f"Service '{self.service_name}' call timed out after {self.config.total_timeout}s"
            )
            raise ResilienceTimeoutError(self.service_name, self.config.total_timeout)


async def with_timeout(
    func: Callable[..., T],
    service_name: str,
    config: Optional[TimeoutConfig] = None,
    *args,
    **kwargs
) -> T:
    """
    Convenience function to execute a function with timeout protection.
    
    Args:
        func: The function to execute
        service_name: Name of the service for logging
        config: Timeout configuration
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        The result of the function call
    """
    timeout_manager = TimeoutManager(service_name, config)
    return await timeout_manager.execute(func, *args, **kwargs)