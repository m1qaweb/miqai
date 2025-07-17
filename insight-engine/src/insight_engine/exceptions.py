"""
Custom exception hierarchy for the Insight Engine application.

This module defines a comprehensive exception hierarchy with error codes,
context information, and structured error responses.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, status


class ErrorCode(str, Enum):
    """Enumeration of error codes for consistent error identification."""
    
    # General errors (1000-1999)
    INTERNAL_SERVER_ERROR = "IE1000"
    VALIDATION_ERROR = "IE1001"
    CONFIGURATION_ERROR = "IE1002"
    DEPENDENCY_ERROR = "IE1003"
    
    # Authentication & Authorization errors (2000-2999)
    AUTHENTICATION_FAILED = "IE2000"
    INVALID_TOKEN = "IE2001"
    TOKEN_EXPIRED = "IE2002"
    INSUFFICIENT_PERMISSIONS = "IE2003"
    USER_NOT_FOUND = "IE2004"
    
    # Video processing errors (3000-3999)
    VIDEO_NOT_FOUND = "IE3000"
    VIDEO_UPLOAD_FAILED = "IE3001"
    VIDEO_PROCESSING_FAILED = "IE3002"
    INVALID_VIDEO_FORMAT = "IE3003"
    VIDEO_TOO_LARGE = "IE3004"
    VIDEO_CORRUPTED = "IE3005"
    TRANSCRIPTION_FAILED = "IE3006"
    
    # AI/ML processing errors (4000-4999)
    MODEL_NOT_AVAILABLE = "IE4000"
    INFERENCE_FAILED = "IE4001"
    EMBEDDING_GENERATION_FAILED = "IE4002"
    RAG_PIPELINE_ERROR = "IE4003"
    SUMMARIZATION_FAILED = "IE4004"
    CLIP_EXTRACTION_FAILED = "IE4005"
    
    # External service errors (5000-5999)
    GOOGLE_CLOUD_ERROR = "IE5000"
    REDIS_CONNECTION_ERROR = "IE5001"
    QDRANT_CONNECTION_ERROR = "IE5002"
    STORAGE_ERROR = "IE5003"
    PUBSUB_ERROR = "IE5004"
    CACHE_ERROR = "IE5005"
    CACHE_CONNECTION_ERROR = "IE5006"
    CONNECTION_POOL_ERROR = "IE5007"
    MONITORING_ERROR = "IE5008"
    HEALTH_CHECK_ERROR = "IE5009"
    
    # Data errors (6000-6999)
    DATA_NOT_FOUND = "IE6000"
    DATA_CORRUPTION = "IE6001"
    SCHEMA_VALIDATION_ERROR = "IE6002"
    DATABASE_ERROR = "IE6003"
    
    # Rate limiting & quota errors (7000-7999)
    RATE_LIMIT_EXCEEDED = "IE7000"
    QUOTA_EXCEEDED = "IE7001"
    CONCURRENT_LIMIT_EXCEEDED = "IE7002"


class InsightEngineException(Exception):
    """
    Base exception class for all Insight Engine exceptions.
    
    Provides structured error information including error codes,
    correlation IDs, and contextual metadata.
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.user_id = user_id
        self.request_id = request_id
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for structured logging."""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "exception_type": self.__class__.__name__,
        }
    
    def __str__(self) -> str:
        return f"[{self.error_code.value}] {self.message}"


class ValidationException(InsightEngineException):
    """Exception raised for validation errors."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        if value is not None:
            details["invalid_value"] = str(value)
        
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=details,
            **kwargs
        )


class ConfigurationException(InsightEngineException):
    """Exception raised for configuration errors."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if config_key:
            details["config_key"] = config_key
        
        super().__init__(
            message=message,
            error_code=ErrorCode.CONFIGURATION_ERROR,
            details=details,
            **kwargs
        )


# Authentication & Authorization Exceptions
class AuthenticationException(InsightEngineException):
    """Base class for authentication-related exceptions."""
    pass


class InvalidTokenException(AuthenticationException):
    """Exception raised for invalid authentication tokens."""
    
    def __init__(self, message: str = "Invalid authentication token", **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.INVALID_TOKEN,
            **kwargs
        )


class TokenExpiredException(AuthenticationException):
    """Exception raised for expired authentication tokens."""
    
    def __init__(self, message: str = "Authentication token has expired", **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.TOKEN_EXPIRED,
            **kwargs
        )


class InsufficientPermissionsException(AuthenticationException):
    """Exception raised for insufficient permissions."""
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        required_permission: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if required_permission:
            details["required_permission"] = required_permission
        
        super().__init__(
            message=message,
            error_code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            details=details,
            **kwargs
        )


class UserNotFoundException(AuthenticationException):
    """Exception raised when a user is not found."""
    
    def __init__(self, user_id: str, **kwargs):
        super().__init__(
            message=f"User not found: {user_id}",
            error_code=ErrorCode.USER_NOT_FOUND,
            details={"user_id": user_id},
            **kwargs
        )


# Video Processing Exceptions
class VideoException(InsightEngineException):
    """Base class for video-related exceptions."""
    pass


class VideoNotFoundException(VideoException):
    """Exception raised when a video is not found."""
    
    def __init__(self, video_id: str, **kwargs):
        super().__init__(
            message=f"Video not found: {video_id}",
            error_code=ErrorCode.VIDEO_NOT_FOUND,
            details={"video_id": video_id},
            **kwargs
        )


class VideoUploadException(VideoException):
    """Exception raised for video upload failures."""
    
    def __init__(
        self,
        message: str = "Video upload failed",
        filename: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if filename:
            details["filename"] = filename
        
        super().__init__(
            message=message,
            error_code=ErrorCode.VIDEO_UPLOAD_FAILED,
            details=details,
            **kwargs
        )


class InvalidVideoFormatException(VideoException):
    """Exception raised for invalid video formats."""
    
    def __init__(
        self,
        format_provided: str,
        supported_formats: Optional[list] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details["format_provided"] = format_provided
        if supported_formats:
            details["supported_formats"] = supported_formats
        
        super().__init__(
            message=f"Invalid video format: {format_provided}",
            error_code=ErrorCode.INVALID_VIDEO_FORMAT,
            details=details,
            **kwargs
        )


class VideoTooLargeException(VideoException):
    """Exception raised when video file is too large."""
    
    def __init__(
        self,
        file_size: int,
        max_size: int,
        **kwargs
    ):
        super().__init__(
            message=f"Video file too large: {file_size} bytes (max: {max_size} bytes)",
            error_code=ErrorCode.VIDEO_TOO_LARGE,
            details={"file_size": file_size, "max_size": max_size},
            **kwargs
        )


class VideoProcessingException(VideoException):
    """Exception raised for video processing failures."""
    
    def __init__(
        self,
        message: str = "Video processing failed",
        video_id: Optional[str] = None,
        processing_stage: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if video_id:
            details["video_id"] = video_id
        if processing_stage:
            details["processing_stage"] = processing_stage
        
        super().__init__(
            message=message,
            error_code=ErrorCode.VIDEO_PROCESSING_FAILED,
            details=details,
            **kwargs
        )


class TranscriptionException(VideoException):
    """Exception raised for transcription failures."""
    
    def __init__(
        self,
        message: str = "Video transcription failed",
        video_id: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if video_id:
            details["video_id"] = video_id
        
        super().__init__(
            message=message,
            error_code=ErrorCode.TRANSCRIPTION_FAILED,
            details=details,
            **kwargs
        )


# AI/ML Processing Exceptions
class AIException(InsightEngineException):
    """Base class for AI/ML-related exceptions."""
    pass


class ModelNotAvailableException(AIException):
    """Exception raised when a required model is not available."""
    
    def __init__(self, model_name: str, **kwargs):
        super().__init__(
            message=f"Model not available: {model_name}",
            error_code=ErrorCode.MODEL_NOT_AVAILABLE,
            details={"model_name": model_name},
            **kwargs
        )


class InferenceException(AIException):
    """Exception raised for model inference failures."""
    
    def __init__(
        self,
        message: str = "Model inference failed",
        model_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if model_name:
            details["model_name"] = model_name
        
        super().__init__(
            message=message,
            error_code=ErrorCode.INFERENCE_FAILED,
            details=details,
            **kwargs
        )


class RAGPipelineException(AIException):
    """Exception raised for RAG pipeline failures."""
    
    def __init__(
        self,
        message: str = "RAG pipeline error",
        pipeline_stage: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if pipeline_stage:
            details["pipeline_stage"] = pipeline_stage
        
        super().__init__(
            message=message,
            error_code=ErrorCode.RAG_PIPELINE_ERROR,
            details=details,
            **kwargs
        )


class SummarizationException(AIException):
    """Exception raised for summarization failures."""
    
    def __init__(
        self,
        message: str = "Summarization failed",
        video_id: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if video_id:
            details["video_id"] = video_id
        
        super().__init__(
            message=message,
            error_code=ErrorCode.SUMMARIZATION_FAILED,
            details=details,
            **kwargs
        )


class ClipExtractionException(AIException):
    """Exception raised for clip extraction failures."""
    
    def __init__(
        self,
        message: str = "Clip extraction failed",
        video_id: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if video_id:
            details["video_id"] = video_id
        if query:
            details["query"] = query
        
        super().__init__(
            message=message,
            error_code=ErrorCode.CLIP_EXTRACTION_FAILED,
            details=details,
            **kwargs
        )


# External Service Exceptions
class ExternalServiceException(InsightEngineException):
    """Base class for external service exceptions."""
    pass


class GoogleCloudException(ExternalServiceException):
    """Exception raised for Google Cloud service errors."""
    
    def __init__(
        self,
        message: str = "Google Cloud service error",
        service: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if service:
            details["service"] = service
        
        super().__init__(
            message=message,
            error_code=ErrorCode.GOOGLE_CLOUD_ERROR,
            details=details,
            **kwargs
        )


class RedisConnectionException(ExternalServiceException):
    """Exception raised for Redis connection errors."""
    
    def __init__(self, message: str = "Redis connection error", **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.REDIS_CONNECTION_ERROR,
            **kwargs
        )


class QdrantConnectionException(ExternalServiceException):
    """Exception raised for Qdrant connection errors."""
    
    def __init__(self, message: str = "Qdrant connection error", **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.QDRANT_CONNECTION_ERROR,
            **kwargs
        )


# Rate Limiting Exceptions
class RateLimitException(InsightEngineException):
    """Base class for rate limiting exceptions."""
    pass


class RateLimitExceededException(RateLimitException):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        window: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if limit:
            details["limit"] = limit
        if window:
            details["window"] = window
        if retry_after:
            details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            details=details,
            **kwargs
        )


# Data Exceptions
class DataException(InsightEngineException):
    """Base class for data-related exceptions."""
    pass


class DataNotFoundException(DataException):
    """Exception raised when requested data is not found."""
    
    def __init__(
        self,
        resource: str,
        identifier: str,
        **kwargs
    ):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code=ErrorCode.DATA_NOT_FOUND,
            details={"resource": resource, "identifier": identifier},
            **kwargs
        )


class DatabaseException(DataException):
    """Exception raised for database errors."""
    
    def __init__(
        self,
        message: str = "Database error",
        operation: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if operation:
            details["operation"] = operation
        
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_ERROR,
            details=details,
            **kwargs
        )


# Cache Exceptions
class CacheException(InsightEngineException):
    """Exception raised for cache-related errors."""
    
    def __init__(
        self,
        message: str = "Cache error",
        cache_key: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if cache_key:
            details["cache_key"] = cache_key
        
        super().__init__(
            message=message,
            error_code=ErrorCode.CACHE_ERROR,
            details=details,
            **kwargs
        )


class CacheConnectionException(CacheException):
    """Exception raised when cache connection fails."""
    
    def __init__(
        self,
        message: str = "Cache connection error",
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.CACHE_CONNECTION_ERROR,
            **kwargs
        )


# Connection Pool Exceptions
class ConnectionPoolException(InsightEngineException):
    """Exception raised for connection pool errors."""
    
    def __init__(
        self,
        message: str = "Connection pool error",
        pool_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if pool_name:
            details["pool_name"] = pool_name
        
        super().__init__(
            message=message,
            error_code=ErrorCode.CONNECTION_POOL_ERROR,
            details=details,
            **kwargs
        )


# Monitoring Exceptions
class MonitoringException(InsightEngineException):
    """Exception raised for monitoring-related errors."""
    
    def __init__(
        self,
        message: str = "Monitoring error",
        metric_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if metric_name:
            details["metric_name"] = metric_name
        
        super().__init__(
            message=message,
            error_code=ErrorCode.MONITORING_ERROR,
            details=details,
            **kwargs
        )


class HealthCheckException(MonitoringException):
    """Exception raised for health check errors."""
    
    def __init__(
        self,
        message: str = "Health check error",
        check_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if check_name:
            details["check_name"] = check_name
        
        super().__init__(
            message=message,
            error_code=ErrorCode.HEALTH_CHECK_ERROR,
            details=details,
            **kwargs
        )


# Circuit Breaker and Resilience Exceptions
class CircuitBreakerException(ExternalServiceException):
    """Exception raised when circuit breaker is open."""
    
    def __init__(
        self,
        message: str = "Circuit breaker is open",
        service_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if service_name:
            details["service_name"] = service_name
        
        super().__init__(
            message=message,
            error_code=ErrorCode.DEPENDENCY_ERROR,
            details=details,
            **kwargs
        )


class RetryExhaustedException(ExternalServiceException):
    """Exception raised when all retry attempts are exhausted."""
    
    def __init__(
        self,
        message: str = "All retry attempts exhausted",
        max_attempts: Optional[int] = None,
        last_exception: Optional[Exception] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if max_attempts:
            details["max_attempts"] = max_attempts
        if last_exception:
            details["last_exception"] = str(last_exception)
            details["last_exception_type"] = type(last_exception).__name__
        
        super().__init__(
            message=message,
            error_code=ErrorCode.DEPENDENCY_ERROR,
            details=details,
            **kwargs
        )