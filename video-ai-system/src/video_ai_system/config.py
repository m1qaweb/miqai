from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import RedisDsn, computed_field
from typing import Optional, Dict
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Manages application configuration using a layered approach.
    Values are loaded from environment variables, which can be populated
    by a .env file. It also loads a JSON configuration file.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # --- Security ---
    API_KEY_SECRET_FILE: Optional[str] = None

    @computed_field
    @property
    def api_key(self) -> Optional[str]:
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

    # --- Data and Model Paths ---
    MODEL_REGISTRY_PATH: str = "models"
    model_registry_path: Optional[str] = None
    PIPELINE_CONFIG_PATH: str = "config/development.json"

    # --- Preprocessing Service Configuration ---
    PREPROCESSING_HIST_THRESHOLD: float = 0.8
    PREPROCESSING_TARGET_WIDTH: int = 224
    PREPROCESSING_TARGET_HEIGHT: int = 224
    PREPROCESSING_CPU_THRESHOLD: int = 85
    PREPROCESSING_THROTTLE_DELAY: float = 0.5

    # --- Inference Service Configuration ---
    DEFAULT_MODEL_NAME: str = "yolov8n-coco"
    MODEL_PATH: str = "models/yolov8n.onnx"

    # Qdrant settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "video_frames"
    EMBEDDING_DIMENSION: int = 512

    # --- Active Learning Service Configuration ---
    LOW_CONFIDENCE_THRESHOLD: float = 0.5

    # --- Drift Detection Service Configuration ---
    DRIFT_THRESHOLD: float = 0.1
    PCA_COMPONENTS: int = 10

    # --- Pipeline Configuration ---
    pipelines: Optional[Dict] = None

    # --- Shadow Testing ---
    LOKI_API_URL: Optional[str] = None

    def __init__(self, **values):
        super().__init__(**values)
        self._load_json_config()
        if self.model_registry_path:
            self.MODEL_REGISTRY_PATH = self.model_registry_path

    def _load_json_config(self):
        """Loads settings from a JSON file and merges them."""
        config_path = Path(self.PIPELINE_CONFIG_PATH)
        if config_path.is_file():
            logger.info(f"Loading configuration from {config_path}")
            with open(config_path) as f:
                config_data = json.load(f)
                for key, value in config_data.items():
                    setattr(self, key, value)
        else:
            logger.warning(f"JSON configuration file not found at {config_path}")

# Create a single, importable instance of the settings
settings = Settings()