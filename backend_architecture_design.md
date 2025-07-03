# Backend Architecture Design (Phase 0)

This document outlines the initial backend architecture for the AI Video Analysis System. The design focuses on modularity, scalability, and observability from the ground up, in line with the requirements for Phase 0.

## 1. Application Structure (FastAPI)

A modular directory structure is proposed to ensure separation of concerns, making the application easier to develop, test, and maintain.

```
video-ai-system/
├── src/
│   └── video_ai_system/
│       ├── api/
│       │   ├── __init__.py
│       │   ├── endpoints/
│       │   │   ├── __init__.py
│       │   │   ├── analysis.py   # Handles /analyze endpoint
│       │   │   └── system.py     # Handles /health, /metrics
│       │   └── models.py         # Pydantic request/response models
│       ├── services/
│       │   ├── __init__.py
│       │   └── analysis_service.py # Business logic for video analysis
│       ├── modules/
│       │   ├── __init__.py
│       │   └── qdrant_client.py  # Module for interacting with Qdrant
│       ├── core/
│       │   ├── __init__.py
│       │   └── config.py         # Configuration loading and validation
│       ├── __init__.py
│       └── main.py               # FastAPI app instantiation and router setup
├── tests/
│   ├── __init__.py
│   ├── test_api.py
│   └── test_services.py
├── config/
│   ├── config.schema.json
│   └── config.yml
├── docker-compose.yml
└── Dockerfile
```

### Key Components:

- **`api/`**: Contains all FastAPI-related code.
  - **`endpoints/`**: Each file corresponds to a logical grouping of API endpoints.
  - **`models.py`**: Defines Pydantic models for request and response data validation.
- **`services/`**: Holds the core business logic. It is decoupled from the API layer and can be reused.
- **`modules/`**: Contains clients or wrappers for external services like the Qdrant vector database.
- **`core/`**: Manages application-wide concerns like configuration.
- **`main.py`**: The entry point for the FastAPI application.

## 2. API Layer

The initial API provides endpoints for submitting analysis tasks and monitoring the system's health.

### Endpoints

#### `POST /analyze` (Asynchronous)

- **Description**: Submits a video for analysis. The request is immediately accepted, and an async job is queued for processing.
- **Request Body**:
  ```json
  {
    "video_url": "string",
    "callback_url": "string"
  }
  ```
- **Response (202 Accepted)**:
  ```json
  {
    "job_id": "string",
    "status": "queued"
  }
  ```
- **Pydantic Models (`api/models.py`)**:

  ```python
  from pydantic import BaseModel, Field
  from uuid import UUID, uuid4

  class AnalysisRequest(BaseModel):
      video_url: str
      callback_url: str

  class AnalysisResponse(BaseModel):
      job_id: UUID = Field(default_factory=uuid4)
      status: str = "queued"
  ```

#### `GET /health`

- **Description**: A simple health check endpoint.
- **Response (200 OK)**:
  ```json
  {
    "status": "ok"
  }
  ```

#### `GET /metrics`

- **Description**: Exposes application metrics in a Prometheus-compatible format. This will be implemented using a library like `starlette-prometheus`.
- **Response (200 OK)**: Prometheus metrics text.

## 3. Configuration Management

Configuration will be managed via a YAML file with validation against a Pydantic schema. This allows for clear, structured, and type-safe configuration.

### `config/config.yml`

```yaml
qdrant:
  host: "qdrant"
  port: 6333
  api_key: "your-secret-key" # Loaded from environment variable

logging:
  level: "INFO"
```

### Configuration Loading (`core/config.py`)

A Pydantic model will be used to parse and validate the configuration file. The application will use a library like `watchfiles` to monitor the config file for changes and trigger a hot-reload mechanism.

```python
import yaml
from pydantic import BaseModel
from watchfiles import awatch

class QdrantConfig(BaseModel):
    host: str
    port: int
    api_key: str

class LoggingConfig(BaseModel):
    level: str

class AppConfig(BaseModel):
    qdrant: QdrantConfig
    logging: LoggingConfig

config: AppConfig

def load_config(path="config/config.yml") -> AppConfig:
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    return AppConfig(**data)

async def watch_config(path="config/config.yml"):
    global config
    async for changes in awatch(path):
        print("Configuration changed, reloading...")
        config = load_config(path)

# Initial load
config = load_config()
```

The `watch_config` coroutine will be started as a background task when the FastAPI application boots up.

## 4. Containerization (`docker-compose.yml`)

Docker Compose will be used to orchestrate the application and its dependencies for local development and testing.

```yaml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src
      - ./config:/app/config
    environment:
      - QDRANT_API_KEY=${QDRANT_API_KEY} # Securely pass secrets
    depends_on:
      - qdrant
    command: uvicorn video_ai_system.main:app --host 0.0.0.0 --port 8000 --reload

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - ./qdrant_storage:/qdrant/storage

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
```

### Service Descriptions:

- **`app`**: The main FastAPI application service. It mounts the source code and configuration for live-reloading during development.
- **`qdrant`**: The Qdrant vector database service, with persistent storage mounted to the host.
- **`prometheus`**: A placeholder for the Prometheus monitoring service. Configuration will be added to scrape metrics from the `/metrics` endpoint.
- **`grafana`**: A placeholder for the Grafana visualization service.
