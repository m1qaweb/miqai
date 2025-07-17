"""
Test utilities and helpers for the Insight Engine test suite.

This module provides utility functions, decorators, and helpers
for writing comprehensive tests.
"""

import asyncio
import functools
import json
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response


class AsyncTestCase:
    """Base class for async test cases with common utilities."""
    
    async def assert_response_success(
        self, 
        response: Response, 
        expected_status: int = 200
    ) -> Dict[str, Any]:
        """Assert response is successful and return JSON data."""
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}. "
            f"Response: {response.text}"
        )
        return response.json()
    
    async def assert_response_error(
        self, 
        response: Response, 
        expected_status: int,
        expected_error_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Assert response is an error and return error data."""
        assert response.status_code == expected_status, (
            f"Expected error status {expected_status}, got {response.status_code}. "
            f"Response: {response.text}"
        )
        
        error_data = response.json()
        assert "error_code" in error_data, "Error response missing error_code"
        assert "message" in error_data, "Error response missing message"
        assert "correlation_id" in error_data, "Error response missing correlation_id"
        
        if expected_error_code:
            assert error_data["error_code"] == expected_error_code, (
                f"Expected error code {expected_error_code}, "
                f"got {error_data['error_code']}"
            )
        
        return error_data
    
    async def wait_for_condition(
        self,
        condition: Callable[[], bool],
        timeout: float = 5.0,
        interval: float = 0.1,
        error_message: str = "Condition not met within timeout"
    ) -> None:
        """Wait for a condition to become true within a timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition():
                return
            await asyncio.sleep(interval)
        
        raise AssertionError(f"{error_message} (timeout: {timeout}s)")


def async_test(func: Callable) -> Callable:
    """Decorator to run async test functions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper


def mock_async_context_manager(return_value: Any = None):
    """Create a mock async context manager."""
    @asynccontextmanager
    async def mock_context():
        yield return_value or AsyncMock()
    
    return mock_context


class MockExternalServices:
    """Helper class for mocking external services consistently."""
    
    def __init__(self):
        self.redis_mock = AsyncMock()
        self.gcs_mock = MagicMock()
        self.qdrant_mock = MagicMock()
        self.pubsub_mock = MagicMock()
        self._setup_default_behaviors()
    
    def _setup_default_behaviors(self):
        """Set up default mock behaviors."""
        # Redis defaults
        self.redis_mock.get.return_value = None
        self.redis_mock.set.return_value = True
        self.redis_mock.delete.return_value = 1
        self.redis_mock.exists.return_value = False
        
        # GCS defaults
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://test-upload-url.com"
        mock_blob.exists.return_value = True
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        self.gcs_mock.bucket.return_value = mock_bucket
        
        # Qdrant defaults
        self.qdrant_mock.search.return_value = []
        self.qdrant_mock.upsert.return_value = True
        self.qdrant_mock.get_collections.return_value.collections = []
        
        # Pub/Sub defaults
        self.pubsub_mock.publish.return_value.result.return_value = "message-id-123"
    
    def patch_all(self):
        """Return a context manager that patches all external services."""
        return patch.multiple(
            'insight_engine.services',
            redis_service=self.redis_mock,
            storage_client=self.gcs_mock,
            qdrant_client=self.qdrant_mock,
            pubsub_client=self.pubsub_mock
        )


class TestDataBuilder:
    """Builder pattern for creating complex test data."""
    
    def __init__(self):
        self.data = {}
    
    def with_user(
        self, 
        user_id: str = "test-user", 
        permissions: List[str] = None
    ) -> "TestDataBuilder":
        """Add user data to the test scenario."""
        self.data["user"] = {
            "id": user_id,
            "username": f"user_{user_id}",
            "email": f"{user_id}@example.com",
            "permissions": permissions or ["read", "write"],
            "is_active": True
        }
        return self
    
    def with_video(
        self, 
        video_id: str = "test-video", 
        status: str = "processed"
    ) -> "TestDataBuilder":
        """Add video data to the test scenario."""
        self.data["video"] = {
            "id": video_id,
            "filename": f"{video_id}.mp4",
            "duration": 120.0,
            "size": 1024000,
            "status": status,
            "created_at": "2024-01-01T00:00:00Z"
        }
        return self
    
    def with_transcript(
        self, 
        video_id: str = None, 
        segments: List[Dict] = None
    ) -> "TestDataBuilder":
        """Add transcript data to the test scenario."""
        video_id = video_id or self.data.get("video", {}).get("id", "test-video")
        self.data["transcript"] = {
            "video_id": video_id,
            "segments": segments or [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Test transcript segment",
                    "confidence": 0.95
                }
            ],
            "language": "en-US",
            "duration": 5.0
        }
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build and return the test data."""
        return self.data.copy()


def create_test_file(
    content: Union[str, bytes], 
    filename: str = "test_file.txt",
    content_type: str = "text/plain"
) -> Dict[str, Any]:
    """Create a test file object for upload testing."""
    if isinstance(content, str):
        content = content.encode('utf-8')
    
    return {
        "filename": filename,
        "content": content,
        "content_type": content_type,
        "size": len(content)
    }


def assert_logs_contain(
    caplog, 
    level: str, 
    message_substring: str,
    logger_name: Optional[str] = None
) -> None:
    """Assert that logs contain a specific message."""
    matching_records = []
    
    for record in caplog.records:
        if record.levelname == level.upper():
            if logger_name is None or record.name == logger_name:
                if message_substring in record.getMessage():
                    matching_records.append(record)
    
    assert matching_records, (
        f"No {level} log found containing '{message_substring}'. "
        f"Available logs: {[r.getMessage() for r in caplog.records]}"
    )


def assert_correlation_id_in_logs(caplog, correlation_id: str) -> None:
    """Assert that a correlation ID appears in logs."""
    correlation_found = False
    
    for record in caplog.records:
        if hasattr(record, 'correlation_id') and record.correlation_id == correlation_id:
            correlation_found = True
            break
        # Also check in the message
        if correlation_id in record.getMessage():
            correlation_found = True
            break
    
    assert correlation_found, (
        f"Correlation ID '{correlation_id}' not found in logs. "
        f"Available records: {[r.getMessage() for r in caplog.records]}"
    )


class DatabaseTestHelper:
    """Helper for database-related testing operations."""
    
    def __init__(self, redis_client=None, qdrant_client=None):
        self.redis_client = redis_client
        self.qdrant_client = qdrant_client
    
    async def clear_redis_keys(self, pattern: str = "test_*") -> None:
        """Clear Redis keys matching a pattern."""
        if self.redis_client:
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
    
    async def create_test_collection(
        self, 
        collection_name: str, 
        vector_size: int = 512
    ) -> None:
        """Create a test collection in Qdrant."""
        if self.qdrant_client:
            from qdrant_client import models
            
            try:
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size, 
                        distance=models.Distance.COSINE
                    )
                )
            except Exception:
                # Collection might already exist
                pass
    
    async def cleanup_test_collections(self) -> None:
        """Clean up test collections from Qdrant."""
        if self.qdrant_client:
            try:
                collections = self.qdrant_client.get_collections().collections
                for collection in collections:
                    if collection.name.startswith("test_"):
                        self.qdrant_client.delete_collection(collection.name)
            except Exception:
                # Ignore cleanup errors
                pass


class PerformanceTestHelper:
    """Helper for performance testing."""
    
    def __init__(self):
        self.start_time = None
        self.measurements = []
    
    def start_timer(self) -> None:
        """Start timing an operation."""
        self.start_time = time.time()
    
    def stop_timer(self, operation_name: str = "operation") -> float:
        """Stop timer and record measurement."""
        if self.start_time is None:
            raise ValueError("Timer not started")
        
        duration = time.time() - self.start_time
        self.measurements.append({
            "operation": operation_name,
            "duration": duration,
            "timestamp": time.time()
        })
        self.start_time = None
        return duration
    
    def assert_performance(
        self, 
        max_duration: float, 
        operation_name: str = None
    ) -> None:
        """Assert that the last operation was within performance limits."""
        if not self.measurements:
            raise ValueError("No measurements recorded")
        
        last_measurement = self.measurements[-1]
        if operation_name and last_measurement["operation"] != operation_name:
            raise ValueError(f"Expected operation '{operation_name}', got '{last_measurement['operation']}'")
        
        assert last_measurement["duration"] <= max_duration, (
            f"Operation '{last_measurement['operation']}' took "
            f"{last_measurement['duration']:.3f}s, expected <= {max_duration}s"
        )
    
    def get_average_duration(self, operation_name: str = None) -> float:
        """Get average duration for operations."""
        measurements = self.measurements
        if operation_name:
            measurements = [m for m in measurements if m["operation"] == operation_name]
        
        if not measurements:
            return 0.0
        
        return sum(m["duration"] for m in measurements) / len(measurements)


# Pytest markers for test categorization
pytest_markers = {
    "unit": pytest.mark.unit,
    "integration": pytest.mark.integration,
    "e2e": pytest.mark.e2e,
    "slow": pytest.mark.slow,
    "performance": pytest.mark.performance,
    "security": pytest.mark.security,
}


def requires_redis(func):
    """Decorator to skip tests if Redis is not available."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            import redis.asyncio as redis
            client = redis.Redis.from_url("redis://localhost:6379/15")
            await client.ping()
            await client.close()
        except Exception:
            pytest.skip("Redis not available")
        
        return await func(*args, **kwargs)
    
    return wrapper


def requires_qdrant(func):
    """Decorator to skip tests if Qdrant is not available."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            from qdrant_client import QdrantClient
            client = QdrantClient(host="localhost", port=6333)
            client.get_collections()
        except Exception:
            pytest.skip("Qdrant not available")
        
        return func(*args, **kwargs)
    
    return wrapper