"""
Middleware for request processing, correlation ID tracking, and context management.

This module provides middleware for:
- Correlation ID generation and propagation
- Request/response logging
- Performance monitoring
- Security headers
"""

import time
import uuid
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle correlation ID generation and propagation.
    
    Ensures every request has a unique correlation ID for tracing
    across services and logs.
    """
    
    def __init__(self, app: ASGIApp, header_name: str = "x-correlation-id"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get(self.header_name)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Store in request state for access in handlers
        request.state.correlation_id = correlation_id
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers[self.header_name] = correlation_id
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured request/response logging.
    
    Logs request details, response status, and performance metrics
    with correlation ID for tracing.
    """
    
    def __init__(
        self, 
        app: ASGIApp, 
        log_request_body: bool = False,
        log_response_body: bool = False,
        exclude_paths: list = None
    ):
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        start_time = time.time()
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        
        # Extract request information
        request_info = {
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": request.client.host if request.client else None,
            "correlation_id": correlation_id,
            "user_agent": request.headers.get("user-agent"),
        }
        
        # Log request body if enabled (be careful with sensitive data)
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    request_info["body_size"] = len(body)
                    # Don't log actual body content for security reasons
                    # request_info["body"] = body.decode("utf-8")[:1000]  # First 1000 chars
            except Exception as e:
                logger.warning(f"Failed to read request body: {e}")
        
        logger.info("Request started", extra=request_info)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response information
            response_info = {
                "status_code": response.status_code,
                "process_time": round(process_time, 4),
                "correlation_id": correlation_id,
                "method": request.method,
                "path": str(request.url.path),
            }
            
            # Add processing time header
            response.headers["x-process-time"] = str(process_time)
            
            # Log based on status code
            if response.status_code >= 500:
                logger.error("Request completed with server error", extra=response_info)
            elif response.status_code >= 400:
                logger.warning("Request completed with client error", extra=response_info)
            else:
                logger.info("Request completed successfully", extra=response_info)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "Request failed with exception",
                extra={
                    "exception": str(e),
                    "exception_type": type(e).__name__,
                    "process_time": round(process_time, 4),
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": str(request.url.path),
                },
                exc_info=True
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to responses.
    
    Adds common security headers to protect against various attacks.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and store request context information.
    
    Extracts user information, request ID, and other context
    for use in exception handlers and logging.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract request ID
        request_id = request.headers.get("x-request-id")
        if request_id:
            request.state.request_id = request_id
        
        # Extract user information from JWT token (if present)
        # This would typically decode the JWT token from Authorization header
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                # TODO: Implement JWT token decoding
                # token = auth_header.split(" ")[1]
                # user_info = decode_jwt_token(token)
                # request.state.user_id = user_info.get("user_id")
                # request.state.user_email = user_info.get("email")
                pass
            except Exception as e:
                logger.warning(f"Failed to decode JWT token: {e}")
        
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Basic rate limiting middleware.
    
    Implements simple in-memory rate limiting based on client IP.
    For production, use Redis-based rate limiting.
    """
    
    def __init__(
        self, 
        app: ASGIApp, 
        requests_per_minute: int = 60,
        exclude_paths: list = None
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.exclude_paths = exclude_paths or ["/health", "/metrics"]
        self.request_counts = {}  # In production, use Redis
        self.window_start = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        window_start = self.window_start.get(client_ip, current_time)
        
        # Reset window if more than 60 seconds have passed
        if current_time - window_start > 60:
            self.request_counts[client_ip] = 0
            self.window_start[client_ip] = current_time
            window_start = current_time
        
        # Increment request count
        self.request_counts[client_ip] = self.request_counts.get(client_ip, 0) + 1
        
        # Check rate limit
        if self.request_counts[client_ip] > self.requests_per_minute:
            from insight_engine.exceptions import RateLimitExceededException
            
            retry_after = 60 - (current_time - window_start)
            raise RateLimitExceededException(
                limit=self.requests_per_minute,
                window="60 seconds",
                retry_after=int(retry_after),
                remaining=0,
                correlation_id=getattr(request.state, "correlation_id", None)
            )
        
        return await call_next(request)