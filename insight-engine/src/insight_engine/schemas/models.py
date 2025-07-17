"""Enhanced Pydantic models with comprehensive validation."""

import re
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator, EmailStr, constr
from pydantic.types import PositiveInt, PositiveFloat

from insight_engine.models.video import ProcessingStatus


class UserBase(BaseModel):
    """Base user model with common fields."""
    
    username: constr(min_length=3, max_length=50, regex=r'^[a-zA-Z0-9_-]+$') = Field(
        ...,
        description="Username must be 3-50 characters, alphanumeric with underscores and hyphens only"
    )
    
    email: EmailStr = Field(
        ...,
        description="Valid email address"
    )
    
    full_name: Optional[constr(max_length=255)] = Field(
        None,
        description="Full name of the user"
    )


class UserCreate(UserBase):
    """User creation model with password validation."""
    
    password: constr(min_length=8, max_length=128) = Field(
        ...,
        description="Password must be at least 8 characters long"
    )
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password strength requirements."""
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserUpdate(BaseModel):
    """User update model with optional fields."""
    
    username: Optional[constr(min_length=3, max_length=50, regex=r'^[a-zA-Z0-9_-]+$')] = None
    email: Optional[EmailStr] = None
    full_name: Optional[constr(max_length=255)] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """User response model for API responses."""
    
    id: uuid.UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class VideoBase(BaseModel):
    """Base video model with common fields."""
    
    filename: constr(min_length=1, max_length=255) = Field(
        ...,
        description="Video filename"
    )
    
    original_filename: constr(min_length=1, max_length=255) = Field(
        ...,
        description="Original filename as uploaded"
    )
    
    content_type: constr(regex=r'^video/(mp4|avi|mov|mkv|webm|flv)$') = Field(
        ...,
        description="Video MIME type"
    )
    
    size_bytes: PositiveInt = Field(
        ...,
        description="File size in bytes"
    )
    
    duration_seconds: Optional[PositiveFloat] = Field(
        None,
        description="Video duration in seconds"
    )
    
    @validator('filename', 'original_filename')
    def validate_filename(cls, v):
        """Validate filename for security."""
        # Check for path traversal attempts
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Filename cannot contain path separators or traversal sequences')
        
        # Check for dangerous characters
        if re.search(r'[<>:"|?*]', v):
            raise ValueError('Filename contains invalid characters')
        
        return v
    
    @validator('size_bytes')
    def validate_file_size(cls, v):
        """Validate file size limits."""
        max_size = 5 * 1024 * 1024 * 1024  # 5GB
        if v > max_size:
            raise ValueError(f'File size cannot exceed {max_size} bytes (5GB)')
        return v


class VideoCreate(VideoBase):
    """Video creation model."""
    
    gcs_path: constr(min_length=1, max_length=500) = Field(
        ...,
        description="Google Cloud Storage path"
    )


class VideoUpdate(BaseModel):
    """Video update model with optional fields."""
    
    processing_status: Optional[ProcessingStatus] = None
    processing_error: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    duration_seconds: Optional[PositiveFloat] = None


class VideoResponse(VideoBase):
    """Video response model for API responses."""
    
    id: uuid.UUID
    user_id: uuid.UUID
    gcs_path: str
    processing_status: ProcessingStatus
    processing_error: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class VideoClipBase(BaseModel):
    """Base video clip model with common fields."""
    
    title: constr(min_length=1, max_length=255) = Field(
        ...,
        description="Clip title"
    )
    
    description: Optional[str] = Field(
        None,
        description="Clip description"
    )
    
    start_time: PositiveFloat = Field(
        ...,
        description="Clip start time in seconds"
    )
    
    end_time: PositiveFloat = Field(
        ...,
        description="Clip end time in seconds"
    )
    
    confidence_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1"
    )
    
    query_used: Optional[constr(max_length=500)] = Field(
        None,
        description="Query used to extract this clip"
    )
    
    @validator('end_time')
    def validate_time_range(cls, v, values):
        """Validate that end_time is after start_time."""
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v


class VideoClipCreate(VideoClipBase):
    """Video clip creation model."""
    
    video_id: uuid.UUID = Field(
        ...,
        description="ID of the parent video"
    )
    
    gcs_path: constr(min_length=1, max_length=500) = Field(
        ...,
        description="Google Cloud Storage path for the clip"
    )


class VideoClipResponse(VideoClipBase):
    """Video clip response model for API responses."""
    
    id: uuid.UUID
    video_id: uuid.UUID
    duration: float
    gcs_path: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """Generic paginated response model."""
    
    items: List[BaseModel]
    total_count: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_previous: bool
    
    @validator('total_pages', always=True)
    def calculate_total_pages(cls, v, values):
        """Calculate total pages based on total_count and page_size."""
        if 'total_count' in values and 'page_size' in values:
            import math
            return math.ceil(values['total_count'] / values['page_size'])
        return v
    
    @validator('has_next', always=True)
    def calculate_has_next(cls, v, values):
        """Calculate if there's a next page."""
        if 'page' in values and 'total_pages' in values:
            return values['page'] < values['total_pages']
        return False
    
    @validator('has_previous', always=True)
    def calculate_has_previous(cls, v, values):
        """Calculate if there's a previous page."""
        if 'page' in values:
            return values['page'] > 1
        return False


class VideoListResponse(PaginatedResponse):
    """Paginated video list response."""
    
    items: List[VideoResponse]


class VideoClipListResponse(PaginatedResponse):
    """Paginated video clip list response."""
    
    items: List[VideoClipResponse]


class VideoUploadRequest(BaseModel):
    """Request model for video upload initialization."""
    
    file_name: constr(min_length=1, max_length=255) = Field(
        ...,
        description="Name of the file to upload"
    )
    
    content_type: constr(regex=r'^video/(mp4|avi|mov|mkv|webm|flv)$') = Field(
        ...,
        description="MIME type of the video file"
    )
    
    file_size: PositiveInt = Field(
        ...,
        description="Size of the file in bytes"
    )
    
    @validator('file_name')
    def validate_upload_filename(cls, v):
        """Validate upload filename."""
        # Check for path traversal attempts
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Filename cannot contain path separators')
        
        # Check for dangerous characters
        if re.search(r'[<>:"|?*]', v):
            raise ValueError('Filename contains invalid characters')
        
        # Check file extension
        allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']
        if not any(v.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError(f'File must have one of these extensions: {", ".join(allowed_extensions)}')
        
        return v
    
    @validator('file_size')
    def validate_upload_size(cls, v):
        """Validate upload file size."""
        max_size = 5 * 1024 * 1024 * 1024  # 5GB
        min_size = 1024  # 1KB
        
        if v > max_size:
            raise ValueError(f'File size cannot exceed {max_size} bytes (5GB)')
        if v < min_size:
            raise ValueError(f'File size must be at least {min_size} bytes (1KB)')
        
        return v


class VideoSummarizeRequest(BaseModel):
    """Request model for video summarization."""
    
    video_id: uuid.UUID = Field(
        ...,
        description="ID of the video to summarize"
    )
    
    query: constr(min_length=1, max_length=1000) = Field(
        ...,
        description="Query or prompt for summarization"
    )
    
    @validator('query')
    def validate_query(cls, v):
        """Validate summarization query."""
        # Remove excessive whitespace
        v = ' '.join(v.split())
        
        # Check for potentially harmful content
        harmful_patterns = [
            r'<script',
            r'javascript:',
            r'data:',
            r'vbscript:',
        ]
        
        for pattern in harmful_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError('Query contains potentially harmful content')
        
        return v