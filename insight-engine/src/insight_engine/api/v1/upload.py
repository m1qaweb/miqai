"""API endpoints for video uploads."""

import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException
from google.cloud import storage
from pydantic import HttpUrl

from insight_engine.schemas import VideoUploadRequest, VideoUploadResponse
from insight_engine.security import get_current_user

router = APIRouter()

@router.post(
    "/request-url",
    response_model=VideoUploadResponse,
    summary="Request a presigned URL for video upload",
)
async def request_upload_url(
    request: VideoUploadRequest, _: str = Depends(get_current_user)
) -> VideoUploadResponse:
    """
    Provides a client with a presigned URL to upload a video file to GCS.
    """
    storage_client = storage.Client()
    # TODO: Externalize this bucket name into configuration
    bucket_name = "insight-engine-videos"
    video_identifier = str(uuid.uuid4())
    object_name = f"{video_identifier}-{request.file_name}"

    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=request.content_type,
        )
        return VideoUploadResponse(video_id=video_identifier, upload_url=HttpUrl(url))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not generate upload URL: {e}")