"""
Test configuration and settings for the Insight Engine test suite.

This module provides test-specific configuration, database setup,
and environment management for comprehensive testing.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest


class TestConfig:
    """Test configuration settings."""
    
    # Test environment settings
    ENVIRONMENT = "test"
    DEBUG = True
    SECRET_KEY = "test-secret-key-for-testing-only-32-chars-long"
    
    # Test database settings
    REDIS_DSN = "redis://localhost:6379/15"  # Use DB 15 for tests
    QDRANT_HOST = "localhost"
    QDRANT_PORT = 6333
    
    # Test file paths
    TEST_DATA_DIR = Path(__file__).parent / "data"
    TEMP_DIR = Path(tempfile.gettempdir()) / "insight_engine_tests"
    
    # Test timeouts and limits
    DEFAULT_TIMEOUT = 30.0
    SLOW_TEST_TIMEOUT = 60.0
    MAX_TEST_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Mock service settings
    MOCK_EXTERNAL_SERVICES = True
    MOCK_GCS_BUCKET = "test-bucket"
    MOCK_PUBSUB_TOPIC = "test-topic"
    
    # Test user settings
    TEST_USER_ID = "test-user-123"
    TEST_USER_EMAIL = "test@example.com"
    TEST_USER_PERMISSIONS = ["read", "write", "admin"]
    
    @classmethod
    def setup_test_environment(cls) -> None:
        """Set up test environment variables."""
        test_env_vars = {
            "ENVIRONMENT": cls.ENVIRONMENT,
            "DEBUG": str(cls.DEBUG),
            "SECRET_KEY": cls.SECRET_KEY,
            "REDIS_DSN": cls.REDIS_DSN,
            "QDRANT_HOST": cls.QDRANT_HOST,
            "QDRANT_PORT": str(cls.QDRANT_PORT),
            "GCS_BUCKET_VIDEOS": cls.MOCK_GCS_BUCKET,
            "GCS_BUCKET_CLIPS": cls.MOCK_GCS_BUCKET,
            "PUBSUB_TOPIC": cls.MOCK_PUBSUB_TOPIC,
        }
        
        for key, value in test_env_vars.items():
            os.environ[key] = value
    
    @classmethod
    def create_test_directories(cls) -> None:
        """Create necessary test directories."""
        cls.TEST_DATA_DIR.mkdir(exist_ok=True)
        cls.TEMP_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def cleanup_test_directories(cls) -> None:
        """Clean up test directories."""
        import shutil
        if cls.TEMP_DIR.exists():
            shutil.rmtree(cls.TEMP_DIR)


class TestDatabaseConfig:
    """Test database configuration and utilities."""
    
    # Redis test configuration
    REDIS_TEST_DB = 15
    REDIS_KEY_PREFIX = "test:"
    
    # Qdrant test configuration
    QDRANT_TEST_COLLECTION_PREFIX = "test_"
    QDRANT_VECTOR_SIZE = 512
    
    # Test data retention
    CLEANUP_AFTER_TESTS = True
    PRESERVE_TEST_DATA = False  # Set to True for debugging
    
    @classmethod
    def get_redis_config(cls) -> Dict[str, Any]:
        """Get Redis configuration for tests."""
        return {
            "host": "localhost",
            "port": 6379,
            "db": cls.REDIS_TEST_DB,
            "decode_responses": True,
            "socket_timeout": 5.0,
            "socket_connect_timeout": 5.0,
        }
    
    @classmethod
    def get_qdrant_config(cls) -> Dict[str, Any]:
        """Get Qdrant configuration for tests."""
        return {
            "host": "localhost",
            "port": 6333,
            "timeout": 10.0,
        }
    
    @classmethod
    def get_test_collection_name(cls, base_name: str) -> str:
        """Generate a test collection name."""
        return f"{cls.QDRANT_TEST_COLLECTION_PREFIX}{base_name}"


class TestDataConfig:
    """Test data configuration and sample data."""
    
    # Sample video data
    SAMPLE_VIDEO_METADATA = {
        "id": "test-video-123",
        "filename": "sample_video.mp4",
        "duration": 120.5,
        "size": 1024000,
        "format": "mp4",
        "resolution": "1920x1080",
        "fps": 30,
        "status": "processed",
        "created_at": "2024-01-01T00:00:00Z"
    }
    
    # Sample transcript data
    SAMPLE_TRANSCRIPT = {
        "video_id": "test-video-123",
        "segments": [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Hello, this is a test video for the Insight Engine.",
                "confidence": 0.95
            },
            {
                "start": 5.0,
                "end": 10.0,
                "text": "We are testing the video analysis capabilities.",
                "confidence": 0.92
            },
            {
                "start": 10.0,
                "end": 15.0,
                "text": "This transcript will be used for RAG pipeline testing.",
                "confidence": 0.88
            }
        ],
        "language": "en-US",
        "duration": 15.0,
        "created_at": "2024-01-01T00:00:00Z"
    }
    
    # Sample user data
    SAMPLE_USER = {
        "id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "name": "Test User",
        "is_active": True,
        "permissions": ["read", "write"],
        "created_at": "2024-01-01T00:00:00Z",
        "last_login": None
    }
    
    # Sample embedding data
    SAMPLE_EMBEDDING = [0.1] * 512  # 512-dimensional vector
    
    # Sample API responses
    SAMPLE_ERROR_RESPONSE = {
        "error_code": "IE1000",
        "message": "Test error message",
        "correlation_id": "test-correlation-123",
        "timestamp": "2024-01-01T00:00:00Z",
        "path": "/test/endpoint",
        "method": "POST"
    }
    
    @classmethod
    def get_sample_video_file_content(cls) -> bytes:
        """Get sample video file content for testing."""
        # This would normally be actual video content
        # For testing, we'll use a simple byte sequence
        return b"FAKE_VIDEO_CONTENT_FOR_TESTING" * 1000
    
    @classmethod
    def get_sample_image_content(cls) -> bytes:
        """Get sample image content for testing."""
        # Simple PNG header + minimal content
        return (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
            b'\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01'
            b'\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00'
            b'\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        )


class TestPerformanceConfig:
    """Performance testing configuration."""
    
    # Performance thresholds
    API_RESPONSE_THRESHOLD = 1.0  # seconds
    DATABASE_QUERY_THRESHOLD = 0.5  # seconds
    FILE_UPLOAD_THRESHOLD = 5.0  # seconds
    
    # Load testing settings
    CONCURRENT_REQUESTS = 10
    LOAD_TEST_DURATION = 30  # seconds
    
    # Memory and resource limits
    MAX_MEMORY_USAGE_MB = 500
    MAX_CPU_USAGE_PERCENT = 80
    
    @classmethod
    def get_performance_thresholds(cls) -> Dict[str, float]:
        """Get performance thresholds for different operations."""
        return {
            "api_response": cls.API_RESPONSE_THRESHOLD,
            "database_query": cls.DATABASE_QUERY_THRESHOLD,
            "file_upload": cls.FILE_UPLOAD_THRESHOLD,
        }


class TestSecurityConfig:
    """Security testing configuration."""
    
    # Test JWT settings
    TEST_JWT_SECRET = "test-jwt-secret-key-for-testing-only"
    TEST_JWT_ALGORITHM = "HS256"
    TEST_JWT_EXPIRATION = 3600  # 1 hour
    
    # Test rate limiting
    TEST_RATE_LIMIT = 1000  # requests per minute
    TEST_RATE_LIMIT_BURST = 100
    
    # Test CORS settings
    TEST_CORS_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://testclient"
    ]
    
    # Security test payloads
    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        "javascript:alert('xss')",
        "<img src=x onerror=alert('xss')>",
        "';alert('xss');//"
    ]
    
    SQL_INJECTION_PAYLOADS = [
        "'; DROP TABLE users; --",
        "' OR '1'='1",
        "' UNION SELECT * FROM users --",
        "'; INSERT INTO users VALUES ('hacker', 'password'); --"
    ]
    
    @classmethod
    def get_malicious_payloads(cls) -> Dict[str, list]:
        """Get malicious payloads for security testing."""
        return {
            "xss": cls.XSS_PAYLOADS,
            "sql_injection": cls.SQL_INJECTION_PAYLOADS,
        }


# Initialize test configuration
def setup_test_config():
    """Set up test configuration."""
    TestConfig.setup_test_environment()
    TestConfig.create_test_directories()


def teardown_test_config():
    """Clean up test configuration."""
    if TestDatabaseConfig.CLEANUP_AFTER_TESTS:
        TestConfig.cleanup_test_directories()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    
    # Set up test configuration
    setup_test_config()


def pytest_unconfigure(config):
    """Clean up after pytest run."""
    teardown_test_config()