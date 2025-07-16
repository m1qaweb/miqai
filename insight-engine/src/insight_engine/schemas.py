"""Data models for The Insight Engine API."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


# --- Core Schemas ---

class VideoUploadRequest(BaseModel):
    """Request to get a presigned URL for video upload."""
    file_name: str = Field(..., description="The name of the video file to be uploaded.")
    content_type: str = Field(..., description="The MIME type of the video file.")


class VideoUploadResponse(BaseModel):
    """Response containing the presigned URL and video ID."""
    video_id: str = Field(..., description="A unique identifier for the video.")
    upload_url: HttpUrl = Field(..., description="The presigned URL for the client to upload the video to.")


class Clip(BaseModel):
    """Defines a time range for a video clip."""
    start_time: float = Field(..., description="Start time of the clip in seconds.")
    end_time: float = Field(..., description="End time of the clip in seconds.")


class ExtractClipsRequest(BaseModel):
    """Request to extract multiple clips from a video."""
    video_uri: str = Field(..., description="The GCS URI of the video.")
    clips: List[Clip] = Field(..., description="A list of clips to extract.")


class JobStatusResponse(BaseModel):
    """Response model for checking the status of a background job."""
    status: str = Field(..., description="The current status of the job (e.g., 'in_progress', 'complete', 'failed').")
    result: Optional[Any] = Field(None, description="The result of the job if it is complete.")
    error: Optional[str] = Field(None, description="Error message if the job failed.")


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""
    status: str = "ok"
