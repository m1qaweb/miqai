import asyncio
from typing import Dict, Any

from video_ai_system.modules.module_interface import VideoModule
from video_ai_system.services.model_registry_service import ModelRegistryService
from video_ai_system.services.shadow_testing_service import ShadowTestingService
from video_ai_system.services.inference_router import InferenceRouter


class ShadowingModule(VideoModule):
    """
    A pipeline module that triggers a shadow test for a candidate model.
    """

    def __init__(
        self,
        module_config: Dict[str, Any],
        model_registry_service: ModelRegistryService,
        shadow_testing_service: ShadowTestingService,
        inference_router: InferenceRouter,
    ):
        super().__init__(module_config)
        self.model_registry_service = model_registry_service
        self.shadow_testing_service = shadow_testing_service
        self.inference_router = inference_router  # For future use in canary routing

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives data from the previous module, checks for a shadow model,
        and triggers the shadow test in the background.

        :param data: The data dictionary from the previous module.
                     Expected to contain 'video_id', 'video_path',
                     'model_id', 'results', and 'latency'.
        :return: The original data, passed through unmodified.
        """
        prod_model_id = data.get("model_id")
        if not prod_model_id:
            # Cannot run shadow test without knowing the production model
            return data

        shadow_model_id = self.model_registry_service.get_shadow_model(prod_model_id)

        if shadow_model_id:
            # Run the shadow test in a non-blocking background task
            asyncio.create_task(
                self.shadow_testing_service.compare_and_log(
                    video_id=data["video_id"],
                    production_model_id=prod_model_id,
                    candidate_model_id=shadow_model_id,
                    production_results=data["results"],
                    production_latency=data["latency"],
                    video_path=data["video_path"],
                )
            )

        return data

    def initialize(self, module_params: Dict[str, Any]):
        """Initializes the module."""
        # No specific initialization needed for this module
        pass

    def teardown(self):
        """Cleans up resources."""
        # No resources to clean up
        pass
