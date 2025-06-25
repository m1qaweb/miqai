import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from pathlib import Path
import json

from video_ai_system.main import app, get_model_registry_service
from video_ai_system.services.model_registry_service import ModelRegistryService
from video_ai_system.config import settings

@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """
    Provides a TestClient with a fully isolated ModelRegistryService for each test.
    """
    # Setup: Create a temporary directory for the model registry
    registry_path = tmp_path / "test_registry.json"
    api_key_file = tmp_path / "api_key.txt"
    api_key_file.write_text("test-registry-api-key")

    settings.MODEL_REGISTRY_PATH = str(registry_path)
    settings.DEFAULT_MODEL_NAME = "test-model"
    settings.API_KEY_SECRET_FILE = str(api_key_file)

    def override_get_model_registry_service():
        return ModelRegistryService(registry_path=str(registry_path))

    app.dependency_overrides[get_model_registry_service] = override_get_model_registry_service

    # Mock services that are not relevant to these tests
    with patch("video_ai_system.main.arq.create_pool", new_callable=AsyncMock), \
         patch("video_ai_system.main.QdrantClient"), \
         patch("video_ai_system.main.VectorDBService"), \
         patch("video_ai_system.main.ActiveLearningService"), \
         patch("video_ai_system.main.DriftDetectionService"), \
         patch("video_ai_system.main.AnalyticsService"):
        with TestClient(app) as c:
            yield c

    # Teardown: Clear dependency overrides after each test
    app.dependency_overrides.clear()


def get_headers():
    return {"X-API-Key": "test-registry-api-key"}


def test_register_model_endpoint_unauthorized(client: TestClient):
    """Test that the endpoint is protected."""
    response = client.post("/api/v1/registry/models", json={})
    assert response.status_code == 401


def test_register_model_endpoint(client: TestClient):
    """Test the POST /api/v1/registry/models endpoint."""
    response = client.post(
        "/api/v1/registry/models",
        headers=get_headers(),
        json={
            "model_name": "api-test-model",
            "path": "models/api-test-model/v1/model.onnx",
            "metadata": {"source": "api_test"}
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["model_name"] == "api-test-model"
    assert data["version"] == 1
    assert data["status"] == "staging"
    assert data["metadata"]["source"] == "api_test"

def test_list_models_endpoint(client: TestClient):
    """Test the GET /api/v1/registry/models endpoint."""
    # First, register a model to ensure the list is not empty
    client.post(
        "/api/v1/registry/models",
        headers=get_headers(),
        json={"model_name": "list-model", "path": "path/v1"}
    )
    
    response = client.get("/api/v1/registry/models", headers=get_headers())
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(m["model_name"] == "list-model" for m in data)

def test_list_models_empty(client: TestClient):
    """Test listing models when the registry is empty."""
    response = client.get("/api/v1/registry/models", headers=get_headers())
    assert response.status_code == 200
    assert response.json() == []

def test_list_models_filtered_endpoint(client: TestClient):
    """Test filtering models by name via the API."""
    client.post("/api/v1/registry/models", headers=get_headers(), json={"model_name": "filter-a", "path": "p1"})
    client.post("/api/v1/registry/models", headers=get_headers(), json={"model_name": "filter-b", "path": "p2"})

    response = client.get("/api/v1/registry/models?model_name=filter-a", headers=get_headers())
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["model_name"] == "filter-a"

def test_activate_model_endpoint_and_inference_reload(client: TestClient):
    """
    Test the full lifecycle: register, activate, and verify inference service reload.
    """
    # 1. Register two versions of a model
    reg_response_v1 = client.post(
        "/api/v1/registry/models",
        headers=get_headers(),
        json={"model_name": "reload-test", "path": "path/to/model_v1.onnx"}
    )
    assert reg_response_v1.status_code == 201
    
    reg_response_v2 = client.post(
        "/api/v1/registry/models",
        headers=get_headers(),
        json={"model_name": "reload-test", "path": "path/to/model_v2.onnx"}
    )
    assert reg_response_v2.status_code == 201

    # 2. Activate version 2
    with patch("video_ai_system.main.InferenceService") as mock_inference_service:
        act_response = client.put(
            "/api/v1/registry/models/activate",
            headers=get_headers(),
            json={"model_name": "reload-test", "version": 2}
        )
        assert act_response.status_code == 200
        data = act_response.json()
        assert data["status"] == "production"
        assert data["version"] == 2

        # 3. Verify that the InferenceService was re-initialized with the correct path
        mock_inference_service.assert_called_once_with(model_path="path/to/model_v2.onnx")

def test_activate_nonexistent_model_returns_404(client: TestClient):
    """Test that activating a model that doesn't exist returns a 404 error."""
    response = client.put(
        "/api/v1/registry/models/activate",
        headers=get_headers(),
        json={"model_name": "nonexistent", "version": 1}
    )
    assert response.status_code == 404
