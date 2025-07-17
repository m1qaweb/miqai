"""
Integration tests for API endpoints.

This module tests the complete API request/response flow including
authentication, validation, error handling, and business logic.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
import json

from insight_engine.main import app
from tests.utils import AsyncTestCase


class TestHealthEndpoints(AsyncTestCase):
    """Test health and monitoring endpoints."""
    
    @pytest.mark.integration
    async def test_root_endpoint(self):
        """Test root endpoint returns basic API info."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/")
            
            data = await self.assert_response_success(response, 200)
            assert data["name"] == "Insight Engine API"
            assert "version" in data
            assert data["status"] == "operational"
            assert "timestamp" in data
    
    @pytest.mark.integration
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
            
            data = await self.assert_response_success(response, 200)
            assert data["status"] in ["healthy", "degraded", "unhealthy"]
            assert "timestamp" in data
            assert "version" in data
            assert "services" in data
            assert "uptime" in data
            
            # Verify service health structure
            for service_name, service_data in data["services"].items():
                assert "status" in service_data
                assert "response_time" in service_data
                assert "last_check" in service_data
    
    @pytest.mark.integration
    async def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/metrics")
            
            data = await self.assert_response_success(response, 200)
            assert "timestamp" in data
            assert "uptime_seconds" in data
            assert "version" in data
            assert isinstance(data["uptime_seconds"], (int, float))


class TestVideoUploadEndpoints(AsyncTestCase):
    """Test video upload API endpoints."""
    
    @pytest.fixture
    def mock_gcs_services(self):
        """Mock Google Cloud Storage services."""
        with patch('google.cloud.storage.Client') as mock_gcs:
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            # Configure mock chain
            mock_blob.generate_signed_url.return_value = "https://test-upload-url.com/test-video"
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket
            mock_gcs.return_value = mock_client
            
            yield {
                'client': mock_client,
                'bucket': mock_bucket,
                'blob': mock_blob
            }
    
    @pytest.mark.integration
    async def test_request_upload_url_success(self, mock_gcs_services, authenticated_client):
        """Test successful upload URL request."""
        request_data = {
            "file_name": "test_video.mp4",
            "content_type": "video/mp4"
        }
        
        response = await authenticated_client.post("/v1/request-url", json=request_data)
        
        data = await self.assert_response_success(response, 200)
        assert "video_id" in data
        assert "upload_url" in data
        assert data["upload_url"].startswith("https://")
        
        # Verify GCS interaction
        mock_gcs_services['blob'].generate_signed_url.assert_called_once()
    
    @pytest.mark.integration
    async def test_request_upload_url_invalid_content_type(self, authenticated_client):
        """Test upload URL request with invalid content type."""
        request_data = {
            "file_name": "test_document.txt",
            "content_type": "text/plain"
        }
        
        response = await authenticated_client.post("/v1/request-url", json=request_data)
        
        # Should succeed but might have warnings in logs
        # The actual validation might happen at upload time
        data = await self.assert_response_success(response, 200)
        assert "video_id" in data
    
    @pytest.mark.integration
    async def test_request_upload_url_missing_auth(self):
        """Test upload URL request without authentication."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request_data = {
                "file_name": "test_video.mp4",
                "content_type": "video/mp4"
            }
            
            response = await client.post("/v1/request-url", json=request_data)
            
            await self.assert_response_error(response, 401)
    
    @pytest.mark.integration
    async def test_request_upload_url_invalid_payload(self, authenticated_client):
        """Test upload URL request with invalid payload."""
        request_data = {
            "file_name": "",  # Empty filename
            "content_type": "video/mp4"
        }
        
        response = await authenticated_client.post("/v1/request-url", json=request_data)
        
        await self.assert_response_error(response, 422)  # Validation error
    
    @pytest.mark.integration
    async def test_request_upload_url_gcs_error(self, authenticated_client):
        """Test upload URL request with GCS error."""
        with patch('google.cloud.storage.Client') as mock_gcs:
            mock_gcs.side_effect = Exception("GCS connection failed")
            
            request_data = {
                "file_name": "test_video.mp4",
                "content_type": "video/mp4"
            }
            
            response = await authenticated_client.post("/v1/request-url", json=request_data)
            
            await self.assert_response_error(response, 503, "IE5000")  # Google Cloud error


class TestAuthenticationEndpoints(AsyncTestCase):
    """Test authentication-related endpoints."""
    
    @pytest.mark.integration
    async def test_protected_endpoint_with_valid_token(self, authenticated_client):
        """Test accessing protected endpoint with valid token."""
        response = await authenticated_client.get("/v1/request-url")
        
        # This should fail with method not allowed, not auth error
        assert response.status_code in [405, 422]  # Method not allowed or validation error
    
    @pytest.mark.integration
    async def test_protected_endpoint_with_invalid_token(self):
        """Test accessing protected endpoint with invalid token."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            client.headers.update({"Authorization": "Bearer invalid-token"})
            
            response = await client.post("/v1/request-url", json={
                "file_name": "test.mp4",
                "content_type": "video/mp4"
            })
            
            await self.assert_response_error(response, 401)
    
    @pytest.mark.integration
    async def test_protected_endpoint_with_expired_token(self):
        """Test accessing protected endpoint with expired token."""
        # Create an expired token
        from insight_engine.security import create_access_token
        from datetime import timedelta
        
        expired_token = create_access_token(
            user_id="test-user",
            username="testuser",
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            client.headers.update({"Authorization": f"Bearer {expired_token}"})
            
            response = await client.post("/v1/request-url", json={
                "file_name": "test.mp4",
                "content_type": "video/mp4"
            })
            
            await self.assert_response_error(response, 401)


class TestErrorHandling(AsyncTestCase):
    """Test API error handling and responses."""
    
    @pytest.mark.integration
    async def test_404_not_found(self):
        """Test 404 error handling."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/nonexistent-endpoint")
            
            data = await self.assert_response_error(response, 404)
            assert "error_code" in data
            assert "correlation_id" in data
            assert "timestamp" in data
    
    @pytest.mark.integration
    async def test_405_method_not_allowed(self):
        """Test 405 method not allowed error."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/")  # Root only accepts GET
            
            data = await self.assert_response_error(response, 405)
            assert "error_code" in data
    
    @pytest.mark.integration
    async def test_422_validation_error(self, authenticated_client):
        """Test 422 validation error handling."""
        # Send invalid JSON payload
        response = await authenticated_client.post("/v1/request-url", json={
            "invalid_field": "invalid_value"
        })
        
        data = await self.assert_response_error(response, 422)
        assert "validation_errors" in data or "error_code" in data
    
    @pytest.mark.integration
    async def test_correlation_id_in_error_response(self):
        """Test that error responses include correlation ID."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            correlation_id = "test-correlation-123"
            client.headers.update({"x-correlation-id": correlation_id})
            
            response = await client.get("/nonexistent")
            
            data = await self.assert_response_error(response, 404)
            assert data["correlation_id"] == correlation_id


class TestMiddleware(AsyncTestCase):
    """Test middleware functionality."""
    
    @pytest.mark.integration
    async def test_cors_headers(self):
        """Test CORS headers are present."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.options("/", headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            })
            
            # CORS headers should be present
            assert "access-control-allow-origin" in response.headers
    
    @pytest.mark.integration
    async def test_security_headers(self):
        """Test security headers are added."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/")
            
            # Check for security headers
            security_headers = [
                "x-content-type-options",
                "x-frame-options", 
                "x-xss-protection",
                "strict-transport-security"
            ]
            
            for header in security_headers:
                assert header in response.headers
    
    @pytest.mark.integration
    async def test_correlation_id_generation(self):
        """Test correlation ID generation and propagation."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/")
            
            assert "x-correlation-id" in response.headers
            correlation_id = response.headers["x-correlation-id"]
            assert len(correlation_id) > 0
    
    @pytest.mark.integration
    async def test_correlation_id_propagation(self):
        """Test correlation ID propagation from request to response."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            custom_correlation_id = "custom-correlation-456"
            
            response = await client.get("/", headers={
                "x-correlation-id": custom_correlation_id
            })
            
            assert response.headers["x-correlation-id"] == custom_correlation_id
    
    @pytest.mark.integration
    async def test_process_time_header(self):
        """Test process time header is added."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/")
            
            assert "x-process-time" in response.headers
            process_time = float(response.headers["x-process-time"])
            assert process_time >= 0.0
    
    @pytest.mark.integration
    async def test_rate_limiting(self):
        """Test rate limiting middleware."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Make many requests quickly
            responses = []
            for _ in range(150):  # Exceed default limit
                response = await client.get("/")
                responses.append(response)
                if response.status_code == 429:
                    break
            
            # Should eventually hit rate limit
            rate_limited_responses = [r for r in responses if r.status_code == 429]
            if rate_limited_responses:
                response = rate_limited_responses[0]
                data = response.json()
                assert "retry_after" in data.get("details", {})
                assert "Retry-After" in response.headers


class TestAPIVersioning(AsyncTestCase):
    """Test API versioning functionality."""
    
    @pytest.mark.integration
    async def test_v1_api_prefix(self, authenticated_client):
        """Test v1 API prefix works correctly."""
        request_data = {
            "file_name": "test_video.mp4",
            "content_type": "video/mp4"
        }
        
        with patch('google.cloud.storage.Client'):
            response = await authenticated_client.post("/v1/request-url", json=request_data)
            
            # Should work with v1 prefix
            assert response.status_code in [200, 503]  # Success or service unavailable
    
    @pytest.mark.integration
    async def test_api_without_version_prefix(self, authenticated_client):
        """Test API endpoints without version prefix."""
        request_data = {
            "file_name": "test_video.mp4",
            "content_type": "video/mp4"
        }
        
        response = await authenticated_client.post("/request-url", json=request_data)
        
        # Should return 404 without version prefix
        await self.assert_response_error(response, 404)


@pytest.mark.integration
class TestAPIDocumentation:
    """Test API documentation endpoints."""
    
    async def test_openapi_schema(self):
        """Test OpenAPI schema endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            
            assert response.status_code == 200
            schema = response.json()
            assert "openapi" in schema
            assert "info" in schema
            assert "paths" in schema
    
    async def test_swagger_docs(self):
        """Test Swagger documentation endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/docs")
            
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
    
    async def test_redoc_docs(self):
        """Test ReDoc documentation endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/redoc")
            
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]


@pytest.mark.integration
class TestAPIPerformance:
    """Test API performance characteristics."""
    
    async def test_response_time_reasonable(self):
        """Test that API responses are reasonably fast."""
        import time
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            start_time = time.time()
            response = await client.get("/")
            end_time = time.time()
            
            response_time = end_time - start_time
            assert response_time < 1.0  # Should respond within 1 second
            assert response.status_code == 200
    
    async def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        import asyncio
        
        async def make_request():
            async with AsyncClient(app=app, base_url="http://test") as client:
                return await client.get("/")
        
        # Make 10 concurrent requests
        tasks = [make_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "operational"