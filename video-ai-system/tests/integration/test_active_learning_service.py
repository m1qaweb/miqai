import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import numpy as np

from video_ai_system.services.active_learning_service import ActiveLearningService
from video_ai_system.services.cvat_service import CVATService

@pytest.fixture
def mock_cvat_service():
    """Fixture for a mocked CVATService."""
    mock = MagicMock(spec=CVATService)
    mock.get_or_create_project.return_value = 1  # project_id
    mock.create_task.return_value = 101  # task_id
    mock.upload_data.return_value = None

    # Simulate one completed task
    mock.get_completed_tasks.return_value = [{'id': 101, 'name': 'task-101'}]
    # Simulate annotation data
    mock.get_task_annotations.return_value = {"version": "1.1", "tags": [], "shapes": [], "tracks": []}
    mock.delete_task.return_value = None
    return mock

@patch('video_ai_system.services.active_learning_service.CVATService', autospec=True)
def test_full_active_learning_loop(mock_cvat_service_class, tmp_path):
    """
    Tests the full active learning loop from sending frames for annotation
    to processing the completed annotations, with a mocked CVATService.
    """
    # --- Setup ---
    # Configure the mock instance that will be created
    mock_cvat_instance = mock_cvat_service_class.return_value
    mock_cvat_instance.get_or_create_project.return_value = 1
    mock_cvat_instance.create_task.return_value = 101
    mock_cvat_instance.get_completed_tasks.return_value = [{'id': 101, 'name': 'task-101'}]
    mock_cvat_instance.get_task_annotations.return_value = {"some": "annotation_data"}
    
    # Create a temporary directory for annotations
    annotation_output_dir = tmp_path / "annotations"
    annotation_output_dir.mkdir()

    # Instantiate the service
    active_learning_service = ActiveLearningService(
        cvat_url="http://localhost:8080",
        cvat_user="user",
        cvat_pass="pass",
        project_name="Test Project",
        annotation_output_dir=str(annotation_output_dir)
    )

    # --- Part 1: Send for Annotation ---
    sample_frames = [(f"frame_{i:04d}.jpg", np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)) for i in range(5)]
    
    active_learning_service.send_for_annotation(sample_frames, "test_video_01")

    # Assertions for sending
    mock_cvat_instance.get_or_create_project.assert_called_once_with("Test Project")
    assert mock_cvat_instance.create_task.call_count == 1
    assert mock_cvat_instance.upload_data.call_count == 1
    
    # Check that task name was created correctly
    create_task_args, _ = mock_cvat_instance.create_task.call_args
    assert create_task_args[0].startswith("annotation_test_video_01")
    assert create_task_args[1] == 1 # project_id

    # --- Part 2: Process Completed Annotations ---
    active_learning_service.process_completed_annotations()

    # Assertions for processing
    mock_cvat_instance.get_completed_tasks.assert_called_once_with("Test Project")
    mock_cvat_instance.get_task_annotations.assert_called_once_with(101)
    mock_cvat_instance.delete_task.assert_called_once_with(101)

    # --- Part 3: Verify Output ---
    # Check if the annotation file was created
    expected_file = annotation_output_dir / "task-101.json"
    assert expected_file.exists()

    # Check the content of the saved file
    with open(expected_file, 'r') as f:
        data = json.load(f)
    assert data == {"some": "annotation_data"}