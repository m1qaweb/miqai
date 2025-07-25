import pytest
import cv2
import numpy as np
from insight_engine.modules.data_collection_module import DataCollectionModule


@pytest.fixture
def dummy_video_file(tmp_path):
    """Creates a dummy video file for testing."""
    video_path = tmp_path / "test.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 1, (10, 10))
    for _ in range(3):
        out.write(np.zeros((10, 10, 3), dtype=np.uint8))
    out.release()
    return video_path


def test_initialization_success(dummy_video_file):
    """Tests successful initialization of the module."""
    config = {"video_source_path": str(dummy_video_file)}
    module = DataCollectionModule(config)
    module.initialize(config)
    assert module.video_path == dummy_video_file


def test_initialization_file_not_found():
    """Tests that initialization fails if the video file does not exist."""
    config = {"video_source_path": "non_existent_video.mp4"}
    with pytest.raises(FileNotFoundError):
        module = DataCollectionModule(config)
        module.initialize(config)


def test_process_yields_frames(dummy_video_file):
    """Tests that the process method correctly yields frames from the video."""
    config = {"video_source_path": str(dummy_video_file)}
    module = DataCollectionModule(config)
    module.initialize(config)

    frame_count = 0
    for frame in module.process():
        assert frame is not None
        assert frame.shape == (10, 10, 3)
        frame_count += 1

    assert frame_count == 3
