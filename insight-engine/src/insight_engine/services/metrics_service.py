"""
A service to simulate fetching real-time performance metrics from a
monitoring system like Prometheus.
"""
import random
import logging

logger = logging.getLogger(__name__)

class MetricsService:
    """
    Simulates fetching metrics from a monitoring service.
    In a real production environment, this service would query Prometheus
    or a similar system to get real-time performance data.
    """

    def __init__(self):
        """Initializes the MetricsService."""
        # Simulate a database of model performance metrics
        self._mock_metrics = {
            "yolov8n-coco": {"latency_ms": 150, "cpu_percent": 45},
            "yolov8n-light": {"latency_ms": 80, "cpu_percent": 30},
            "gemini-pro": {"latency_ms": 500, "cpu_percent": 10},
        }
        logger.info("MetricsService initialized with mock data.")

    def get_model_latency(self, model_name: str) -> float:
        """
        Gets the simulated latency for a given model.

        Args:
            model_name: The name of the model.

        Returns:
            The simulated latency in milliseconds, with some random variance.
        """
        base_latency = self._mock_metrics.get(model_name, {}).get("latency_ms", 1000)
        # Add some random jitter to simulate real-world conditions
        simulated_latency = base_latency + random.uniform(-10, 20)
        logger.info(f"Fetched simulated latency for '{model_name}': {simulated_latency:.2f} ms")
        return simulated_latency

    def get_system_cpu_usage(self) -> float:
        """Gets the simulated overall system CPU usage."""
        # Simulate fluctuating CPU usage
        return random.uniform(40.0, 85.0)

