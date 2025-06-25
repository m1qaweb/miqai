import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from video_ai_system import main, config
from video_ai_system.main import app


@pytest.fixture
def monkeypatch_settings(monkeypatch, tmp_path):
    """Monkeypatches the global settings for testing."""
    # Create a dummy secret file for the API key
    api_key_file = tmp_path / "api_key.txt"
    api_key_file.write_text("test-api-key")

    config_content = {"pipelines": {"production": [], "shadow": []}}
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config_content))

    # Create dummy model files required by the default pipeline config
    model_registry_path = tmp_path / "model_registry"
    (model_registry_path / "feature_extractor" / "v1").mkdir(parents=True)
    (model_registry_path / "feature_extractor" / "v1" / "model.placeholder").touch()

    monkeypatch.setattr(config.settings, "API_KEY_SECRET_FILE", str(api_key_file))
    monkeypatch.setattr(config.settings, "PIPELINE_CONFIG_PATH", str(config_file))
    monkeypatch.setattr(config.settings, "MODEL_REGISTRY_PATH", str(model_registry_path))
    monkeypatch.setattr(config.settings, "REDIS_DSN", "redis://fakeredis:6379/0")


@pytest.fixture
def mock_arq_pool(monkeypatch):
    """Mocks the arq.create_pool and arq.Job to avoid real Redis connections."""
    mock_pool = AsyncMock()
    mock_job_enqueued = MagicMock()
    mock_job_enqueued.job_id = "test_task_123"
    mock_pool.enqueue_job.return_value = mock_job_enqueued

    mock_job_instance = MagicMock()
    mock_job_instance.status = AsyncMock(return_value='complete')
    mock_job_instance.result = AsyncMock(return_value={"analysis": "ok"})

    def mock_job_init(job_id, redis, _queue_name='arq:queue'):
        return mock_job_instance

    monkeypatch.setattr(main, "Job", mock_job_init)
    monkeypatch.setattr(main.arq, "create_pool", AsyncMock(return_value=mock_pool))
    return mock_pool


@pytest.fixture
def client(monkeypatch_settings, mock_arq_pool):
    """A test client for the app, with patched settings and Redis."""
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_check(client: TestClient):
    headers = {"X-API-Key": "test-api-key"}
    response = client.get("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_check_unauthorized(client: TestClient):
    response = client.get("/api/v1/health", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401

    response_no_key = client.get("/api/v1/health")
    assert response_no_key.status_code == 401


@pytest.mark.asyncio
async def test_analyze_and_get_results(client: TestClient):
    """
    Tests the full asynchronous analysis flow:
    1. POST to /analyze to submit a job.
    2. GET from /results/{task_id} to retrieve the outcome.
    """
    headers = {"X-API-Key": "test-api-key"}
    # 1. Submit the job
    analyze_response = client.post(
        "/api/v1/analyze",
        json={"file_path": "/path/to/video.mp4"},
        headers=headers
    )
    assert analyze_response.status_code == 202
    data = analyze_response.json()
    task_id = data["task_id"]
    assert task_id == "test_task_123"
    assert data["status_endpoint"] == f"/api/v1/results/{task_id}"

    # 2. Poll for the result
    result_response = client.get(f"/api/v1/results/{task_id}", headers=headers)
    assert result_response.status_code == 200
    result_data = result_response.json()
    assert result_data["task_id"] == task_id
    assert result_data["status"] == "SUCCESS"
    assert result_data["result"] == {"analysis": "ok"}
    assert result_data["error_message"] is None
