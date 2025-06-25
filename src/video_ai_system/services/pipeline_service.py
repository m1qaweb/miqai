# -*- coding: utf-8 -*-
"""
Service responsible for orchestrating the end-to-end video analysis pipeline.

This service coordinates the preprocessing, inference, and vector DB storage
steps.

Design Reference: video-ai-system/docs/pipeline_service_design.md
"""
import logging
import cv2
import httpx
from fastapi.concurrency import run_in_threadpool

from .preprocessing_service import VideoPreprocessor
from .vector_db_service import VectorDBService, FramePoint, FramePayload
from .pipeline_models import InferenceRequest, InferenceResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PipelineService:
    """
    Orchestrates the video analysis pipeline.
    
    1. Extracts keyframes using PreprocessingService.
    2. For each keyframe, calls a remote InferenceService.
    3. Batches the results and upserts them to the VectorDBService.
    """

    def __init__(
        self,
        preprocessor: VideoPreprocessor,
        vector_db: VectorDBService,
        inference_service_url: str,
        batch_size: int = 50,
    ):
        """
        Initializes the PipelineService.

        Args:
            preprocessor: An instance of VideoPreprocessor.
            vector_db: An instance of VectorDBService.
            inference_service_url: The base URL for the remote inference service.
            batch_size: The number of results to batch before upserting to the DB.
        """
        self.preprocessor = preprocessor
        self.vector_db = vector_db
        self.inference_client = httpx.AsyncClient(
            base_url=inference_service_url,
            timeout=30.0,
            # Future: Add transport with retry logic
        )
        self.batch_size = batch_size
        logger.info(f"PipelineService initialized with inference URL: {inference_service_url}")

    async def process_video(self, video_path: str, video_id: str):
        """
        Executes the full analysis pipeline for a given video.

        Args:
            video_path: The local path to the video file.
            video_id: A unique identifier for this video.
        """
        logger.info(f"Starting pipeline for video_id: {video_id} at path: {video_path}")
        points_to_upsert = []
        
        try:
            # The keyframe extractor is a generator, which is synchronous.
            # We run the consumption of this generator in a thread pool to avoid
            # blocking the main async event loop.
            def consume_keyframes():
                nonlocal points_to_upsert
                keyframes_generator = self.preprocessor.extract_keyframes(video_path)
                for keyframe in keyframes_generator:
                    # This part will run in the thread pool
                    _, frame_bytes = cv2.imencode('.jpg', keyframe.frame_array)
                    
                    try:
                        # Note: httpx is async, but we are in a sync function here.
                        # A more advanced pattern might use an async generator,
                        # but this keeps the CPU-bound work clearly separated.
                        # For simplicity, we'll make a sync request from the thread.
                        req = InferenceRequest(frame_bytes=frame_bytes.tobytes())
                        response = httpx.post(f"{self.inference_client.base_url}/infer", content=req.model_dump_json(), timeout=30.0)
                        response.raise_for_status()
                        inference_result = InferenceResult(**response.json())

                        payload = FramePayload(
                            video_id=video_id,
                            video_path=video_path,
                            frame_number=keyframe.frame_number,
                            timestamp=keyframe.timestamp_sec,
                            model_version=inference_result.model_version,
                            detections=inference_result.detections
                        )
                        point = FramePoint(
                            vector=inference_result.embedding,
                            payload=payload
                        )
                        points_to_upsert.append(point)

                        if len(points_to_upsert) >= self.batch_size:
                            logger.info(f"Upserting batch of {len(points_to_upsert)} points.")
                            self.vector_db.upsert_points(points_to_upsert)
                            points_to_upsert = [] # Reset batch

                    except httpx.RequestError as e:
                        logger.error(f"Error calling inference service for frame {keyframe.frame_number}: {e}. Skipping frame.")
                        continue
                    except Exception as e:
                        logger.error(f"An unexpected error occurred during frame processing: {e}")
                        continue

            await run_in_threadpool(consume_keyframes)

            # Upsert any remaining points after the loop
            if points_to_upsert:
                logger.info(f"Upserting final batch of {len(points_to_upsert)} points.")
                self.vector_db.upsert_points(points_to_upsert)

            logger.info(f"Successfully completed pipeline for video_id: {video_id}")

        except Exception as e:
            logger.critical(f"A critical error occurred in the pipeline for video_id {video_id}: {e}")
            # Re-raise the exception to allow the worker to handle it (e.g., mark task as FAILED)
            raise