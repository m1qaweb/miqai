from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from video_ai_system.services.model_registry_service import ModelRegistryService


class VideoModule(ABC):
    """
    Abstract Base Class for all video processing modules.
    Defines the standard interface for module initialization, processing, and teardown.
    """

    def __init__(
        self,
        module_config: Dict[str, Any],
        model_registry_service: Optional[ModelRegistryService] = None,
    ):
        """
        Initializes the base module, setting up the model registry and loading a model if specified.

        Args:
            module_config (Dict[str, Any]): The configuration dictionary for the module.
            model_registry_service (Optional[ModelRegistryService]): The service for accessing registered models.
        """
        self.module_config = module_config
        self.model_registry_service = model_registry_service
        self.model_path: Optional[str] = None

        if self.model_registry_service and "model_loader" in self.module_config:
            model_loader_config = module_config["model_loader"]
            model_name = model_loader_config.get("model_name")
            model_version = model_loader_config.get("model_version")

            if model_name and model_version:
                self.model_path = self.model_registry_service.get_model_path(
                    model_name, model_version
                )

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initializes the module with its specific configuration.
        This method is called once when the application starts.
        Args:
            config (Dict[str, Any]): A dictionary containing configuration parameters
                                      for the module.
        """
        pass

    @abstractmethod
    def process(self, frame: Any) -> Any:
        """
        Processes a single video frame.
        Args:
            frame (Any): The video frame to be processed. The exact type will
                         depend on the video capture source (e.g., a NumPy array).
        Returns:
            Any: The processed frame or analysis results.
        """
        pass

    @abstractmethod
    def teardown(self) -> None:
        """
        Cleans up resources used by the module.
        This method is called once when the application shuts down.
        """
        pass
