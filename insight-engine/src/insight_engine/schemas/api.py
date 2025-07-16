from uuid import UUID
from pydantic import BaseModel, HttpUrl


class VideoUploadRequest(BaseModel):
    """
    Request model for initiating a video upload.

    Attributes:
        file_name: The name of the video file to be uploaded.
        content_type: The MIME type of the video file (e.g., "video/mp4").
    """
    file_name: str
    content_type: str


class UploadResponse(BaseModel):
    """
    Response model for a successful upload initialization.

    Provides the client with a unique ID for the video and the pre-signed URL
    to perform the direct GCS upload.

    Attributes:
        video_id: A unique identifier for the video.
        upload_url: The secure, short-lived URL for the client to upload the file to.
    """
    video_id: UUID
    upload_url: HttpUrl
