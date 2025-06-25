import pytest
import json
from unittest.mock import MagicMock, patch
from typing import Dict, Any

from video_ai_system.services.pipeline_service import PipelineService
from video_ai_system.services.model_registry_service import ModelRegistryService
from video_ai_system.modules.module_interface import VideoModule
from video_ai_system.config import settings


class MockModule(VideoModule):
    def __init__(self, module_config: Dict[str, Any], **kwargs):
        super().__init__(module_config, **kwargs)
        self.module_id = module_config.get("module_id", "mock_module")
        self.was_called = False
        self.teardown_called = False
        self.initialized_called = False

    def initialize(self, config: Dict[str, Any]) -> None:
        self.initialized_called = True

    def process(self, frame: Any) -> Any:
        self.was_called = True
        return frame

    def teardown(self) -> None:
        self.teardown_called = True

    def get_id(self) -> str:
        return self.module_id


@pytest.fixture
def mock_module_instance():
    # This fixture is now more complex because the service instantiates the module.
    # We will use patching to control the class that gets instantiated.
    return MockModule


@pytest.fixture
def model_registry_service(tmp_path):
    """Creates a ModelRegistryService pointing to a temporary directory."""
    registry_path = tmp_path / "model_registry"
    registry_path.mkdir()
    # Create a dummy model file for the mock module to "load"
    (registry_path / "mock_module").mkdir()
    (registry_path / "mock_module" / "1").mkdir()
    (registry_path / "mock_module" / "1" / "model.mock").touch()
    return ModelRegistryService(registry_path=str(registry_path))


@pytest.fixture
def pipeline_service(model_registry_service):
    """Creates a PipelineService with a real model registry."""
    return PipelineService(model_registry_service=model_registry_service)


@pytest.fixture
def test_config_file(tmp_path):
    """Creates a temporary pipeline config file."""
    config = {
        "pipelines": {
            "test_pipeline": [
                {"module_name": "mock_module", "version": "1", "config": {}}
            ]
        }
    }
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config))
    return str(config_file)


def test_pipeline_execution(pipeline_service, test_config_file):
    """
    Tests that a pipeline correctly executes all its modules.
    """
    with patch(
        "video_ai_system.services.pipeline_service.importlib.import_module"
    ) as mock_import:
        # We need to control what class is returned by the dynamic import
        mock_import.return_value = MagicMock(MockModule=MockModule)

        pipeline_service.load_from_config(test_config_file)
        # The pipeline now holds the *instance* of the module
        mock_instance = pipeline_service.pipelines["test_pipeline"][0]
        
        pipeline_service.execute_pipeline("test_pipeline", {})

        assert mock_instance.was_called
        assert mock_instance.initialized_called


def test_pipeline_teardown(pipeline_service, test_config_file):
    """
    Tests that the teardown method is called on all modules.
    """
    with patch(
        "video_ai_system.services.pipeline_service.importlib.import_module"
    ) as mock_import:
        mock_import.return_value = MagicMock(MockModule=MockModule)

        pipeline_service.load_from_config(test_config_file)
        mock_instance = pipeline_service.pipelines["test_pipeline"][0]

        # Simulate shutdown by calling teardown on modules
        for pipeline in pipeline_service.pipelines.values():
            for module in pipeline:
                module.teardown()

        assert mock_instance.teardown_called
