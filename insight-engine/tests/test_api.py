"""Unit tests for the FastAPI application."""

from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from insight_engine.main import app

client = TestClient(app)

def test_health_check():
    """Tests the /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_request_upload_url(mock_gcs_client):
    """Tests the /uploads/request-url endpoint."""
    app.dependency_overrides[MagicMock] = lambda: mock_gcs_client
    response = client.post(
        "/v1/uploads/request-url",
        json={"file_name": "test.mp4", "content_type": "video/mp4"},
    )
    assert response.status_code == 200
    assert "video_id" in response.json()
    assert "upload_url" in response.json()

def test_summarize_video(mock_vector_store):
    """Tests the /analysis/summarize endpoint."""
    app.dependency_overrides[MagicMock] = lambda: mock_vector_store
    response = client.get("/v1/analysis/summarize/?video_id=123&q=test")
    assert response.status_code == 200

def test_extract_clips(mock_pubsub_publisher):
    """Tests the /analysis/extract-clips endpoint."""
    app.dependency_overrides[MagicMock] = lambda: mock_pubsub_publisher
    response = client.post(
        "/v1/analysis/extract-clips/",
        json={"video_uri": "gs://bucket/test.mp4", "clips": [{"start_time": 0, "end_time": 1}]},
    )
    assert response.status_code == 202
    assert response.json() == {"status": "clip_extraction_jobs_enqueued"}
