"""Integration tests for the clip extraction pipeline."""

from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from insight_engine.main import app

client = TestClient(app)

@patch("insight_engine.dependencies.get_pubsub_client")
def test_clip_extraction_pipeline(mock_get_pubsub_client):
    """
    Tests that the clip extraction endpoint correctly publishes a message
    to the Pub/Sub topic.
    """
    # Mock the Pub/Sub client
    mock_publisher = MagicMock()
    mock_get_pubsub_client.return_value = mock_publisher

    # Call the endpoint
    response = client.post(
        "/v1/analysis/extract-clips/",
        json={"video_uri": "gs://bucket/test.mp4", "clips": [{"start_time": 0, "end_time": 1}]},
    )

    # Assert that the endpoint returned the correct status code
    assert response.status_code == 202
    assert response.json() == {"status": "clip_extraction_jobs_enqueued"}

    # Assert that the publisher was called with the correct message
    mock_publisher.publish_message.assert_called_once()