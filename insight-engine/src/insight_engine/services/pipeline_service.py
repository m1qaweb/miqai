import logging
from typing import List, Any, Dict
from insight_engine.config import Settings
from insight_engine.services.inference_service import InferenceService
from insight_engine.services.preprocessing_service import VideoPreprocessor
from insight_engine.services.vector_db_service import VectorDBService, FramePoint

logger = logging.getLogger(__name__)

class PipelineService:
    """
    Orchestrates the core video analysis pipeline, from preprocessing to
    inference and storage.
    """

    def __init__(
        self,
        settings: Settings,
        inference_service: InferenceService,
        vector_db_service: VectorDBService,
    ):
        """
        Initializes the PipelineService.
        """
        self.settings = settings
        self.inference_service = inference_service
        self.vector_db_service = vector_db_service
        # The preprocessor is now created directly within the service
        self.preprocessor = VideoPreprocessor(config=settings.preprocessing.model_dump())
        logger.info("PipelineService initialized.")

    async def execute_video_analysis_pipeline(self, video_path: str) -> List[Dict[str, Any]]:
        """
        Executes the full video analysis pipeline for a given video file.

        Args:
            video_path: The path to the video file to be analyzed.

        Returns:
            A list of dictionaries, where each dictionary contains the
            analysis results for a single frame.
        """
        logger.info(f"Starting video analysis pipeline for: {video_path}")

        # 1. Preprocess the video to get keyframes
        # The new preprocessor returns a list of dictionaries with frame data
        keyframes_data = await self.preprocessor.process_video_with_frame_numbers(video_path)

        if not keyframes_data:
            logger.warning(f"No keyframes extracted from {video_path}. Ending pipeline.")
            return []

        all_results = []
        points_to_upsert = []

        # 2. Run inference on each keyframe
        for frame_data in keyframes_data:
            frame = frame_data["frame"]
            frame_number = frame_data["frame_number"]
            timestamp = frame_data["timestamp"]

            # The new inference service expects a single frame
            detections = self.inference_service.run_inference(frame)

            # 3. Prepare results for storage and return
            frame_result = {
                "video_path": video_path,
                "frame_number": frame_number,
                "timestamp": timestamp,
                "detections": detections,
            }
            all_results.append(frame_result)

            # Create a point for the vector database
            # Note: The new inference service does not provide embeddings.
            # We will need to add a separate embedding step here if needed.
            # For now, we will use a placeholder zero vector.
            embedding_vector = [0.0] * self.settings.qdrant.embedding_dimension
            
            point = FramePoint(
                vector=embedding_vector,
                payload=frame_result,
            )
            points_to_upsert.append(point)

        # 4. Upsert all points to the vector database in a single batch
        if points_to_upsert:
            self.vector_db_service.upsert_points(points_to_upsert)
            logger.info(f"Upserted {len(points_to_upsert)} points to the vector database.")

        logger.info(f"Successfully completed analysis for: {video_path}")
        return all_results
