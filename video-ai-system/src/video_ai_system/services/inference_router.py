import logging
from typing import Dict
import redis.asyncio as redis
from video_ai_system.services.model_registry_service import ModelRegistryService
from video_ai_system.services.inference_service import InferenceService

logger = logging.getLogger(__name__)

class InferenceRouter:
    """
    Manages the active inference model based on system state, controlled
    by the AdaptationController.
    """

    def __init__(
        self,
        model_mapping: Dict[str, str],
        redis_client: redis.Redis,
        model_registry_service: ModelRegistryService,
        inference_service: InferenceService,
    ):
        self.model_mapping = model_mapping
        self.redis_client = redis_client
        self.model_registry = model_registry_service
        self.inference_service = inference_service
        self._current_model_name = None

    async def initialize(self, default_level: str = "NORMAL"):
        """
        Initializes the router by loading the default model.
        """
        initial_model = self.model_mapping.get(default_level)
        if initial_model:
            await self.set_active_model(initial_model)
        else:
            logger.error("Default model for NORMAL level not found in mapping. Router not initialized.")

    def get_current_model_name(self) -> str:
        """Returns the identifier of the currently active model."""
        return self._current_model_name

    async def set_active_model(self, model_name: str):
        """
        Switches the active model in the underlying InferenceService.
        
        :param model_name: The name of the model to activate (e.g., 'yolov8n-light').
        """
        if self._current_model_name == model_name:
            logger.debug(f"Model '{model_name}' is already active.")
            return

        model_info = self.model_registry.get_production_model(model_name)
        if not model_info:
            logger.error(f"Model '{model_name}' not found in the registry. Cannot switch.")
            return

        try:
            self.inference_service.load_model(model_info["path"])
            self._current_model_name = model_name
            logger.info(f"Successfully switched active model to: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load model '{model_name}' from path '{model_info['path']}': {e}")
