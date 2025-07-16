"""API endpoints for clip extraction."""

import json
import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from insight_engine.schemas import ExtractClipsRequest
from insight_engine.security import get_current_user
from insight_engine.dependencies import get_pubsub_client
from insight_engine.tools.pubsub_client import PubSubClient

router = APIRouter()

@router.post(
    "/",
    summary="Extract relevant clips from a video",
    status_code=202,
)
async def extract_clips(
    request: ExtractClipsRequest,
    pubsub_client: PubSubClient = Depends(get_pubsub_client),
    _: str = Depends(get_current_user),
) -> JSONResponse:
    """
    Enqueues tasks to extract relevant clips from a video by publishing
    messages to a GCP Pub/Sub topic.
    """
    topic_name = "clip-extraction-jobs"
    for clip in request.clips:
        job_id = str(uuid.uuid4())
        message = {
            "job_id": job_id,
            "video_uri": request.video_uri,
            "start_time": clip.start_time,
            "end_time": clip.end_time,
            "output_path": f"/clips/{job_id}.mp4",
        }
        pubsub_client.publish_message(topic_name, json.dumps(message).encode("utf-8"))

    return JSONResponse(
        content={"status": "clip_extraction_jobs_enqueued"},
        status_code=202,
    )