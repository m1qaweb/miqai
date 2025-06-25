# -*- coding: utf-8 -*-
"""
Standalone FastAPI application for the Inference Service.

This service exposes a single endpoint to run object detection and embedding
extraction on a given image. It is designed to be run as a separate, scalable
microservice.

Design Reference: video-ai-system/docs/pipeline_service_design.md
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import List, Tuple

import cv2
import numpy as np
import onnxruntime
from fastapi import FastAPI, Depends
from fastapi.concurrency import run_in_threadpool
from starlette_prometheus import PrometheusMiddleware, metrics

# Assuming pipeline_models.py is in a location accessible via PYTHONPATH
# In a real setup, this would be part of a shared library/package.
from video_ai_system.services.pipeline_models import InferenceRequest, InferenceResult, Detection

# --- Globals for Model ---
# This is a simple way to hold the model in memory for the app's lifetime.
# A class-based dependency would also be a good pattern.
onnx_session = None
model_input_shape = (1, 3, 640, 640) # Default for YOLOv8
model_version = "yolov8n_v1.0" # Should be loaded from model metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def preprocess_image(image_bytes: bytes) -> Tuple[np.ndarray, Tuple[int, int]]:
    """Preprocesses the input image bytes."""
    original_image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    original_shape = original_image.shape[:2]
    
    # Resize and pad to model input size
    input_height, input_width = model_input_shape[2:]
    image = cv2.resize(original_image, (input_width, input_height))
    
    # Normalize and transpose
    image = image.astype(np.float32) / 255.0
    image = image.transpose(2, 0, 1)
    return np.expand_dims(image, axis=0), original_shape

def postprocess_output(output: List[np.ndarray], original_shape: Tuple[int, int]) -> InferenceResult:
    """Postprocesses the model output to create detections and embedding."""
    # Placeholder logic for parsing YOLOv8 output
    # The first output is typically detections, the second might be embeddings/features
    detections_output = output[0]
    embedding_output = np.random.rand(512).astype(np.float32) # Placeholder for actual embedding

    # Example: Extracting one dummy detection
    detections = [
        Detection(box=[10.0, 10.0, 50.0, 50.0], label="person", score=0.95)
    ]

    return InferenceResult(
        detections=detections,
        embedding=embedding_output.flatten().tolist(),
        model_version=model_version
    )

def get_onnx_session():
    """Dependency to provide the ONNX session."""
    global onnx_session
    if onnx_session is None:
        raise RuntimeError("ONNX session is not initialized.")
    return onnx_session

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the ONNX model on startup."""
    global onnx_session
    logger.info("Loading ONNX model...")
    # In a real app, this path would come from config
    model_path = "models/yolov8n.onnx"
    onnx_session = onnxruntime.InferenceSession(model_path, providers=['CPUExecutionProvider'])
    logger.info(f"Model '{model_path}' loaded successfully.")
    yield
    # Clean up resources if needed on shutdown
    logger.info("Shutting down.")
    onnx_session = None

app = FastAPI(
    title="Video AI System - Inference Service",
    description="A microservice to run object detection and embedding models.",
    version="1.0.0",
    lifespan=lifespan
)

# Add Prometheus middleware to expose /metrics endpoint
app.add_middleware(PrometheusMiddleware)
# Add custom metric to track inference latency
INFERENCE_LATENCY = metrics.register('inference_latency_seconds', 'Latency of the /infer endpoint')

@app.post("/infer", response_model=InferenceResult)
async def infer(
    request: InferenceRequest,
    session: onnxruntime.InferenceSession = Depends(get_onnx_session)
):
    """
    Runs inference on a single image frame.

    Assumption A1.1: The overhead of HTTP communication is acceptable.
    This endpoint is optimized to validate this by running the blocking
    inference call in a thread pool.
    """
    start_time = time.time()

    # Preprocess the image
    input_tensor, original_shape = preprocess_image(request.frame_bytes)

    # Run inference in a thread pool to avoid blocking the event loop
    def run_model():
        input_name = session.get_inputs()[0].name
        output_names = [output.name for output in session.get_outputs()]
        return session.run(output_names, {input_name: input_tensor})

    model_output = await run_in_threadpool(run_model)

    # Postprocess the output
    result = postprocess_output(model_output, original_shape)

    latency = time.time() - start_time
    INFERENCE_LATENCY.observe(latency)
    logger.info(f"Inference completed in {latency:.4f} seconds.")

    return result

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "ok"}