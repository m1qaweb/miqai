"""Integration tests for the Insight Engine."""

from fastapi.testclient import TestClient
from unittest.mock import patch

from insight_engine.main import app

client = TestClient(app)

@patch("insight_engine.services.multimodal_extractor.MultimodalExtractor.extract_data")
@patch("insight_engine.services.rag_service.RAGService.process_and_store")
@patch("insight_engine.services.rag_service.RAGService.generate_summary")
def test_summarization_pipeline(
    mock_generate_summary, mock_process_and_store, mock_extract_data
):
    """
    Tests the full summarization pipeline, from video processing to summary generation.
    """
    # Mock the external services
    mock_extract_data.return_value.transcript = "This is a test transcript."
    mock_generate_summary.return_value = "This is a test summary."

    # 1. Process the video
    response = client.post("/v1/analysis/summarize/process?video_uri=gs://bucket/test.mp4")
    assert response.status_code == 200
    assert response.json()["status"] == "processing_complete"
    video_id = response.json()["video_id"]

    # 2. Generate a summary
    response = client.get(f"/v1/analysis/summarize/?video_id={video_id}&q=test")
    assert response.status_code == 200
    assert "summary" in response.text