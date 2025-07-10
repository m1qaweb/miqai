import pytest
import httpx
from insight_engine.main import app


@pytest.mark.asyncio
async def test_request_upload_url_success():
    """
    Tests successful request for a video upload URL.
    """
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/uploads/request-url/",
            json={"file_name": "test_video.mp4", "content_type": "video/mp4"},
        )
        assert response.status_code == 200
        json_response = response.json()
        assert "upload_url" in json_response
        assert "video_uri" in json_response


@pytest.mark.asyncio
async def test_request_upload_url_validation_error():
    """
    Tests validation error when requesting an upload URL with invalid data.
    """
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Request body is missing the 'file_name' field
        response = await client.post(
            "/uploads/request-url/", json={"content_type": "video/mp4"}
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_summarize_video_success():
    """
    Tests successful request to summarize a video.
    """
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/analysis/summarize/", json={"gcs_uri": "gs://fake-bucket/test_video.mp4"}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_extract_clips_accepted():
    """
    Tests that the clip extraction task is accepted successfully.
    """
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/analysis/extract-clips/",
            json={
                "gcs_uri": "gs://fake-bucket/test_video.mp4",
                "prompt": "Show me all clips where a person is wearing a hard hat.",
            },
        )
        assert response.status_code == 202
        json_response = response.json()
        assert "task_id" in json_response
        assert json_response["status"] == "accepted"
