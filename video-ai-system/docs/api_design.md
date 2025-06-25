# AI Video Analysis System - API Design (Phase 0)

This document outlines the design for the RESTful API for the AI Video Analysis System. The API is built using FastAPI and uses Pydantic models for request and response validation.

## Table of Contents

1.  [General Concepts](#general-concepts)
    - [Asynchronous Processing](#asynchronous-processing)
    - [Authentication](#authentication)
    - [Error Handling](#error-handling)
2.  [Endpoints](#endpoints)
    - [Health Check](#health-check)
      - `GET /health`
    - [Metrics](#metrics)
      - `GET /metrics`
    - [Video Analysis](#video-analysis)
      - `POST /analyze`
      - `GET /analysis/{task_id}`
    - [Similarity Search](#similarity-search)
      - `POST /search_similar`
    - [Annotation Queue](#annotation-queue)
      - `GET /annotation_queue`

---

## 1. General Concepts

### Asynchronous Processing

Video analysis is a long-running task. To avoid blocking clients, the `/analyze` endpoint operates asynchronously. The client submits a video for analysis and receives a `task_id`. The client can then poll the `/analysis/{task_id}` endpoint to check the status and retrieve the results when ready. This approach ensures the API remains responsive and scalable.

### Authentication

**(Future Phase)** API endpoints will be protected. For Phase 0, we assume an internal-only deployment model where authentication is handled at the network layer. Future phases will introduce token-based authentication (e.g., OAuth2 with JWT).

### Error Handling

The API will use standard HTTP status codes to indicate success or failure. Error responses will have a consistent JSON format:

```json
{
  "detail": "A human-readable error message."
}
```

---

## 2. Endpoints

### Health Check

Provides a simple health check for monitoring services (e.g., Kubernetes liveness/readiness probes).

#### `GET /health`

- **Description**: Checks if the service is running and healthy.
- **Request Body**: None.
- **Response Body (200 OK)**:

  ```python
  # Pydantic-style Response Model
  from pydantic import BaseModel

  class HealthStatus(BaseModel):
      status: str = "ok"
  ```

  **Example Response**:

  ```json
  {
    "status": "ok"
  }
  ```

- **cURL Example**:
  ```bash
  curl -X GET http://localhost:8000/health
  ```

---

### Metrics

Exposes operational metrics in a format compatible with Prometheus for monitoring and alerting.

#### `GET /metrics`

- **Description**: Exposes system and application metrics (e.g., request latency, error rates, processing queue length) in the Prometheus text format. This endpoint is typically scraped by a Prometheus server.
- **Request Body**: None.
- **Response Body (200 OK)**:
  - **Content-Type**: `text/plain; version=0.0.4`
  - **Example Response**:
  ```
  # HELP python_gc_objects_collected_total Objects collected during gc
  # TYPE python_gc_objects_collected_total counter
  python_gc_objects_collected_total{generation="0"} 835.0
  python_gc_objects_collected_total{generation="1"} 180.0
  python_gc_objects_collected_total{generation="2"} 0.0
  # HELP fastapi_requests_total Total number of requests
  # TYPE fastapi_requests_total counter
  fastapi_requests_total{method="GET",path="/metrics"} 1.0
  ...
  ```
- **cURL Example**:
  ```bash
  curl -X GET http://localhost:8000/metrics
  ```

---

### Video Analysis

Endpoints for submitting videos and retrieving analysis results.

#### `POST /analyze`

- **Description**: Submits a video for asynchronous analysis. The video can be provided as a URL. The system will download the video, process it through the analysis pipeline (embedding extraction), and store the results.
- **Request Body**:

  ```python
  # Pydantic-style Request Model
  from typing import Optional
  from pydantic import BaseModel, HttpUrl

  class AnalyzeRequest(BaseModel):
      video_url: HttpUrl
      callback_url: Optional[HttpUrl] = None # Optional webhook for when analysis is complete
  ```

  **Example Request**:

  ```json
  {
    "video_url": "https://example.com/videos/my_video.mp4",
    "callback_url": "https://my-service.com/webhook/analysis_complete"
  }
  ```

- **Response Body (202 Accepted)**:
  ```python
  # Pydantic-style Response Model
  class AnalyzeResponse(BaseModel):
      task_id: str
      status_endpoint: str
  ```
  **Example Response**:
  ```json
  {
    "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "status_endpoint": "/analysis/a1b2c3d4-e5f6-7890-1234-567890abcdef"
  }
  ```
- **cURL Example**:
  ```bash
  curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/videos/my_video.mp4"
  }'
  ```

#### `GET /analysis/{task_id}`

- **Description**: Retrieves the status and results of an analysis task.
- **URL Parameters**:
  - `task_id` (str): The ID of the analysis task, returned by the `/analyze` endpoint.
- **Request Body**: None.
- **Response Body (200 OK)**:

  ```python
  # Pydantic-style Response Model
  from enum import Enum
  from typing import Optional
  from pydantic import BaseModel

  class TaskStatus(str, Enum):
      PENDING = "PENDING"
      PROCESSING = "PROCESSING"
      SUCCESS = "SUCCESS"
      FAILED = "FAILED"

  class AnalysisResult(BaseModel):
      video_id: str # A unique ID assigned to the video after processing
      # Further details like extracted metadata will be added in future phases

  class AnalysisStatusResponse(BaseModel):
      task_id: str
      status: TaskStatus
      result: Optional[AnalysisResult] = None
      error_message: Optional[str] = None
  ```

  **Example Response (Processing)**:

  ```json
  {
    "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "status": "PROCESSING",
    "result": null,
    "error_message": null
  }
  ```

  **Example Response (Success)**:

  ```json
  {
    "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "status": "SUCCESS",
    "result": {
      "video_id": "vid_abc123"
    },
    "error_message": null
  }
  ```

- **cURL Example**:
  ```bash
  curl -X GET http://localhost:8000/analysis/a1b2c3d4-e5f6-7890-1234-567890abcdef
  ```

---

### Similarity Search

Finds videos similar to a given video.

#### `POST /search_similar`

- **Description**: Searches the vector database for videos with content embeddings similar to a specified source video.
- **Request Body**:

  ```python
  # Pydantic-style Request Model
  from pydantic import BaseModel

  class SimilarityRequest(BaseModel):
      video_id: str
      top_k: int = 5 # Number of similar items to return
  ```

  **Example Request**:

  ```json
  {
    "video_id": "vid_abc123",
    "top_k": 3
  }
  ```

- **Response Body (200 OK)**:

  ```python
  # Pydantic-style Response Model
  from typing import List
  from pydantic import BaseModel

  class SimilarityHit(BaseModel):
      video_id: str
      score: float # Similarity score (e.g., cosine similarity)

  class SimilarityResponse(BaseModel):
      source_video_id: str
      similar_videos: List[SimilarityHit]
  ```

  **Example Response**:

  ```json
  {
    "source_video_id": "vid_abc123",
    "similar_videos": [
      {
        "video_id": "vid_xyz789",
        "score": 0.987
      },
      {
        "video_id": "vid_def456",
        "score": 0.954
      }
    ]
  }
  ```

- **cURL Example**:
  ```bash
  curl -X POST http://localhost:8000/search_similar \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "vid_abc123",
    "top_k": 3
  }'
  ```

---

### Annotation Queue

Retrieves items that require manual review or annotation. This is a key component for the active learning loop (Phase 1).

#### `GET /annotation_queue`

- **Description**: Fetches a batch of video segments or frames that have been flagged for manual annotation. Items are flagged based on model uncertainty, drift detection, or other active learning strategies.
- **Query Parameters**:
  - `limit` (int, optional, default: 10): The maximum number of items to return.
- **Request Body**: None.
- **Response Body (200 OK)**:

  ```python
  # Pydantic-style Response Model
  from enum import Enum
  from typing import List
  from pydantic import BaseModel

  class AnnotationReason(str, Enum):
      LOW_CONFIDENCE = "LOW_CONFIDENCE"
      DRIFT_DETECTED = "DRIFT_DETECTED"
      RANDOM_SAMPLE = "RANDOM_SAMPLE"

  class AnnotationQueueItem(BaseModel):
      item_id: str # Unique ID for this annotation task
      video_id: str
      timestamp_sec: float # The point in the video that needs annotation
      reason: AnnotationReason

  class AnnotationQueueResponse(BaseModel):
      items: List[AnnotationQueueItem]
  ```

  **Example Response**:

  ```json
  {
    "items": [
      {
        "item_id": "anno_task_001",
        "video_id": "vid_lmn456",
        "timestamp_sec": 123.45,
        "reason": "LOW_CONFIDENCE"
      },
      {
        "item_id": "anno_task_002",
        "video_id": "vid_pqr789",
        "timestamp_sec": 45.1,
        "reason": "DRIFT_DETECTED"
      }
    ]
  }
  ```

- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/annotation_queue?limit=5"
  ```
