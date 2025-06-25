# src/video_ai_system/services/drift_detection_service.py

import numpy as np
from sklearn.decomposition import PCA
from sklearn.neighbors import KernelDensity

from ..services.vector_db_service import VectorDBService


class DriftDetectionService:
    def __init__(self, vector_db_service: VectorDBService, pca_components: int = 10, drift_threshold: float = 0.1):
        """
        Initializes the DriftDetectionService.

        Args:
            vector_db_service (VectorDBService): An instance of the vector database service.
            pca_components (int): The number of principal components to reduce to.
            drift_threshold (float): The KL divergence value above which drift is considered detected.
        """
        self.vector_db_service = vector_db_service
        self.pca = PCA(n_components=pca_components)
        self.drift_threshold = drift_threshold

    def _fetch_embeddings(self, start_time: float, end_time: float) -> np.ndarray:
        """
        Fetches embeddings from the vector database within a given time window.
        """
        embeddings = self.vector_db_service.get_embeddings_by_timestamp(
            start_ts=start_time,
            end_ts=end_time
        )
        return np.array([emb.vector for emb in embeddings])

    def _calculate_kl_divergence(self, p_samples: np.ndarray, q_samples: np.ndarray) -> float:
        """
        Calculates the KL divergence between two sets of samples after fitting a Kernel Density Estimator.
        """
        kde_p = KernelDensity(kernel='gaussian').fit(p_samples)
        kde_q = KernelDensity(kernel='gaussian').fit(q_samples)

        log_p = kde_p.score_samples(p_samples)
        log_q = kde_q.score_samples(p_samples)

        return np.mean(log_p - log_q)

    def check_drift(self, start_time_ref: float, end_time_ref: float, start_time_comp: float, end_time_comp: float) -> dict:
        """
        Performs drift detection between a reference and a comparison time window.

        Returns:
            A dictionary containing the drift status and the KL divergence score.
        """
        # 1. Fetch embeddings for both periods
        ref_embeddings = self._fetch_embeddings(start_time_ref, end_time_ref)
        comp_embeddings = self._fetch_embeddings(start_time_comp, end_time_comp)

        if ref_embeddings.shape[0] == 0 or comp_embeddings.shape[0] == 0:
            return {"drift_detected": False, "kl_divergence": 0.0, "message": "Not enough data for comparison."}

        # 2. Fit PCA on the reference data and transform both sets
        ref_embeddings_pca = self.pca.fit_transform(ref_embeddings)
        comp_embeddings_pca = self.pca.transform(comp_embeddings)

        # 3. Calculate KL divergence
        kl_divergence = self._calculate_kl_divergence(ref_embeddings_pca, comp_embeddings_pca)

        # 4. Compare to threshold
        drift_detected = kl_divergence > self.drift_threshold

        return {
            "drift_detected": drift_detected,
            "kl_divergence": kl_divergence
        }