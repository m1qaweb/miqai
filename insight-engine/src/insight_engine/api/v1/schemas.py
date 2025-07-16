from uuid import UUID
from pydantic import BaseModel, Field


class SummarizationRequest(BaseModel):
    query: str
    video_id: str


class ClipRequest(BaseModel):
    video_id: UUID = Field(..., description="The unique identifier for the video.")
    query: str = Field(
        ..., description="The user's query to find relevant clips."
    )


class ClipResult(BaseModel):
    clip_id: UUID = Field(..., description="The unique identifier for the generated clip.")
    video_id: UUID = Field(..., description="The original video ID.")
    gcs_url: str = Field(..., description="The GCS URL of the new clip.")
    start_time: float = Field(..., description="Start time of the clip in seconds.")
    end_time: float = Field(..., description="End time of the clip in seconds.")
    query: str = Field(..., description="The query that generated this clip.")
    score: float = Field(..., description="The relevance score of the clip.")


class ClipJobResponse(BaseModel):
    job_id: UUID = Field(..., description="The unique identifier for the clip extraction job.")