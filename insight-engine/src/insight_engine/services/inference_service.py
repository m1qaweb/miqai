import logging
from typing import List, Dict, Any
import numpy as np
from ultralytics import YOLO
from insight_engine.config import settings

logger = logging.getLogger(__name__)

class InferenceService:
    """
    A service to perform inference using the official ultralytics library.
    This service automatically downloads and caches the specified model.
    """

    def __init__(self):
        """
        Initializes the InferenceService by loading the specified model
        using the ultralytics.YOLO class.
        """
        self.model_name = settings.inference.model_name
        logger.info(f"Loading model '{self.model_name}' using ultralytics.YOLO.")
        try:
            # YOLO() will automatically download the model if it's not cached.
            self.model = YOLO(self.model_name)
            logger.info(f"Model '{self.model_name}' loaded successfully.")
        except Exception as e:
            logger.exception(f"Failed to load model with ultralytics.YOLO: {e}")
            raise

    def run_inference(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs inference on a single frame.

        Args:
            frame: A single frame represented as a NumPy array (in BGR format).

        Returns:
            A list of detection dictionaries, where each dictionary contains
            'box', 'label', and 'score'.
        """
        if not isinstance(frame, np.ndarray):
            logger.error(f"Input must be a NumPy array, but got {type(frame)}")
            raise TypeError("Input frame must be a NumPy array.")

        try:
            # The ultralytics library returns a list of Results objects.
            results = self.model(frame, verbose=False)

            # Process the first result object.
            result = results[0]
            boxes = result.boxes
            
            detections = []
            for box in boxes:
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                class_id = int(box.cls[0])
                label = self.model.names[class_id]
                
                detections.append({
                    "box": xyxy,
                    "score": conf,
                    "label": label,
                })

            return detections
        except Exception as e:
            logger.exception(f"An error occurred during inference: {e}")
            raise
