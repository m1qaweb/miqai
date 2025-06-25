# Architect Mode: Design Specification

## Design Goal: Active Learning Service and API

This document outlines the design for the `ActiveLearningService`, a component responsible for identifying data points (video frames) that require human annotation to improve model performance. It also specifies the API endpoint to expose this data.

This design supports the active learning loop by programmatically selecting the most informative data for labeling, thereby optimizing the annotation budget and improving model accuracy more efficiently.

---

### 1. Context Restatement & Alignment

**Design Goal:** Design a service to query the vector database for low-confidence detections and expose them via a REST API for consumption by an annotation workflow.

**Phase Objectives:** This aligns with Phase 1 objectives to establish a data pipeline that can feed into an active learning loop.

**Success Metrics:**

- **API Latency:** The `GET /active-learning/low-confidence-frames` endpoint should respond in < 500ms under normal load.
- **Query Accuracy:** The service must accurately filter and retrieve frames based on a confidence threshold.
- **Configurability:** The confidence threshold must be configurable without code changes.

**Constraints & Assumptions:**

- **A0101 (Pending):** Assumes that detection confidence scores are stored in the Qdrant vector database payload alongside frame metadata. **Validation:** Confirm via inspection of the data being written by the `InferenceService`.
- **Infrastructure:** The service will be part of the main FastAPI application and will run in the same container. It will have network access to the Qdrant database.

---

### 2. Design Alternatives & Trade-Offs

#### Alternative 1: Direct Qdrant Query in API Endpoint (Low Confidence)

- **Description:** The API endpoint handler directly contains the logic to build and execute the Qdrant query.
- **Performance:** Similar to the preferred approach, as the query is the main bottleneck.
- **Security:** Business logic is mixed with the presentation layer, which is poor practice.
- **Maintainability:** Low. Tightly couples the API to the database implementation. Changes to the query logic or database technology require modifying the API layer.
- **Extensibility:** Poor. Difficult to reuse the query logic elsewhere or to introduce more complex selection strategies.

#### Alternative 2: Dedicated `ActiveLearningService` (Preferred - High Confidence)

- **Description:** A dedicated service class encapsulates all logic for active learning queries. The API endpoint is a thin wrapper around this service.
- **Performance:** Negligible overhead compared to Alternative 1.
- **Security:** Good separation of concerns. Access to the database is mediated by the service layer.
- **Maintainability:** High. Logic is centralized and decoupled. The database client can be swapped out with minimal changes to the API layer.
- **Extensibility:** High. The service can be easily extended with new methods for different selection strategies (e.g., entropy-based, margin-based) in future phases.

#### Alternative 3: Asynchronous Batch Job (Medium Confidence)

- **Description:** A background worker (e.g., Celery) periodically runs a job to find low-confidence frames and caches the results in a simple key-value store (like Redis). The API reads from this cache.
- **Performance:** Fastest API response time as it reads from a cache. However, the data may be stale depending on the job frequency.
- **Security:** Similar to the preferred approach.
- **Maintainability:** Higher complexity due to the introduction of a caching layer and a background worker.
- **Extensibility:** Good, but adds architectural complexity that is not yet required. This is a potential future optimization if the direct query becomes too slow.

---

### 3. Selected Approach & Justification

**Selected Approach: Alternative 2 - Dedicated `ActiveLearningService`**

This approach provides the best balance of maintainability, extensibility, and simplicity for the current project phase.

- **Meets Metrics:** It can meet the latency and accuracy requirements. The confidence threshold is passed as a parameter, making it configurable.
- **Mitigates Risks:** It decouples the API from the data layer, making the system more robust to change.
- **Future-Proof:** It establishes a clear pattern for adding more sophisticated active learning strategies in the future without refactoring the API layer. The `ActiveLearningService` can become the home for all such logic.

---

### 4. Interfaces & Configuration Schema

#### 4.1. Service and Method Specification

**File:** `src/video_ai_system/services/active_learning_service.py`

```python
from qdrant_client import QdrantClient
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class LowConfidenceFrame(BaseModel):
    """Data structure for a frame with low-confidence detections."""
    frame_id: str = Field(..., description="Unique identifier for the frame.")
    video_path: str = Field(..., description="Path or identifier of the source video.")
    detections: List[Dict[str, Any]] = Field(..., description="List of low-confidence detections.")
    timestamp: str = Field(..., description="Timestamp of the frame capture.")

class ActiveLearningService:
    """Service for active learning selection strategies."""

    def __init__(self, qdrant_client: QdrantClient, collection_name: str):
        """
        Initializes the service with a Qdrant client and collection name.
        """
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name

    def get_low_confidence_frames(
        self, confidence_threshold: float = 0.5, limit: int = 100
    ) -> List[LowConfidenceFrame]:
        """
        Queries Qdrant for frames with detections below a confidence threshold.

        Args:
            confidence_threshold: The upper bound for detection confidence.
            limit: The maximum number of frames to return.

        Returns:
            A list of LowConfidenceFrame objects.
        """
        # This method will implement the Qdrant query logic.
        # The query will use a filter on the payload.
        pass
```

#### 4.2. API Endpoint Specification

**File:** `src/video_ai_system/main.py` (or a dedicated router)

**Endpoint:** `GET /active-learning/low-confidence-frames`

**Query Parameters:**

- `confidence_threshold` (float, optional, default: 0.5): The confidence score threshold.
- `limit` (int, optional, default: 100): The maximum number of frames to return.

**Success Response (200 OK):**

```json
[
  {
    "frame_id": "video1_frame_123",
    "video_path": "/data/videos/video1.mp4",
    "detections": [
      {
        "box": [100, 150, 50, 50],
        "label": "car",
        "confidence": 0.45
      }
    ],
    "timestamp": "2025-06-25T10:30:00Z"
  },
  {
    "frame_id": "video2_frame_456",
    "video_path": "/data/videos/video2.mp4",
    "detections": [
      {
        "box": [200, 250, 60, 60],
        "label": "person",
        "confidence": 0.39
      }
    ],
    "timestamp": "2025-06-25T11:00:00Z"
  }
]
```

---

### 5. Validation & Testing Plan

- **Unit Tests:**
  - `test_get_low_confidence_frames_with_valid_data`: Mock the `qdrant_client` and verify that the service correctly formats the returned data.
  - `test_qdrant_query_construction`: Verify that the service constructs the correct filter query for Qdrant based on the `confidence_threshold`.
- **Integration Tests:**
  - `test_api_endpoint_returns_200`: Call the `GET /active-learning/low-confidence-frames` endpoint and verify a successful response.
  - `test_api_endpoint_with_qdrant`: With a running Qdrant instance populated with test data, verify the endpoint returns the correct low-confidence frames.
- **Benchmark Scripts:**
  - A script to measure the response time of the API endpoint with a large number of points in the database to ensure it meets the <500ms target.

---

### 6. Next Tasks for Code Mode

- **T1.1:** Implement the `ActiveLearningService` class in `src/video_ai_system/services/active_learning_service.py` as specified.
- **T1.2:** Implement the `get_low_confidence_frames` method with the actual Qdrant query logic.
- **T1.3:** Create and register the `GET /active-learning/low-confidence-frames` API endpoint in the FastAPI application.
- **T1.4:** Add unit and integration tests for the new service and endpoint.
- **T1.5:** Update application configuration to include the Qdrant collection name for the service.
