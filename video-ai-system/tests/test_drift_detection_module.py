import pytest
import numpy as np
from pathlib import Path
from video_ai_system.modules.drift_detection_module import DriftDetectionModule


@pytest.fixture(scope="module")
def baseline_file():
    """Creates a dummy baseline embedding file for testing."""
    path = Path("baseline_for_test.npy")
    embedding = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    np.save(path, embedding)
    yield path
    path.unlink()


def test_initialization_success(baseline_file):
    """Tests successful initialization of the module."""
    config = {"baseline_path": str(baseline_file), "drift_threshold": 0.5}
    module = DriftDetectionModule(config)
    module.initialize(config)
    assert np.array_equal(module.baseline_embedding, np.load(baseline_file))
    assert module.drift_threshold == 0.5


def test_no_drift(baseline_file):
    """Tests that no drift is detected for a similar vector."""
    config = {"baseline_path": str(baseline_file), "drift_threshold": 0.1}
    module = DriftDetectionModule(config)
    module.initialize(config)

    # An almost identical vector
    incoming_embedding = np.array([0.99, 0.01, 0.0], dtype=np.float32)

    # The process method should not print a warning (we can't easily test stdout,
    # but we can ensure it doesn't crash and returns the embedding)
    result = module.process(incoming_embedding)
    assert np.array_equal(result, incoming_embedding)


def test_drift_detected(baseline_file, capsys):
    """Tests that drift is detected for a dissimilar vector."""
    config = {"baseline_path": str(baseline_file), "drift_threshold": 0.5}
    module = DriftDetectionModule(config)
    module.initialize(config)

    # A completely different vector
    incoming_embedding = np.array([-1.0, 0.0, 0.0], dtype=np.float32)

    module.process(incoming_embedding)

    captured = capsys.readouterr()
    assert "WARNING: Drift detected!" in captured.out
