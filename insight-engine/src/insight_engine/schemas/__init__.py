"""Schema definitions for the Insight Engine application."""

from .error import (
    ErrorDetail,
    ErrorResponse,
    ValidationErrorResponse,
    RateLimitErrorResponse,
    ServiceUnavailableResponse,
    HealthCheckResponse,
    ServiceHealth,
)

__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "ValidationErrorResponse", 
    "RateLimitErrorResponse",
    "ServiceUnavailableResponse",
    "HealthCheckResponse",
    "ServiceHealth",
]