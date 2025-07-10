import cv2
from pathlib import Path
from typing import Any, Dict, Generator, Optional
from insight_engine.services.model_registry_service import ModelRegistryService


from .module_interface import VideoModule


class DataCollectionModule(VideoModule):
    """
    A module to read video files, apply privacy protection, and yield frames.
    """

    def __init__(
        self,
        module_config: Dict[str, Any],
        model_registry_service: Optional[ModelRegistryService] = None,
    ):
        super().__init__(module_config, model_registry_service)
        self.video_path = None

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initializes the module with the path to the video source.
        """
        self.video_path = Path(config.get("video_source_path"))
        if not self.video_path or not self.video_path.is_file():
            raise FileNotFoundError(f"Video source not found at: {self.video_path}")
        print(f"DataCollectionModule initialized for video: {self.video_path}")

    def _apply_privacy_protection(self, frame: Any) -> Any:
        """
        Placeholder for applying privacy protection like face/text blurring.
        """
        # In a future implementation, this would contain logic to detect and
        # blur sensitive information. For now, it's a no-op.
        return frame

    def process(self, frame_data: Any = None) -> Generator[Any, None, None]:
        """
        Opens the configured video file and yields each processed frame.
        The 'frame_data' argument is ignored as the path is set during initialization.
        """
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise IOError(f"Could not open video file: {self.video_path}")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                processed_frame = self._apply_privacy_protection(frame)
                yield processed_frame
        finally:
            cap.release()
            print("Video processing complete. Resources released.")

    def teardown(self) -> None:
        """
        No-op for this module as resources are released in process().
        """
        print("DataCollectionModule torn down.")
        pass
