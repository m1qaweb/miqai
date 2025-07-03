from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import RedisDsn, computed_field, Field, BaseModel
from typing import Optional, Dict, Any
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class PreprocessingSettings(BaseSettings):
    hist_threshold: float = 0.8
    target_width: int = 224
    target_height: int = 224
    cpu_threshold: int = 85
    throttle_delay: float = 0.5

class InferenceSettings(BaseSettings):
    default_model_name: str = "yolov8n-coco"
    model_path: str = "models/yolov8n.onnx"

class QdrantSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6333
    collection: str = "video_frames"
    embedding_dimension: int = 512

class ActiveLearningSettings(BaseSettings):
    low_confidence_threshold: float = 0.5

class DriftDetectionSettings(BaseSettings):
    drift_threshold: float = 0.1
    pca_components: int = 10

class HeuristicPolicyConfig(BaseModel):
    rate_fps: int = 1

class LearnedPolicyConfig(BaseModel):
    model_path: str
    feature_extractor_model_path: str

class SafetyGuardsConfig(BaseModel):
    enabled: bool = True
    latency_threshold_ms: float = 5.0
    accuracy_drop_threshold: float = 0.10
    monitoring_window_seconds: int = 60
    cooldown_period_minutes: int = 10

class SamplingConfig(BaseModel):
    policy: str = "heuristic"
    heuristic_policy: HeuristicPolicyConfig = Field(default_factory=HeuristicPolicyConfig)
    learned_policy: Optional[LearnedPolicyConfig] = None
    safety_guards: SafetyGuardsConfig = Field(default_factory=SafetyGuardsConfig)

class AuditSettings(BaseModel):
    log_file_path: str = "logs/audit.log"

class AdaptationSettings(BaseModel):
    poll_interval_seconds: int = 10
    cooldown_seconds: int = 300

class Settings(BaseSettings):
    """
    Manages application configuration using a layered approach.
    Values are loaded from environment variables, a .env file, and a JSON config file.
    """
    model_config = SettingsConfigDict(
        env_file='.env', 
        env_file_encoding='utf-8', 
        extra='ignore',
        json_file="config/development.json",
        json_file_encoding="utf-8"
    )

    # --- Security ---
    API_KEY_SECRET_FILE: str = "video-ai-system/secrets/api_key.txt"

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
    MODEL_REGISTRY_PATH: str = "models/registry.json"

    # --- Service Configurations ---
    preprocessing: PreprocessingSettings = Field(default_factory=PreprocessingSettings)
    inference: InferenceSettings = Field(default_factory=InferenceSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    active_learning: ActiveLearningSettings = Field(default_factory=ActiveLearningSettings)
    drift_detection: DriftDetectionSettings = Field(default_factory=DriftDetectionSettings)
    sampling: SamplingConfig = Field(default_factory=SamplingConfig)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    adaptation: AdaptationSettings = Field(default_factory=AdaptationSettings)
    
    # --- Pipeline Configuration ---
    pipelines: Optional[Dict[str, Any]] = None

    # --- Shadow Testing ---
    LOKI_API_URL: Optional[str] = None
    PROMETHEUS_URL: str = "http://localhost:9090"

# Create a single, importable instance of the settings
settings = Settings()