"""
Client for interacting with the remote video-ai-system API.

This module encapsulates the logic for submitting analysis jobs,
polling for results, and handling API communication with resilience patterns.
"""

import asyncio
import httpx
import logging
from typing import Any, Dict, Tuple
from insight_engine.config import settings
from insight_engine.resilience import http_resilient
from insight_engine.resilience.fallbacks import FallbackManager

logger = logging.getLogger(__name__)

# Constants for polling
POLLING_INTERVAL_SECONDS = 5
MAX_POLLING_ATTEMPTS = 36  # 3 minutes max


class VideoAIClientError(Exception):
    """Custom exception for client failures."""
    pass


@http_resilient("video_ai_submit", fallback=None)
async def _submit_analysis_job(file_path: str) -> Tuple[str, str]:
    """Submit video analysis job with resilience patterns."""
    if not settings.VIDEO_AI_SYSTEM_URL or not settings.VIDEO_AI_API_KEY:
        raise VideoAIClientError(
            "VIDEO_AI_SYSTEM_URL and VIDEO_AI_API_KEY must be set."
        )

    headers = {"X-API-Key": settings.VIDEO_AI_API_KEY}
    payload = {"file_path": file_path}

    async with httpx.AsyncClient(timeout=60.0) as client:
        logger.info(f"Submitting analysis job for: {file_path}")
        response = await client.post(
            f"{settings.VIDEO_AI_SYSTEM_URL}/api/v1/analyze",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        job_data = response.json()
        task_id = job_data["task_id"]
        status_endpoint = job_data["status_endpoint"]
        logger.info(f"Job submitted successfully. Task ID: {task_id}")
        return task_id, status_endpoint


@http_resilient("video_ai_poll", fallback=None)
async def _poll_analysis_result(status_endpoint: str) -> Dict[str, Any]:
    """Poll for analysis result with resilience patterns."""
    headers = {"X-API-Key": settings.VIDEO_AI_API_KEY}
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{settings.VIDEO_AI_SYSTEM_URL}{status_endpoint}",
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


async def run_analysis_job(file_path: str) -> Tuple[str, Dict[str, Any]]:
    """
    Submits a video for analysis and waits for the result with resilience patterns.

    Args:
        file_path: The local path to the video file to be analyzed.

    Returns:
        A tuple containing (task_id, analysis_result)

    Raises:
        VideoAIClientError: If configuration is missing or the pipeline fails.
    """
    try:
        # 1. Submit the video for analysis
        task_id, status_endpoint = await _submit_analysis_job(file_path)
        
        # 2. Poll for the result
        for attempt in range(MAX_POLLING_ATTEMPTS):
            logger.debug(f"Polling for result... Attempt {attempt + 1}/{MAX_POLLING_ATTEMPTS}")
            
            try:
                result_data = await _poll_analysis_result(status_endpoint)
                
                status = result_data.get("status")
                if status == "SUCCESS":
                    logger.info("Analysis successful.")
                    return task_id, result_data.get("result", {})
                
                elif status == "FAILED":
                    error_message = result_data.get("error_message", "Unknown error.")
                    raise VideoAIClientError(
                        f"Analysis failed for task {task_id}: {error_message}"
                    )
                
                # Wait before next poll
                await asyncio.sleep(POLLING_INTERVAL_SECONDS)
                
            except VideoAIClientError:
                # Re-raise VideoAI specific errors
                raise
            except Exception as e:
                logger.warning(f"Polling attempt {attempt + 1} failed: {e}")
                if attempt == MAX_POLLING_ATTEMPTS - 1:
                    raise VideoAIClientError(f"Failed to poll for results: {e}")
                await asyncio.sleep(POLLING_INTERVAL_SECONDS)
        
        raise VideoAIClientError(
            f"Polling timed out for task {task_id}. The job is still processing."
        )
        
    except Exception as e:
        logger.error(f"Video AI analysis failed for {file_path}: {e}")
        # Try fallback
        return await FallbackManager.video_ai_fallback(file_path=file_path)
