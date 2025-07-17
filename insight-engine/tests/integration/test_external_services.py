"""
Integration tests for external service interactions.

This module tests integration with Google Cloud services,
third-party APIs, and external dependencies.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import asyncio

from insight_engine.exceptions import (
    GoogleCloudException,
    ExternalServiceException,
    ValidationException
)
from tests.utils import MockExternalServices


class TestGoogleCloudStorageIntegration:
    """Test Google Cloud Storage integration."""
    
    @pytest.mark.integration
    def test_gcs_client_initialization(self):
        """Test GCS client initialization."""
        with patch('google.cloud.storage.Client') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            from google.cloud import storage
            client = storage.Client()
            
            assert client is mock_instance
            mock_client.assert_called_once()
    
    @pytest.mark.integration
    def test_gcs_bucket_operations(self):
        """Test GCS bucket operations."""
        with patch('google.cloud.storage.Client') as mock_client:
            # Setup mock chain
            mock_client_instance = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_client.return_value = mock_client_instance
            mock_client_instance.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            
            # Test bucket access
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket("test-bucket")
            blob = bucket.blob("test-file.txt")
            
            # Verify mock calls
            mock_client_instance.bucket.assert_called_with("test-bucket")
            mock_bucket.blob.assert_called_with("test-file.txt")
    
    @pytest.mark.integration
    def test_gcs_signed_url_generation(self):
        """Test GCS signed URL generation."""
        with patch('google.cloud.storage.Client') as mock_client:
            mock_client_instance = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            # Configure mock chain
            mock_client.return_value = mock_client_instance
            mock_client_instance.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"
            
            # Test signed URL generation
            from google.cloud import storage
            from datetime import timedelta
            
            client = storage.Client()
            bucket = client.bucket("test-bucket")
            blob = bucket.blob("test-video.mp4")
            
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=15),
                method="PUT"
            )
            
            assert url == "https://signed-url.example.com"
            mock_blob.generate_signed_url.assert_called_once()
    
    @pytest.mark.integration
    def test_gcs_error_handling(self):
        """Test GCS error handling."""
        with patch('google.cloud.storage.Client') as mock_client:
            mock_client.side_effect = Exception("GCS connection failed")
            
            with pytest.raises(Exception) as exc_info:
                from google.cloud import storage
                storage.Client()
            
            assert "GCS connection failed" in str(exc_info.value)


class TestGoogleCloudPubSubIntegration:
    """Test Google Cloud Pub/Sub integration."""
    
    @pytest.mark.integration
    def test_pubsub_publisher_initialization(self):
        """Test Pub/Sub publisher initialization."""
        with patch('google.cloud.pubsub_v1.PublisherClient') as mock_publisher:
            mock_instance = MagicMock()
            mock_publisher.return_value = mock_instance
            
            from google.cloud import pubsub_v1
            publisher = pubsub_v1.PublisherClient()
            
            assert publisher is mock_instance
            mock_publisher.assert_called_once()
    
    @pytest.mark.integration
    def test_pubsub_message_publishing(self):
        """Test Pub/Sub message publishing."""
        with patch('google.cloud.pubsub_v1.PublisherClient') as mock_publisher:
            mock_instance = MagicMock()
            mock_future = MagicMock()
            mock_future.result.return_value = "message-id-123"
            
            mock_publisher.return_value = mock_instance
            mock_instance.publish.return_value = mock_future
            mock_instance.topic_path.return_value = "projects/test/topics/test-topic"
            
            # Test message publishing
            from google.cloud import pubsub_v1
            
            publisher = pubsub_v1.PublisherClient()
            topic_path = publisher.topic_path("test-project", "test-topic")
            
            message_data = json.dumps({
                "video_id": "video-123",
                "operation": "process"
            }).encode("utf-8")
            
            future = publisher.publish(topic_path, message_data)
            message_id = future.result()
            
            assert message_id == "message-id-123"
            mock_instance.publish.assert_called_once_with(topic_path, message_data)
    
    @pytest.mark.integration
    def test_pubsub_subscriber_integration(self):
        """Test Pub/Sub subscriber integration."""
        with patch('google.cloud.pubsub_v1.SubscriberClient') as mock_subscriber:
            mock_instance = MagicMock()
            mock_subscriber.return_value = mock_instance
            mock_instance.subscription_path.return_value = "projects/test/subscriptions/test-sub"
            
            # Mock streaming pull future
            mock_future = MagicMock()
            mock_instance.subscribe.return_value = mock_future
            
            from google.cloud import pubsub_v1
            
            subscriber = pubsub_v1.SubscriberClient()
            subscription_path = subscriber.subscription_path("test-project", "test-subscription")
            
            def callback(message):
                message.ack()
            
            streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
            
            assert streaming_pull_future is mock_future
            mock_instance.subscribe.assert_called_once()


class TestExternalAPIIntegration:
    """Test external API integrations."""
    
    @pytest.mark.integration
    async def test_http_client_integration(self):
        """Test HTTP client for external API calls."""
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "success"}
            
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/test")
                data = response.json()
            
            assert response.status_code == 200
            assert data["status"] == "success"
    
    @pytest.mark.integration
    async def test_external_api_error_handling(self):
        """Test external API error handling."""
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.ConnectError("Connection failed")
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            with pytest.raises(httpx.ConnectError):
                async with httpx.AsyncClient() as client:
                    await client.get("https://api.example.com/test")
    
    @pytest.mark.integration
    async def test_external_api_timeout_handling(self):
        """Test external API timeout handling."""
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.TimeoutException("Request timeout")
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            with pytest.raises(httpx.TimeoutException):
                async with httpx.AsyncClient(timeout=1.0) as client:
                    await client.get("https://api.example.com/slow-endpoint")


class TestServiceIntegrationPatterns:
    """Test service integration patterns and utilities."""
    
    @pytest.mark.integration
    def test_mock_external_services_helper(self):
        """Test MockExternalServices helper utility."""
        mock_services = MockExternalServices()
        
        # Test Redis mock
        assert mock_services.redis_mock.get.return_value is None
        assert mock_services.redis_mock.set.return_value is True
        
        # Test GCS mock
        mock_blob = mock_services.gcs_mock.bucket.return_value.blob.return_value
        assert "https://test-upload-url.com" in mock_blob.generate_signed_url.return_value
        
        # Test Qdrant mock
        assert mock_services.qdrant_mock.search.return_value == []
        assert mock_services.qdrant_mock.upsert.return_value is True
    
    @pytest.mark.integration
    def test_service_integration_with_mocks(self):
        """Test service integration using mock utilities."""
        mock_services = MockExternalServices()
        
        with mock_services.patch_all():
            # Test that services work with mocked dependencies
            # This would typically test actual service classes
            pass
    
    @pytest.mark.integration
    async def test_async_service_integration(self):
        """Test async service integration patterns."""
        async def mock_async_service():
            await asyncio.sleep(0.1)  # Simulate async work
            return {"result": "success"}
        
        # Test async service call
        result = await mock_async_service()
        assert result["result"] == "success"
        
        # Test concurrent async calls
        tasks = [mock_async_service() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert all(r["result"] == "success" for r in results)


class TestServiceResilience:
    """Test service resilience and error recovery."""
    
    @pytest.mark.integration
    async def test_retry_mechanism_simulation(self):
        """Test retry mechanism for external services."""
        call_count = 0
        
        async def flaky_service():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Service temporarily unavailable")
            return {"status": "success"}
        
        # Simulate retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await flaky_service()
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
        
        assert result["status"] == "success"
        assert call_count == 3
    
    @pytest.mark.integration
    async def test_circuit_breaker_simulation(self):
        """Test circuit breaker pattern simulation."""
        failure_count = 0
        circuit_open = False
        
        async def unreliable_service():
            nonlocal failure_count, circuit_open
            
            if circuit_open:
                raise Exception("Circuit breaker is open")
            
            failure_count += 1
            if failure_count < 5:
                raise Exception("Service failure")
            
            # Reset on success
            failure_count = 0
            return {"status": "success"}
        
        # Simulate circuit breaker logic
        max_failures = 3
        
        for _ in range(max_failures + 1):
            try:
                await unreliable_service()
            except Exception:
                if failure_count >= max_failures:
                    circuit_open = True
                    break
        
        assert circuit_open is True
        
        # Test that circuit breaker prevents calls
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await unreliable_service()
    
    @pytest.mark.integration
    async def test_service_health_monitoring(self):
        """Test service health monitoring patterns."""
        services_health = {
            "redis": {"status": "healthy", "last_check": None},
            "qdrant": {"status": "healthy", "last_check": None},
            "gcs": {"status": "healthy", "last_check": None}
        }
        
        async def check_service_health(service_name):
            # Simulate health check
            await asyncio.sleep(0.1)
            
            # Simulate occasional failures
            import random
            if random.random() < 0.1:  # 10% failure rate
                services_health[service_name]["status"] = "unhealthy"
            else:
                services_health[service_name]["status"] = "healthy"
            
            from datetime import datetime
            services_health[service_name]["last_check"] = datetime.utcnow()
        
        # Run health checks
        health_check_tasks = [
            check_service_health(service) 
            for service in services_health.keys()
        ]
        
        await asyncio.gather(*health_check_tasks)
        
        # Verify health checks ran
        for service_name, health in services_health.items():
            assert health["last_check"] is not None
            assert health["status"] in ["healthy", "unhealthy"]


@pytest.mark.integration
class TestExternalServiceErrorHandling:
    """Test comprehensive external service error handling."""
    
    async def test_google_cloud_error_mapping(self):
        """Test Google Cloud error mapping to custom exceptions."""
        from insight_engine.utils.error_utils import handle_external_service_error
        
        # Test different Google Cloud errors
        gcs_error = Exception("Bucket not found")
        mapped_exception = handle_external_service_error(
            service_name="Google Cloud Storage",
            operation="upload_file",
            original_exception=gcs_error
        )
        
        assert isinstance(mapped_exception, GoogleCloudException)
        assert "Google Cloud Storage" in mapped_exception.message
        assert mapped_exception.details["operation"] == "upload_file"
    
    async def test_external_service_timeout_handling(self):
        """Test external service timeout handling."""
        async def slow_service():
            await asyncio.sleep(2.0)  # Simulate slow service
            return "success"
        
        # Test timeout handling
        try:
            result = await asyncio.wait_for(slow_service(), timeout=1.0)
        except asyncio.TimeoutError:
            # Expected timeout
            result = "timeout_handled"
        
        assert result == "timeout_handled"
    
    async def test_service_degradation_handling(self):
        """Test handling of service degradation."""
        service_performance = {"response_time": 0.1, "error_rate": 0.0}
        
        async def degraded_service():
            # Simulate degraded performance
            service_performance["response_time"] = 2.0
            service_performance["error_rate"] = 0.3
            
            import random
            if random.random() < service_performance["error_rate"]:
                raise Exception("Service degraded")
            
            await asyncio.sleep(service_performance["response_time"])
            return "success"
        
        # Test degradation detection
        try:
            result = await asyncio.wait_for(degraded_service(), timeout=1.5)
        except (asyncio.TimeoutError, Exception):
            # Handle degradation
            result = "degradation_detected"
        
        assert result in ["success", "degradation_detected"]
        assert service_performance["response_time"] > 1.0  # Degraded performance detected