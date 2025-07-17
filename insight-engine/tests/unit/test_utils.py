"""
Unit tests for utility functions and helpers.

This module tests error utilities, logging utilities,
and other helper functions.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import uuid

from insight_engine.utils.error_utils import (
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
from insight_engine.exceptions import (
    GoogleCloudException,
    RedisConnectionException,
    QdrantConnectionException,
    ExternalServiceException,
)


class TestContextVariables:
    """Test context variable management."""
    
    def test_correlation_id_management(self):
        """Test correlation ID setting and getting."""
        test_id = "test-correlation-123"
        
        set_correlation_id(test_id)
        retrieved_id = get_correlation_id()
        
        assert retrieved_id == test_id
    
    def test_correlation_id_default(self):
        """Test correlation ID default generation."""
        # Clear any existing correlation ID
        set_correlation_id("")
        
        correlation_id = get_correlation_id()
        
        assert isinstance(correlation_id, str)
        assert len(correlation_id) > 0
        # Should be a valid UUID format
        try:
            uuid.UUID(correlation_id)
        except ValueError:
            pytest.fail("Generated correlation ID is not a valid UUID")
    
    def test_user_id_management(self):
        """Test user ID setting and getting."""
        test_user_id = "user-123"
        
        set_user_id(test_user_id)
        retrieved_id = get_user_id()
        
        assert retrieved_id == test_user_id
    
    def test_user_id_default(self):
        """Test user ID default value."""
        set_user_id("")  # Clear user ID
        
        user_id = get_user_id()
        
        assert user_id is None or user_id == ""
    
    def test_request_id_management(self):
        """Test request ID setting and getting."""
        test_request_id = "req-456"
        
        set_request_id(test_request_id)
        retrieved_id = get_request_id()
        
        assert retrieved_id == test_request_id


class TestLoggingUtilities:
    """Test logging utility functions."""
    
    @patch('insight_engine.utils.error_utils.logger')
    def test_log_error_basic(self, mock_logger):
        """Test basic error logging."""
        exception = ValueError("Test error")
        message = "Test error occurred"
        
        log_error(exception, message)
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert message in call_args[0][0]
        assert "extra" in call_args[1]
    
    @patch('insight_engine.utils.error_utils.logger')
    def test_log_error_with_context(self, mock_logger):
        """Test error logging with extra context."""
        exception = ValueError("Test error")
        message = "Test error occurred"
        extra_context = {"operation": "test_operation", "user_id": "user-123"}
        
        log_error(exception, message, extra_context=extra_context)
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        extra_data = call_args[1]["extra"]
        assert extra_data["operation"] == "test_operation"
        assert extra_data["user_id"] == "user-123"
    
    @patch('insight_engine.utils.error_utils.logger')
    def test_log_warning(self, mock_logger):
        """Test warning logging."""
        message = "Test warning"
        extra_context = {"component": "test"}
        
        log_warning(message, extra_context=extra_context)
        
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert message in call_args[0][0]
        assert call_args[1]["extra"]["component"] == "test"
    
    @patch('insight_engine.utils.error_utils.logger')
    def test_log_info(self, mock_logger):
        """Test info logging."""
        message = "Test info"
        extra_context = {"status": "success"}
        
        log_info(message, extra_context=extra_context)
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert message in call_args[0][0]
        assert call_args[1]["extra"]["status"] == "success"


class TestErrorContextCreation:
    """Test error context creation utilities."""
    
    def test_create_error_context_basic(self):
        """Test basic error context creation."""
        context = create_error_context("test_operation")
        
        assert context["operation"] == "test_operation"
        assert "correlation_id" in context
        assert isinstance(context["correlation_id"], str)
    
    def test_create_error_context_with_resource_id(self):
        """Test error context creation with resource ID."""
        context = create_error_context("test_operation", resource_id="resource-123")
        
        assert context["operation"] == "test_operation"
        assert context["resource_id"] == "resource-123"
    
    def test_create_error_context_with_kwargs(self):
        """Test error context creation with additional kwargs."""
        context = create_error_context(
            "test_operation",
            custom_field="custom_value",
            another_field=42
        )
        
        assert context["operation"] == "test_operation"
        assert context["custom_field"] == "custom_value"
        assert context["another_field"] == 42


class TestExternalServiceErrorHandling:
    """Test external service error handling utilities."""
    
    def test_handle_google_cloud_error(self):
        """Test handling Google Cloud service errors."""
        original_error = Exception("GCS bucket not found")
        
        result = handle_external_service_error(
            service_name="Google Cloud Storage",
            operation="upload_file",
            original_exception=original_error,
            resource_id="file-123"
        )
        
        assert isinstance(result, GoogleCloudException)
        assert "Google Cloud Google Cloud Storage error" in result.message
        assert result.details["service"] == "Google Cloud Storage"
        assert result.details["operation"] == "upload_file"
        assert result.details["resource_id"] == "file-123"
    
    def test_handle_redis_error(self):
        """Test handling Redis service errors."""
        original_error = ConnectionError("Redis connection failed")
        
        result = handle_external_service_error(
            service_name="Redis",
            operation="cache_get",
            original_exception=original_error
        )
        
        assert isinstance(result, RedisConnectionException)
        assert "Redis error during cache_get" in result.message
    
    def test_handle_qdrant_error(self):
        """Test handling Qdrant service errors."""
        original_error = Exception("Qdrant collection not found")
        
        result = handle_external_service_error(
            service_name="Qdrant",
            operation="vector_search",
            original_exception=original_error
        )
        
        assert isinstance(result, QdrantConnectionException)
        assert "Qdrant error during vector_search" in result.message
    
    def test_handle_generic_external_service_error(self):
        """Test handling generic external service errors."""
        original_error = Exception("Unknown service error")
        
        result = handle_external_service_error(
            service_name="Unknown Service",
            operation="unknown_operation",
            original_exception=original_error
        )
        
        assert isinstance(result, ExternalServiceException)
        assert "External service Unknown Service error" in result.message


class TestSafeExecute:
    """Test safe execution utility."""
    
    def test_safe_execute_success(self):
        """Test safe execute with successful operation."""
        def successful_operation():
            return "success"
        
        result = safe_execute(
            successful_operation,
            "test_operation",
            log_errors=False
        )
        
        assert result == "success"
    
    def test_safe_execute_with_error_reraise(self):
        """Test safe execute with error and reraise=True."""
        def failing_operation():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            safe_execute(
                failing_operation,
                "test_operation",
                log_errors=False,
                reraise=True
            )
    
    def test_safe_execute_with_error_no_reraise(self):
        """Test safe execute with error and reraise=False."""
        def failing_operation():
            raise ValueError("Test error")
        
        result = safe_execute(
            failing_operation,
            "test_operation",
            default_return="default_value",
            log_errors=False,
            reraise=False
        )
        
        assert result == "default_value"
    
    @patch('insight_engine.utils.error_utils.log_error')
    def test_safe_execute_with_logging(self, mock_log_error):
        """Test safe execute with error logging."""
        def failing_operation():
            raise ValueError("Test error")
        
        safe_execute(
            failing_operation,
            "test_operation",
            log_errors=True,
            reraise=False
        )
        
        mock_log_error.assert_called_once()


class TestErrorContextManager:
    """Test ErrorContext context manager."""
    
    @patch('insight_engine.utils.error_utils.log_info')
    def test_error_context_success(self, mock_log_info):
        """Test ErrorContext with successful operation."""
        with ErrorContext("test_operation", test_param="test_value"):
            result = "success"
        
        assert result == "success"
        # Should log entry and exit
        assert mock_log_info.call_count == 2
    
    @patch('insight_engine.utils.error_utils.log_error')
    @patch('insight_engine.utils.error_utils.log_info')
    def test_error_context_with_exception(self, mock_log_info, mock_log_error):
        """Test ErrorContext with exception."""
        with pytest.raises(ValueError):
            with ErrorContext("test_operation", test_param="test_value"):
                raise ValueError("Test error")
        
        # Should log entry and error
        mock_log_info.assert_called_once()  # Entry log
        mock_log_error.assert_called_once()  # Error log
    
    @patch('insight_engine.utils.error_utils.log_info')
    def test_error_context_no_entry_log(self, mock_log_info):
        """Test ErrorContext with entry logging disabled."""
        with ErrorContext("test_operation", log_entry=False):
            pass
        
        # Should only log exit
        mock_log_info.assert_called_once()
    
    @patch('insight_engine.utils.error_utils.log_info')
    def test_error_context_no_exit_log(self, mock_log_info):
        """Test ErrorContext with exit logging disabled."""
        with ErrorContext("test_operation", log_exit=False):
            pass
        
        # Should only log entry
        mock_log_info.assert_called_once()
    
    def test_error_context_returns_self(self):
        """Test that ErrorContext returns self on enter."""
        context = ErrorContext("test_operation")
        
        with context as ctx:
            assert ctx is context


@pytest.mark.unit
class TestUtilityIntegration:
    """Integration tests for utility functions."""
    
    def test_full_error_handling_flow(self):
        """Test complete error handling flow."""
        # Set up context
        set_correlation_id("test-correlation-123")
        set_user_id("user-456")
        set_request_id("req-789")
        
        # Create error context
        context = create_error_context(
            "test_operation",
            resource_id="resource-123"
        )
        
        # Verify context contains all information
        assert context["operation"] == "test_operation"
        assert context["resource_id"] == "resource-123"
        assert context["correlation_id"] == "test-correlation-123"
        assert context["user_id"] == "user-456"
        assert context["request_id"] == "req-789"
    
    @patch('insight_engine.utils.error_utils.log_error')
    def test_error_context_manager_integration(self, mock_log_error):
        """Test ErrorContext integration with error handling."""
        set_correlation_id("test-correlation-456")
        
        with pytest.raises(ValueError):
            with ErrorContext("integration_test", component="test"):
                raise ValueError("Integration test error")
        
        # Verify error was logged with context
        mock_log_error.assert_called_once()
        call_args = mock_log_error.call_args
        assert "Integration test error" in str(call_args[0][1])
        assert call_args[1]["extra_context"]["component"] == "test"
    
    def test_safe_execute_with_context(self):
        """Test safe_execute with error context."""
        set_correlation_id("safe-execute-test")
        
        def operation_with_context():
            context = create_error_context("safe_operation")
            assert context["correlation_id"] == "safe-execute-test"
            return "success"
        
        result = safe_execute(
            operation_with_context,
            "safe_execute_test",
            log_errors=False
        )
        
        assert result == "success"


class TestUtilityHelpers:
    """Test additional utility helper functions."""
    
    def test_verify_pythonpath(self):
        """Test PYTHONPATH verification utility."""
        from insight_engine.utils import verify_pythonpath
        
        # This should not raise an exception
        verify_pythonpath()
        # Function prints to stdout, so we can't easily test output
        # but we can verify it doesn't crash
    
    def test_context_variable_isolation(self):
        """Test that context variables are properly isolated."""
        # Set initial values
        set_correlation_id("initial-correlation")
        set_user_id("initial-user")
        
        # Verify initial values
        assert get_correlation_id() == "initial-correlation"
        assert get_user_id() == "initial-user"
        
        # Change values
        set_correlation_id("new-correlation")
        set_user_id("new-user")
        
        # Verify changed values
        assert get_correlation_id() == "new-correlation"
        assert get_user_id() == "new-user"
    
    def test_error_context_with_multiple_operations(self):
        """Test error context with nested operations."""
        contexts = []
        
        with ErrorContext("outer_operation", level="outer") as outer_ctx:
            contexts.append(outer_ctx)
            
            with ErrorContext("inner_operation", level="inner") as inner_ctx:
                contexts.append(inner_ctx)
                
                # Both contexts should be different instances
                assert outer_ctx is not inner_ctx
                assert outer_ctx.operation == "outer_operation"
                assert inner_ctx.operation == "inner_operation"
        
        assert len(contexts) == 2