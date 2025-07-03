import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from video_ai_system.api.governance_routes import (
    get_audit_service,
    get_drift_detection_service,
    get_model_registry_service,
    get_shadow_testing_service,
    router,
)
from video_ai_system.services.audit_service import AuditLogEntry
from video_ai_system.services.drift_detection_service import DriftAlert
from video_ai_system.services.model_registry_service import ModelVersion
from video_ai_system.services.shadow_testing_service import ShadowTestResult


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app instance with the governance router."""
    app = FastAPI()
    app.include_router(router)
    return app




@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Provides a test client for making requests to the app."""
    return TestClient(app)


@pytest.fixture
def mock_audit_service() -> MagicMock:
    """Fixture for a mocked AuditService."""
    return MagicMock()


@pytest.fixture
def mock_model_registry_service() -> MagicMock:
    """Fixture for a mocked ModelRegistryService."""
    return MagicMock()


@pytest.fixture
def mock_shadow_testing_service() -> MagicMock:
    """Fixture for a mocked ShadowTestingService."""
    return MagicMock()


@pytest.fixture
def mock_drift_detection_service() -> MagicMock:
    """Fixture for a mocked DriftDetectionService."""
    return MagicMock()


@pytest.fixture(autouse=True)
def override_dependencies(
    app: FastAPI,
    mock_audit_service: MagicMock,
    mock_model_registry_service: MagicMock,
    mock_shadow_testing_service: MagicMock,
    mock_drift_detection_service: MagicMock,
):
    """Override dependencies for the test session."""
    app.dependency_overrides[get_audit_service] = lambda: mock_audit_service
    app.dependency_overrides[get_model_registry_service] = (
        lambda: mock_model_registry_service
    )
    app.dependency_overrides[get_shadow_testing_service] = (
        lambda: mock_shadow_testing_service
    )
    app.dependency_overrides[get_drift_detection_service] = (
        lambda: mock_drift_detection_service
    )
    yield
    app.dependency_overrides.clear()


def test_list_models(
    app: FastAPI, mock_model_registry_service: MagicMock, client: TestClient
):
    """Test the /models endpoint."""
    mock_models = [
        ModelVersion(name="model-a", version="1.0.0", stage="Production"),
        ModelVersion(name="model-a", version="1.1.0", stage="Staging"),
    ]
    mock_model_registry_service.get_all_models_with_versions = AsyncMock(
        return_value=mock_models
    )

    response = client.get("/governance/models")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "model-a"
    assert data[1]["stage"] == "Staging"


def test_get_shadow_test_results_found(
    app: FastAPI, mock_shadow_testing_service: MagicMock, client: TestClient
):
    """Test getting shadow test results when they exist."""
    mock_result = ShadowTestResult(
        model_name="model-b",
        model_version="2.0.0",
        total_requests=100,
        mismatches=5,
        latency_comparison={"p50_candidate": 50, "p50_production": 48},
    )
    mock_shadow_testing_service.get_results = AsyncMock(return_value=mock_result)

    response = client.get("/governance/shadow_results/model-b/2.0.0")
    assert response.status_code == 200
    assert response.json()["mismatches"] == 5


def test_get_shadow_test_results_not_found(
    app: FastAPI, mock_shadow_testing_service: MagicMock, client: TestClient
):
    """Test getting shadow test results when they do not exist."""
    mock_shadow_testing_service.get_results = AsyncMock(return_value=None)
    response = client.get("/governance/shadow_results/model-c/3.0.0")
    assert response.status_code == 404


def test_get_drift_alerts(
    app: FastAPI, mock_drift_detection_service: MagicMock, client: TestClient
):
    """Test the /drift_alerts endpoint."""
    mock_alerts = [
        DriftAlert(
            alert_id="alert1",
            model_name="model-d",
            drift_score=0.8,
            threshold=0.5,
            comparison_window_start=datetime.now(timezone.utc),
            comparison_window_end=datetime.now(timezone.utc),
        )
    ]
    mock_drift_detection_service.get_all_alerts = AsyncMock(return_value=mock_alerts)

    response = client.get("/governance/drift_alerts")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["alert_id"] == "alert1"


def test_trigger_retraining(
    app: FastAPI,
    mock_drift_detection_service: MagicMock,
    mock_audit_service: MagicMock,
    client: TestClient,
):
    """Test triggering the retraining hook."""
    alert = DriftAlert(
        alert_id="alert2",
        model_name="model-e",
        drift_score=0.6,
        threshold=0.4,
        comparison_window_start=datetime.now(timezone.utc),
        comparison_window_end=datetime.now(timezone.utc),
    )
    mock_drift_detection_service.get_alert = AsyncMock(return_value=alert)
    mock_drift_detection_service.trigger_retraining_hook = AsyncMock()
    mock_audit_service.log = AsyncMock()

    response = client.post("/governance/trigger_retraining/alert2")
    assert response.status_code == 202
    assert response.json() == {"message": "Retraining process has been initiated."}

    # Allow background tasks to run
    # In a real async test, we would sleep here.
    # For a sync test, we assume the background task is scheduled.
    pass

    mock_drift_detection_service.trigger_retraining_hook.assert_called_once_with("model-e")
    mock_audit_service.log.assert_called_once()


def test_decide_on_rollout_approve(
    app: FastAPI,
    mock_model_registry_service: MagicMock,
    mock_audit_service: MagicMock,
    client: TestClient,
):
    """Test approving a model rollout."""
    mock_model_registry_service.transition_model_stage = AsyncMock()
    mock_audit_service.log = AsyncMock()

    payload = {
        "model_name": "model-f",
        "model_version": "4.0.0",
        "approved": True,
        "reason": "Looks good",
    }
    response = client.post("/governance/rollout_decision", json=payload)
    assert response.status_code == 202


    mock_model_registry_service.transition_model_stage.assert_called_once_with(
        name="model-f", version="4.0.0", stage="Production"
    )
    mock_audit_service.log.assert_called_once()
    call_args = mock_audit_service.log.call_args[1]
    assert call_args["action"] == "MODEL_ROLLOUT_APPROVED"


def test_decide_on_rollout_reject(
    app: FastAPI,
    mock_model_registry_service: MagicMock,
    mock_audit_service: MagicMock,
    client: TestClient,
):
    """Test rejecting a model rollout."""
    mock_model_registry_service.transition_model_stage = AsyncMock()
    mock_audit_service.log = AsyncMock()

    payload = {
        "model_name": "model-g",
        "model_version": "5.0.0",
        "approved": False,
        "reason": "High latency",
    }
    response = client.post("/governance/rollout_decision", json=payload)
    assert response.status_code == 202


    mock_model_registry_service.transition_model_stage.assert_called_once_with(
        name="model-g", version="5.0.0", stage="Archived"
    )
    call_args = mock_audit_service.log.call_args[1]
    assert call_args["action"] == "MODEL_ROLLOUT_REJECTED"


def test_get_all_audit_logs(
    app: FastAPI, mock_audit_service: MagicMock, client: TestClient
):
    """Test retrieving all audit logs."""
    mock_logs = [
        AuditLogEntry(
            actor="user1",
            action="TEST",
            details={},
            previous_hash="abc",
            entry_hash="def",
            timestamp=datetime.now(timezone.utc),
        )
    ]
    mock_audit_service.get_all_logs = AsyncMock(return_value=mock_logs)

    response = client.get("/governance/audit_logs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["actor"] == "user1"