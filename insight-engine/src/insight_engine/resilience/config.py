"""Configuration for resilience patterns across different services."""

from typing import Dict, Optional
from dataclasses import dataclass

from .circuit_breaker import CircuitBreakerConfig
from .retry import RetryConfig
from .timeout import TimeoutConfig


@dataclass
class ResilienceConfig:
    """Combined configuration for all resilience patterns."""
    circuit_breaker: CircuitBreakerConfig
    retry: RetryConfig
    timeout: TimeoutConfig


class ResilienceConfigManager:
    """Manages resilience configurations for different service types."""
    
    def __init__(self):
        self._configs: Dict[str, ResilienceConfig] = {}
        self._setup_default_configs()
    
    def _setup_default_configs(self):
        """Setup default configurations for different service types."""
        
        # HTTP API services (Brave Search, Video AI, etc.)
        self._configs["http_api"] = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=30.0,
                success_threshold=3,
                timeout_window=60.0
            ),
            retry=RetryConfig(
                max_attempts=3,
                base_delay=1.0,
                max_delay=30.0,
                exponential_base=2.0,
                jitter=True
            ),
            timeout=TimeoutConfig(
                connect_timeout=10.0,
                read_timeout=30.0,
                total_timeout=45.0
            )
        )
        
        # Google Cloud services
        self._configs["gcp"] = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=60.0,
                success_threshold=2,
                timeout_window=120.0
            ),
            retry=RetryConfig(
                max_attempts=5,
                base_delay=2.0,
                max_delay=60.0,
                exponential_base=2.0,
                jitter=True
            ),
            timeout=TimeoutConfig(
                connect_timeout=15.0,
                read_timeout=300.0,  # GCP operations can take longer
                total_timeout=600.0
            )
        )
        
        # Background tasks and workers
        self._configs["background_task"] = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=10,
                recovery_timeout=120.0,
                success_threshold=5,
                timeout_window=300.0
            ),
            retry=RetryConfig(
                max_attempts=5,
                base_delay=5.0,
                max_delay=300.0,
                exponential_base=2.0,
                jitter=True
            ),
            timeout=TimeoutConfig(
                connect_timeout=30.0,
                read_timeout=600.0,
                total_timeout=1800.0  # 30 minutes for long-running tasks
            )
        )
        
        # Database operations
        self._configs["database"] = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30.0,
                success_threshold=2,
                timeout_window=60.0
            ),
            retry=RetryConfig(
                max_attempts=3,
                base_delay=0.5,
                max_delay=10.0,
                exponential_base=2.0,
                jitter=True
            ),
            timeout=TimeoutConfig(
                connect_timeout=5.0,
                read_timeout=30.0,
                total_timeout=60.0
            )
        )
    
    def get_config(self, service_type: str) -> ResilienceConfig:
        """
        Get resilience configuration for a service type.
        
        Args:
            service_type: Type of service (http_api, gcp, background_task, database)
            
        Returns:
            ResilienceConfig for the service type
        """
        if service_type not in self._configs:
            # Return default HTTP API config for unknown service types
            service_type = "http_api"
        
        return self._configs[service_type]
    
    def set_config(self, service_type: str, config: ResilienceConfig):
        """
        Set custom resilience configuration for a service type.
        
        Args:
            service_type: Type of service
            config: Custom resilience configuration
        """
        self._configs[service_type] = config
    
    def get_available_service_types(self) -> list[str]:
        """Get list of available service types."""
        return list(self._configs.keys())


# Global configuration manager instance
resilience_config_manager = ResilienceConfigManager()