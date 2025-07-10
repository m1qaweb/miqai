from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Any, Tuple, Dict
from enum import Enum


class VideoListResponse(BaseModel):
    videos: List[str]


class Detection(BaseModel):
    label: str
    confidence: float
    box: Tuple[float, float, float, float]  # (x1, y1, x2, y2)


class FrameData(BaseModel):
    frame_number: int
    timestamp: float
    detections: List[Detection]


class FrameDataResponse(BaseModel):
    video_id: str
    frames: List[FrameData]


class AnalyzeRequest(BaseModel):
    """
    Specifies the video to be analyzed by providing its local file path.
    The model is strict, preventing unexpected fields.
    """

    file_path: str
    callback_url: Optional[HttpUrl] = None

    class Config:
        extra = "forbid"


class AnalyzeResponse(BaseModel):
    """
    Confirms the task was accepted.
    """

    task_id: str
    status_endpoint: str


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None
    error_message: Optional[str] = None


class TimeWindow(BaseModel):
    start_time: float
    end_time: float


class DriftCheckRequest(BaseModel):
    reference_window: TimeWindow
    comparison_window: TimeWindow


class ModelRegistrationRequest(BaseModel):
    model_name: str
    path: str
    metadata: Optional[Dict] = Field(default_factory=dict)


class ModelActivationRequest(BaseModel):
    model_name: str
    version: int


class ModelEntryResponse(BaseModel):
    model_name: str
    version: int
    path: str
    status: str
    creation_timestamp: str
    metadata: Dict
