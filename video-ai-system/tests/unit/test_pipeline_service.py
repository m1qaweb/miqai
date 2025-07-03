import pytest
from unittest.mock import MagicMock, patch
import redis
from video_ai_system.services.pipeline_service import PipelineService
from video_ai_system.modules.module_interface import VideoModule

# Mock configuration for adaptation rules
ADAPTATION_CONFIG = {
    "DEGRADED": {
        "parameter_overrides": {"fps_limit": 15}
    },
    "CRITICAL": {
        "parameter_overrides": {"fps_limit": 10}
    }
}

# A mock VideoModule to test parameter updates
class MockVideoModule(VideoModule):
    def __init__(self, module_config=None, model_registry_service=None):
        super().__init__(module_config, model_registry_service)
        self.params = {}
        self.process_called_with = None

    def initialize(self, params: dict):
        self.params = params

    def process(self, data: any) -> any:
        self.process_called_with = data
        return "processed"

    def update_params(self, params_to_update: dict):
        self.params.update(params_to_update)

@pytest.fixture
def mock_redis_client():
    """Pytest fixture for a mock Redis client."""
    return MagicMock(spec=redis.Redis)

@pytest.fixture
def mock_services(mock_redis_client):
    """Fixture to create a PipelineService with mocked dependencies."""
    return {
        "model_registry_service": MagicMock(),
        "shadow_testing_service": MagicMock(),
        "inference_router": MagicMock(),
        "comparison_service": MagicMock(),
        "redis_client": mock_redis_client,
        "adaptation_config": ADAPTATION_CONFIG,
    }

def test_execute_pipeline_normal_level(mock_services, mock_redis_client):
    """
    Test that pipeline executes normally when adaptation level is NORMAL.
    """
    mock_redis_client.get.return_value = b"NORMAL"
    service = PipelineService(**mock_services)
    
    mock_module = MockVideoModule()
    service.pipelines["test_pipeline"] = [mock_module]
    
    service.execute_pipeline("test_pipeline", "initial_data")
    
    # No overrides should be applied
    assert mock_module.params == {}

def test_execute_pipeline_degraded_level_applies_overrides(mock_services, mock_redis_client):
    """
    Test that parameter overrides are applied for DEGRADED level.
    """
    mock_redis_client.get.return_value = b"DEGRADED"
    service = PipelineService(**mock_services)
    
    mock_module = MockVideoModule()
    service.pipelines["test_pipeline"] = [mock_module]
    
    service.execute_pipeline("test_pipeline", "initial_data")
    
    assert mock_module.params == {"fps_limit": 15}

def test_execute_pipeline_critical_level_applies_overrides(mock_services, mock_redis_client):
    """
    Test that parameter overrides are applied for CRITICAL level.
    """
    mock_redis_client.get.return_value = b"CRITICAL"
    service = PipelineService(**mock_services)
    
    mock_module = MockVideoModule()
    service.pipelines["test_pipeline"] = [mock_module]
    
    service.execute_pipeline("test_pipeline", "initial_data")
    
    assert mock_module.params == {"fps_limit": 10}

def test_execute_pipeline_redis_down_defaults_to_normal(mock_services, mock_redis_client, caplog):
    """
    Test that the pipeline defaults to NORMAL when Redis is down.
    """
    mock_redis_client.get.side_effect = redis.exceptions.ConnectionError
    service = PipelineService(**mock_services)
    
    mock_module = MockVideoModule()
    service.pipelines["test_pipeline"] = [mock_module]
    
    service.execute_pipeline("test_pipeline", "initial_data")
    
    # No overrides should be applied
    assert mock_module.params == {}
    assert "Redis connection failed" in caplog.text

def test_execute_pipeline_key_not_set_defaults_to_normal(mock_services, mock_redis_client, caplog):
    """
    Test that the pipeline defaults to NORMAL when the adaptation key is not set.
    """
    mock_redis_client.get.return_value = None
    service = PipelineService(**mock_services)
    
    mock_module = MockVideoModule()
    service.pipelines["test_pipeline"] = [mock_module]
    
    service.execute_pipeline("test_pipeline", "initial_data")
    
    # No overrides should be applied
    assert mock_module.params == {}
    assert "not found in Redis" in caplog.text