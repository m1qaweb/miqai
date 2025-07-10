import asyncio
import time
from typing import Any, Dict, List, Optional
import yaml
from loguru import logger
from prometheus_api_client import PrometheusConnect

from video_ai_system.services.inference_router import InferenceRouter


class AdaptationController:
    """
    Monitors system metrics and adjusts the application's behavior by
    switching the active inference model based on a set of rules.
    """

    def __init__(
        self,
        rules: List[Dict[str, Any]],
        inference_router: InferenceRouter,
        prometheus_url: str,
        poll_interval_seconds: int = 15,
        cooldown_seconds: int = 60,
    ):
        """
        Initializes the AdaptationController.

        :param rules: A list of adaptation rules from the configuration.
        :param inference_router: An instance of the InferenceRouter to control model selection.
        :param prometheus_url: The URL of the Prometheus server.
        :param poll_interval_seconds: How often to check metrics and apply rules.
        :param cooldown_seconds: Minimum time to wait between adaptation changes.
        """
        self.rules = sorted(
            rules,
            key=lambda r: ("CRITICAL", "DEGRADED", "NORMAL").index(r["level"]),
        )
        self.inference_router = inference_router
        self.prom_client = PrometheusConnect(url=prometheus_url, disable_ssl=True)
        self.poll_interval_seconds = poll_interval_seconds
        self.cooldown_seconds = cooldown_seconds
        self.last_adaptation_time = 0
        self._task = None
        self._running = False

    async def _get_metric_value(self, metric_name: str) -> Optional[float]:
        """
        Queries Prometheus for the latest value of a given metric.

        :param metric_name: The name of the metric to query.
        :return: The latest value as a float, or None if not found.
        """
        try:
            # This query gets the average value over the last minute.
            query = f"avg_over_time({metric_name}[1m])"
            result = await self.prom_client.async_custom_query(query=query)
            if result and "value" in result[0]:
                return float(result[0]["value"][1])
            logger.warning(
                f"Metric '{metric_name}' not found or has no value in Prometheus."
            )
            return None
        except Exception as e:
            logger.error(f"Error querying Prometheus for metric '{metric_name}': {e}")
            return None

    async def _evaluate_rules(self):
        """
        Evaluates the current metrics from Prometheus against the rules and
        triggers an adaptation if necessary.
        """
        current_time = time.time()
        if (current_time - self.last_adaptation_time) < self.cooldown_seconds:
            return  # Respect cooldown period

        for rule in self.rules:
            metric_name = rule["metric"]
            threshold = rule["threshold"]
            operator = rule["operator"]
            target_level = rule["level"]
            target_model = rule["target_model"]

            current_value = await self._get_metric_value(metric_name)
            if current_value is None:
                continue

            is_triggered = False
            if operator == ">" and current_value > threshold:
                is_triggered = True
            elif operator == "<" and current_value < threshold:
                is_triggered = True

            if is_triggered:
                if self.inference_router.get_current_model_name() != target_model:
                    logger.info(
                        f"Rule triggered: {metric_name} ({current_value:.4f}) {operator} {threshold}. "
                        f"Switching to model '{target_model}' for level {target_level}."
                    )
                    await self.inference_router.set_active_model(target_model)
                    self.last_adaptation_time = current_time
                # Since rules are sorted by severity, we can break after the first match.
                break

    async def _run_loop(self):
        """The main background loop for the controller."""
        logger.info("Starting AdaptationController background task.")
        while self._running:
            await self._evaluate_rules()
            await asyncio.sleep(self.poll_interval_seconds)
        logger.info("AdaptationController background task stopped.")

    def start(self):
        """Starts the controller's background task."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stops the controller's background task gracefully."""
        if self._running and self._task:
            self._running = False
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("AdaptationController task was cancelled successfully.")


def load_rules_from_yaml(path: str) -> List[Dict[str, Any]]:
    """Loads adaptation rules from a specified YAML file."""
    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
        logger.info(f"Successfully loaded adaptation rules from {path}")
        return config.get("adaptation_rules", [])
    except FileNotFoundError:
        logger.error(f"Adaptation rules file not found at: {path}")
        return []
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file at {path}: {e}")
        return []
