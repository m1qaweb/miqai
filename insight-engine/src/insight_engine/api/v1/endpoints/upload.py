import os
import re
import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import storage
from pydantic import HttpUrl

from insight_engine.dependencies import get_gcs_client
from insight_engine.schemas.api import UploadResponse, VideoUploadRequest
from insight_engine.security import get_current_user

router = APIRouter()

INGESTION_BUCKET_NAME = os.environ.get("INGESTION_BUCKET_NAME")
if not INGESTION_BUCKET_NAME:
    raise RuntimeError("INGESTION_BUCKET_NAME environment variable not set.")


@router.post(
    "/",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Pre-Signed URL for Video Upload",
    description="""
    Generates a secure, short-lived URL that the client can use to upload a
    video file directly to Google Cloud Storage. This offloads the upload
    process from the API server.
    """,
)
def generate_upload_url(
    request: VideoUploadRequest,
    gcs_client: storage.Client = Depends(get_gcs_client),
    current_user: dict = Depends(get_current_user),
) -> UploadResponse:
    """
    Handles the request to generate a pre-signed GCS URL.

    Args:
        request: The request body containing file metadata.
        gcs_client: Injected GCS storage client.

    Returns:
        An UploadResponse containing the new video_id and the pre-signed URL.
    """
    user_id = current_user.get("username")
    video_id = uuid.uuid4()
    # Sanitize the filename to prevent path traversal attacks.
    # This regex removes any characters that are not alphanumeric, a period, or a hyphen.
    # This is a critical security measure to ensure that the filename cannot be
    # manipulated to access or overwrite unintended files in the storage bucket.
    sanitized_file_name = re.sub(r"[^a-zA-Z0-9.-]", "", request.file_name)
    if not sanitized_file_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file name provided.",
        )

    # Namespace the object with the user_id to enforce authorization
    object_name = f"{user_id}/{video_id}/{sanitized_file_name}"

    try:
        bucket = gcs_client.bucket(INGESTION_BUCKET_NAME)
        blob = bucket.blob(blob_name=object_name)
        
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=request.content_type,
        )
        return UploadResponse(video_id=video_id, upload_url=HttpUrl(signed_url))
    except Exception as e:
        # In a production scenario, log this exception `e` for debugging.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate upload URL.",
        )