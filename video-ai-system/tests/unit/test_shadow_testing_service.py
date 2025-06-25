import pytest
from unittest.mock import MagicMock, AsyncMock

from video_ai_system.services.shadow_testing_service import ShadowTestingService

# --- Test Data ---

PROD_RESULTS_BASE = {
    "detections": [
        {"label": "car", "confidence": 0.95},
        {"label": "person", "confidence": 0.88},
        {"label": "bicycle", "confidence": 0.91},
    ]
}

CAND_RESULTS_SIMILAR = {
    "detections": [
        {"label": "car", "confidence": 0.92},
        {"label": "person", "confidence": 0.90},
        {"label": "bicycle", "confidence": 0.85},
    ]
}

CAND_RESULTS_DIFFERENT = {
    "detections": [
        {"label": "car", "confidence": 0.93},
        {"label": "bus", "confidence": 0.80},
        {"label": "dog", "confidence": 0.75},
    ]
}

CAND_RESULTS_EMPTY = {"detections": []}
PROD_RESULTS_EMPTY = {"detections": []}


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
def shadow_testing_service(mock_inference_service, mock_logger):
    """Provides an instance of the ShadowTestingService with mock dependencies."""
    return ShadowTestingService(
        inference_service=mock_inference_service, logger=mock_logger
    )


# --- Unit Tests for _calculate_metrics ---

def test_calculate_metrics_similar_results(shadow_testing_service):
    metrics = shadow_testing_service._calculate_metrics(
        PROD_RESULTS_BASE, CAND_RESULTS_SIMILAR
    )
    assert metrics["detection_count_prod"] == 3
    assert metrics["detection_count_cand"] == 3
    assert metrics["class_jaccard_similarity"] == 1.0
    assert not metrics["classes_only_in_prod"]
    assert not metrics["classes_only_in_cand"]
    assert pytest.approx(metrics["avg_confidence_prod"], 0.001) == 0.913
    assert pytest.approx(metrics["avg_confidence_cand"], 0.001) == 0.890

def test_calculate_metrics_different_results(shadow_testing_service):
    metrics = shadow_testing_service._calculate_metrics(
        PROD_RESULTS_BASE, CAND_RESULTS_DIFFERENT
    )
    assert metrics["detection_count_prod"] == 3
    assert metrics["detection_count_cand"] == 3
    assert pytest.approx(metrics["class_jaccard_similarity"], 0.001) == 0.2 # 1 / 5
    assert sorted(metrics["classes_only_in_prod"]) == ["bicycle", "person"]
    assert sorted(metrics["classes_only_in_cand"]) == ["bus", "dog"]

def test_calculate_metrics_candidate_empty(shadow_testing_service):
    metrics = shadow_testing_service._calculate_metrics(
        PROD_RESULTS_BASE, CAND_RESULTS_EMPTY
    )
    assert metrics["detection_count_prod"] == 3
    assert metrics["detection_count_cand"] == 0
    assert metrics["class_jaccard_similarity"] == 0.0
    assert sorted(metrics["classes_only_in_prod"]) == ["bicycle", "car", "person"]
    assert not metrics["classes_only_in_cand"]
    assert metrics["avg_confidence_cand"] == 0.0

def test_calculate_metrics_both_empty(shadow_testing_service):
    metrics = shadow_testing_service._calculate_metrics(
        PROD_RESULTS_EMPTY, CAND_RESULTS_EMPTY
    )
    assert metrics["detection_count_prod"] == 0
    assert metrics["detection_count_cand"] == 0
    assert metrics["class_jaccard_similarity"] == 1.0 # No classes, so union is 0
    assert not metrics["classes_only_in_prod"]
    assert not metrics["classes_only_in_cand"]
    assert metrics["avg_confidence_prod"] == 0.0
    assert metrics["avg_confidence_cand"] == 0.0


# --- Integration-style Test for compare_and_log ---

@pytest.mark.asyncio
async def test_compare_and_log_flow(
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
    # 1. Check that inference was called for the candidate model
    mock_inference_service.analyze.assert_called_once_with(video_path, cand_model_id)

    # 2. Check that the results were logged
    assert mock_logger.info.call_count == 2
    log_payload = mock_logger.info.call_args_list[0].args[0]
    
    assert log_payload["message"] == "shadow_test_result"
    assert log_payload["video_id"] == video_id
    assert log_payload["production_model_id"] == prod_model_id
    assert log_payload["candidate_model_id"] == cand_model_id
    assert log_payload["production_latency_ms"] == 500
    assert log_payload["candidate_latency_ms"] == 700
    assert log_payload["detection_count_prod"] == 3
    assert log_payload["detection_count_cand"] == 3
    assert log_payload["class_jaccard_similarity"] == 1.0