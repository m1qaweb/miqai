# AI Video Analysis System

[![CI Pipeline](https://github.com/YOUR_GITHUB_USERNAME/video-ai-system/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_GITHUB_USERNAME/video-ai-system/actions/workflows/ci.yml)

A modular system for asynchronous, self-supervised video analysis. This project uses FastAPI for the API, ARQ (Asynchronous Redis Queue) for background task processing, and a structured model registry for managing different AI models.

## Running the System (Docker)

The recommended way to run the entire application stack is with Docker Compose. This includes the FastAPI server, ARQ worker, n8n, Qdrant, and the observability stack. Qdrant is a vector database used for storing and querying video frame embeddings and their associated metadata.

### 1. Prerequisites

- **Docker and Docker Compose:** Ensure they are installed on your system.
- **Clone the Repository:**
  ```bash
  git clone https://github.com/YOUR_GITHUB_USERNAME/video-ai-system.git
  cd video-ai-system
  ```
- **Configure Secrets:** Create a `secrets/` directory in the root of the `video-ai-system` directory and add the required secret files.

### 2. Secrets Management

This system uses Docker Secrets to manage sensitive information. Instead of a `.env` file, you must create a `secrets` directory in the project root and place the following files inside it. Each file should contain only the secret value.

- `api_key.txt`: Your desired API key for accessing protected API endpoints.
- `grafana_admin_password.txt`: The admin password for the Grafana dashboard.
- `n8n_secure_cookie.txt`: A secure, random string for the n8n cookie.

**Example:**

```bash
mkdir secrets
echo "your-super-secret-api-key" > secrets/api_key.txt
echo "your-grafana-password" > secrets/grafana_admin_password.txt
echo "a-very-long-and-random-string-for-n8n" > secrets/n8n_secure_cookie.txt
```

### 3. Model Storage Setup (One-Time Task)

The system now uses a persistent Docker volume for the `models/` directory. This means that models are no longer bundled with the Docker image and their data will be preserved across container restarts.

Before running the system for the first time, you must perform a one-time setup to populate the model storage:

1.  **Create the models directory:**

    ```bash
    mkdir -p models
    ```

2.  **Download the initial model:**
    The `get_model.sh` script is located in the `video-ai-system/models` directory. Make sure you are in the `video-ai-system` directory when running it.

    ```bash
    # This script downloads the default model into the models/ directory.
    ./models/get_model.sh
    ```

3.  **Create the model registry file:**
    Create a file named `models/registry.json` with the following content. This file tells the system which models are available.

    ```json
    {
      "yolov8n": {
        "path": "/app/models/yolov8n.onnx",
        "type": "object_detection"
      }
    }
    ```

### 3. Start the System

To build and start all services, run the following single command:

```bash
docker-compose up --build
```

This command will build the Docker image and start all services (FastAPI, ARQ Worker, n8n, Redis, etc.) in the foreground. To run in the background, add the `-d` flag.

### 4. Accessing Services

- **API Server:** `http://127.0.0.1:8000`
- **Grafana Dashboard:** `http://localhost:3000` (Login: `admin` / `admin`)
- **n8n Workflow Editor:** `http://localhost:5678`

### 5. Stopping the System

```bash
docker-compose down
```

## API Usage

**Authentication:** All API endpoints under `/api/v1` are protected and require a valid API key to be sent in the `X-API-Key` header.

### POST /analyze

Submits a video for asynchronous analysis by providing a path to the file.

- **Method**: `POST`
- **Path**: `/analyze`
- **Request Body**:
  ```json
  {
    "file_path": "/data/videos/input.mp4",
    "callback_url": "http://optional-webhook-url.com/callback"
  }
  ```
- **Success Response**: `202 Accepted` with a task ID.
  ```json
  {
    "task_id": "some-unique-task-id",
    "status_endpoint": "/results/some-unique-task-id"
  }
  ```

**Example with `curl`:**

```bash
curl -X POST http://localhost:8000/analyze \
-H "Content-Type: application/json" \
-H "X-API-Key: your-super-secret-api-key" \
-d '{"file_path": "/data/videos/input1.mp4"}'
```

_Note: The `file_path` must be accessible from within the Docker container's filesystem. The `video-ai-system/data` directory on the host is mounted to `/data` inside the containers._

## Model Management

### Shadow Testing

Shadow testing allows you to compare a candidate model against the production model using live data without impacting the primary results. The system runs both models in parallel, logs the outputs and performance metrics of each, and allows you to compare them to make an informed decision about promoting the candidate model to production.

#### Enabling Shadow Testing

To enable shadow testing, you must configure the `SHADOW_MODEL_NAME` and `SHADOW_MODEL_VERSION` in your configuration file (e.g., `config/development.json`), not via environment variables.

When these variables are set, the `ShadowTestingService` will be activated. For every incoming analysis request, it will run inference with both the primary production model and the specified shadow model.

#### Viewing Shadow Test Results

The comparison results and performance metrics are logged and can also be accessed via an API endpoint.

- **Endpoint**: `GET /api/v1/shadow-testing/results`
- **Method**: `GET`
- **Description**: Retrieves a summary of the most recent shadow testing comparisons. This includes metrics like latency, throughput, and any custom output comparisons defined for the models.

**Example with `curl`:**

```bash
curl -X GET http://localhost:8000/api/v1/shadow-testing/results
```

The results from this endpoint, combined with the detailed logs, provide the necessary data to confidently decide whether to promote the candidate model.

## Local Development & Testing (Optional)

If you need to run tests or develop outside of Docker:

### 1. Install Dependencies

This project uses `pyproject.toml`. Install the project in editable mode with dev dependencies.

```bash
pip install -e .[dev]
```

### 2. Run Tests

Execute the test suite from the project root:

```bash
pytest
```

## Data Annotation (CVAT)

CVAT (Computer Vision Annotation Tool) is used in this project for labeling video frames and other data, which is essential for training and fine-tuning our AI models, particularly for active learning workflows.

### 1. Start the CVAT Stack

To start the CVAT services, run the following command from the `video-ai-system` directory:

```bash
docker-compose -f docker-compose.cvat.yml up -d
```

The CVAT UI will be available at `http://localhost:8080`.

### 2. Create a Superuser Account

After starting the services, you need to create an admin account. Execute the following command and follow the prompts to set up your username and password:

```bash
docker exec -it cvat_server bash -ic 'python3 ~/manage.py createsuperuser'
```
