import numpy as np
from pathlib import Path
from typing import Any, Dict, Optional
from insight_engine.services.model_registry_service import ModelRegistryService

from .module_interface import VideoModule


class DriftDetectionModule(VideoModule):
    """
    A module to detect drift by comparing incoming embeddings to a baseline.
    """

    def __init__(
        self,
        module_config: Dict[str, Any],
        model_registry_service: Optional[ModelRegistryService] = None,
    ):
        super().__init__(module_config, model_registry_service)
        self.baseline_embedding = None
        self.drift_threshold = 0.5

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initializes the module by loading the baseline embedding and setting the threshold.
        """
        baseline_path = Path(config.get("baseline_path"))
        if not baseline_path or not baseline_path.is_file():
            raise FileNotFoundError(f"Baseline embedding not found at: {baseline_path}")

        self.baseline_embedding = np.load(baseline_path)
        self.drift_threshold = config.get("drift_threshold", 0.5)
        print(f"DriftDetectionModule initialized with baseline: {baseline_path}")

    def process(self, embedding: np.ndarray) -> np.ndarray:
        """
        Calculates the cosine distance to the baseline and logs a warning if drift is detected.
        """
        # Normalize vectors to unit length
        embedding_norm = np.linalg.norm(embedding)
        baseline_norm = np.linalg.norm(self.baseline_embedding)

        if embedding_norm == 0 or baseline_norm == 0:
            cosine_similarity = 0.0
        else:
            cosine_similarity = np.dot(embedding, self.baseline_embedding) / (
                embedding_norm * baseline_norm
            )

        # Distance is 1 - similarity
        distance = 1.0 - cosine_similarity

        if distance > self.drift_threshold:
            print(
                f"WARNING: Drift detected! Distance: {distance:.4f} > Threshold: {self.drift_threshold}"
            )

        # Pass the embedding through to the next stage
        return embedding

    def teardown(self) -> None:
        """No-op for this module."""
        print("DriftDetectionModule torn down.")
        pass
