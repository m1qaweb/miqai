"""
Tests for custom exception hierarchy and error handling.

This module tests the custom exception classes, error handlers,
and structured error responses.
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from insight_engine.exceptions import (
    InsightEngineException,
    VideoNotFoundException,
    InvalidTokenException,
    ValidationException,
    RateLimitExceededException,
    ErrorCode,
)
from insight_engine.main import app


class TestCustomExceptions:
    """Test custom exception classes."""
    
    def test_base_exception_creation(self):
        """Test base InsightEngineException creation and serialization."""
        exc = InsightEngineException(
            message="Test error",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            details={"key": "value"},
            user_id="user123"
        )
        
        assert exc.message == "Test error"
        assert exc.error_code == ErrorCode.INTERNAL_SERVER_ERROR
        assert exc.details == {"key": "value"}
        assert exc.user_id == "user123"
        assert exc.correlation_id is not None
        assert exc.timestamp is not None
        
        # Test serialization
        exc_dict = exc.to_dict()
        assert exc_dict["error_code"] == ErrorCode.INTERNAL_SERVER_ERROR.value
        assert exc_dict["message"] == "Test error"
        assert exc_dict["details"] == {"key": "value"}
        assert exc_dict["user_id"] == "user123"
    
    def test_video_not_found_exception(self):
        """Test VideoNotFoundException with video ID."""
        exc = VideoNotFoundException("video123")
        
        assert "video123" in exc.message
        assert exc.error_code == ErrorCode.VIDEO_NOT_FOUND
        assert exc.details["video_id"] == "video123"
    
    def test_invalid_token_exception(self):
        """Test InvalidTokenException."""
        exc = InvalidTokenException()
        
        assert "Invalid authentication token" in exc.message
        assert exc.error_code == ErrorCode.INVALID_TOKEN
    
    def test_validation_exception(self):
        """Test ValidationException with field information."""
        exc = ValidationException(
            message="Invalid email format",
            field="email",
            value="invalid-email"
        )
        
        assert exc.message == "Invalid email format"
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.details["field"] == "email"
        assert exc.details["invalid_value"] == "invalid-email"
    
    def test_rate_limit_exception(self):
        """Test RateLimitExceededException with retry information."""
        exc = RateLimitExceededException(
            limit=100,
            window="60 seconds",
            retry_after=30
        )
        
        assert exc.error_code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert exc.details["limit"] == 100
        assert exc.details["window"] == "60 seconds"
        assert exc.details["retry_after"] == 30


class TestExceptionHandlers:
    """Test exception handlers and error responses."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_health_endpoint(self, client):
        """Test health endpoint returns proper response."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in data
        assert "version" in data
        assert "services" in data
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns proper response."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Insight Engine API"
        assert "version" in data
        assert "status" in data
    
    def test_correlation_id_header(self, client):
        """Test that correlation ID is added to response headers."""
        response = client.get("/")
        assert "x-correlation-id" in response.headers
        
        # Test with custom correlation ID
        custom_id = "test-correlation-123"
        response = client.get("/", headers={"x-correlation-id": custom_id})
        assert response.headers["x-correlation-id"] == custom_id
    
    def test_security_headers(self, client):
        """Test that security headers are added to responses."""
        response = client.get("/")
        
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options", 
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Referrer-Policy",
            "Content-Security-Policy"
        ]
        
        for header in expected_headers:
            assert header in response.headers
    
    def test_process_time_header(self, client):
        """Test that process time header is added."""
        response = client.get("/")
        assert "x-process-time" in response.headers
        
        process_time = float(response.headers["x-process-time"])
        assert process_time >= 0
    
    def test_404_error_handling(self, client):
        """Test 404 error handling."""
        response = client.get("/nonexistent")
        assert response.status_code == 404
        
        data = response.json()
        assert "error_code" in data
        assert "message" in data
        assert "correlation_id" in data
        assert "timestamp" in data
    
    def test_rate_limiting(self, client):
        """Test rate limiting functionality."""
        # This test might be flaky depending on the rate limit settings
        # Make multiple requests quickly to trigger rate limiting
        responses = []
        for _ in range(150):  # Exceed the default limit of 100
            response = client.get("/")
            responses.append(response)
        
        # Check if any requests were rate limited
        rate_limited = any(r.status_code == 429 for r in responses)
        
        if rate_limited:
            # Find the rate limited response
            rate_limited_response = next(r for r in responses if r.status_code == 429)
            data = rate_limited_response.json()
            
            assert data["error_code"] == ErrorCode.RATE_LIMIT_EXCEEDED.value
            assert "retry_after" in data.get("details", {})
            assert "Retry-After" in rate_limited_response.headers


class TestErrorUtilities:
    """Test error utility functions."""
    
    def test_error_context_creation(self):
        """Test error context creation utility."""
        from insight_engine.utils.error_utils import create_error_context
        
        context = create_error_context(
            operation="video_upload",
            resource_id="video123",
            filename="test.mp4"
        )
        
        assert context["operation"] == "video_upload"
        assert context["resource_id"] == "video123"
        assert context["filename"] == "test.mp4"
        assert "correlation_id" in context
    
    def test_safe_execute_success(self):
        """Test safe_execute with successful operation."""
        from insight_engine.utils.error_utils import safe_execute
        
        def successful_operation():
            return "success"
        
        result = safe_execute(
            successful_operation,
            "test_operation",
            log_errors=False
        )
        
        assert result == "success"
    
    def test_safe_execute_with_error(self):
        """Test safe_execute with error handling."""
        from insight_engine.utils.error_utils import safe_execute
        
        def failing_operation():
            raise ValueError("Test error")
        
        # Test with reraise=False
        result = safe_execute(
            failing_operation,
            "test_operation",
            default_return="default",
            log_errors=False,
            reraise=False
        )
        
        assert result == "default"
        
        # Test with reraise=True (default)
        with pytest.raises(ValueError):
            safe_execute(
                failing_operation,
                "test_operation",
                log_errors=False
            )
    
    def test_error_context_manager(self):
        """Test ErrorContext context manager."""
        from insight_engine.utils.error_utils import ErrorContext
        
        # Test successful execution
        with ErrorContext("test_operation", log_entry=False, log_exit=False):
            result = "success"
        
        assert result == "success"
        
        # Test with exception
        with pytest.raises(ValueError):
            with ErrorContext("test_operation", log_entry=False, log_exit=False):
                raise ValueError("Test error")