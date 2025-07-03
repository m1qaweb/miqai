import logging
from typing import Dict, Any, Optional
import numpy as np
from prometheus_client import Counter, Histogram, CollectorRegistry
from pydantic import BaseModel, Field

from video_ai_system.services.inference_service import InferenceService
from video_ai_system.services.comparison_service import ComparisonService


class ShadowTestResult(BaseModel):
    """Represents the results of a shadow test for a specific model version."""
    model_name: str
    model_version: str
    total_requests: int = 0
    mismatches: int = 0
    latency_comparison: Dict[str, float] = Field(default_factory=dict)
    error_samples: list = Field(default_factory=list)

# Prometheus metrics to monitor the shadow testing process
SHADOW_RUNS_TOTAL = Counter(
    "shadow_runs_total", "Total number of shadow tests initiated."
)
SHADOW_RUNS_FAILED = Counter(
    "shadow_runs_failed", "Total number of shadow tests that failed."
)
SHADOW_CANDIDATE_LATENCY = Histogram(
    "shadow_candidate_latency_seconds", "Latency of candidate model inference."
)


class ShadowTestingService:
    """
    A service to run a candidate model's inference in "shadow mode" against the
    production model and log the comparison for analysis.
    """

    def __init__(
        self,
        inference_service: InferenceService,
        logger: logging.Logger,
        registry: CollectorRegistry,
        comparison_service: Optional[ComparisonService] = None,
    ):
        """
        Initializes the ShadowTestingService.

        :param inference_service: The service to use for running model inference.
        :param logger: A logger instance for structured logging of results.
        :param registry: A Prometheus collector registry.
        :param comparison_service: The service to use for comparing model outputs.
        """
        self.inference_service = inference_service
        self.logger = logger
        self.comparison_service = comparison_service
        # Register metrics if a registry is provided (for production)
        if registry:
            registry.register(SHADOW_RUNS_TOTAL)
            registry.register(SHADOW_RUNS_FAILED)
            registry.register(SHADOW_CANDIDATE_LATENCY)

    async def compare_and_log(
        self,
        video_id: str,
        production_model_id: str,
        candidate_model_id: str,
        production_results: Dict[str, Any],
        production_latency: float,
        video_path: str,
    ):
        """
        Runs inference with a candidate model, compares its results to the
        production model's, and logs the comparison metrics.
        """
        SHADOW_RUNS_TOTAL.inc()
        self.logger.info(
            f"Starting shadow analysis for video_id: {video_id} with candidate: {candidate_model_id}"
        )

        try:
            # 1. Run candidate inference
            with SHADOW_CANDIDATE_LATENCY.time():
                cand_results, cand_latency = await self.inference_service.analyze(
                    video_path, candidate_model_id
                )

            # 2. Use ComparisonService to log and compare results
            if self.comparison_service:
                self.comparison_service.compare_and_log(
                    production_output=production_results,
                    candidate_output=cand_results,
                    request_id=video_id,
                )

            # Legacy logging for now
            self.logger.info(
                f"Shadow run for {video_id} complete. Prod Latency: {production_latency:.2f}s, Cand Latency: {cand_latency:.2f}s"
            )

        except Exception as e:
            SHADOW_RUNS_FAILED.inc()
            self.logger.error(
                f"Shadow analysis failed for video_id: {video_id} with candidate: {candidate_model_id}. Error: {e}",
                exc_info=True,
            )

    async def get_results(self, model_name: str, model_version: str) -> Optional[ShadowTestResult]:
        """
        Retrieves aggregated shadow test results.
        NOTE: This is a placeholder. In a real system, these results would be
        read from a database or a persistent cache (like Redis) where they are
        aggregated over time.
        """
        logger.info(f"Fetching shadow results for {model_name} v{model_version}")
        # Simulate fetching data
        if model_name == "model-b" and model_version == "2.0.0":
            return ShadowTestResult(
                model_name=model_name,
                model_version=model_version,
                total_requests=100,
                mismatches=5,
                latency_comparison={"p50_candidate": 50, "p50_production": 48},
                error_samples=[{"video_id": "vid_001", "reason": "mismatch"}],
            )
        return None
