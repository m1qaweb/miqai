"""
A service for making dynamic decisions about model selection,
pipeline configuration, and other adaptive behaviors.
"""

import logging
from typing import Dict, Any, List
from insight_engine.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class DecisionEngineService:
    """
    The DecisionEngineService is responsible for selecting the best model
    for a given task based on real-time metrics and predefined rules.
    """

    def __init__(self, metrics_service: MetricsService, rules: Dict[str, Any] = None):
        """
        Initializes the DecisionEngineService.

        Args:
            metrics_service: An instance of MetricsService to fetch performance data.
            rules: A dictionary of rules to guide decision-making.
        """
        self.metrics_service = metrics_service
        self.rules = rules or self._load_default_rules()
        logger.info("Decision Engine Service initialized.")

    def _load_default_rules(self) -> Dict[str, Any]:
        """Loads a default set of rules."""
        return {
            "default_model": "yolov8n-light",
            "task_model_mapping": {
                "object_detection": ["yolov8n-coco", "yolov8n-light"],
                "summarization": ["gemini-pro"],
            },
            "performance_thresholds": {
                "max_latency_ms": 200,
            },
        }

    def select_model(self, task_description: str) -> str:
        """
        Selects the best model for a given task based on performance metrics.

        This logic now queries the MetricsService to find the best-performing
        model from a list of candidates that is still within performance thresholds.

        Args:
            task_description: A string describing the task (e.g., "object_detection").

        Returns:
            The name of the selected model.
        """
        logger.info(f"Selecting model for task: {task_description}")

        candidate_models: List[str] = self.rules["task_model_mapping"].get(
            task_description, [self.rules["default_model"]]
        )
        
        if not candidate_models:
            logger.warning(f"No candidate models found for task '{task_description}'. Returning default.")
            return self.rules["default_model"]

        best_model = None
        lowest_latency = float("inf")
        max_latency_threshold = self.rules["performance_thresholds"]["max_latency_ms"]

        for model_name in candidate_models:
            latency = self.metrics_service.get_model_latency(model_name)
            if latency < lowest_latency and latency <= max_latency_threshold:
                lowest_latency = latency
                best_model = model_name
        
        if best_model:
            logger.info(f"Selected model '{best_model}' with latency {lowest_latency:.2f} ms.")
            return best_model
        else:
            logger.warning(
                f"No candidate models for task '{task_description}' met the performance threshold of {max_latency_threshold} ms. "
                f"Falling back to default model '{self.rules['default_model']}'."
            )
            return self.rules["default_model"]
