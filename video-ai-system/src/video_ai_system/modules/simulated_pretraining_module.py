import numpy as np
from typing import Any, Dict

from .module_interface import VideoModule

class SimulatedPretrainingModule(VideoModule):
    """
    A module to simulate the output of a self-supervised pretraining model.
    It takes a frame and returns a random embedding vector.
    """
    def __init__(self):
        self.embedding_dim = 512

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initializes the module with a configured embedding dimension.
        """
        self.embedding_dim = config.get("embedding_dim", 512)
        print(f"SimulatedPretrainingModule initialized with embedding_dim: {self.embedding_dim}")

    def process(self, frame: np.ndarray) -> np.ndarray:
        """
        Generates a random NumPy array to simulate a feature embedding.
        The input 'frame' is ignored in this simulation.
        """
        return np.random.rand(self.embedding_dim).astype(np.float32)

    def teardown(self) -> None:
        """
        No-op for this simple module.
        """
        print("SimulatedPretrainingModule torn down.")
        pass