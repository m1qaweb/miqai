from abc import ABC, abstractmethod
from typing import Any, Dict

class VideoModule(ABC):
    """
    Abstract Base Class for all video processing modules.
    Defines the standard interface for module initialization, processing, and teardown.
    """

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