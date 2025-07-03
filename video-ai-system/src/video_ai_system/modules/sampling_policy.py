import abc
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np
import onnxruntime

# A placeholder for a more sophisticated logging setup
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SamplingPolicy(abc.ABC):
    """
    Abstract base class for all sampling policies.
    Defines the interface for deciding whether a frame should be processed.
    """

    @abc.abstractmethod
    def should_process(self, features: Dict[str, Any]) -> bool:
        """
        Determines if the current frame should be processed based on input features.

        Args:
            features: A dictionary containing features for the current frame,
                      such as 'timestamp', 'motion_vectors', etc.

        Returns:
            True if the frame should be processed, False otherwise.
        """
        raise NotImplementedError


class FixedRateSamplingPolicy(SamplingPolicy):
    """
    A simple policy that samples frames at a fixed rate (frames per second).
    """
    def __init__(self, rate_fps: int):
        if rate_fps <= 0:
            raise ValueError("rate_fps must be positive.")
        self.interval_seconds = 1.0 / rate_fps
        self.last_processed_time = -1.0
        logger.info(f"Initialized FixedRateSamplingPolicy with rate: {rate_fps} FPS (interval: {self.interval_seconds:.2f}s)")

    def should_process(self, features: Dict[str, Any]) -> bool:
        """
        Processes the frame if enough time has passed since the last processed frame.

        Args:
            features: Expects a 'timestamp' key with the current frame's timestamp.
        """
        current_time = features.get("timestamp")
        if current_time is None:
            logger.warning("Timestamp not found in features. Defaulting to processing frame.")
            return True

        if self.last_processed_time < 0 or (current_time - self.last_processed_time) >= self.interval_seconds:
            self.last_processed_time = current_time
            return True
        return False


class HeuristicSamplingPolicy(SamplingPolicy):
    """
    A policy that samples frames based on a simple heuristic, like motion detection.
    This serves as a baseline content-aware policy.
    """
    def __init__(self, motion_threshold: float = 0.1):
        if motion_threshold <= 0:
            raise ValueError("motion_threshold must be positive.")
        self.motion_threshold = motion_threshold
        logger.info(f"Initialized HeuristicSamplingPolicy with motion threshold: {self.motion_threshold}")

    def should_process(self, features: Dict[str, Any]) -> bool:
        """
        Processes the frame if motion magnitude exceeds a threshold.

        Args:
            features: Expects a 'motion_magnitude' key with a float value.
        """
        motion_magnitude = features.get("motion_magnitude", 0.0)
        if motion_magnitude > self.motion_threshold:
            logger.debug(f"Motion ({motion_magnitude:.2f}) exceeded threshold ({self.motion_threshold}). Processing frame.")
            return True
        return False


class LearnedSamplingPolicy(SamplingPolicy):
    """
    An intelligent policy that uses a lightweight ML model to decide on frame processing.
    Implements a tiered analysis to balance performance and accuracy.

    Design Reference: learned_sampling_design.md
    Assumption: A3.1 - Lightweight models can meet performance budget.
    """
    def __init__(
        self,
        policy_model_path: str,
        feature_extractor_model_path: str,
        motion_threshold: float = 0.1,
        time_threshold_seconds: float = 2.0
    ):
        logger.info("Initializing LearnedSamplingPolicy...")
        self.policy_session = self._load_model(policy_model_path)
        self.feature_extractor_session = self._load_model(feature_extractor_model_path)
        self.motion_threshold = motion_threshold
        self.time_threshold_seconds = time_threshold_seconds
        self.last_processed_embedding = None
        self.last_processed_time = -1.0

        self._warm_up_models()
        logger.info("LearnedSamplingPolicy initialized and models warmed up.")

    def _load_model(self, model_path: str) -> onnxruntime.InferenceSession:
        """Loads an ONNX model and returns an inference session."""
        path = Path(model_path)
        if not path.is_file():
            logger.error(f"Model file not found at path: {model_path}")
            raise FileNotFoundError(f"Learned policy model not found: {model_path}")
        
        # For now, we assume CPU execution. This can be configured later.
        providers = ['CPUExecutionProvider']
        return onnxruntime.InferenceSession(str(path), providers=providers)

    def _warm_up_models(self):
        """Performs a dummy inference call to warm up the models."""
        try:
            # Warm up feature extractor
            input_name = self.feature_extractor_session.get_inputs()[0].name
            input_shape = self.feature_extractor_session.get_inputs()[0].shape
            dummy_input = np.random.rand(*[1 if s == 'N' or not isinstance(s, int) else s for s in input_shape]).astype(np.float32)
            self.feature_extractor_session.run(None, {input_name: dummy_input})

            # Warm up policy model
            input_name = self.policy_session.get_inputs()[0].name
            input_shape = self.policy_session.get_inputs()[0].shape
            dummy_input = np.random.rand(*[1 if s == 'N' or not isinstance(s, int) else s for s in input_shape]).astype(np.float32)
            self.policy_session.run(None, {input_name: dummy_input})
        except Exception as e:
            logger.error(f"Error during model warm-up: {e}", exc_info=True)
            # Depending on policy, we might want to raise this
            raise

    def _has_significant_motion(self, features: Dict[str, Any]) -> bool:
        """Tier 1 Check: Analyzes motion vectors."""
        # Placeholder for actual motion vector analysis
        motion_magnitude = features.get("motion_magnitude", 0.0)
        return motion_magnitude > self.motion_threshold

    def _has_significant_semantic_change(self, features: Dict[str, Any]) -> bool:
        """Tier 2 Check: Runs feature extractor and policy model."""
        # This is the expensive path
        current_frame = features.get("frame_data")
        if current_frame is None:
            return False # Cannot process without frame data

        # 1. Extract embedding for the current frame
        extractor_input_name = self.feature_extractor_session.get_inputs()[0].name
        current_embedding = self.feature_extractor_session.run(None, {extractor_input_name: current_frame})[0]

        if self.last_processed_embedding is None:
            self.last_processed_embedding = current_embedding
            return True # Always process the first frame with an embedding

        # 2. Calculate difference and prepare policy model input
        embedding_diff = current_embedding - self.last_processed_embedding
        time_since_last = features.get("timestamp", 0) - self.last_processed_time
        
        # The exact shape and composition of the input depends on the trained model
        policy_input = np.concatenate([embedding_diff.flatten(), [time_since_last]]).astype(np.float32)
        policy_input = np.expand_dims(policy_input, axis=0) # Add batch dimension

        # 3. Run the policy model
        policy_input_name = self.policy_session.get_inputs()[0].name
        decision_logit = self.policy_session.run(None, {policy_input_name: policy_input})[0]
        
        # Assuming output is a single logit, apply sigmoid
        decision_prob = 1 / (1 + np.exp(-decision_logit))

        if decision_prob > 0.5:
            self.last_processed_embedding = current_embedding
            return True
        
        return False

    def should_process(self, features: Dict[str, Any]) -> bool:
        """
        Applies the tiered analysis to decide if a frame should be processed.
        """
        current_time = features.get("timestamp")
        if current_time is None:
            logger.warning("Timestamp not found in features. Defaulting to processing frame.")
            return True

        # Tier 1: Check for significant motion (cheap)
        if self._has_significant_motion(features):
            self.last_processed_time = current_time
            # In a pure tiered system, we might not update the embedding here
            # For simplicity now, we assume this implies a semantic change is likely
            self.last_processed_embedding = None # Invalidate to force re-compute on next semantic check
            return True

        # Tier 2: If no motion, check if enough time has passed to warrant a semantic check (expensive)
        if self.last_processed_time < 0 or (current_time - self.last_processed_time) >= self.time_threshold_seconds:
            if self._has_significant_semantic_change(features):
                self.last_processed_time = current_time
                return True

        return False