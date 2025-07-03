# src/video_ai_system/services/drift_detection_service.py

import time
import numpy as np
import httpx
from sklearn.decomposition import PCA
from sklearn.neighbors import KernelDensity
from prometheus_client import Gauge, Histogram, Counter
from loguru import logger
from pydantic import BaseModel, Field
from datetime import datetime, timezone
 
from ..services.vector_db_service import VectorDBService

class DriftAlert(BaseModel):
    """Represents a data drift alert."""
    alert_id: str = Field(..., description="Unique identifier for the alert.")
    model_name: str = Field(..., description="The name of the model experiencing drift.")
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    drift_score: float = Field(..., description="The calculated drift score (e.g., KL divergence).")
    threshold: float = Field(..., description="The drift threshold that was breached.")
    comparison_window_start: datetime = Field(..., description="Start of the comparison data window.")
    comparison_window_end: datetime = Field(..., description="End of the comparison data window.")
 
 # Prometheus Metrics defined as per drift_detection_design.md
DRIFT_SCORE = Gauge(
    "video_ai_drift_score",
    "Latest drift score.",
    ["method", "source"]
)
DRIFT_CHECK_DURATION = Histogram(
    "video_ai_drift_check_duration_seconds",
    "Latency of the drift check operation."
)
DRIFT_DETECTED_TOTAL = Counter(
    "video_ai_drift_detected_total",
    "Total number of times drift has been detected."
)

class DriftDetectionService:
    def __init__(
        self,
        vector_db_service: VectorDBService,
        pca_components: int = 10,
        drift_threshold: float = 0.1,
        retraining_webhook_url: str = None,
    ):
        """
        Initializes the DriftDetectionService.

        Args:
            vector_db_service (VectorDBService): An instance of the vector database service.
            pca_components (int): The number of principal components to reduce to.
            drift_threshold (float): The KL divergence value above which drift is considered detected.
            retraining_webhook_url (str, optional): The URL to call to trigger a retraining pipeline.
        """
        self.vector_db_service = vector_db_service
        self.pca = PCA(n_components=pca_components)
        self.drift_threshold = drift_threshold
        self.retraining_webhook_url = retraining_webhook_url
        self.http_client = httpx.AsyncClient()

    def _fetch_embeddings(self, start_time: float, end_time: float) -> np.ndarray:
        """
        Fetches embeddings from the vector database within a given time window.
        """
        # This is a placeholder for the actual implementation of fetching embeddings
        # In a real scenario, this would interact with self.vector_db_service
        logger.info(f"Fetching embeddings from {start_time} to {end_time}")
        embeddings = self.vector_db_service.get_embeddings_by_timestamp(
            start_ts=start_time,
            end_ts=end_time
        )
        return np.array([emb.vector for emb in embeddings])

    def _calculate_kl_divergence(self, p_samples: np.ndarray, q_samples: np.ndarray) -> float:
        """
        Calculates the KL divergence between two sets of samples after fitting a Kernel Density Estimator.
        """
        if p_samples.ndim == 1:
            p_samples = p_samples.reshape(-1, 1)
        if q_samples.ndim == 1:
            q_samples = q_samples.reshape(-1, 1)

        kde_p = KernelDensity(kernel='gaussian').fit(p_samples)
        kde_q = KernelDensity(kernel='gaussian').fit(q_samples)

        # We score p_samples under both models
        log_p = kde_p.score_samples(p_samples)
        log_q = kde_q.score_samples(p_samples)

        # KL(P || Q) = E_p[log(P) - log(Q)]
        kl_div = np.mean(log_p - log_q)
        
        # Clamp the value to be non-negative
        return max(0.0, kl_div)

    @DRIFT_CHECK_DURATION.time()
    def check_drift(self, start_time_ref: float, end_time_ref: float, start_time_comp: float, end_time_comp: float) -> dict:
        """
        Performs drift detection between a reference and a comparison time window.
        Updates Prometheus metrics with the results.

        Returns:
            A dictionary containing the drift status and the KL divergence score.
        """
        logger.info("Starting drift check...")
        
        # 1. Fetch embeddings for both periods
        ref_embeddings = self._fetch_embeddings(start_time_ref, end_time_ref)
        comp_embeddings = self._fetch_embeddings(start_time_comp, end_time_comp)

        if ref_embeddings.shape[0] < self.pca.n_components or comp_embeddings.shape[0] < self.pca.n_components:
            logger.warning("Not enough data for drift comparison.")
            DRIFT_SCORE.labels(method="kl_divergence", source="embeddings").set(0.0)
            return {"drift_detected": False, "kl_divergence": 0.0, "message": "Not enough data for comparison."}

        # 2. Fit PCA on the reference data and transform both sets
        ref_embeddings_pca = self.pca.fit_transform(ref_embeddings)
        comp_embeddings_pca = self.pca.transform(comp_embeddings)

        # 3. Calculate KL divergence
        kl_divergence = self._calculate_kl_divergence(ref_embeddings_pca, comp_embeddings_pca)
        logger.info(f"Calculated KL Divergence: {kl_divergence}")

        # 4. Update Prometheus Gauge
        DRIFT_SCORE.labels(method="kl_divergence", source="embeddings").set(kl_divergence)

        # 5. Compare to threshold
        drift_detected = kl_divergence > self.drift_threshold
        if drift_detected:
            logger.warning(f"Drift detected! Score: {kl_divergence} > Threshold: {self.drift_threshold}")
            DRIFT_DETECTED_TOTAL.inc()

        return {
            "drift_detected": drift_detected,
            "kl_divergence": kl_divergence
        }

    async def trigger_retraining(self, event_id: str, comparison_window_start: float, comparison_window_end: float) -> dict:
        """
        Triggers an external retraining pipeline.

        This method is designed to be called from an API endpoint (e.g., /retrain)
        as specified in the design document.

        Args:
            event_id (str): The unique identifier for the drift event.
            comparison_window_start (float): The start timestamp of the data that showed drift.
            comparison_window_end (float): The end timestamp of the data that showed drift.

        Returns:
            A dictionary with the status of the retraining trigger.
        """
        if not self.retraining_webhook_url:
            logger.error("Retraining webhook URL is not configured.")
            return {"status": "failed", "reason": "Retraining webhook URL not configured."}

        # In a real implementation, we would package data and upload to S3.
        # Here, we simulate this by preparing the payload for the webhook.
        logger.info(f"Packaging data for event {event_id} from {comparison_window_start} to {comparison_window_end}")
        
        # Placeholder for fetching representative data and uploading to S3
        s3_data_path = f"s3://video-ai-retraining-data/batch-{event_id}-{int(time.time())}.zip"
        
        payload = {
            "event_id": event_id,
            "s3_data_path": s3_data_path,
            "source": "drift_detection_service"
        }

        try:
            logger.info(f"Triggering retraining pipeline at {self.retraining_webhook_url}")
            response = await self.http_client.post(self.retraining_webhook_url, json=payload, timeout=30.0)
            response.raise_for_status()
            
            retraining_job_id = response.json().get("retraining_job_id", "unknown")
            logger.info(f"Successfully triggered retraining. Job ID: {retraining_job_id}")
            
            return {
                "status": "Retraining pipeline triggered successfully",
                "retraining_job_id": retraining_job_id
            }
        except httpx.RequestError as e:
            logger.error(f"Failed to trigger retraining pipeline for event {event_id}: {e}")
            # F2.1 Fallback: Here you would implement retry logic.
            return {"status": "failed", "reason": str(e)}