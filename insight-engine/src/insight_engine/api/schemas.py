"""Pydantic schemas for the Insight Engine API."""

from pydantic import BaseModel


class VideoUploadRequest(BaseModel):
    """Request model for initiating a video upload."""
    file_name: str
    content_type: str


class VideoUploadResponse(BaseModel):
    """Response model for a video upload request."""
    video_id: str
    upload_url: str


class SummarizeRequest(BaseModel):
    """Request model for the summarization endpoint."""
    video_id: str


class Clip(BaseModel):
    """Defines a clip to be extracted from a video."""

    start_time: float
    end_time: float


class ExtractClipsRequest(BaseModel):
    """Request model for the clip extraction endpoint."""

    video_uri: str
    clips: list[Clip]
