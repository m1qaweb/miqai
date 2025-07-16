import pytest
from unittest.mock import MagicMock

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
