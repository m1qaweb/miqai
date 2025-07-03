import pytest
from unittest.mock import MagicMock, AsyncMock
from prometheus_client import CollectorRegistry

from video_ai_system.services.shadow_testing_service import ShadowTestingService

# --- Test Data ---

PROD_RESULTS_BASE = {"embedding": [0.1, 0.2, 0.3, 0.4]}
CAND_RESULTS_SIMILAR = {"embedding": [0.11, 0.22, 0.33, 0.44]} # High similarity
CAND_RESULTS_DIFFERENT = {"embedding": [0.9, 0.8, 0.7, 0.6]} # Low similarity
CAND_RESULTS_ORTHOGONAL = {"embedding": [-0.2, 0.1, -0.4, 0.3]} # Zero similarity
CAND_RESULTS_NO_EMBEDDING = {"embedding": None}
PROD_RESULTS_NO_EMBEDDING = {"embedding": None}


# --- Fixtures ---

@pytest.fixture
def mock_inference_service():
    """Provides a mock InferenceService."""
    return AsyncMock()

@pytest.fixture
def mock_logger():
    """Provides a mock logger."""
    return MagicMock()

@pytest.fixture
def mock_registry():
    """Provides a mock Prometheus CollectorRegistry."""
    # For unit tests, we can often pass None or a simple mock
    # as we are not testing the metric registration itself.
    return CollectorRegistry()


@pytest.fixture
def shadow_testing_service(mock_inference_service, mock_logger, mock_registry):
    """Provides an instance of the ShadowTestingService with mock dependencies."""
    return ShadowTestingService(
        inference_service=mock_inference_service,
        logger=mock_logger,
        registry=mock_registry,
    )


# --- Unit Tests for _calculate_metrics (V1) ---

def test_calculate_metrics_similar_embeddings(shadow_testing_service):
    metrics = shadow_testing_service._calculate_metrics(
        PROD_RESULTS_BASE, CAND_RESULTS_SIMILAR
    )
    assert metrics["has_prod_embedding"]
    assert metrics["has_cand_embedding"]
    assert pytest.approx(metrics["embedding_cosine_similarity"], 0.001) == 0.996

def test_calculate_metrics_different_embeddings(shadow_testing_service):
    metrics = shadow_testing_service._calculate_metrics(
        PROD_RESULTS_BASE, CAND_RESULTS_DIFFERENT
    )
    assert pytest.approx(metrics["embedding_cosine_similarity"], 0.001) == 0.653

def test_calculate_metrics_orthogonal_embeddings(shadow_testing_service):
    metrics = shadow_testing_service._calculate_metrics(
        PROD_RESULTS_BASE, CAND_RESULTS_ORTHOGONAL
    )
    assert pytest.approx(metrics["embedding_cosine_similarity"], 0.001) == 0.0

def test_calculate_metrics_candidate_missing_embedding(shadow_testing_service):
    metrics = shadow_testing_service._calculate_metrics(
        PROD_RESULTS_BASE, CAND_RESULTS_NO_EMBEDDING
    )
    assert metrics["has_prod_embedding"]
    assert not metrics["has_cand_embedding"]
    assert metrics["embedding_cosine_similarity"] == 0.0

def test_calculate_metrics_both_missing_embedding(shadow_testing_service):
    metrics = shadow_testing_service._calculate_metrics(
        PROD_RESULTS_NO_EMBEDDING, CAND_RESULTS_NO_EMBEDDING
    )
    assert not metrics["has_prod_embedding"]
    assert not metrics["has_cand_embedding"]
    assert metrics["embedding_cosine_similarity"] == 0.0


# --- Integration-style Test for compare_and_log ---

@pytest.mark.asyncio
async def test_compare_and_log_flow_success(
    shadow_testing_service, mock_inference_service, mock_logger
):
    # Arrange
    video_id = "test_vid_123"
    prod_model_id = "prod:v1"
    cand_model_id = "cand:v2"
    video_path = "/path/to/video.mp4"
    prod_latency = 0.5

    mock_inference_service.analyze.return_value = (CAND_RESULTS_SIMILAR, 0.7)

    # Act
    await shadow_testing_service.compare_and_log(
        video_id=video_id,
        production_model_id=prod_model_id,
        candidate_model_id=cand_model_id,
        production_results=PROD_RESULTS_BASE,
        production_latency=prod_latency,
        video_path=video_path,
    )

    # Assert
    mock_inference_service.analyze.assert_called_once_with(video_path, cand_model_id)
    log_payload = mock_logger.info.call_args_list[1].args[0]
    assert log_payload["message"] == "shadow_test_result"
    assert log_payload["video_id"] == video_id
    assert log_payload["production_latency_ms"] == 500
    assert log_payload["candidate_latency_ms"] == 700
    assert pytest.approx(log_payload["embedding_cosine_similarity"], 0.001) == 0.996
    mock_logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_compare_and_log_handles_inference_failure(
    shadow_testing_service, mock_inference_service, mock_logger
):
    # Arrange
    video_id = "test_vid_fail"
    prod_model_id = "prod:v1"
    cand_model_id = "cand:v2_fails"
    video_path = "/path/to/video.mp4"
    prod_latency = 0.5
    
    # Simulate the candidate inference failing
    mock_inference_service.analyze.side_effect = Exception("Candidate model crashed")

    # Act
    await shadow_testing_service.compare_and_log(
        video_id=video_id,
        production_model_id=prod_model_id,
        candidate_model_id=cand_model_id,
        production_results=PROD_RESULTS_BASE,
        production_latency=prod_latency,
        video_path=video_path,
    )

    # Assert
    mock_inference_service.analyze.assert_called_once_with(video_path, cand_model_id)
    mock_logger.error.assert_called_once()
    error_log = mock_logger.error.call_args[0][0]
    assert "Shadow analysis failed" in error_log
    assert "Candidate model crashed" in error_log