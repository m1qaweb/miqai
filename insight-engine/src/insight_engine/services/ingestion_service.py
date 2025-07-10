"""
Service to handle the serverless ingestion and analysis of a video file.
"""
import logging
from insight_engine.services.pipeline_service import PipelineService

logger = logging.getLogger(__name__)

class IngestionService:
    """
    Orchestrates the video analysis pipeline in a simulated serverless environment.
    """

    def __init__(self, pipeline_service: PipelineService):
        """
        Initializes the IngestionService.

        Args:
            pipeline_service: An instance of the PipelineService to run the analysis.
        """
        self.pipeline_service = pipeline_service
        logger.info("IngestionService initialized.")

    async def process_video(self, file_path: str):
        """
        Processes a single video file through the analysis pipeline.
        This method would be triggered by a cloud event (e.g., a new file in a bucket).

        Args:
            file_path: The path to the video file in the "cloud bucket".
        """
        logger.info(f"Starting ingestion and analysis for: {file_path}")
        try:
            # The pipeline service already contains the full logic for processing a video.
            # In the future, we can pass more context here if needed.
            # For now, we just need to execute the main video pipeline.
            # Note: The original PipelineService had a hardcoded pipeline name.
            # We will need to ensure a default or appropriate pipeline is called.
            # Let's assume a 'video_analysis_pipeline' for now.
            await self.pipeline_service.execute_pipeline(
                pipeline_name="video_analysis_pipeline", initial_data={"file_path": file_path}
            )
            logger.info(f"Successfully completed analysis for: {file_path}")
        except Exception as e:
            logger.error(f"Failed to process video {file_path}: {e}", exc_info=True)
            # In a real serverless function, you might move the file to a "failed"
            # directory or log the error to a monitoring service.
            raise

