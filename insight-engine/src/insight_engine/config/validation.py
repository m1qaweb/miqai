"""
Configuration validation and startup checks for the Insight Engine application.

This module provides comprehensive validation of configuration settings,
environment-specific validation, and startup health checks.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from pydantic import ValidationError

# Import will be done locally to avoid circular imports
from insight_engine.exceptions import ConfigurationException
from insight_engine.logging_config import get_logger

logger = get_logger(__name__)


class ConfigurationValidator:
    """
    Comprehensive configuration validator for application settings.
    
    Validates all configuration settings at startup and provides
    detailed error reporting for misconfigurations.
    """
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all configuration settings.
        
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        logger.info("Starting comprehensive configuration validation")
        
        # Reset validation state
        self.errors.clear()
        self.warnings.clear()
        
        # Run all validation checks
        self._validate_environment()
        self._validate_security_settings()
        self._validate_database_settings()
        self._validate_external_services()
        self._validate_logging_settings()
        self._validate_file_paths()
        self._validate_network_settings()
        self._validate_resource_limits()
        
        is_valid = len(self.errors) == 0
        
        if is_valid:
            logger.info("Configuration validation completed successfully")
        else:
            logger.error(f"Configuration validation failed with {len(self.errors)} errors")
        
        if self.warnings:
            logger.warning(f"Configuration validation completed with {len(self.warnings)} warnings")
        
        return is_valid, self.errors.copy(), self.warnings.copy()
    
    def _validate_environment(self) -> None:
        """Validate environment-specific settings."""
        from insight_engine.config import settings
        
        logger.debug("Validating environment settings")
        
        # Check environment value
        if settings.ENVIRONMENT not in ["development", "staging", "production"]:
            self.errors.append(
                f"Invalid environment '{settings.ENVIRONMENT}'. "
                "Must be one of: development, staging, production"
            )
        
        # Production-specific checks
        if settings.ENVIRONMENT == "production":
            if settings.DEBUG:
                self.errors.append("DEBUG mode must be disabled in production")
            
            if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
                self.errors.append(
                    "SECRET_KEY must be at least 32 characters long in production"
                )
            
            if settings.logging.level == "DEBUG":
                self.warnings.append(
                    "DEBUG log level is not recommended for production"
                )
        
        # Development-specific warnings
        if settings.ENVIRONMENT == "development":
            if not settings.DEBUG:
                self.warnings.append(
                    "DEBUG mode is recommended for development environment"
                )
    
    def _validate_security_settings(self) -> None:
        """Validate security-related settings."""
        from insight_engine.config import settings
        
        logger.debug("Validating security settings")
        
        # JWT settings
        if not settings.SECRET_KEY:
            self.errors.append("SECRET_KEY is required")
        elif len(settings.SECRET_KEY) < 16:
            self.errors.append("SECRET_KEY must be at least 16 characters long")
        
        if settings.ALGORITHM not in ["HS256", "HS384", "HS512", "RS256"]:
            self.errors.append(
                f"Invalid JWT algorithm '{settings.ALGORITHM}'. "
                "Must be one of: HS256, HS384, HS512, RS256"
            )
        
        # CORS settings
        if not settings.security.cors_origins:
            self.warnings.append("No CORS origins configured")
        else:
            for origin in settings.security.cors_origins:
                if not self._is_valid_url(origin) and origin != "*":
                    self.errors.append(f"Invalid CORS origin: {origin}")
        
        # Rate limiting
        if settings.security.rate_limit_requests_per_minute <= 0:
            self.errors.append("Rate limit must be greater than 0")
        elif settings.security.rate_limit_requests_per_minute > 10000:
            self.warnings.append(
                "Very high rate limit may impact performance"
            )
    
    def _validate_database_settings(self) -> None:
        """Validate database and storage settings."""
        from insight_engine.config import settings
        
        logger.debug("Validating database settings")
        
        # Redis settings
        try:
            redis_url = str(settings.REDIS_DSN)
            parsed = urlparse(redis_url)
            if not parsed.hostname:
                self.errors.append("Invalid Redis DSN: missing hostname")
            if parsed.port and (parsed.port < 1 or parsed.port > 65535):
                self.errors.append(f"Invalid Redis port: {parsed.port}")
        except Exception as e:
            self.errors.append(f"Invalid Redis DSN: {e}")
        
        # Qdrant settings
        if not settings.qdrant.host:
            self.errors.append("Qdrant host is required")
        
        if settings.qdrant.port < 1 or settings.qdrant.port > 65535:
            self.errors.append(f"Invalid Qdrant port: {settings.qdrant.port}")
        
        if settings.qdrant.embedding_dimension <= 0:
            self.errors.append("Qdrant embedding dimension must be positive")
        elif settings.qdrant.embedding_dimension > 4096:
            self.warnings.append(
                "Very high embedding dimension may impact performance"
            )
    
    def _validate_external_services(self) -> None:
        """Validate external service configurations."""
        from insight_engine.config import settings
        
        logger.debug("Validating external service settings")
        
        # Google Cloud settings
        if settings.GCP_PROJECT_ID and not settings.GCP_PROJECT_ID.strip():
            self.errors.append("GCP_PROJECT_ID cannot be empty if provided")
        
        # API keys validation (check if they exist when required)
        if settings.ENVIRONMENT == "production":
            if not settings.VIDEO_AI_API_KEY:
                self.warnings.append(
                    "VIDEO_AI_API_KEY not configured for production"
                )
            
            if not settings.BRAVE_API_KEY:
                self.warnings.append(
                    "BRAVE_API_KEY not configured for production"
                )
    
    def _validate_logging_settings(self) -> None:
        """Validate logging configuration."""
        from insight_engine.config import settings
        
        logger.debug("Validating logging settings")
        
        # Log level validation
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if settings.logging.level not in valid_levels:
            self.errors.append(
                f"Invalid log level '{settings.logging.level}'. "
                f"Must be one of: {', '.join(valid_levels)}"
            )
        
        # Log file validation
        if settings.logging.file:
            log_path = Path(settings.logging.file)
            try:
                # Check if parent directory exists or can be created
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Check write permissions
                if log_path.exists() and not os.access(log_path, os.W_OK):
                    self.errors.append(f"No write permission for log file: {log_path}")
                elif not os.access(log_path.parent, os.W_OK):
                    self.errors.append(f"No write permission for log directory: {log_path.parent}")
            except Exception as e:
                self.errors.append(f"Invalid log file path: {e}")
        
        # Logger levels validation
        for logger_name, level in settings.logging.logger_levels.items():
            if level not in valid_levels:
                self.errors.append(
                    f"Invalid log level '{level}' for logger '{logger_name}'"
                )
    
    def _validate_file_paths(self) -> None:
        """Validate file paths and directories."""
        from insight_engine.config import settings
        
        logger.debug("Validating file paths")
        
        # Model registry path
        if settings.MODEL_REGISTRY_PATH:
            registry_path = Path(settings.MODEL_REGISTRY_PATH)
            try:
                registry_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.errors.append(f"Cannot create model registry directory: {e}")
        
        # Pipeline config path
        if settings.PIPELINE_CONFIG_PATH:
            config_path = Path(settings.PIPELINE_CONFIG_PATH)
            if not config_path.exists():
                self.warnings.append(f"Pipeline config file not found: {config_path}")
        
        # Audit log path
        audit_path = Path(settings.audit.log_file_path)
        try:
            audit_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.errors.append(f"Cannot create audit log directory: {e}")
    
    def _validate_network_settings(self) -> None:
        """Validate network-related settings."""
        from insight_engine.config import settings
        
        logger.debug("Validating network settings")
        
        # Service URLs validation
        urls_to_check = [
            ("VIDEO_AI_SYSTEM_URL", settings.VIDEO_AI_SYSTEM_URL),
            ("AZURE_OPENAI_ENDPOINT", settings.AZURE_OPENAI_ENDPOINT),
            ("LOKI_API_URL", settings.LOKI_API_URL),
            ("PROMETHEUS_URL", settings.PROMETHEUS_URL),
        ]
        
        for name, url in urls_to_check:
            if url and not self._is_valid_url(url):
                self.errors.append(f"Invalid URL for {name}: {url}")
    
    def _validate_resource_limits(self) -> None:
        """Validate resource limits and thresholds."""
        from insight_engine.config import settings
        
        logger.debug("Validating resource limits")
        
        # Preprocessing settings
        if settings.preprocessing.cpu_threshold < 10 or settings.preprocessing.cpu_threshold > 100:
            self.errors.append(
                f"CPU threshold must be between 10 and 100, got: {settings.preprocessing.cpu_threshold}"
            )
        
        if settings.preprocessing.throttle_delay < 0:
            self.errors.append("Throttle delay cannot be negative")
        elif settings.preprocessing.throttle_delay > 10:
            self.warnings.append("Very high throttle delay may impact performance")
        
        # Active learning settings
        if not (0 < settings.active_learning.low_confidence_threshold < 1):
            self.errors.append(
                "Low confidence threshold must be between 0 and 1"
            )
        
        # Drift detection settings
        if not (0 < settings.drift_detection.drift_threshold < 1):
            self.errors.append(
                "Drift threshold must be between 0 and 1"
            )
        
        if settings.drift_detection.pca_components <= 0:
            self.errors.append("PCA components must be positive")
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if a URL is valid."""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False


def validate_configuration_at_startup() -> None:
    """
    Validate configuration at application startup.
    
    Raises:
        ConfigurationException: If critical configuration errors are found
    """
    from insight_engine.config import settings
    
    validator = ConfigurationValidator()
    is_valid, errors, warnings = validator.validate_all()
    
    # Log warnings
    for warning in warnings:
        logger.warning(f"Configuration warning: {warning}")
    
    # Handle errors
    if not is_valid:
        error_message = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
        logger.error(error_message)
        raise ConfigurationException(
            message="Critical configuration errors detected",
            details={
                "errors": errors,
                "warnings": warnings,
                "environment": settings.ENVIRONMENT
            }
        )
    
    logger.info("Configuration validation completed successfully")


def get_configuration_summary() -> Dict[str, Any]:
    """
    Get a summary of current configuration for debugging.
    
    Returns:
        Dictionary with configuration summary (sensitive values masked)
    """
    from insight_engine.config import settings
    
    return {
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "logging": {
            "level": settings.logging.level,
            "format": settings.logging.format,
            "file": settings.logging.file,
            "console": settings.logging.console,
        },
        "security": {
            "cors_origins": settings.security.cors_origins,
            "rate_limit": settings.security.rate_limit_requests_per_minute,
            "security_headers": settings.security.enable_security_headers,
        },
        "database": {
            "redis_host": str(settings.REDIS_DSN).split("@")[-1] if "@" in str(settings.REDIS_DSN) else str(settings.REDIS_DSN),
            "qdrant_host": settings.qdrant.host,
            "qdrant_port": settings.qdrant.port,
        },
        "monitoring": {
            "enable_metrics": settings.monitoring.enable_metrics,
            "prometheus_url": settings.PROMETHEUS_URL,
        },
        "services": {
            "gcp_project": settings.GCP_PROJECT_ID,
            "video_ai_configured": bool(settings.VIDEO_AI_API_KEY),
            "brave_api_configured": bool(settings.BRAVE_API_KEY),
        }
    }


def check_required_environment_variables() -> List[str]:
    """
    Check for required environment variables.
    
    Returns:
        List of missing required environment variables
    """
    from insight_engine.config import settings
    
    required_vars = ["SECRET_KEY"]
    
    if settings.ENVIRONMENT == "production":
        required_vars.extend([
            "GOOGLE_CLOUD_PROJECT",
            "REDIS_DSN",
        ])
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    return missing_vars


def validate_external_service_connectivity() -> Dict[str, bool]:
    """
    Validate connectivity to external services.
    
    Returns:
        Dictionary with service connectivity status
    """
    connectivity_status = {}
    
    # This would contain actual connectivity checks
    # For now, we'll return a placeholder
    services = ["redis", "qdrant", "google_cloud", "prometheus"]
    
    for service in services:
        # TODO: Implement actual connectivity checks
        connectivity_status[service] = True
    
    return connectivity_status