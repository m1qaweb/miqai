import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator, Dict, Generator, Any, Optional
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from qdrant_client import QdrantClient

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-32-chars"
os.environ["REDIS_DSN"] = "redis://localhost:6379/15"  # Use DB 15 for tests

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_gcs_client():
    """Mocks the GCS client."""
    return MagicMock()

@pytest.fixture
def mock_pubsub_publisher():
    """Mocks the Pub/Sub publisher client."""
    return MagicMock()

@pytest.fixture
def mock_dlp_client():
    """Mocks the DLP client."""
    return MagicMock()

@pytest.fixture
def mock_vector_store():
    """Mocks the VectorStore client."""
    return MagicMock()

@pytest.fixture
def mock_redis_client():
    """Mocks the Redis client."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.exists.return_value = False
    return mock_redis

@pytest.fixture
def mock_qdrant_client():
    """Mocks the Qdrant client."""
    mock_client = MagicMock()
    mock_client.search.return_value = []
    mock_client.upsert.return_value = True
    return mock_client

@pytest.fixture
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    """Create a test client for the FastAPI application."""
    from src.insight_engine.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def sync_test_client() -> TestClient:
    """Create a synchronous test client for the FastAPI application."""
    from src.insight_engine.main import app
    return TestClient(app)

@pytest.fixture
def sample_video_metadata():
    """Sample video metadata for testing."""
    return {
        "id": "test-video-123",
        "filename": "test_video.mp4",
        "duration": 120.5,
        "size": 1024000,
        "format": "mp4",
        "resolution": "1920x1080",
        "fps": 30,
        "created_at": "2024-01-01T00:00:00Z"
    }

@pytest.fixture
def sample_transcript():
    """Sample transcript data for testing."""
    return {
        "segments": [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Hello, this is a test video.",
                "confidence": 0.95
            },
            {
                "start": 5.0,
                "end": 10.0,
                "text": "We are testing the transcription service.",
                "confidence": 0.92
            }
        ],
        "language": "en-US",
        "duration": 10.0
    }

@pytest.fixture
def sample_user():
    """Sample user data for testing."""
    return {
        "id": "user-123",
        "email": "test@example.com",
        "name": "Test User",
        "is_active": True
    }

# Test Database Configuration
@pytest.fixture(scope="session")
async def test_redis_client() -> AsyncGenerator[redis.Redis, None]:
    """Create a Redis client for testing."""
    client = redis.Redis.from_url(os.environ["REDIS_DSN"], decode_responses=True)
    try:
        # Clear test database before tests
        await client.flushdb()
        yield client
    finally:
        # Clean up after tests
        await client.flushdb()
        await client.close()


@pytest.fixture(scope="session")
def test_qdrant_client() -> Generator[QdrantClient, None, None]:
    """Create a Qdrant client for testing."""
    client = QdrantClient(host="localhost", port=6333)
    yield client
    # Clean up test collections after tests
    try:
        collections = client.get_collections().collections
        for collection in collections:
            if collection.name.startswith("test_"):
                client.delete_collection(collection.name)
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


# Test Data Factories
class TestDataFactory:
    """Factory for creating consistent test data."""
    
    @staticmethod
    def create_user(
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        is_active: bool = True,
        permissions: Optional[list] = None
    ) -> Dict[str, Any]:
        """Create test user data."""
        return {
            "id": user_id or f"user-{uuid.uuid4().hex[:8]}",
            "email": email or f"test-{uuid.uuid4().hex[:8]}@example.com",
            "username": username or f"testuser{uuid.uuid4().hex[:8]}",
            "is_active": is_active,
            "permissions": permissions or ["read", "write"],
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None
        }
    
    @staticmethod
    def create_video_metadata(
        video_id: Optional[str] = None,
        filename: Optional[str] = None,
        duration: float = 120.0,
        size: int = 1024000
    ) -> Dict[str, Any]:
        """Create test video metadata."""
        return {
            "id": video_id or f"video-{uuid.uuid4().hex[:8]}",
            "filename": filename or f"test_video_{uuid.uuid4().hex[:8]}.mp4",
            "duration": duration,
            "size": size,
            "format": "mp4",
            "resolution": "1920x1080",
            "fps": 30,
            "created_at": datetime.utcnow().isoformat(),
            "status": "processed"
        }
    
    @staticmethod
    def create_transcript(
        video_id: Optional[str] = None,
        language: str = "en-US"
    ) -> Dict[str, Any]:
        """Create test transcript data."""
        return {
            "video_id": video_id or f"video-{uuid.uuid4().hex[:8]}",
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "This is a test transcript segment.",
                    "confidence": 0.95
                },
                {
                    "start": 5.0,
                    "end": 10.0,
                    "text": "This is another test segment for testing.",
                    "confidence": 0.92
                }
            ],
            "language": language,
            "duration": 10.0,
            "created_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_jwt_token(
        user_id: str = "test-user-123",
        username: str = "testuser",
        permissions: Optional[list] = None,
        expires_in_minutes: int = 30
    ) -> str:
        """Create a test JWT token."""
        from insight_engine.security import create_access_token
        from datetime import timedelta
        
        return create_access_token(
            user_id=user_id,
            username=username,
            permissions=permissions or ["read", "write"],
            expires_delta=timedelta(minutes=expires_in_minutes)
        )


@pytest.fixture
def test_data_factory() -> TestDataFactory:
    """Provide test data factory."""
    return TestDataFactory()


# Enhanced Test Client Fixtures
@pytest.fixture
async def authenticated_client(test_data_factory: TestDataFactory) -> AsyncGenerator[AsyncClient, None]:
    """Create an authenticated test client."""
    from insight_engine.main import app
    from insight_engine.security import get_current_user
    from insight_engine.security import TokenData
    
    # Create test user
    test_user = test_data_factory.create_user()
    
    # Mock the authentication dependency
    async def mock_get_current_user():
        return TokenData(
            user_id=test_user["id"],
            username=test_user["username"],
            email=test_user["email"],
            permissions=test_user["permissions"],
            token_type="access",
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
    
    # Override the dependency
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    try:
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Add auth header
            token = test_data_factory.create_jwt_token(
                user_id=test_user["id"],
                username=test_user["username"],
                permissions=test_user["permissions"]
            )
            client.headers.update({"Authorization": f"Bearer {token}"})
            yield client
    finally:
        # Clean up dependency override
        app.dependency_overrides.clear()


@pytest.fixture
def mock_external_services():
    """Mock all external services for testing."""
    with patch('insight_engine.services.redis_service.RedisService') as mock_redis, \
         patch('google.cloud.storage.Client') as mock_gcs, \
         patch('google.cloud.pubsub_v1.PublisherClient') as mock_pubsub, \
         patch('qdrant_client.QdrantClient') as mock_qdrant:
        
        # Configure Redis mock
        mock_redis_instance = AsyncMock()
        mock_redis_instance.get.return_value = None
        mock_redis_instance.set.return_value = True
        mock_redis.return_value = mock_redis_instance
        
        # Configure GCS mock
        mock_gcs_instance = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://test-upload-url.com"
        mock_bucket.blob.return_value = mock_blob
        mock_gcs_instance.bucket.return_value = mock_bucket
        mock_gcs.return_value = mock_gcs_instance
        
        # Configure Pub/Sub mock
        mock_pubsub_instance = MagicMock()
        mock_pubsub.return_value = mock_pubsub_instance
        
        # Configure Qdrant mock
        mock_qdrant_instance = MagicMock()
        mock_qdrant_instance.search.return_value = []
        mock_qdrant.return_value = mock_qdrant_instance
        
        yield {
            'redis': mock_redis_instance,
            'gcs': mock_gcs_instance,
            'pubsub': mock_pubsub_instance,
            'qdrant': mock_qdrant_instance
        }


# Async Test Utilities
@pytest.fixture
async def async_test_session():
    """Create an async test session for database operations."""
    # This would typically set up an async database session
    # For now, we'll use a mock
    session = AsyncMock()
    try:
        yield session
    finally:
        await session.close()


# Test Configuration Override
@pytest.fixture(autouse=True)
def override_settings():
    """Override settings for testing."""
    import sys
    from pathlib import Path
    
    # Import settings from the correct location
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    
    # Import directly from the config module to avoid circular imports
    import importlib.util
    config_path = Path(__file__).parent.parent / "src" / "insight_engine" / "config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    settings = config_module.settings
    
    # Store original values
    original_values = {}
    
    # Override for testing
    test_overrides = {
        'ENVIRONMENT': 'test',
        'DEBUG': True,
        'SECRET_KEY': 'test-secret-key-for-testing-only-32-chars',
        'REDIS_DSN': 'redis://localhost:6379/15'
    }
    
    for key, value in test_overrides.items():
        if hasattr(settings, key):
            original_values[key] = getattr(settings, key)
            setattr(settings, key, value)
    
    yield
    
    # Restore original values
    for key, value in original_values.items():
        setattr(settings, key, value)


# Legacy fixtures (maintained for backward compatibility)
@pytest.fixture
def auth_headers(test_data_factory: TestDataFactory):
    """Generate authentication headers for testing."""
    token = test_data_factory.create_jwt_token()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_user(test_data_factory: TestDataFactory):
    """Sample user data for testing."""
    return test_data_factory.create_user()


@pytest.fixture
def sample_video_metadata(test_data_factory: TestDataFactory):
    """Sample video metadata for testing."""
    return test_data_factory.create_video_metadata()


@pytest.fixture
def sample_transcript(test_data_factory: TestDataFactory):
    """Sample transcript data for testing."""
    return test_data_factory.create_transcript()
