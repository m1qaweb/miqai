import logging
from typing import Dict
import redis.asyncio as redis
from insight_engine.services.model_registry_service import ModelRegistryService
from insight_engine.services.inference_service import InferenceService
from insight_engine.services.decision_engine_service import DecisionEngineService

logger = logging.getLogger(__name__)


class InferenceRouter:
    """
    Manages the active inference model based on system state, controlled
    by the DecisionEngineService.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        model_registry_service: ModelRegistryService,
        inference_service: InferenceService,
        decision_engine_service: DecisionEngineService,
    ):
        self.redis_client = redis_client
        self.model_registry = model_registry_service
        self.inference_service = inference_service
        self.decision_engine = decision_engine_service
        self._current_model_name = None

    def get_current_model_name(self) -> str:
        """Returns the identifier of the currently active model."""
        return self._current_model_name

    async def update_active_model_for_task(self, task_description: str):
        """
        Selects and switches the active model based on the task description.

        Args:
            task_description: A string describing the task (e.g., "object_detection").
        """
        model_name = self.decision_engine.select_model(task_description)

        if self._current_model_name == model_name:
            logger.debug(f"Model '{model_name}' is already active.")
            return

        model_info = self.model_registry.get_production_model(model_name)
        if not model_info:
            logger.error(
                f"Model '{model_name}' not found in the registry. Cannot switch."
            )
            return

        try:
            self.inference_service.load_model(model_info["path"])
            self._current_model_name = model_name
            logger.info(f"Successfully switched active model to: {model_name}")
        except Exception as e:
            logger.error(
                f"Failed to load model '{model_name}' from path '{model_info['path']}': {e}"
            )
