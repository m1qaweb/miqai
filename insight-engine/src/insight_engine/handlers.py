"""
Global exception handlers for FastAPI application.

This module provides centralized exception handling with structured error responses,
logging, and correlation ID tracking.
"""

import logging
import traceback
from datetime import datetime
from typing import Union

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from insight_engine.exceptions import (
    InsightEngineException,
    AuthenticationException,
    VideoException,
    AIException,
    ExternalServiceException,
    RateLimitException,
    DataException,
    ValidationException,
    ConfigurationException,
    ErrorCode,
)
from insight_engine.schemas.error import (
    ErrorResponse,
    ValidationErrorResponse,
    RateLimitErrorResponse,
    ErrorDetail,
)

logger = logging.getLogger(__name__)


def get_correlation_id(request: Request) -> str:
    """Extract correlation ID from request headers or generate new one."""
    return getattr(request.state, "correlation_id", "unknown")


def get_user_id(request: Request) -> str:
    """Extract user ID from request if authenticated."""
    return getattr(request.state, "user_id", None)


def get_request_id(request: Request) -> str:
    """Extract request ID from request headers."""
    return request.headers.get("x-request-id") or getattr(request.state, "request_id", None)


async def insight_engine_exception_handler(
    request: Request, 
    exc: InsightEngineException
) -> JSONResponse:
    """
    Handle custom InsightEngineException instances.
    
    Converts custom exceptions to structured JSON responses with appropriate
    HTTP status codes and detailed error information.
    """
    # Determine HTTP status code based on exception type
    status_code = _get_status_code_for_exception(exc)
    
    # Create error response
    error_response = ErrorResponse(
        error_code=exc.error_code.value,
        message=exc.message,
        details=exc.details,
        correlation_id=exc.correlation_id or get_correlation_id(request),
        timestamp=datetime.fromisoformat(exc.timestamp),
        path=str(request.url.path),
        method=request.method,
        user_id=exc.user_id or get_user_id(request),
        request_id=exc.request_id or get_request_id(request),
    )
    
    # Log the error with context
    logger.error(
        f"Application error: {exc.error_code.value}",
        extra={
            "error_data": exc.to_dict(),
            "request_path": str(request.url.path),
            "request_method": request.method,
            "status_code": status_code,
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(exclude_none=True)
    )


async def rate_limit_exception_handler(
    request: Request,
    exc: RateLimitException
) -> JSONResponse:
    """Handle rate limiting exceptions with retry information."""
    error_response = RateLimitErrorResponse(
        error_code=exc.error_code.value,
        message=exc.message,
        details=exc.details,
        correlation_id=exc.correlation_id or get_correlation_id(request),
        timestamp=datetime.fromisoformat(exc.timestamp),
        path=str(request.url.path),
        method=request.method,
        user_id=exc.user_id or get_user_id(request),
        request_id=exc.request_id or get_request_id(request),
        limit=exc.details.get("limit"),
        window=exc.details.get("window"),
        retry_after=exc.details.get("retry_after"),
        remaining=exc.details.get("remaining"),
    )
    
    logger.warning(
        f"Rate limit exceeded: {exc.error_code.value}",
        extra={
            "error_data": exc.to_dict(),
            "request_path": str(request.url.path),
            "request_method": request.method,
        }
    )
    
    # Add Retry-After header if available
    headers = {}
    if exc.details.get("retry_after"):
        headers["Retry-After"] = str(exc.details["retry_after"])
    
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=error_response.model_dump(exclude_none=True),
        headers=headers
    )


async def validation_exception_handler(
    request: Request,
    exc: Union[RequestValidationError, ValidationError, ValidationException]
) -> JSONResponse:
    """Handle validation errors with detailed field information."""
    correlation_id = get_correlation_id(request)
    
    if isinstance(exc, ValidationException):
        # Handle our custom validation exception
        error_response = ValidationErrorResponse(
            error_code=exc.error_code.value,
            message=exc.message,
            details=exc.details,
            correlation_id=correlation_id,
            timestamp=datetime.fromisoformat(exc.timestamp),
            path=str(request.url.path),
            method=request.method,
            user_id=exc.user_id or get_user_id(request),
            request_id=exc.request_id or get_request_id(request),
            validation_errors=[
                ErrorDetail(
                    field=exc.details.get("field"),
                    message=exc.message,
                    code=exc.error_code.value,
                    value=exc.details.get("invalid_value")
                )
            ]
        )
    else:
        # Handle FastAPI/Pydantic validation errors
        validation_errors = []
        
        if isinstance(exc, RequestValidationError):
            for error in exc.errors():
                field_path = ".".join(str(loc) for loc in error["loc"])
                validation_errors.append(
                    ErrorDetail(
                        field=field_path,
                        message=error["msg"],
                        code=error["type"],
                        value=error.get("input")
                    )
                )
        elif isinstance(exc, ValidationError):
            for error in exc.errors():
                field_path = ".".join(str(loc) for loc in error["loc"])
                validation_errors.append(
                    ErrorDetail(
                        field=field_path,
                        message=error["msg"],
                        code=error["type"],
                        value=error.get("input")
                    )
                )
        
        error_response = ValidationErrorResponse(
            error_code=ErrorCode.VALIDATION_ERROR.value,
            message="Validation failed",
            correlation_id=correlation_id,
            timestamp=datetime.utcnow(),
            path=str(request.url.path),
            method=request.method,
            user_id=get_user_id(request),
            request_id=get_request_id(request),
            validation_errors=validation_errors
        )
    
    logger.warning(
        "Validation error",
        extra={
            "validation_errors": [err.model_dump() for err in error_response.validation_errors],
            "request_path": str(request.url.path),
            "request_method": request.method,
            "correlation_id": correlation_id,
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(exclude_none=True)
    )


async def http_exception_handler(
    request: Request,
    exc: Union[HTTPException, StarletteHTTPException]
) -> JSONResponse:
    """Handle standard HTTP exceptions."""
    correlation_id = get_correlation_id(request)
    
    error_response = ErrorResponse(
        error_code=f"HTTP{exc.status_code}",
        message=exc.detail if hasattr(exc, 'detail') else str(exc),
        correlation_id=correlation_id,
        timestamp=datetime.utcnow(),
        path=str(request.url.path),
        method=request.method,
        user_id=get_user_id(request),
        request_id=get_request_id(request),
    )
    
    # Log based on severity
    if exc.status_code >= 500:
        logger.error(
            f"HTTP {exc.status_code} error",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail if hasattr(exc, 'detail') else str(exc),
                "request_path": str(request.url.path),
                "request_method": request.method,
                "correlation_id": correlation_id,
            }
        )
    else:
        logger.warning(
            f"HTTP {exc.status_code} error",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail if hasattr(exc, 'detail') else str(exc),
                "request_path": str(request.url.path),
                "request_method": request.method,
                "correlation_id": correlation_id,
            }
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(exclude_none=True)
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with generic error response."""
    correlation_id = get_correlation_id(request)
    
    error_response = ErrorResponse(
        error_code=ErrorCode.INTERNAL_SERVER_ERROR.value,
        message="An unexpected error occurred",
        correlation_id=correlation_id,
        timestamp=datetime.utcnow(),
        path=str(request.url.path),
        method=request.method,
        user_id=get_user_id(request),
        request_id=get_request_id(request),
        details={"exception_type": type(exc).__name__}
    )
    
    logger.error(
        "Unhandled exception",
        extra={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "request_path": str(request.url.path),
            "request_method": request.method,
            "correlation_id": correlation_id,
            "traceback": traceback.format_exc(),
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(exclude_none=True)
    )


def _get_status_code_for_exception(exc: InsightEngineException) -> int:
    """Map custom exceptions to appropriate HTTP status codes."""
    if isinstance(exc, AuthenticationException):
        if isinstance(exc, (InvalidTokenException, TokenExpiredException)):
            return status.HTTP_401_UNAUTHORIZED
        elif isinstance(exc, InsufficientPermissionsException):
            return status.HTTP_403_FORBIDDEN
        else:
            return status.HTTP_401_UNAUTHORIZED
    
    elif isinstance(exc, ValidationException):
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    
    elif isinstance(exc, (VideoNotFoundException, DataNotFoundException)):
        return status.HTTP_404_NOT_FOUND
    
    elif isinstance(exc, RateLimitException):
        return status.HTTP_429_TOO_MANY_REQUESTS
    
    elif isinstance(exc, ConfigurationException):
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    
    elif isinstance(exc, ExternalServiceException):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    
    elif isinstance(exc, (VideoException, AIException)):
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    
    else:
        return status.HTTP_500_INTERNAL_SERVER_ERROR


def register_exception_handlers(app):
    """Register all exception handlers with the FastAPI application."""
    
    # Custom exception handlers
    app.add_exception_handler(InsightEngineException, insight_engine_exception_handler)
    app.add_exception_handler(RateLimitException, rate_limit_exception_handler)
    app.add_exception_handler(ValidationException, validation_exception_handler)
    
    # Standard exception handlers
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)