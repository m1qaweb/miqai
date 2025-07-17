"""
Utility functions for error handling, logging, and context management.

This module provides helper functions for consistent error handling
and structured logging throughout the application.
"""

import logging
import traceback
from contextvars import ContextVar
from typing import Any, Dict, Optional
from uuid import uuid4

from insight_engine.exceptions import InsightEngineException, ErrorCode

# Context variables for request tracking
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')
request_id_var: ContextVar[str] = ContextVar('request_id', default='')

logger = logging.getLogger(__name__)


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID in context."""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Get correlation ID from context."""
    return correlation_id_var.get() or str(uuid4())


def set_user_id(user_id: str) -> None:
    """Set user ID in context."""
    user_id_var.set(user_id)


def get_user_id() -> Optional[str]:
    """Get user ID from context."""
    return user_id_var.get() or None


def set_request_id(request_id: str) -> None:
    """Set request ID in context."""
    request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """Get request ID from context."""
    return request_id_var.get() or None


def log_error(
    exception: Exception,
    message: str = None,
    extra_context: Dict[str, Any] = None,
    include_traceback: bool = True
) -> None:
    """
    Log an error with structured context information.
    
    Args:
        exception: The exception that occurred
        message: Optional custom message
        extra_context: Additional context to include in logs
        include_traceback: Whether to include full traceback
    """
    context = {
        "correlation_id": get_correlation_id(),
        "user_id": get_user_id(),
        "request_id": get_request_id(),
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
    }
    
    if extra_context:
        context.update(extra_context)
    
    if isinstance(exception, InsightEngineException):
        context.update(exception.to_dict())
    
    log_message = message or f"Error occurred: {type(exception).__name__}"
    
    logger.error(
        log_message,
        extra=context,
        exc_info=include_traceback
    )


def log_warning(
    message: str,
    extra_context: Dict[str, Any] = None
) -> None:
    """
    Log a warning with structured context information.
    
    Args:
        message: Warning message
        extra_context: Additional context to include in logs
    """
    context = {
        "correlation_id": get_correlation_id(),
        "user_id": get_user_id(),
        "request_id": get_request_id(),
    }
    
    if extra_context:
        context.update(extra_context)
    
    logger.warning(message, extra=context)


def log_info(
    message: str,
    extra_context: Dict[str, Any] = None
) -> None:
    """
    Log an info message with structured context information.
    
    Args:
        message: Info message
        extra_context: Additional context to include in logs
    """
    context = {
        "correlation_id": get_correlation_id(),
        "user_id": get_user_id(),
        "request_id": get_request_id(),
    }
    
    if extra_context:
        context.update(extra_context)
    
    logger.info(message, extra=context)


def create_error_context(
    operation: str,
    resource_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create standardized error context for exceptions.
    
    Args:
        operation: The operation being performed
        resource_id: ID of the resource being operated on
        **kwargs: Additional context fields
    
    Returns:
        Dictionary with error context
    """
    context = {
        "operation": operation,
        "correlation_id": get_correlation_id(),
        "user_id": get_user_id(),
        "request_id": get_request_id(),
    }
    
    if resource_id:
        context["resource_id"] = resource_id
    
    context.update(kwargs)
    return context


def handle_external_service_error(
    service_name: str,
    operation: str,
    original_exception: Exception,
    resource_id: Optional[str] = None
) -> InsightEngineException:
    """
    Convert external service errors to standardized exceptions.
    
    Args:
        service_name: Name of the external service
        operation: Operation being performed
        original_exception: The original exception from the service
        resource_id: ID of the resource being operated on
    
    Returns:
        Standardized InsightEngineException
    """
    from insight_engine.exceptions import (
        GoogleCloudException,
        RedisConnectionException,
        QdrantConnectionException,
        ExternalServiceException
    )
    
    context = create_error_context(
        operation=operation,
        resource_id=resource_id,
        service=service_name,
        original_error=str(original_exception),
        original_error_type=type(original_exception).__name__
    )
    
    # Map to specific exception types based on service
    if "google" in service_name.lower() or "gcp" in service_name.lower():
        return GoogleCloudException(
            message=f"Google Cloud {service_name} error during {operation}",
            service=service_name,
            details=context,
            correlation_id=get_correlation_id(),
            user_id=get_user_id(),
            request_id=get_request_id()
        )
    elif "redis" in service_name.lower():
        return RedisConnectionException(
            message=f"Redis error during {operation}",
            details=context,
            correlation_id=get_correlation_id(),
            user_id=get_user_id(),
            request_id=get_request_id()
        )
    elif "qdrant" in service_name.lower():
        return QdrantConnectionException(
            message=f"Qdrant error during {operation}",
            details=context,
            correlation_id=get_correlation_id(),
            user_id=get_user_id(),
            request_id=get_request_id()
        )
    else:
        return ExternalServiceException(
            message=f"External service {service_name} error during {operation}",
            error_code=ErrorCode.DEPENDENCY_ERROR,
            details=context,
            correlation_id=get_correlation_id(),
            user_id=get_user_id(),
            request_id=get_request_id()
        )


def safe_execute(
    operation: callable,
    operation_name: str,
    default_return=None,
    log_errors: bool = True,
    reraise: bool = True,
    **context_kwargs
):
    """
    Safely execute an operation with error handling and logging.
    
    Args:
        operation: The operation to execute
        operation_name: Name of the operation for logging
        default_return: Default value to return on error
        log_errors: Whether to log errors
        reraise: Whether to reraise exceptions
        **context_kwargs: Additional context for logging
    
    Returns:
        Operation result or default_return on error
    """
    try:
        return operation()
    except Exception as e:
        if log_errors:
            log_error(
                e,
                f"Error in {operation_name}",
                extra_context=context_kwargs
            )
        
        if reraise:
            raise
        
        return default_return


class ErrorContext:
    """
    Context manager for error handling with automatic logging.
    
    Usage:
        with ErrorContext("video_processing", video_id="123"):
            # Your code here
            pass
    """
    
    def __init__(
        self,
        operation: str,
        log_entry: bool = True,
        log_exit: bool = True,
        **context_kwargs
    ):
        self.operation = operation
        self.log_entry = log_entry
        self.log_exit = log_exit
        self.context = context_kwargs
    
    def __enter__(self) -> "ErrorContext":
        if self.log_entry:
            log_info(f"Starting {self.operation}", extra_context=self.context)
        return self
    
    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> bool:
        if exc_type is not None:
            log_error(
                exc_val,
                f"Error in {self.operation}",
                extra_context=self.context
            )
        elif self.log_exit:
            log_info(f"Completed {self.operation}", extra_context=self.context)
        
        return False  # Don't suppress exceptions