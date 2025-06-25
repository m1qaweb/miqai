from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import RedisDsn, computed_field
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Manages application configuration using a layered approach.
    Values are loaded from environment variables, which can be populated
    by a .env file.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # --- Security ---
    # Path to the file containing the API key (e.g., a Docker secret)
    API_KEY_SECRET_FILE: Optional[str] = None

    @computed_field
    @property
    def api_key(self) -> Optional[str]:
        """
        Reads the API key from the secret file.
        Caches the result to avoid repeated file reads.
        """
        if not self.API_KEY_SECRET_FILE:
            return None
        try:
            with open(self.API_KEY_SECRET_FILE, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.error(f"API key secret file not found at: {self.API_KEY_SECRET_FILE}")
            return None

    # Redis DSN for ARQ task queue
    REDIS_DSN: RedisDsn = "redis://localhost:6379/0"

    # Path to the model registry directory
    MODEL_REGISTRY_PATH: str = "./models"

    # Default path to the pipeline configuration file
    PIPELINE_CONFIG_PATH: str = "config/development.json"

    # --- Preprocessing Service Configuration ---
    PREPROCESSING_HIST_THRESHOLD: float = 0.8
    PREPROCESSING_TARGET_WIDTH: int = 224
    PREPROCESSING_TARGET_HEIGHT: int = 224
    PREPROCESSING_CPU_THRESHOLD: int = 85
    PREPROCESSING_THROTTLE_DELAY: float = 0.5

    # --- Inference Service Configuration ---
    DEFAULT_MODEL_NAME: str = "yolov8n-coco"
    model_path: str = "models/yolov8n.onnx"

    # Qdrant settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "video_frames"
    EMBEDDING_DIMENSION: int = 512 # Example dimension for YOLOv8 feature map

    # --- Active Learning Service Configuration ---
    LOW_CONFIDENCE_THRESHOLD: float = 0.5

    # --- Drift Detection Service Configuration ---
    DRIFT_THRESHOLD: float = 0.1
    PCA_COMPONENTS: int = 10

# Create a single, importable instance of the settings
settings = Settings()