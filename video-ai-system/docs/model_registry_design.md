# Model Registry Service Design

**Author**: Architect Mode
**Date**: 2025-06-25
**Status**: Proposed

## 1. Overview

This document outlines the design for a `ModelRegistryService`, a critical component for enabling MLOps capabilities within the AI Video Analysis System. The current system relies on a hardcoded model path, which is inflexible and hinders versioning, experimentation, and automated deployment.

This design adheres to the "Zero-Budget" principle by using a simple, file-based registry (`registry.json`) stored on a persistent volume. This approach provides essential model management features without introducing external dependencies or significant infrastructure overhead.

## 2. Goals

- Decouple the `InferenceService` from a hardcoded model path.
- Establish a centralized system for tracking and managing different model versions.
- Provide a mechanism to promote specific model versions to "staging" or "production" status.
- Enable programmatic access to the model registry via a REST API.
- Ensure the model registry state persists across application restarts.

## 3. Design Alternatives

### Alternative 1: Simple JSON File (Selected)

- **Description**: A single `registry.json` file stores an array of model metadata objects. The `ModelRegistryService` reads from and writes to this file.
- **Pros**:
  - Extremely simple to implement and understand.
  - No external dependencies.
  - Human-readable and easily editable for manual overrides.
  - Perfectly aligns with the "Zero-Budget" constraint.
- **Cons**:
  - Not suitable for high-concurrency scenarios (requires file locking to prevent race conditions).
  - Performance may degrade with a very large number of model entries.
  - No built-in transactional integrity.
- **Confidence**: High

### Alternative 2: SQLite Database

- **Description**: A lightweight, file-based SQL database to store model metadata.
- **Pros**:
  - Provides ACID compliance and transactional integrity.
  - Better performance and scalability for a larger number of models compared to a single JSON file.
  - Supports structured queries.
- **Cons**:
  - Adds a dependency on the `sqlite3` library (standard in Python, but still a dependency).
  - Slightly more complex to implement and manage than a plain JSON file.
- **Confidence**: High

### Alternative 3: MLflow Tracking (File Store Mode)

- **Description**: Utilize the open-source MLflow Tracking component, configured to use the local filesystem for backend and artifact storage.
- **Pros**:
  - Provides a rich, pre-built solution with a UI, client libraries, and a comprehensive feature set (metrics, parameters, artifacts).
  - Industry standard for MLOps.
- **Cons**:
  - Introduces a significant new dependency (`mlflow`).
  - More complex to configure and integrate.
  - Overkill for the current, simple requirements of the system.
- **Confidence**: Medium

## 4. Selected Approach & Rationale

**Alternative 1 (Simple JSON File)** is selected.

This approach perfectly balances the immediate need for a functional model registry with the guiding principle of maintaining a "Zero-Budget," low-complexity architecture. The anticipated number of models in the early phases of this project is small, making the performance and concurrency limitations of a JSON file negligible. Its simplicity ensures rapid implementation and minimal maintenance overhead.

For future scalability, the `ModelRegistryService` will be designed as an interface, allowing the underlying storage mechanism to be swapped (e.g., to SQLite or a dedicated database) with minimal changes to the application logic that consumes the service.

## 5. Detailed Design

### 5.1. Data Model (`registry.json`)

The registry will be a JSON file located at `models/registry.json`. The `models/` directory must be configured as a persistent volume.

**Schema:**

```json
{
  "models": [
    {
      "model_name": "string",
      "version": "integer",
      "path": "string",
      "status": "string (e.g., 'staging', 'production', 'archived')",
      "creation_timestamp": "string (ISO 8601 format)",
      "metadata": {
        "description": "string",
        "metrics": {
          "accuracy": "float",
          "latency_ms": "integer"
        }
      }
    }
  ]
}
```

**Example `models/registry.json`:**

```json
{
  "models": [
    {
      "model_name": "yolov8n-coco",
      "version": 1,
      "path": "models/yolov8n-coco/v1/model.onnx",
      "status": "production",
      "creation_timestamp": "2025-06-25T12:00:00Z",
      "metadata": {
        "description": "Initial YOLOv8 Nano model trained on COCO.",
        "metrics": {
          "accuracy": 0.78,
          "latency_ms": 30
        }
      }
    },
    {
      "model_name": "yolov8n-coco",
      "version": 2,
      "path": "models/yolov8n-coco/v2/model.onnx",
      "status": "staging",
      "creation_timestamp": "2025-07-01T15:30:00Z",
      "metadata": {
        "description": "Retrained with additional data.",
        "metrics": {
          "accuracy": 0.82,
          "latency_ms": 32
        }
      }
    }
  ]
}
```

### 5.2. `ModelRegistryService` Class

This service will be located at [`src/video_ai_system/services/model_registry_service.py`](src/video_ai_system/services/model_registry_service.py). It will handle all interactions with the `registry.json` file. A file lock will be used during write operations to prevent race conditions.

```python
# In src/video_ai_system/services/model_registry_service.py

import fcntl # Or a cross-platform equivalent for file locking
import json
from datetime import datetime
from typing import List, Dict, Optional

class ModelRegistryService:
    def __init__(self, registry_path: str = "models/registry.json"):
        self.registry_path = registry_path
        self._ensure_registry_exists()

    def _ensure_registry_exists(self):
        # ... implementation to create the file with {"models": []} if not present

    def _read_registry(self) -> Dict:
        # ... implementation to read the JSON file

    def _write_registry(self, data: Dict):
        # ... implementation to write to the JSON file using a file lock

    def register_model(self, model_name: str, version: int, path: str, metadata: Dict) -> Dict:
        """Registers a new model version."""
        # ... implementation to add a new entry and save

    def list_models(self, model_name: Optional[str] = None) -> List[Dict]:
        """Lists all versions of all models, or all versions of a specific model."""
        # ... implementation to read and filter models

    def activate_model_version(self, model_name: str, version: int) -> Optional[Dict]:
        """Sets a model version's status to 'production' and others to 'staging'."""
        # ... implementation to find the model, update its status,
        # and ensure only one 'production' model exists per model_name.

    def get_production_model(self, model_name: str) -> Optional[Dict]:
        """Gets the model entry currently marked as 'production'."""
        # ... implementation to find the active model
```

### 5.3. API Endpoints

The API endpoints will be defined in [`src/video_ai_system/main.py`](src/video_ai_system/main.py) and will use the `ModelRegistryService`.

#### `POST /api/v1/registry/models`

- **Description**: Register a new model version.
- **Request Body**:
  ```json
  {
    "model_name": "yolov8n-coco",
    "version": 3,
    "path": "models/yolov8n-coco/v3/model.onnx",
    "metadata": {
      "description": "Fine-tuned on custom dataset."
    }
  }
  ```
- **Success Response (201 Created)**: The full model entry that was created.

#### `GET /api/v1/registry/models`

- **Description**: List all registered models. Can be filtered by `model_name`.
- **Query Parameters**:
  - `model_name` (optional, string): Filter by model name.
- **Success Response (200 OK)**:
  ```json
  {
    "models": [
      // ... list of model entries
    ]
  }
  ```

#### `PUT /api/v1/registry/models/{model_name}/{version}/activate`

- **Description**: Promote a specific model version to 'production'. This will atomically set the specified version's status to `production` and set any other version of the same model that was `production` to `staging`.
- **Path Parameters**:
  - `model_name` (string)
  - `version` (integer)
- **Success Response (200 OK)**: The updated model entry.
- **Failure Response (404 Not Found)**: If the model name or version does not exist.

### 5.4. `InferenceService` Integration

The [`InferenceService`](src/video_ai_system/services/inference_service.py) will be modified to use the `ModelRegistryService` on startup.

**Current (Simplified):**

```python
class InferenceService:
    def __init__(self, model_path: str):
        self.model = self._load_model(model_path)
    # ...
```

**Proposed Change:**

```python
# In src/video_ai_system/main.py (or wherever services are initialized)
model_registry = ModelRegistryService()
production_model_entry = model_registry.get_production_model(model_name="yolov8n-coco")
if not production_model_entry:
    raise RuntimeError("No production model found in registry!")

inference_service = InferenceService(model_path=production_model_entry["path"])


# In src/video_ai_system/services/inference_service.py
class InferenceService:
    def __init__(self, model_path: str):
        # The core logic remains the same, but it's now instantiated with a dynamic path.
        self.model = self._load_model(model_path)
    # ...
```

## 6. Infrastructure Considerations

- **Persistent Volume**: The `models/` directory, containing both the model artifacts (`*.onnx`) and the `registry.json` file, **must** be mounted as a persistent volume in the Docker environment (`docker-compose.yml`). This ensures that the registry is not lost when the container is restarted. This task will be handled by **DevOps Mode**.

## 7. Validation & Testing Plan

- **Unit Tests** ([`tests/test_model_registry_service.py`](tests/test_model_registry_service.py)):
  - `test_register_new_model`: Verify a model is added correctly.
  - `test_register_duplicate_version_fails`: Ensure registering the same version twice fails.
  - `test_list_models`: Verify all models are returned.
  - `test_list_models_by_name`: Verify filtering works.
  - `test_activate_model`: Verify status changes to 'production'.
  - `test_activate_demotes_old_production`: Verify the previous production model is demoted.
  - `test_get_production_model`: Verify the correct model is returned.
  - `test_file_locking`: Simulate concurrent writes to test the lock.
- **Integration Tests** ([`tests/test_registry_api.py`](tests/test_registry_api.py)):
  - Test the full lifecycle via API calls: `POST` to register, `GET` to verify, `PUT` to activate, `GET` again to confirm.
- **Application Startup Test**:
  - An integration test to ensure the `main` application correctly initializes the `InferenceService` with the production model from a pre-populated `registry.json`.

## 8. Next Tasks for Code Mode

- **T-MR-1**: Implement the `ModelRegistryService` class in [`src/video_ai_system/services/model_registry_service.py`](src/video_ai_system/services/model_registry_service.py) as specified.
- **T-MR-2**: Implement the API endpoints (`POST`, `GET`, `PUT`) in [`src/video_ai_system/main.py`](src/video_ai_system/main.py).
- **T-MR-3**: Modify the application startup logic in [`src/video_ai_system/main.py`](src/video_ai_system/main.py) to initialize `InferenceService` using the `ModelRegistryService`.
- **T-MR-4**: Implement the unit and integration tests as outlined in the "Validation & Testing Plan".
