import numpy as np
from typing import Any, Dict, Optional
from video_ai_system.services.model_registry_service import ModelRegistryService

from .module_interface import VideoModule


class SimulatedPretrainingModule(VideoModule):
    """
    A module to simulate the output of a self-supervised pretraining model.
    It takes a frame and returns a random embedding vector.
    """

    def __init__(
        self,
        module_config: Dict[str, Any],
        model_registry_service: Optional[ModelRegistryService] = None,
    ):
        super().__init__(module_config, model_registry_service)
        self.embedding_dim = 512
        self.processed_frames_count = 0

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initializes the module with a configured embedding dimension.
        """
        self.embedding_dim = config.get("embedding_dim", 512)
        print(
            f"SimulatedPretrainingModule initialized with embedding_dim: {self.embedding_dim}"
        )

    def process(self, frame: np.ndarray) -> np.ndarray:
        """
        Generates a random NumPy array to simulate a feature embedding.
        If a training_data_source is provided in the config, it will iterate
        through it to simulate processing multiple frames.
        """
        training_data = self.module_config.get("module_params", {}).get(
            "training_data_source"
        )
        if training_data and isinstance(training_data, list):
            self.processed_frames_count += len(training_data)
        else:
            self.processed_frames_count += 1

        return np.random.rand(self.embedding_dim).astype(np.float32)

    def teardown(self) -> None:
        """
        Registers the "trained" model with the ModelRegistryService.
        """
        if self.model_registry_service:
            model_loader_config = self.module_config.get("model_loader", {})
            model_name = model_loader_config.get("model_name")

            if model_name:
                metadata = {"processed_frames": self.processed_frames_count}
                self.model_registry_service.register_model(
                    model_name=model_name, metadata=metadata
                )
                print(
                    f"SimulatedPretrainingModule: Registered model '{model_name}' with metadata {metadata}"
                )
            else:
                print(
                    "SimulatedPretrainingModule: No model_name found in model_loader config, skipping registration."
                )
        else:
            print(
                "SimulatedPretrainingModule: No model registry service available, skipping registration."
            )

        print("SimulatedPretrainingModule torn down.")
