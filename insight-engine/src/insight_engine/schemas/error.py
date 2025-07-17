"""
Error response schemas for structured API error responses.

This module defines Pydantic models for consistent error response formatting
across all API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Individual error detail for validation errors."""
    
    field: Optional[str] = Field(None, description="Field that caused the error")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")
    value: Optional[Any] = Field(None, description="Invalid value that caused the error")


class ErrorResponse(BaseModel):
    """Standard error response model for all API errors."""
    
    error_code: str = Field(..., description="Unique error code for identification")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None, 
        description="Additional error context and metadata"
    )
    correlation_id: str = Field(..., description="Unique correlation ID for request tracking")
    timestamp: datetime = Field(..., description="Error occurrence timestamp")
    path: Optional[str] = Field(None, description="API path where error occurred")
    method: Optional[str] = Field(None, description="HTTP method used")
    user_id: Optional[str] = Field(None, description="User ID if authenticated")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")


class ValidationErrorResponse(ErrorResponse):
    """Extended error response for validation errors."""
    
    validation_errors: List[ErrorDetail] = Field(
        default_factory=list,
        description="List of validation error details"
    )


class RateLimitErrorResponse(ErrorResponse):
    """Extended error response for rate limiting errors."""
    
    limit: Optional[int] = Field(None, description="Rate limit threshold")
    window: Optional[str] = Field(None, description="Rate limit time window")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")
    remaining: Optional[int] = Field(None, description="Remaining requests in window")


class ServiceUnavailableResponse(ErrorResponse):
    """Extended error response for service unavailability."""
    
    service: Optional[str] = Field(None, description="Unavailable service name")
    estimated_recovery: Optional[datetime] = Field(
        None, 
        description="Estimated service recovery time"
    )
    alternative_endpoints: Optional[List[str]] = Field(
        None,
        description="Alternative endpoints if available"
    )


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="Application version")
    services: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Individual service health status"
    )
    uptime: Optional[float] = Field(None, description="Application uptime in seconds")


class ServiceHealth(BaseModel):
    """Individual service health status."""
    
    status: str = Field(..., description="Service status (healthy/unhealthy/degraded)")
    response_time: Optional[float] = Field(None, description="Service response time in ms")
    last_check: datetime = Field(..., description="Last health check timestamp")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional service-specific metadata"
    )