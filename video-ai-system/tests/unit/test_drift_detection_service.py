# tests/unit/test_drift_detection_service.py

import pytest
import numpy as np
import httpx
from unittest.mock import MagicMock, patch, AsyncMock

from video_ai_system.services.drift_detection_service import DriftDetectionService
from video_ai_system.services.vector_db_service import VectorDBService
from qdrant_client.http.models import PointStruct, ScoredPoint

# A fixture to create a mock VectorDBService
@pytest.fixture
def mock_vector_db_service():
    return MagicMock(spec=VectorDBService)

# A fixture to initialize the DriftDetectionService with the mock
@pytest.fixture
def drift_service(mock_vector_db_service):
    return DriftDetectionService(
        vector_db_service=mock_vector_db_service,
        pca_components=2,
        drift_threshold=0.1,
        retraining_webhook_url="http://fake-retraining-hook.com/trigger"
    )

def _generate_embeddings(count, dim, shift=0.0):
    """Helper to generate some random embeddings."""
    return np.random.rand(count, dim).astype(np.float32) + shift

def _create_scored_points(embeddings):
    """Helper to wrap embeddings in ScoredPoint objects."""
    return [ScoredPoint(id=i, version=1, score=1.0, vector=emb.tolist()) for i, emb in enumerate(embeddings)]

def test_check_drift_no_drift(drift_service, mock_vector_db_service):
    """
    Test case where the reference and comparison distributions are similar,
    so no drift should be detected.
    """
    # Arrange
    ref_embeddings = _generate_embeddings(100, 10)
    comp_embeddings = _generate_embeddings(100, 10, shift=0.01) # very little shift

    mock_vector_db_service.get_embeddings_by_timestamp.side_effect = [
        _create_scored_points(ref_embeddings),
        _create_scored_points(comp_embeddings)
    ]

    # Act
    result = drift_service.check_drift(0, 1, 2, 3)

    # Assert
    assert not result["drift_detected"]
    assert "kl_divergence" in result
    assert result["kl_divergence"] < drift_service.drift_threshold
    assert mock_vector_db_service.get_embeddings_by_timestamp.call_count == 2

def test_check_drift_with_significant_drift(drift_service, mock_vector_db_service):
    """
    Test case where the distributions are different, expecting drift to be detected.
    """
    # Arrange
    ref_embeddings = _generate_embeddings(100, 10)
    comp_embeddings = _generate_embeddings(100, 10, shift=1.5) # significant shift

    mock_vector_db_service.get_embeddings_by_timestamp.side_effect = [
        _create_scored_points(ref_embeddings),
        _create_scored_points(comp_embeddings)
    ]

    # Act
    result = drift_service.check_drift(0, 1, 2, 3)

    # Assert
    assert result["drift_detected"]
    assert result["kl_divergence"] > drift_service.drift_threshold

def test_check_drift_not_enough_data(drift_service, mock_vector_db_service):
    """
    Test case where there isn't enough data to perform PCA and drift detection.
    """
    # Arrange
    ref_embeddings = _generate_embeddings(1, 10) # Only 1 sample
    comp_embeddings = _generate_embeddings(10, 10)

    mock_vector_db_service.get_embeddings_by_timestamp.side_effect = [
        _create_scored_points(ref_embeddings),
        _create_scored_points(comp_embeddings)
    ]

    # Act
    result = drift_service.check_drift(0, 1, 2, 3)

    # Assert
    assert not result["drift_detected"]
    assert result["message"] == "Not enough data for comparison."

@pytest.mark.asyncio
async def test_trigger_retraining_success(drift_service):
    """
    Test the successful triggering of the retraining webhook.
    """
    # Arrange
    event_id = "evt_test_123"
    
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        # Configure the mock to return a successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"retraining_job_id": "job-abc"}
        mock_post.return_value = mock_response

        drift_service.http_client = httpx.AsyncClient() # re-assign to ensure mock is used
        drift_service.http_client.post = mock_post

        # Act
        result = await drift_service.trigger_retraining(event_id, 0, 1)

        # Assert
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.args[0] == "http://fake-retraining-hook.com/trigger"
        assert call_args.kwargs['json']['event_id'] == event_id
        assert "s3_data_path" in call_args.kwargs['json']
        
        assert result["status"] == "Retraining pipeline triggered successfully"
        assert result["retraining_job_id"] == "job-abc"

@pytest.mark.asyncio
async def test_trigger_retraining_http_error(drift_service):
    """
    Test the failure case where the retraining webhook returns an error.
    """
    # Arrange
    event_id = "evt_test_456"
    
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        # Configure the mock to raise an HTTP error
        mock_post.side_effect = httpx.RequestError("Connection failed")

        drift_service.http_client = httpx.AsyncClient()
        drift_service.http_client.post = mock_post

        # Act
        result = await drift_service.trigger_retraining(event_id, 0, 1)

        # Assert
        mock_post.assert_called_once()
        assert result["status"] == "failed"
        assert "Connection failed" in result["reason"]