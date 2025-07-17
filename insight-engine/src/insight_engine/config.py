from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import RedisDsn, computed_field, Field, BaseModel
from typing import Optional, Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Define the project's root directory relative to this config file
# config.py is in D:\miqai\insight-engine\src\insight_engine
# The project root is D:\miqai\insight-engine
PROJECT_ROOT = Path(__file__).parent.parent.parent

class PreprocessingSettings(BaseSettings):
    hist_threshold: float = 0.8
    target_width: int = 224
    target_height: int = 224
    cpu_threshold: int = 85
    throttle_delay: float = 0.5


class InferenceSettings(BaseSettings):
    default_model_name: str = "yolov8n.pt"
    # The model name will be used by the ultralytics library to
    # automatically download and manage the model.
    model_name: str = "yolov8n.pt"


class QdrantSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6333
    collection: str = "video_frames"
    embedding_dimension: int = 512
    api_key: Optional[str] = None

    @computed_field
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


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
    heuristic_policy: HeuristicPolicyConfig = Field(
        default_factory=HeuristicPolicyConfig
    )
    learned_policy: Optional[LearnedPolicyConfig] = None
    safety_guards: SafetyGuardsConfig = Field(default_factory=SafetyGuardsConfig)


class LoggingSettings(BaseModel):
    """Logging configuration settings."""
    level: str = "INFO"
    format: str = "structured"  # "structured" or "console"
    file: Optional[str] = None
    console: bool = True
    json_format: Optional[bool] = None  # Auto-detect based on environment
    max_file_size: str = "10MB"
    backup_count: int = 5
    
    # Logger-specific levels
    logger_levels: Dict[str, str] = Field(default_factory=lambda: {
        "uvicorn": "WARNING",
        "uvicorn.access": "WARNING", 
        "fastapi": "INFO",
        "httpx": "WARNING",
        "google": "WARNING",
        "urllib3": "WARNING",
        "insight_engine": "INFO",
    })


class SecuritySettings(BaseModel):
    """Security configuration settings."""
    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:3001"
    ])
    cors_credentials: bool = True
    cors_methods: list[str] = Field(default_factory=lambda: ["*"])
    cors_headers: list[str] = Field(default_factory=lambda: ["*"])
    
    # Rate limiting
    rate_limit_requests_per_minute: int = 100
    rate_limit_burst: int = 20
    
    # Security headers
    enable_security_headers: bool = True
    hsts_max_age: int = 31536000
    content_security_policy: str = "default-src 'self'"


class MonitoringSettings(BaseModel):
    """Monitoring and observability settings."""
    enable_metrics: bool = True
    metrics_path: str = "/metrics"
    health_check_path: str = "/health"
    
    # Performance monitoring
    enable_performance_logging: bool = True
    slow_query_threshold: float = 1.0  # seconds
    
    # External monitoring
    prometheus_url: Optional[str] = None
    grafana_url: Optional[str] = None


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
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        json_file="config/development.json",
        json_file_encoding="utf-8",
    )

    # --- Security ---
    SECRET_KEY: str  # IMPORTANT: Load from env var in production
    ALGORITHM: str = "HS256"
    VIDEO_AI_API_KEY: Optional[str] = None
    BRAVE_API_KEY: Optional[str] = None
    AZURE_OPENAI_KEY: Optional[str] = None
    GCP_PROJECT_ID: Optional[str] = None
    
    @computed_field
    @property
    def api_key(self) -> Optional[str]:
        if self.VIDEO_AI_API_KEY:
            return self.VIDEO_AI_API_KEY
        logger.warning("VIDEO_AI_API_KEY environment variable not set.")
        return None

    # Redis DSN for ARQ task queue
    REDIS_DSN: RedisDsn = Field(default=RedisDsn("redis://localhost:6379/0"))

    # --- Data and Model Paths ---
    MODEL_REGISTRY_PATH: str = "models/registry.json"

    # --- Service URLs ---
    VIDEO_AI_SYSTEM_URL: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None

    # --- Application Configuration ---
    ENVIRONMENT: str = Field(default="development", description="Application environment")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    
    # --- Service Configurations ---
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    preprocessing: PreprocessingSettings = Field(default_factory=PreprocessingSettings)
    inference: InferenceSettings = Field(default_factory=InferenceSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    active_learning: ActiveLearningSettings = Field(
        default_factory=ActiveLearningSettings
    )
    drift_detection: DriftDetectionSettings = Field(
        default_factory=DriftDetectionSettings
    )
    sampling: SamplingConfig = Field(default_factory=SamplingConfig)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    adaptation: AdaptationSettings = Field(default_factory=AdaptationSettings)

    # --- Pipeline Configuration ---
    PIPELINE_CONFIG_PATH: Optional[str] = None
    pipelines: Optional[Dict[str, Any]] = None

    # --- Shadow Testing ---
    LOKI_API_URL: Optional[str] = None
    PROMETHEUS_URL: str = "http://localhost:9090"


# Create a single, importable instance of the settings
settings = Settings()
