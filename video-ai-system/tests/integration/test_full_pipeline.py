# -*- coding: utf-8 -*-
"""
Integration test for the full video analysis pipeline.

This test validates the end-to-end workflow:
1. Submits a video via the /analyze API endpoint.
2. Polls the /analysis/{task_id} endpoint until the job is complete.
3. Connects to the Qdrant database to verify that results were persisted.

Requirements for running this test:
- A running instance of the main application (with the ARQ worker).
- A running instance of the InferenceService.
- A running instance of Qdrant and Redis.
- A sample video file located at `tests/fixtures/sample_video.mp4`.
"""
import os
import time
import httpx
import pytest
from qdrant_client import QdrantClient

# --- Test Configuration ---
# These should ideally be loaded from a test-specific config or environment vars
API_BASE_URL = "http://localhost:8000"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_COLLECTION = "video_frames" # Should match the default in config
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 120 # 2 minutes
SAMPLE_VIDEO_PATH = "tests/fixtures/sample_video.mp4"

@pytest.fixture(scope="module")
def api_client():
    """Provides an httpx client for the API."""
    return httpx.Client(base_url=API_BASE_URL)

@pytest.fixture(scope="module")
def qdrant_client():
    """Provides a client for the Qdrant database."""
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    # Optional: clean up the collection before tests run
    # client.recreate_collection(...)
    return client

@pytest.mark.integration
def test_full_video_analysis_pipeline(api_client, qdrant_client):
    """
    Tests the entire video analysis pipeline from end to end.
    """
    # --- Pre-check: Ensure sample video exists ---
    # In a real CI/CD, this file would be checked in or downloaded.
    if not os.path.exists(SAMPLE_VIDEO_PATH):
        pytest.skip(f"Sample video not found at {SAMPLE_VIDEO_PATH}")

    # --- Step 1: Submit the video for analysis ---
    # In a real test, we would upload the file or provide a URL.
    # Here, we assume the worker has access to the file path.
    # The API needs to be adapted to accept a file path for testing,
    # or the test needs to host the file at a URL.
    # For this example, we'll assume an endpoint that takes a local path.
    
    # This is a conceptual call. The actual /analyze endpoint expects a URL.
    # A test helper endpoint might be needed.
    # For now, we'll simulate the job submission and get a task_id.
    # Let's assume the main app's POST /analyze is modified to return a task_id
    # even for a placeholder request.
    
    # Let's assume we have a way to trigger the job with a local file path.
    # This part of the test will need to be adapted to the actual API.
    # For now, we'll focus on the polling and verification logic.
    
    # Let's imagine we have a test-only endpoint for this.
    # For now, we can't fully implement this step without modifying the main API.
    # We will proceed with the assumption that a job has been started
    # and we have a task_id.
    
    # This test is therefore a template for the full workflow.
    # A developer would need to complete the job submission part.
    
    # --- Step 1: Submit the video for analysis ---
    with open(SAMPLE_VIDEO_PATH, "rb") as f:
        response = api_client.post("/analyze", files={"video_file": f})

    assert response.status_code == 202
    task_id = response.json()["task_id"]
    status_endpoint = f"/analysis/{task_id}"

    # --- Step 2: Poll for job completion ---
    start_time = time.time()
    task_status = {}
    while time.time() - start_time < POLL_TIMEOUT_SECONDS:
        response = api_client.get(status_endpoint)
        assert response.status_code == 200
        task_status = response.json()

        if task_status["status"] in ["SUCCESS", "FAILED"]:
            break
        
        time.sleep(POLL_INTERVAL_SECONDS)
    
    # --- Step 3: Assert the final status ---
    assert task_status.get("status") == "SUCCESS", f"Job failed with message: {task_status.get('error_message')}"
    assert task_status.get("result", {}).get("results_persisted") is True
    video_id = task_status.get("result", {}).get("video_id")
    assert video_id is not None

    # --- Step 4: Verify results in the database ---
    # Give a small grace period for the final DB write to complete.
    time.sleep(2)

    # Search for points associated with the processed video_id
    search_result = qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter={
            "must": [
                {
                    "key": "video_id",
                    "match": {
                        "value": video_id
                    }
                }
            ]
        },
        limit=10,
        with_payload=True,
        with_vectors=False
    )
    
    points = search_result[0]
    assert len(points) > 0, "No points were found in the database for the processed video."

    # Optional: More detailed checks on the payload
    first_point_payload = points[0].payload
    assert first_point_payload["video_id"] == video_id
    assert "detections" in first_point_payload
    
    print(f"Successfully verified {len(points)} points in the database for video_id {video_id}.")