import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from video_ai_system.modules.shadowing_module import ShadowingModule

# --- Test Data ---

PIPELINE_DATA = {
    "video_id": "vid_001",
    "video_path": "/samples/test.mp4",
    "model_id": "prod_model:v1",
    "results": {"embedding": [0.1, 0.2, 0.3]},
    "latency": 0.5,
}

# --- Fixtures ---

@pytest.fixture
def mock_model_registry_service():
    return MagicMock()

@pytest.fixture
def mock_shadow_testing_service():
    return MagicMock(compare_and_log=AsyncMock())

@pytest.fixture
def shadowing_module(mock_model_registry_service, mock_shadow_testing_service):
    return ShadowingModule(
        module_config={},
        model_registry_service=mock_model_registry_service,
        shadow_testing_service=mock_shadow_testing_service,
    )

# --- Unit Tests ---

@pytest.mark.asyncio
async def test_process_triggers_shadow_test_when_shadow_model_exists(
    shadowing_module, mock_model_registry_service, mock_shadow_testing_service
):
    # Arrange
    shadow_model_id = "shadow_model:v2"
    mock_model_registry_service.get_shadow_model.return_value = shadow_model_id

    # Act
    result_data = shadowing_module.process(PIPELINE_DATA)
    await asyncio.sleep(0.01) # Allow the background task to run

    # Assert
    mock_model_registry_service.get_shadow_model.assert_called_once_with("prod_model:v1")
    mock_shadow_testing_service.compare_and_log.assert_called_once_with(
        video_id="vid_001",
        production_model_id="prod_model:v1",
        candidate_model_id=shadow_model_id,
        production_results={"embedding": [0.1, 0.2, 0.3]},
        production_latency=0.5,
        video_path="/samples/test.mp4",
    )
    assert result_data is PIPELINE_DATA # Ensure data is passed through unmodified

@pytest.mark.asyncio
async def test_process_does_nothing_when_no_shadow_model(
    shadowing_module, mock_model_registry_service, mock_shadow_testing_service
):
    # Arrange
    mock_model_registry_service.get_shadow_model.return_value = None

    # Act
    result_data = shadowing_module.process(PIPELINE_DATA)
    await asyncio.sleep(0.01)

    # Assert
    mock_model_registry_service.get_shadow_model.assert_called_once_with("prod_model:v1")
    mock_shadow_testing_service.compare_and_log.assert_not_called()
    assert result_data is PIPELINE_DATA

def test_process_handles_missing_model_id_gracefully(
    shadowing_module, mock_model_registry_service, mock_shadow_testing_service
):
    # Arrange
    data_without_model_id = PIPELINE_DATA.copy()
    del data_without_model_id["model_id"]

    # Act
    result_data = shadowing_module.process(data_without_model_id)

    # Assert
    mock_model_registry_service.get_shadow_model.assert_not_called()
    mock_shadow_testing_service.compare_and_log.assert_not_called()
    assert result_data is data_without_model_id