# Drift Detection Service Design

## 1. Overview

This document outlines the design for the `DriftDetectionService`, a component responsible for detecting data drift by analyzing the distribution of feature embeddings over time. Data drift occurs when the statistical properties of the production data change, which can degrade model performance. This service provides a mechanism to detect such drift, enabling proactive model maintenance, such as retraining.

The design is based on the principles described in the "Zero-Budget" guide, specifically using dimensionality reduction via Principal Component Analysis (PCA) and measuring the difference between embedding distributions with Kullback-Leibler (KL) divergence.

## 2. Service Architecture

### 2.1. `DriftDetectionService` Class

The core of the drift detection mechanism will be encapsulated in the `DriftDetectionService` class.

**Dependencies:**

- `VectorDBService`: To fetch embeddings from Qdrant.
- `scikit-learn`: For PCA and KL divergence calculation.

**Class Structure:**

```python
# src/video_ai_system/services/drift_detection_service.py

from sklearn.decomposition import PCA
from sklearn.neighbors import KernelDensity
import numpy as np
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

    def _fetch_embeddings(self, start_time: str, end_time: str) -> np.ndarray:
        """
        Fetches embeddings from the vector database within a given time window.
        (This assumes the VectorDBService will have a method to filter by timestamp)
        """
        # Implementation will query Qdrant using a time range filter
        # This is a conceptual representation.
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

    def check_drift(self, start_time_ref: str, end_time_ref: str, start_time_comp: str, end_time_comp: str) -> dict:
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
```

### 2.2. Configuration

The following parameters will be configurable:

- `pca_components`: Number of dimensions for PCA.
- `drift_threshold`: KL divergence threshold for detecting drift.

These will be added to the application's configuration files (`development.json` and `config.schema.json`).

## 3. API Endpoint Design

A new API endpoint will be exposed in `main.py` to trigger the drift detection check on demand.

### `POST /drift-detection/check`

- **Description**: Triggers a drift detection analysis between two specified time windows.
- **Request Body**:

```json
{
  "reference_window": {
    "start_time": "2025-06-23T00:00:00Z",
    "end_time": "2025-06-23T23:59:59Z"
  },
  "comparison_window": {
    "start_time": "2025-06-24T00:00:00Z",
    "end_time": "2025-06-24T23:59:59Z"
  }
}
```

- **Success Response (200 OK)**:

```json
{
  "drift_detected": true,
  "kl_divergence": 0.15
}
```

- **Error Response (400 Bad Request)**: If time windows are invalid or missing.
- **Error Response (500 Internal Server Error)**: If the analysis fails for an unexpected reason.

## 4. Cross-Mode Instructions

- **To Code Mode**:

  - Implement the `DriftDetectionService` in a new file: `src/video_ai_system/services/drift_detection_service.py`.
  - Add `scikit-learn` to the project dependencies (`pyproject.toml` or `requirements.txt`).
  - Implement the `POST /drift-detection/check` endpoint in `src/video_ai_system/main.py`.
  - The `VectorDBService` will need a new method `get_embeddings_by_timestamp` that can filter points in Qdrant based on a timestamp payload key.
  - Add configuration options for `pca_components` and `drift_threshold`.

- **To DevOps Mode**:
  - Ensure the `scikit-learn` dependency is included in the Docker image.
  - The new n8n workflow (detailed in `n8n_workflow_design.md`) will need to be deployed.
