import pytest
from unittest.mock import MagicMock
import redis
from video_ai_system.services.inference_router import InferenceRouter

# A mapping of adaptation levels to model names for use in tests
MODEL_MAPPING = {
    "NORMAL": "model-normal.onnx",
    "DEGRADED": "model-light.onnx",
    "CRITICAL": "model-fast.onnx",
}

@pytest.fixture
def mock_redis_client():
    """Pytest fixture for a mock Redis client."""
    return MagicMock(spec=redis.Redis)

def test_get_target_model_normal_level(mock_redis_client):
    """
    Test that the router returns the normal model when the adaptation level is 'NORMAL'.
    """
    mock_redis_client.get.return_value = b"NORMAL"
    router = InferenceRouter(model_mapping=MODEL_MAPPING, redis_client=mock_redis_client)
    assert router.get_target_model() == "model-normal.onnx"
    mock_redis_client.get.assert_called_once_with(InferenceRouter.ADAPTATION_KEY)

def test_get_target_model_degraded_level(mock_redis_client):
    """
    Test that the router returns the light model when the adaptation level is 'DEGRADED'.
    """
    mock_redis_client.get.return_value = b"DEGRADED"
    router = InferenceRouter(model_mapping=MODEL_MAPPING, redis_client=mock_redis_client)
    assert router.get_target_model() == "model-light.onnx"

def test_get_target_model_critical_level(mock_redis_client):
    """
    Test that the router returns the fast model when the adaptation level is 'CRITICAL'.
    """
    mock_redis_client.get.return_value = b"CRITICAL"
    router = InferenceRouter(model_mapping=MODEL_MAPPING, redis_client=mock_redis_client)
    assert router.get_target_model() == "model-fast.onnx"

def test_get_target_model_redis_key_not_set(mock_redis_client):
    """
    Test that the router defaults to the NORMAL model if the Redis key is not set.
    """
    mock_redis_client.get.return_value = None
    router = InferenceRouter(model_mapping=MODEL_MAPPING, redis_client=mock_redis_client)
    assert router.get_target_model() == "model-normal.onnx"

def test_get_target_model_redis_connection_error(mock_redis_client, caplog):
    """

    Test that the router defaults to the NORMAL model if Redis is unavailable.
    """
    mock_redis_client.get.side_effect = redis.exceptions.ConnectionError
    router = InferenceRouter(model_mapping=MODEL_MAPPING, redis_client=mock_redis_client)
    
    assert router.get_target_model() == "model-normal.onnx"
    assert "Redis connection failed" in caplog.text

def test_get_target_model_unknown_level_falls_back_to_normal(mock_redis_client, caplog):
    """
    Test that an unknown adaptation level falls back to the NORMAL model.
    """
    mock_redis_client.get.return_value = b"UNKNOWN_LEVEL"
    router = InferenceRouter(model_mapping=MODEL_MAPPING, redis_client=mock_redis_client)

    assert router.get_target_model() == "model-normal.onnx"
    assert "No model mapped for adaptation level 'UNKNOWN_LEVEL'" in caplog.text
