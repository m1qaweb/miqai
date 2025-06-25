# Design: End-to-End Inference and Embedding Pipeline

**Version:** 1.0
**Author:** Architect Mode
**Status:** Proposed

## 1. Overview

This document outlines the architecture for the main video analysis pipeline, orchestrated by a new `PipelineService`. This service manages the end-to-end workflow, from receiving a video file, extracting keyframes, invoking inference for each frame, and storing the resulting embeddings and metadata in the vector database.

This design emphasizes scalability, maintainability, and resilience by adopting a hybrid service-oriented architecture.

## 2. Requirements & Success Metrics

- **R1:** The pipeline MUST orchestrate preprocessing, inference, and storage services.
- **R2:** The design MUST allow the `InferenceService` to be scaled independently from the rest of the application.
- **R3:** The pipeline MUST be resilient to transient network failures and recoverable from errors in single-frame processing.
- **Metric-1 (Performance):** Process a 5-minute, 1080p video in under 5 minutes.
- **Metric-2 (Reliability):** A failure during a single frame's inference should not cause the entire video analysis to fail.
- **Metric-3 (Scalability):** The architecture must support adding more inference workers without redeploying the main application.

## 3. Architectural Design Alternatives

### 3.1. Alternative A: Monolithic Orchestration

- **Description:** All services run as classes within the same worker process. Communication is via direct method calls.
- **Pros:** Simple, no network overhead internally.
- **Cons:** Not scalable, poor resource utilization, low reliability (a crash in one component fails the entire task).
- **Verdict:** Rejected. Fails to meet scalability and reliability requirements.

### 3.2. Alternative B: Fully Decoupled, Event-Driven Architecture

- **Description:** Each pipeline stage is a microservice communicating via a message queue (e.g., RabbitMQ).
- **Pros:** Highly scalable and reliable.
- **Cons:** High operational complexity (requires managing a message broker). Potentially higher latency.
- **Verdict:** Deferred. A powerful pattern for future phases, but overly complex for the current stage.

### 3.3. Alternative C: Hybrid Service-Oriented Orchestration (Selected)

- **Description:** A stateful `PipelineService` orchestrates the flow, calling a local `PreprocessingService` but communicating with a separate, network-accessible `InferenceService`.
- **Pros:** Balances scalability and complexity. Decouples the most resource-intensive component. High maintainability.
- **Cons:** Introduces network communication between the orchestrator and inference service.
- **Verdict:** **Selected.** Provides the best trade-off for current project goals.

**Diagram of Selected Architecture:**

```mermaid
graph TD
    subgraph ARQ Worker Process
        A[analyze_video task] --> B(PipelineService)
        B --.method call.-> C(PreprocessingService)
        B --.method call.-> D(VectorDBService)
    end

    subgraph Scalable Inference Deployment
        E(InferenceService API)
    end

    B -- HTTP/gRPC call --> E
    D -- network call --> F[(Qdrant DB)]

    style B fill:#ccf,stroke:#333,stroke-width:2px
    style E fill:#f9f,stroke:#333,stroke-width:2px
```

## 4. Detailed Component Design (Selected Approach)

### 4.1. `PipelineService`

The `PipelineService` is the orchestrator. It will be initialized with clients for the services it depends on (dependency injection).

- **Class:** `video_ai_system.services.pipeline_service.PipelineService`
- **Key Method:** `async def process_video(self, video_path: str, video_id: str)`
- **Logic:**
  1.  Get keyframe generator from `PreprocessingService`.
  2.  Loop through keyframes.
  3.  For each keyframe, serialize it and send an HTTP request to the `InferenceService`.
  4.  Implement retry logic for the HTTP request. If retries fail, log the error and skip the frame.
  5.  Collect inference results into a batch.
  6.  When the batch is full, call `VectorDBService.upsert_points`.
  7.  After the loop, upsert any remaining points.

### 4.2. `InferenceService`

The `InferenceService` becomes a standalone FastAPI application.

- **Endpoint:** `POST /infer`
- **Request Body:** `InferenceRequest` (contains serialized frame bytes).
- **Response Body:** `InferenceResult` (contains detections, embedding, and model version).
- **Deployment:** Will be containerized and deployed separately, allowing multiple replicas to be run for scalability.

### 4.3. Data Contracts (Pydantic Models)

A new file `src/video_ai_system/services/pipeline_models.py` will be created to hold the shared data contracts.

```python
from pydantic import BaseModel, Field
from typing import List
import numpy as np

class Keyframe:
    frame_array: np.ndarray
    timestamp_sec: float
    frame_number: int
    class Config: arbitrary_types_allowed = True

class InferenceRequest(BaseModel):
    frame_bytes: bytes

class Detection(BaseModel):
    box: List[float]
    label: str
    score: float

class InferenceResult(BaseModel):
    detections: List[Detection]
    embedding: List[float]
    model_version: str
```

## 5. Configuration

The following configuration will be added to `config.schema.json` and the corresponding settings files.

```json
{
  "inference_client": {
    "description": "Settings for connecting to the internal Inference Service.",
    "type": "object",
    "properties": {
      "url": {
        "type": "string",
        "format": "uri",
        "default": "http://inference-service:8001"
      },
      "timeout_seconds": { "type": "integer", "default": 30 }
    }
  },
  "pipeline": {
    "description": "Settings for the main analysis pipeline.",
    "type": "object",
    "properties": {
      "db_batch_size": {
        "description": "Number of keyframes to process before writing to the database.",
        "type": "integer",
        "default": 50
      }
    }
  }
}
```

## 6. Error Handling & Resilience

- **Timeouts:** All network calls from the `PipelineService` will have configurable timeouts.
- **Retries:** Calls to the `InferenceService` and `VectorDBService` will use an exponential backoff retry strategy for transient errors (e.g., 5xx status codes).
- **Circuit Breaker (Future):** A circuit breaker pattern can be added to the `PipelineService`'s inference client to prevent it from continuously calling a failing `InferenceService`.
- **Per-Frame Errors:** An error in processing a single keyframe (e.g., inference failure after retries) will be logged, and the pipeline will continue with the next frame.

## 7. Validation Plan

- **Unit Tests:** `PipelineService` logic will be tested using mocks for all external services.
- **Integration Tests:** A `docker-compose` environment will be used to test the full pipeline flow, from the public API endpoint to data verification in Qdrant.
- **Benchmark Tests:** An end-to-end benchmark script will measure throughput and latency against a standard video dataset.
