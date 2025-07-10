"""
Service for handling the clip extraction pipeline.
"""

import asyncio
from fastapi import BackgroundTasks
import arq

from insight_engine.services.clip_generation_service import generate_clips


class ClipExtractionError(Exception):
    """Custom exception for clip extraction failures."""

    pass


async def start_clip_extraction(
    file_path: str,
    query: str,
    redis_pool: arq.ArqRedis,
    background_tasks: BackgroundTasks,
) -> tuple[str, list]:
    """
    Orchestrates the clip extraction pipeline.
    """
    # --- Enqueue analysis task ---
    job = await redis_pool.enqueue_job("analyze_video", file_path=file_path)

    # --- Poll for completion ---
    for _ in range(120):  # Poll for up to 2 minutes
        job_info = await job.info()
        if job_info.success:
            break
        if job_info.result and isinstance(job_info.result, Exception):
            raise ClipExtractionError(f"Analysis task failed: {job_info.result}")
        await asyncio.sleep(1)
    else:
        raise ClipExtractionError("Analysis task timed out.")

    analysis_result = await job.result()

    all_detections = analysis_result.get("object_detections", [])

    matching_timestamps = [
        detection["timestamp"]
        for detection in all_detections
        if detection.get("label", "").lower() == query.lower()
    ]

    if not matching_timestamps:
        return job.job_id, []

    # Create 5-second clips around the detected timestamps
    clip_timestamps = [(t, t + 5) for t in matching_timestamps]

    # This can be a long-running task, so run it in a thread
    clip_paths = await asyncio.to_thread(generate_clips, file_path, clip_timestamps)

    return job.job_id, clip_paths
