# PLANNING.md - The Insight Engine Backend

## 1. Role Preamble

As the Lead Backend Engineer and System Architect for "The Insight Engine," I am responsible for the design, execution, and delivery of a robust, scalable, and secure backend infrastructure. This document outlines the comprehensive technical plan to achieve our project goals, focusing on production-grade implementation, cost-efficiency, and high availability. The architecture detailed herein is built upon deep expertise in Python, FastAPI, GCP serverless technologies, and modern AI/ML data pipelines. Every decision is backed by a clear rationale to meet our stringent non-functional requirements.

---

## 2. API Design & Endpoints

The API is the central gateway to our platform. We will use FastAPI for its high performance, asynchronous support, and automatic data validation, which are critical for a responsive user experience and developer efficiency.

### FastAPI Router Schema

Our API will be versioned (`/v1`) to ensure backward compatibility.

```python
# src/insight_engine/api/v1/router.py
from fastapi import APIRouter, Depends
from .endpoints import upload, summarize, clips

api_router = APIRouter(prefix="/v1")

# Include routers from endpoint-specific files
api_router.include_router(upload.router, tags=["Ingestion"])
api_router.include_router(summarize.router, tags=["AI Summarization"])
api_router.include_router(clips.router, tags=["Clip Extraction"])
```

- **`/v1/upload`**: Handles video ingestion.
- **`/v1/summarize`**: Manages summarization chat interactions.
- **`/v1/clips`**: Handles object-based clip extraction requests.

### Streaming: SSE vs. WebSocket

For real-time updates (summarization and clip progress), we will prioritize **Server-Sent Events (SSE)** with a WebSocket fallback.

-   **Rationale**: SSE is a simpler protocol, built on standard HTTP, making it firewall-friendly and easier to implement on both client and server. It is ideal for the unidirectional flow of data from server to client, which fits our use case perfectly. WebSockets, while more powerful for bidirectional communication, add unnecessary complexity here.
-   **Fallback Logic**: The frontend will attempt an SSE connection first. If it fails (e.g., due to an intermediary proxy stripping headers), it will automatically fall back to a WebSocket connection. The FastAPI backend will support both protocols on the relevant endpoints.

### Rate Limiting & Authentication

-   **Authentication**: We will use **JWT (JSON Web Tokens)** for stateless authentication. A token will be issued upon login and validated for all subsequent API requests using a FastAPI dependency. This approach is scalable and standard for modern web services.
-   **Rate Limiting**: To protect against abuse and ensure fair usage, we will implement token-bucket rate limiting using a middleware approach with Redis. This allows us to define flexible, per-user or per-tier limits.

```python
# src/insight_engine/middleware/auth.py
from fastapi import Request, Depends
from fastapi.security import OAuth2PasswordBearer
# ... JWT decoding and user lookup logic ...

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    # Logic to decode JWT and fetch user from DB
    ...
```

---

## 3. Core Pipelines & Services

### Summarization Pipeline (RAG)

This pipeline generates context-aware summaries from video content.

1.  **Orchestrator Trigger**: An API call to [`/summarize`](insight-engine/PLANNING_BACKEND.md:28) with a `video_id` and `query` initiates the process.
2.  **Query Embedding**: The user's query is converted into a vector using **OpenAI's `text-embedding-3-small` model** for a balance of performance and cost.
3.  **Vector DB Lookup**: The query vector is used to search for relevant chunks of transcript and visual metadata in our **Qdrant** vector database. Qdrant is chosen for its performance, scalability, and rich filtering capabilities.
4.  **Context Retrieval**: The top-k results are retrieved and passed to the language model.
5.  **LLM Invocation**: The context and query are fed to a powerful LLM (e.g., GPT-4o or Gemini 1.5 Pro) via the **AI Decision Engine**.
6.  **Streaming Response**: The response is streamed back to the client via SSE.
7.  **Caching**: We will use **Redis** to cache both embeddings and final LLM responses to reduce latency and cost for repeated queries.

### Clip Extraction Pipeline

This pipeline extracts clips based on semantic object queries.

1.  **Job Submission**: A request to [`/clips`](insight-engine/PLANNING_BACKEND.md:28) with a `video_id` and `object_query` (e.g., "all logos") is received.
2.  **Semantic Cache Check**: The orchestrator first checks Redis to see if an identical or semantically similar query has been processed recently. A cache hit returns the stored results immediately.
3.  **Pub/Sub Job Queue**: If it's a cache miss, a job is published to a **GCP Pub/Sub topic** (`clip-extraction-jobs`).
    -   **Rationale**: Pub/Sub decouples the API from the workers, enabling massive scalability and resilience. It allows us to handle ≥100 concurrent jobs easily.
4.  **Cloud Run FFmpeg Workers**: A pool of **Cloud Run** services, subscribed to the Pub/Sub topic, executes the jobs. Each worker:
    a.  Receives the job message.
    b.  Uses Google Vision API to get object timestamps (cost-effective).
    c.  Uses a containerized **FFmpeg** to slice the video from GCS.
    d.  Saves the resulting clip back to GCS.
    e.  Updates the job status in our metadata database (Firestore).
5.  **Retry/Dead-Letter Pattern**:
    -   **Retries**: Pub/Sub automatically retries message delivery on worker failure.
    -   **Dead-Letter Queue (DLQ)**: After a configured number of failed attempts, the message is moved to a DLQ for manual inspection, preventing poison pills from halting the pipeline.

### AI Decision Engine

This service dynamically selects the best AI model for a given task to optimize for cost, latency, and quality.

1.  **Metrics Collection**: We will use **Cloud Monitoring** to collect real-time data on API latency, cost-per-call (via custom metrics), and error rates for each model we use (e.g., Gemini Pro vs. GPT-4o, different embedding models).
2.  **Experiment Tracking**: **MLflow** will be used to log experiments, tracking model versions, prompt templates, and their resulting performance (quality scores from human feedback, latency, cost).
3.  **Dynamic Model Selection Algorithm**: A simple but effective algorithm will run within the orchestrator.

```python
# src/insight_engine/core/ai_decision_engine.py
import mlflow

def select_model(task: str, user_tier: str = "standard"):
    """Dynamically selects a model based on tracked metrics."""
    # Example logic: Prioritize cost for standard tier, quality for premium
    if user_tier == "premium":
        # Fetch best-performing model from MLflow for the given task
        best_model = mlflow.search_runs(filter_string=f"tags.task = '{task}'")
        return best_model.iloc[0]["tags.model_name"]
    else:
        # Default to a cost-effective model
        return "gemini-1.5-flash"
```

---

## 4. Infrastructure as Code

We will use **Terraform** to manage all GCP resources, ensuring our infrastructure is version-controlled, repeatable, and automated.

### Terraform Modules

-   **`gcs`**: Creates GCS buckets for video ingestion and clip storage. Includes a DLP inspection job trigger on object creation.
-   **`pubsub`**: Defines Pub/Sub topics (`clip-extraction-jobs`) and subscriptions, including DLQ configuration.
-   **`cloud-run`**: Deploys our FastAPI orchestrator and FFmpeg worker services. Manages IAM, environment variables, and autoscaling policies.
-   **`iam`**: Manages service accounts and permissions, adhering to the principle of least privilege.

### Example `main.tf`

```terraform
# infra/main.tf
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# Use a remote backend for state management
terraform {
  backend "gcs" {
    bucket = "the-insight-engine-tfstate"
    prefix = "prod"
  }
}

# GCS Buckets for video ingestion and processed clips
module "storage" {
  source      = "./modules/gcs"
  project_id  = var.gcp_project_id
  location    = var.gcp_region
  bucket_name = "insight-engine-ingestion"
}

# Pub/Sub for asynchronous job processing
module "pubsub" {
  source     = "./modules/pubsub"
  project_id = var.gcp_project_id
  topic_name = "clip-extraction-jobs"
}

# Cloud Run service for the main FastAPI orchestrator
module "api_service" {
  source          = "./modules/cloud_run"
  project_id      = var.gcp_project_id
  service_name    = "api-orchestrator"
  container_image = "gcr.io/${var.gcp_project_id}/api-orchestrator:latest"
  # ... other vars like env, secrets, etc.
}
```

---

## 5. Data Schemas & Validation

### Pydantic & Zod

-   **Pydantic**: We will use Pydantic models extensively in FastAPI for request/response validation. This provides strong data integrity at the API boundary.
-   **Zod-style Schemas**: To ensure consistency between the Python backend and the Next.js frontend, we will auto-generate Zod schemas from our Pydantic models or maintain a shared JSON schema definition.

```python
# src/insight_engine/schemas/video.py
from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
import datetime

class VideoMetadata(BaseModel):
    video_id: UUID
    status: str = Field(..., description="e.g., 'processing', 'completed', 'failed'")
    gcs_url: HttpUrl
    created_at: datetime.datetime

class SummarizeRequest(BaseModel):
    video_id: UUID
    query: str
```

### Database Schema (Firestore)

We will use **Firestore** for storing job metadata.

-   **Rationale**: Firestore is a serverless, NoSQL database that scales automatically and integrates seamlessly with other GCP services like Cloud Functions and Cloud Run. Its document-based model is a perfect fit for our flexible job metadata.

**Collections:**

-   `videos`: Stores metadata for each uploaded video (`video_id`, `gcs_url`, `status`, `user_id`).
-   `jobs`: Tracks the status of summarization or clip extraction jobs (`job_id`, `video_id`, `type`, `status`, `result_url`).

---

## 6. Security & Compliance

### DLP Integration

-   **Flow**:
    1.  A video is uploaded to the ingestion GCS bucket.
    2.  A Cloud Function is triggered, which calls the Google Speech-to-Text API to generate a transcript.
    3.  The transcript text is passed to the **Google Cloud DLP (Data Loss Prevention) API** to inspect for PII (e.g., names, credit card numbers).
    4.  The DLP API returns redacted text and a report.
    5.  The redacted transcript is stored for the RAG pipeline.

```python
# FastAPI dependency to inject DLP client
# src/insight_engine/dependencies.py
import google.cloud.dlp_v2

def get_dlp_client():
    return google.cloud.dlp_v2.DlpServiceClient()

# Example usage in an endpoint
@router.post("/redact")
async def redact_text(text: str, dlp_client = Depends(get_dlp_client)):
    # ... call dlp_client.deidentify_content ...
    return {"redacted_text": ...}
```

### Secret Management

-   **Google Secret Manager**: All secrets (API keys, database credentials, JWT secret) will be stored in Secret Manager.
-   **IAM Integration**: Cloud Run services will be granted IAM roles to access specific secrets at runtime. This avoids hardcoding secrets in code or environment variables.
-   **Rotation Policy**: We will enforce a 90-day automatic rotation policy on critical secrets.

### API Gateway

-   **WAF**: We will place **Google API Gateway** in front of our Cloud Run services. It will provide a Web Application Firewall (WAF) with pre-configured rules (e.g., OWASP Top 10) to protect against common threats like SQL injection and XSS.
-   **Rate Limiting & API Keys**: The gateway will also handle API key validation and global rate limiting before requests even hit our application, providing an additional layer of defense.

---

## 7. Scalability & Resiliency

### Cloud Run Autoscaling

-   **Concurrency**: We will set a concurrency target of **80-100** requests per container instance. This is a good starting point for I/O-bound applications like our API orchestrator.
-   **Max Instances**: We will set a `max-instances` limit to control costs, while ensuring it's high enough to handle peak load (e.g., `100` for the orchestrator, `200` for FFmpeg workers).
-   **CPU-based Scaling**: For CPU-intensive workers like FFmpeg, we will scale based on CPU utilization (e.g., target 60%) in addition to concurrency.

### Pub/Sub & Vector DB

-   **Pub/Sub Throughput**: Pub/Sub scales automatically, so no specific tuning is needed initially. We will monitor throughput and latency to ensure it meets our needs.
-   **Vector DB Sharding**: Qdrant supports horizontal scaling via sharding. As our dataset grows beyond 1 million vectors, we will shard our collections across multiple nodes to maintain <100ms search latency.

### Circuit Breaker Pattern

To prevent a failing downstream service (e.g., a third-party AI API) from cascading failures through our system, we will implement a circuit breaker.

-   **Implementation**: We will use a library like `pybreaker` in our API client wrappers.
-   **Logic**: After a certain number of consecutive failures, the circuit "opens," and subsequent calls fail immediately without attempting to contact the service. After a timeout, the circuit moves to a "half-open" state to test if the service has recovered.

---

## 8. Testing Strategy

### Pytest Fixtures & Mocks

We will use `pytest` as our testing framework.

-   **Local Emulators**: For local testing, we will use official emulators for Pub/Sub and GCS.
-   **Mocking Fixtures**: We will create `pytest` fixtures to provide mocked clients for external services (OpenAI, Google APIs), allowing us to test our business logic in isolation.

```python
# tests/conftest.py
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_gcs_client():
    """Mocks the GCS client."""
    return MagicMock()

@pytest.fixture
def mock_pubsub_publisher():
    """Mocks the Pub/Sub publisher client."""
    return MagicMock()
```

### Integration & Load Testing

-   **Integration Tests**: We will write end-to-end tests that simulate the full user workflow: upload a test video, poll for processing completion, and then hit the `/summarize` and `/clips` endpoints.
-   **Load Testing**: We will use **k6** (or Locust) to script realistic load test scenarios.
    -   **Scenario 1 (Concurrency)**: Simulate 100+ concurrent video uploads and clip extraction jobs.
    -   **Scenario 2 (Stress Test)**: Ramp up users to identify the breaking point of the system.
    -   **Metrics**: We will measure p95/p99 latency, error rates, and container instance count.

---

## 9. CI/CD Pipeline

We will use **GitHub Actions** for our CI/CD pipeline.

### Workflow (`.github/workflows/ci.yml`)

The workflow will be triggered on every push to `main` or pull request.

1.  **Lint & Type Check**: Run `flake8` and `mypy` to enforce code quality.
2.  **Test**: Run `pytest` with coverage reporting.
3.  **Security Scan**: Run **Trivy** to scan our Docker container for vulnerabilities.
4.  **Build & Push Docker Image**: Build the FastAPI application Docker image and push it to Google Container Registry (GCR).
5.  **Deploy to Preview**: Deploy the new image to a sandboxed "preview" Cloud Run environment.
6.  **Promote to Production**: On a merge to `main`, a manual approval step will trigger the promotion of the GCR image to the production Cloud Run service.

### Canary Deployments

-   **Strategy**: For production deployments, we will use Cloud Run's built-in traffic splitting to perform canary releases. We will initially direct a small percentage of traffic (e.g., 5%) to the new revision.
-   **Automated Rollback**: We will configure Cloud Monitoring alerts for key metrics (e.g., increased error rate, high latency) on the new revision. If an alert is triggered, a Cloud Function or webhook will automatically roll back the deployment to the previous stable version.

---

## 10. Monitoring & Observability

### Dashboards & Tracing

-   **Cloud Monitoring**: We will create a centralized dashboard in Cloud Monitoring to track:
    -   **API Metrics**: Latency (p50, p95, p99), request count, error rate (4xx/5xx).
    -   **Pipeline Metrics**: Pub/Sub queue depth, number of unprocessed messages, worker execution time.
    -   **Cost Metrics**: A dashboard breaking down GCP costs by service (Cloud Run, Vision API, GCS) to ensure we stay within our budget of ≤$0.10 per video processing hour.
-   **Sentry**: We will integrate the Sentry SDK into our FastAPI app for real-time exception tracking. Releases will be tagged, allowing us to correlate errors with specific deployments.

### Custom Metrics

For deeper insights, we will export custom metrics using a **Prometheus exporter**.

-   **Metrics to Export**:
    -   `job_duration_seconds`: A histogram of how long different types of jobs take.
    -   `queue_depth_total`: The current depth of the Pub/Sub job queue.
    -   `cache_hit_ratio`: The ratio of cache hits to misses in our Redis layer.
-   **Visualization**: These metrics can be scraped by Prometheus and visualized in Grafana or sent to Cloud Monitoring.

---

## 11. Roadmap & Milestones

This 10-week plan is divided into three phases, prioritizing an MVP followed by iterative enhancement.

| Phase | Weeks | Key Objectives & Deliverables | KPIs |
| :--- | :--- | :--- | :--- |
| **Phase 1: MVP Foundation** | 1-4 | - Core API endpoints (`/upload`, `/summarize`, `/clips`)<br>- Basic Summarization & Clip pipelines (no cache/DLQ)<br>- Terraform for core infra (GCS, Cloud Run)<br>- CI/CD pipeline setup | - Successful E2E workflow for both playgrounds<br>- Deployments automated |
| **Phase 2: Scale & Optimize** | 5-8 | - Implement Pub/Sub, DLQs, and worker retries<br>- Add Redis caching (semantic & response)<br>- Build v1 of AI Decision Engine<br>- Full security implementation (DLP, WAF, Secret Mgr) | - Throughput ≥100 concurrent jobs<br>- Latency <100ms for metadata<br>- Cache hit rate >50% |
| **Phase 3: Harden & Extend** | 9-10 | - Advanced monitoring & automated rollback<br>- Load testing and performance tuning<br>- Full test coverage (>80%)<br>- Begin work on user-facing API documentation | - 99.9% Uptime SLA met<br>- Cost ≤$0.10 per video hour<br>- Final security audit passed |