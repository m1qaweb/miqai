import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import onnxruntime as ort

from video_ai_system.config import settings

logger = logging.getLogger(__name__)


class InferenceService:
    """
    A service to perform inference using a pre-trained ONNX model.
    """

    def __init__(self, model_path: str = None):
        """
        Initializes the InferenceService by loading the ONNX model.

        Args:
            model_path (str, optional): The path to the ONNX model file.
                                        If None, it uses the path from settings.
                                        Defaults to None.
        """
        if model_path is None:
            self.model_path = settings.model_path
        else:
            self.model_path = model_path

        if not Path(self.model_path).exists():
            logger.error(f"Model file not found at {self.model_path}")
            raise FileNotFoundError(f"Model file not found at {self.model_path}")

        logger.info(f"Loading model from {self.model_path}")
        try:
            # Load the ONNX model and create an inference session
            self.session = ort.InferenceSession(self.model_path)
            self.input_name = self.session.get_inputs()[0].name

            # Get all output names. We assume the first is detections and the second is embeddings.
            self.output_names = [o.name for o in self.session.get_outputs()]
            if len(self.output_names) < 2:
                raise RuntimeError(f"Model at {self.model_path} has fewer than 2 outputs. Cannot extract embeddings.")

            logger.info(f"Inference session created successfully. Using outputs: {self.output_names}")
            logger.info(f"Assuming '{self.output_names[0]}' is detections and '{self.output_names[1]}' is embeddings.")

        except Exception as e:
            logger.exception(f"Failed to load ONNX model: {e}")
            raise

    def run_inference_with_embedding(self, frames: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Runs inference on a batch of preprocessed frames and extracts embeddings.

        Args:
            frames (np.ndarray): A batch of frames, expected to be a NumPy array
                                 with shape (batch_size, channels, height, width).

        Returns:
            Tuple[np.ndarray, np.ndarray]: A tuple containing:
                - The raw detection output tensor.
                - The feature embedding tensor from an intermediate layer.
        """
        if not isinstance(frames, np.ndarray):
            logger.error(f"Input must be a NumPy array, but got {type(frames)}")
            raise TypeError("Input frames must be a NumPy array.")

        logger.info(f"Running inference on batch of {frames.shape[0]} frames with shape {frames.shape}")

        try:
            # Run inference requesting all outputs
            results = self.session.run(self.output_names, {self.input_name: frames})

            detections = results[0]
            embedding = results[1]

            # The embedding might be for the whole batch. Let's average it if it has a batch dimension.
            # For many models, the embedding output might be (batch_size, embedding_dim, H, W).
            # We can globally average pool it to get (batch_size, embedding_dim).
            if embedding.ndim > 2 and embedding.shape[0] == frames.shape[0]:
                embedding = np.mean(embedding, axis=(2, 3))

            logger.info(f"Inference successful. Detections shape: {detections.shape}, Embeddings shape: {embedding.shape}")

            return detections, embedding
        except Exception as e:
            logger.exception(f"An error occurred during inference: {e}")
            raise