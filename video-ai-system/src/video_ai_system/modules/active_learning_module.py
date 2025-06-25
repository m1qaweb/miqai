import random
import numpy as np
from typing import Any, Dict, Optional
from video_ai_system.services.model_registry_service import ModelRegistryService

from .module_interface import VideoModule
from ..services.annotation_queue import AnnotationQueue


class ActiveLearningModule(VideoModule):
    """
    A module to simulate active learning by flagging low-confidence
    items for human annotation.
    """

    def __init__(
        self,
        module_config: Dict[str, Any],
        model_registry_service: Optional[ModelRegistryService] = None,
        queue: AnnotationQueue = None,
    ):
        super().__init__(module_config, model_registry_service)
        self.confidence_threshold = 0.5
        self.queue = queue or AnnotationQueue()

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initializes the module with a configured confidence threshold.
        If a queue was not provided at construction, it will be created here.
        """
        self.confidence_threshold = config.get("confidence_threshold", 0.5)
        if not self.queue.conn:  # If default constructor was used
            db_path = config.get("db_path", "annotation_queue.db")
            self.queue = AnnotationQueue(db_path=db_path)
        print(
            f"ActiveLearningModule initialized with threshold: {self.confidence_threshold}"
        )

    def process(self, embedding: np.ndarray) -> np.ndarray:
        """
        Simulates a confidence score. If the score is below the threshold,
        it adds metadata to the annotation queue.
        """
        # In a real scenario, confidence would be derived from the model output.
        # Here, we simulate it with a random score.
        simulated_confidence = random.random()

        if simulated_confidence < self.confidence_threshold:
            # The 'embedding' is the data passed from the previous module.
            # We assume it contains or can be linked to the frame metadata.
            # For this simulation, we'll just log the embedding itself.
            metadata = {
                "reason": "low_confidence",
                "confidence_score": simulated_confidence,
                "embedding_preview": embedding[:4].tolist(),  # Store a small preview
            }
            item_id = self.queue.add_item(metadata)
            print(f"Flagged item for annotation with ID: {item_id}")

        # This module passes the embedding through to the next stage.
        return embedding

    def teardown(self) -> None:
        """
        No-op for this module.
        """
        print("ActiveLearningModule torn down.")
        pass
