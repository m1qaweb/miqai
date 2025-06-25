# -*- coding: utf-8 -*-
"""
Pydantic models for the data contracts used within the video analysis pipeline.

This module defines the shared data structures that are passed between the
PipelineService, InferenceService, and other related components. Using shared
models ensures consistency and type safety across service boundaries.

Design Reference: video-ai-system/docs/pipeline_service_design.md
"""
from pydantic import BaseModel, Field
from typing import List
import numpy as np

class Keyframe:
    """
    Represents a single keyframe extracted from a video.

    This is an internal model used by the PipelineService to pass frame data
    from the preprocessor to the inference orchestrator logic.
    """
    frame_array: np.ndarray = Field(description="The keyframe image as a NumPy array")
    timestamp_sec: float = Field(description="Timestamp of the keyframe in the video")
    frame_number: int = Field(description="The frame number in the video sequence")

    class Config:
        # Allows the model to work with numpy arrays
        arbitrary_types_allowed = True

class InferenceRequest(BaseModel):
    """
    Schema for the request body sent to the InferenceService's /infer endpoint.
    """
    frame_bytes: bytes = Field(description="The keyframe image, serialized to bytes (e.g., via cv2.imencode)")

class Detection(BaseModel):
    """
    Represents a single object detection result from the model.
    """
    box: List[float] = Field(description="Bounding box coordinates [x1, y1, x2, y2]")
    label: str = Field(description="Class label of the detected object")
    score: float = Field(description="Confidence score of the detection")

class InferenceResult(BaseModel):
    """
    Schema for the response body received from the InferenceService's /infer endpoint.
    """
    detections: List[Detection] = Field(description="List of object detections")
    embedding: List[float] = Field(description="Feature embedding vector for the frame")
    model_version: str = Field(description="Identifier for the model version used for this inference")