# Refactored API Design: Asynchronous Video Analysis

**Version:** 1.0
**Status:** Proposed

This document outlines the redesigned architecture for the AI Video Analysis System's API, correcting the synchronous processing flaw in the initial implementation. The new design adheres to modern asynchronous patterns, ensuring the system is scalable, responsive, and robust.

## 1. Executive Summary

The previous API implementation featured a blocking endpoint (`/process_frame`) that contradicted the system's requirement for handling long-running video analysis tasks. This redesign introduces a non-blocking, asynchronous workflow using a dedicated task queue.

**Key Changes:**

1.  **Asynchronous Task Processing**: Replaced the blocking endpoint with a proper task queue system. Clients submit analysis jobs and receive a task ID for polling, freeing up the API server immediately.
2.  **New API Endpoints**: Introduced `POST /analyze` for job submission and `GET /results/{task_id}` for status/result retrieval, aligning with the original design intent.
3.  **Strict Input Validation**: Replaced the generic `dict` input with a strict `Pydantic` model (`AnalyzeRequest`) to ensure data integrity.
4.  **Dynamic Configuration**: Implemented a settings management solution to load configuration from environment variables or files, removing hardcoded paths.

## 2. Architectural Design

The proposed architecture separates the API frontend from the processing backend using a Redis-based task queue.

```mermaid
sequenceDiagram
    participant Client
    participant API (FastAPI)
    participant Task Queue (Redis)
    participant Worker
    participant VectorDB (Qdrant)

    Client->>+API: POST /analyze (video_url)
    API->>+Task Queue: Enqueue analysis job
    API-->>-Client: 202 Accepted (task_id)
    loop Poll for results
        Client->>+API: GET /results/{task_id}
        API->>+Task Queue: Check job status
        alt Job Incomplete
            Task Queue-->>-API: Status: PENDING/PROCESSING
            API-->>-Client: 200 OK (status)
        else Job Complete
            Task Queue-->>-API: Status: SUCCESS (result)
            API-->>-Client: 200 OK (status, result)
        end
    end

    Note right of Worker: Worker process runs separately
    Worker->>+Task Queue: Dequeue job
    Worker->>Worker: 1. Process video frame (InferenceService)
    Worker->>+VectorDB: 2. Upsert (Embedding + Metadata)
    Worker->>+Task Queue: 3. Update job status/result
```

### 2.1. Chosen Technology: ARQ (Asynchronous Redis Queue)

For the task queue, we will use **ARQ**.

- **Rationale**: ARQ is a high-performance task queue built for Python's `asyncio`. It is simpler to configure and manage than Celery but more robust than FastAPI's built-in `BackgroundTasks` because it persists jobs in Redis. This prevents task loss if the API server restarts and provides a clear separation between the web server and the workers.
- **Dependencies**: `arq`, `redis-py`.
- **Fallback**: If a Redis instance is unavailable, the design can be simplified to use FastAPI's `BackgroundTasks` as a fallback, with the acknowledged trade-off of losing task persistence and retry capabilities.

## 3. Dynamic Configuration Management

To eliminate hardcoded configuration paths, we will use the `pydantic-settings` library. This allows for a layered configuration approach.

1.  A `Settings` class will define all configuration parameters.
2.  Values will be loaded from environment variables by default.
3.  A `.env` file can be used for local development.

**Example (`src/video_ai_system/config.py`):**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import RedisDsn

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # Redis DSN for ARQ
    REDIS_DSN: RedisDsn = "redis://localhost:6379/0"

    # Path to the model registry
    MODEL_REGISTRY_PATH: str = "./models"

    # Default pipeline configuration file
    PIPELINE_CONFIG_PATH: str = "config/development.json"

# Global settings instance
settings = Settings()
```

The application will import and use the `settings` object instead of hardcoding paths.

## 4. API Endpoint Specification

The `/process_frame` endpoint will be removed and replaced with the following.

### `POST /analyze`

Submits a video for asynchronous analysis.

- **Method**: `POST`
- **Path**: `/analyze`
- **Request Body**: `AnalyzeRequest`
- **Success Response**: `202 Accepted` with `AnalyzeResponse` body.
- **Error Response**: `422 Unprocessable Entity` if the request body is invalid.

**Pydantic Models:**

```python
from pydantic import BaseModel, HttpUrl
from typing import Optional

class AnalyzeRequest(BaseModel):
    """
    Specifies the video to be analyzed.
    The model is strict, preventing unexpected fields.
    """
    video_url: HttpUrl
    callback_url: Optional[HttpUrl] = None

    class Config:
        extra = 'forbid' # Forbid any extra fields

class AnalyzeResponse(BaseModel):
    """
    Confirms the task was accepted.
    """
    task_id: str
    status_endpoint: str
```

### `GET /results/{task_id}`

Retrieves the status and results of an analysis task.

- **Method**: `GET`
- **Path**: `/results/{task_id}`
- **URL Parameters**:
  - `task_id` (str): The ID of the task.
- **Success Response**: `200 OK` with `TaskStatusResponse` body.
- **Error Response**: `404 Not Found` if the `task_id` does not exist.

**Pydantic Models:**

```python
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None # Can be a more specific model later
    error_message: Optional[str] = None
```

## 5. Worker Implementation Outline

A separate worker process must be run to execute the analysis tasks.

**Worker Entrypoint (`src/video_ai_system/worker.py`):**

```python
import asyncio
from video_ai_system.config import settings
from video_ai_system.services.pipeline_service import PipelineService
from video_ai_system.services.model_registry_service import ModelRegistryService

# Initialize services for the worker
model_registry = ModelRegistryService(registry_path=settings.MODEL_REGISTRY_PATH)
pipeline_service = PipelineService(model_registry_service=model_registry)
pipeline_service.load_from_config(settings.PIPELINE_CONFIG_PATH)

async def analyze_video(ctx, video_url: str, **kwargs):
    """
    This is the ARQ task function.
    It executes the 'production' pipeline.
    """
    print(f"Processing video: {video_url}")
    try:
        # The actual data passed to the pipeline would be the video content/frames
        # This is a placeholder for the real processing logic
        data_for_pipeline = {"video_url": video_url}
        result = pipeline_service.execute_pipeline("production", data_for_pipeline)
        await ctx['redis'].set(f"arq:result:{ctx['job_id']}", "SUCCESS") # Simplified
        return result
    except Exception as e:
        await ctx['redis'].set(f"arq:result:{ctx['job_id']}", "FAILED") # Simplified
        raise e

class WorkerSettings:
    """
    ARQ worker configuration.
    """
    functions = [analyze_video]
    redis_settings = settings.REDIS_DSN
```

**To run the worker:** `arq src.video_ai_system.worker.WorkerSettings`

## 6. Validation and Testing Plan

- **Unit Tests**:
  - Test the `/analyze` and `/results/{task_id}` endpoints with mock services.
  - Validate the `AnalyzeRequest` model rejects requests with extra fields.
  - Test the `Settings` object correctly loads from environment variables.
- **Integration Tests**:
  - Write a test that submits a job to `/analyze`, polls `/results/{task_id}`, and verifies the final status is `SUCCESS`. This will require a running Redis instance and a worker in the test environment.
