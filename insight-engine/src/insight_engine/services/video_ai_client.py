"""
Client for interacting with the remote video-ai-system API.

This module encapsulates the logic for submitting analysis jobs,
polling for results, and handling API communication.
"""

import asyncio
import httpx
from typing import Any, Dict
from insight_engine.config import settings

# Constants for polling
POLLING_INTERVAL_SECONDS = 5
MAX_POLLING_ATTEMPTS = 36  # 3 minutes max


class VideoAIClientError(Exception):
    """Custom exception for client failures."""

    pass


async def run_analysis_job(file_path: str) -> Dict[str, Any]:
    """
    Submits a video for analysis and waits for the result.

    Args:
        file_path: The local path to the video file to be analyzed.

    Returns:
        A dictionary containing the full analysis result from the video-ai-system.

    Raises:
        VideoAIClientError: If configuration is missing or the pipeline fails.
    """
    if not settings.VIDEO_AI_SYSTEM_URL or not settings.VIDEO_AI_API_KEY:
        raise VideoAIClientError(
            "VIDEO_AI_SYSTEM_URL and VIDEO_AI_API_KEY must be set."
        )

    headers = {"X-API-Key": settings.VIDEO_AI_API_KEY}
    payload = {"file_path": file_path}

    async with httpx.AsyncClient() as client:
        # 1. Submit the video for analysis
        try:
            print(f"Submitting analysis job for: {file_path}")
            response = await client.post(
                f"{settings.VIDEO_AI_SYSTEM_URL}/api/v1/analyze",
                json=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            job_data = response.json()
            task_id = job_data["task_id"]
            status_endpoint = job_data["status_endpoint"]
            print(f"Job submitted successfully. Task ID: {task_id}")
        except httpx.RequestError as e:
            raise VideoAIClientError(f"Failed to connect to video-ai-system: {e}")
        except httpx.HTTPStatusError as e:
            raise VideoAIClientError(
                f"Error submitting job: {e.response.status_code} - {e.response.text}"
            )

        # 2. Poll for the result
        for attempt in range(MAX_POLLING_ATTEMPTS):
            print(f"Polling for result... Attempt {attempt + 1}/{MAX_POLLING_ATTEMPTS}")
            try:
                result_response = await client.get(
                    f"{settings.VIDEO_AI_SYSTEM_URL}{status_endpoint}",
                    headers=headers,
                    timeout=30,
                )
                result_response.raise_for_status()
                result_data = result_response.json()

                status = result_data.get("status")
                if status == "SUCCESS":
                    print("Analysis successful.")
                    return task_id, result_data.get("result", {})

                elif status == "FAILED":
                    error_message = result_data.get("error_message", "Unknown error.")
                    raise VideoAIClientError(
                        f"Analysis failed for task {task_id}: {error_message}"
                    )

                await asyncio.sleep(POLLING_INTERVAL_SECONDS)

            except httpx.RequestError as e:
                raise VideoAIClientError(f"Failed to poll for results: {e}")
            except httpx.HTTPStatusError as e:
                raise VideoAIClientError(
                    f"Error polling for results: {e.response.status_code} - {e.response.text}"
                )

        raise VideoAIClientError(
            f"Polling timed out for task {task_id}. The job is still processing."
        )
