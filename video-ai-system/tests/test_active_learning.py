import pytest
import numpy as np
from pathlib import Path
from video_ai_system.services.annotation_queue import AnnotationQueue
from video_ai_system.modules.active_learning_module import ActiveLearningModule


@pytest.fixture
def queue():
    """
    Creates a temporary, clean database for each test function
    and ensures the connection is closed.
    """
    db_path = "test_queue.db"
    Path(db_path).unlink(missing_ok=True)

    q = AnnotationQueue(db_path=db_path)
    yield q

    q.close()
    Path(db_path).unlink(missing_ok=True)


def test_annotation_queue_add_and_get(queue):
    """Tests that items can be added to and retrieved from the queue."""
    metadata = {"video": "test.mp4", "frame": 101}
    item_id = queue.add_item(metadata)
    assert item_id == 1

    items = queue.get_items(limit=1)
    assert len(items) == 1
    assert items[0]["id"] == 1
    assert items[0]["metadata"]["frame"] == 101


def test_active_learning_module_flags_low_confidence(queue):
    """
    Tests that the module correctly adds an item to the queue when
    the simulated confidence is below the threshold.
    """
    # Pass the test's queue instance directly to the module
    module_config = {"confidence_threshold": 1.0, "db_path": "test_queue.db"}
    module = ActiveLearningModule(module_config, queue=queue)
    module.initialize(module_config)

    dummy_embedding = np.random.rand(128)
    module.process(dummy_embedding)

    items = queue.get_items()
    assert len(items) == 1
    assert items[0]["metadata"]["reason"] == "low_confidence"


def test_active_learning_module_passes_high_confidence(queue):
    """
    Tests that the module does NOT add an item to the queue when
    the simulated confidence is above the threshold.
    """
    # Pass the test's queue instance directly to the module
    module_config = {"confidence_threshold": 0.0, "db_path": "test_queue.db"}
    module = ActiveLearningModule(module_config, queue=queue)
    module.initialize(module_config)

    dummy_embedding = np.random.rand(128)
    module.process(dummy_embedding)

    items = queue.get_items()
    assert len(items) == 0
