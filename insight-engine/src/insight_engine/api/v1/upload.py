"""API endpoints for video uploads."""

import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from pydantic import HttpUrl

from insight_engine.config import settings
from insight_engine.exceptions import VideoUploadException, GoogleCloudException
from insight_engine.logging_config import get_logger
from insight_engine.schemas import VideoUploadRequest, VideoUploadResponse
from insight_engine.security import get_current_user
from insight_engine.utils import ErrorContext, log_info, log_error

router = APIRouter()
logger = get_logger(__name__)

@router.post(
    "/request-url",
    response_model=VideoUploadResponse,
    summary="Request a presigned URL for video upload",
)
async def request_upload_url(
    request: VideoUploadRequest, user_id: str = Depends(get_current_user)
) -> VideoUploadResponse:
    """
    Provides a client with a presigned URL to upload a video file to GCS.
    
    Args:
        request: Video upload request containing file metadata
        user_id: Authenticated user ID
    
    Returns:
        VideoUploadResponse with video ID and presigned upload URL
    
    Raises:
        VideoUploadException: If upload URL generation fails
        GoogleCloudException: If Google Cloud Storage error occurs
    """
    video_identifier = str(uuid.uuid4())
    
    with ErrorContext(
        "video_upload_url_generation",
        video_id=video_identifier,
        user_id=user_id,
        filename=request.file_name,
        content_type=request.content_type
    ):
        log_info(
            "Generating presigned upload URL",
            extra_context={
                "video_id": video_identifier,
                "user_id": user_id,
                "filename": request.file_name,
                "content_type": request.content_type,
                "file_size": getattr(request, 'file_size', None),
                "operation": "upload_url_generation"
            }
        )
        
        try:
            # TODO: Get bucket name from configuration
            bucket_name = getattr(settings, 'GCS_BUCKET_NAME', "insight-engine-videos")
            object_name = f"{video_identifier}-{request.file_name}"
            
            # Initialize GCS client
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(object_name)
            
            # Generate presigned URL
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=15),
                method="PUT",
                content_type=request.content_type,
            )
            
            log_info(
                "Successfully generated presigned upload URL",
                extra_context={
                    "video_id": video_identifier,
                    "user_id": user_id,
                    "bucket_name": bucket_name,
                    "object_name": object_name,
                    "url_expiration_minutes": 15,
                    "operation": "upload_url_success"
                }
            )
            
            return VideoUploadResponse(
                video_id=video_identifier, 
                upload_url=HttpUrl(url)
            )
            
        except GoogleCloudError as e:
            log_error(
                e,
                "Google Cloud Storage error during upload URL generation",
                extra_context={
                    "video_id": video_identifier,
                    "user_id": user_id,
                    "bucket_name": bucket_name,
                    "operation": "upload_url_gcs_error"
                }
            )
            
            raise GoogleCloudException(
                message="Failed to generate upload URL due to storage service error",
                service="Google Cloud Storage",
                details={
                    "video_id": video_identifier,
                    "bucket_name": bucket_name,
                    "original_error": str(e)
                },
                user_id=user_id
            )
            
        except Exception as e:
            log_error(
                e,
                "Unexpected error during upload URL generation",
                extra_context={
                    "video_id": video_identifier,
                    "user_id": user_id,
                    "operation": "upload_url_unexpected_error"
                }
            )
            
            raise VideoUploadException(
                message="Failed to generate upload URL",
                filename=request.file_name,
                details={
                    "video_id": video_identifier,
                    "error_type": type(e).__name__,
                    "original_error": str(e)
                },
                user_id=user_id
            )