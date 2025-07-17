"""Utility modules for the Insight Engine application."""

from .error_utils import (
    set_correlation_id,
    get_correlation_id,
    set_user_id,
    get_user_id,
    set_request_id,
    get_request_id,
    log_error,
    log_warning,
    log_info,
    create_error_context,
    handle_external_service_error,
    safe_execute,
    ErrorContext,
)

__all__ = [
    "set_correlation_id",
    "get_correlation_id", 
    "set_user_id",
    "get_user_id",
    "set_request_id",
    "get_request_id",
    "log_error",
    "log_warning", 
    "log_info",
    "create_error_context",
    "handle_external_service_error",
    "safe_execute",
    "ErrorContext",
]