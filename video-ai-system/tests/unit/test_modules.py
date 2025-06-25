import unittest
from unittest.mock import patch, MagicMock
import numpy as np

# Assuming the project structure allows this import path
from video_ai_system.modules.module_interface import VideoModule
from video_ai_system.modules.data_collection_module import DataCollectionModule
from video_ai_system.modules.simulated_pretraining_module import (
    SimulatedPretrainingModule,
)
from video_ai_system.services.model_registry_service import ModelRegistryService


# A concrete implementation of the abstract VideoModule for testing purposes
class DummyVideoModule(VideoModule):
    def initialize(self, config):
        pass

    def process(self, frame):
        pass

    def teardown(self):
        pass


class TestCoreModules(unittest.TestCase):

    def test_video_module_initialization(self):
        """
        Tests that a concrete implementation of VideoModule correctly stores
        its configuration and the model registry service.
        """
        mock_config = {"name": "TestModule"}
        mock_registry_service = MagicMock(spec=ModelRegistryService)

        # Instantiate the dummy concrete module
        module = DummyVideoModule(
            module_config=mock_config, model_registry_service=mock_registry_service
        )

        # Assert that the attributes are stored correctly
        self.assertEqual(module.module_config, mock_config)
        self.assertEqual(module.model_registry_service, mock_registry_service)

    @patch("video_ai_system.modules.data_collection_module.cv2.VideoCapture")
    @patch("video_ai_system.modules.data_collection_module.Path")
    def test_data_collection_module_process(self, mock_path_class, mock_video_capture):
        """
        Tests the DataCollectionModule's process method in isolation,
        mocking out filesystem and OpenCV dependencies.
        """
        # Configure mocks
        mock_path_instance = mock_path_class.return_value
        mock_path_instance.is_file.return_value = True

        mock_capture_instance = MagicMock()
        mock_capture_instance.isOpened.return_value = True
        # Simulate two frames being read, then the end of the video
        mock_capture_instance.read.side_effect = [
            (True, np.zeros((100, 100, 3), dtype=np.uint8)),
            (True, np.zeros((100, 100, 3), dtype=np.uint8)),
            (False, None),
        ]
        mock_video_capture.return_value = mock_capture_instance

        # Setup module
        module_config = {}  # Not used by initialize or process
        init_config = {"video_source_path": "dummy/path.mp4"}
        mock_registry_service = MagicMock()
        data_collection_module = DataCollectionModule(
            module_config=module_config, model_registry_service=mock_registry_service
        )

        # Initialize the module
        data_collection_module.initialize(config=init_config)

        # Execute the process method
        output_generator = data_collection_module.process(None)  # No input data needed

        # Verify the output
        results = list(output_generator)
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], np.ndarray)
        self.assertIsInstance(results[1], np.ndarray)

        # Verify that VideoCapture was called with the correct path
        mock_path_class.assert_called_once_with(init_config["video_source_path"])
        mock_video_capture.assert_called_once_with(str(mock_path_instance))
        # Verify that release was called on the capture object
        mock_capture_instance.release.assert_called_once()

    def test_simulated_pretraining_module_process(self):
        """
        Tests that the SimulatedPretrainingModule correctly increments its
        internal counter based on the module_config.
        """
        mock_registry_service = MagicMock()

        # Case 1: No training_data_source, should increment by 1
        with self.subTest("Increment by one without training_data_source"):
            config_1 = {"embedding_dim": 128}
            module_1 = SimulatedPretrainingModule(
                module_config=config_1, model_registry_service=mock_registry_service
            )
            self.assertEqual(module_1.processed_frames_count, 0)

            # Simulate processing a frame
            result = module_1.process(np.zeros((1, 1, 3)))

            self.assertEqual(module_1.processed_frames_count, 1)
            self.assertIsInstance(result, np.ndarray)
            self.assertEqual(result.shape, (512,))

        # Case 2: With training_data_source list, should increment by list length
        with self.subTest("Increment by list length with training_data_source"):
            config_2 = {
                "embedding_dim": 64,
                "module_params": {"training_data_source": ["item1", "item2", "item3"]},
            }
            module_2 = SimulatedPretrainingModule(
                module_config=config_2, model_registry_service=mock_registry_service
            )
            self.assertEqual(module_2.processed_frames_count, 0)

            # Simulate processing a frame
            result = module_2.process(np.zeros((1, 1, 3)))

            self.assertEqual(module_2.processed_frames_count, 3)
            self.assertIsInstance(result, np.ndarray)
            self.assertEqual(result.shape, (512,))


if __name__ == "__main__":
    unittest.main()
