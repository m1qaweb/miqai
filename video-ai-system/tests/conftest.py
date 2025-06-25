import pytest
import cv2
import numpy as np
from pathlib import Path
import tempfile
import shutil
from video_ai_system.services.model_registry_service import ModelRegistryService
from video_ai_system.services.pipeline_service import PipelineService


@pytest.fixture(scope="session")
def dummy_video_file():
    """
    Creates a dummy video file for the entire test session.
    This fixture is available to all test files.
    """
    path = Path("test_video.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(path), fourcc, 1, (10, 10))
    # Create 3 black frames
    for _ in range(3):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    yield path

    # Teardown: remove the file after tests are done
    path.unlink()


@pytest.fixture
def model_registry_service():
    """
    Provides a ModelRegistryService instance initialized in a temporary directory.
    """
    temp_dir = tempfile.mkdtemp()
    registry = ModelRegistryService(registry_path=temp_dir)
    yield registry
    shutil.rmtree(temp_dir)


@pytest.fixture
def pipeline_service(model_registry_service):
    """
    Provides a clean PipelineService instance for each test, using the model_registry_service fixture.
    """
    return PipelineService(model_registry_service)
