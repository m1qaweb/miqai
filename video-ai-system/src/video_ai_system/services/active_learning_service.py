import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models

from .cvat_service import CVATService

logger = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_PROJECT_NAME = "Video-AI-Annotation"
DEFAULT_ANNOTATIONS_DIR = "data/annotations"
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_QUERY_LIMIT = 100
SIMULATED_FRAME_DATA = b"simulated_jpeg_data"

# Qdrant payload keys
QDRANT_KEY_DETECTIONS = "detections"
QDRANT_KEY_CONFIDENCE = "confidence"
QDRANT_KEY_FRAME_ID = "frame_id"
QDRANT_KEY_VIDEO_PATH = "video_path"
QDRANT_KEY_TIMESTAMP = "timestamp"


class LowConfidenceFrame(BaseModel):
    """Data structure for a frame with low-confidence detections."""

    frame_id: str = Field(..., description="Unique identifier for the frame.")
    video_path: str = Field(..., description="Path or identifier of the source video.")
    frame_data: Optional[bytes] = Field(
        None, description="The actual image data of the frame."
    )
    detections: List[Dict[str, Any]] = Field(
        ..., description="List of low-confidence detections."
    )
    timestamp: str = Field(..., description="Timestamp of the frame capture.")


class ActiveLearningService:
    """Service for active learning selection strategies."""

    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str,
        cvat_service: CVATService,
        project_name: str = DEFAULT_PROJECT_NAME,
        annotations_dir: str = DEFAULT_ANNOTATIONS_DIR,
    ):
        """
        Initializes the service.

        Args:
            qdrant_client: Client for interacting with Qdrant.
            collection_name: Name of the Qdrant collection for frames.
            cvat_service: Service for interacting with CVAT.
            project_name: Name of the CVAT project.
            annotations_dir: Directory to store downloaded annotations.
        """
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.cvat_service = cvat_service
        self.project_name = project_name
        self.annotations_dir = annotations_dir
        os.makedirs(self.annotations_dir, exist_ok=True)

    def get_low_confidence_frames(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        limit: int = DEFAULT_QUERY_LIMIT,
    ) -> List[LowConfidenceFrame]:
        """
        Queries Qdrant for frames with detections below a confidence threshold.
        """
        try:
            search_result, _ = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key=f"{QDRANT_KEY_DETECTIONS}.{QDRANT_KEY_CONFIDENCE}",
                            range=models.Range(lt=confidence_threshold),
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as e:
            logger.error(f"Failed to query low-confidence frames from Qdrant: {e}")
            return []

        frames = []
        for record in search_result:
            payload = record.payload
            if not payload:
                continue

            low_confidence_detections = [
                det
                for det in payload.get(QDRANT_KEY_DETECTIONS, [])
                if det.get(QDRANT_KEY_CONFIDENCE, 1.0) < confidence_threshold
            ]

            if low_confidence_detections:
                # In a real system, we'd fetch the frame_data here based on video_path and frame_id
                frames.append(
                    LowConfidenceFrame(
                        frame_id=payload.get(QDRANT_KEY_FRAME_ID, "unknown_frame"),
                        video_path=payload.get(QDRANT_KEY_VIDEO_PATH, "unknown_video"),
                        detections=low_confidence_detections,
                        timestamp=payload.get(
                            QDRANT_KEY_TIMESTAMP, datetime.utcnow().isoformat()
                        ),
                        frame_data=SIMULATED_FRAME_DATA,  # Placeholder
                    )
                )
        return frames

    def send_for_annotation(self, frame: LowConfidenceFrame) -> None:
        """
        Orchestrates sending a low-confidence frame to CVAT for annotation.

        Args:
            frame: The frame to be sent for annotation.
        """
        logger.info(f"Processing frame {frame.frame_id} for annotation.")

        project_id = self.cvat_service.get_or_create_project(self.project_name)
        if not project_id:
            logger.error(
                f"Could not get or create CVAT project '{self.project_name}'. Aborting annotation."
            )
            return

        task_name = f"Annotation-{datetime.utcnow().strftime('%Y-%m-%d')}"
        task_id = self.cvat_service.create_task(project_id, task_name)
        if not task_id:
            # This logic could be improved with a get_task_by_name method in CVATService.
            logger.error(
                f"Could not create or find CVAT task '{task_name}'. Aborting annotation."
            )
            return

        if not frame.frame_data:
            logger.error(f"Frame {frame.frame_id} has no data to upload. Aborting.")
            return

        frame_filename = f"{frame.frame_id}.jpg"
        success = self.cvat_service.upload_data(
            task_id, frame.frame_data, frame_filename
        )

        if success:
            logger.info(
                f"Successfully sent frame {frame.frame_id} to CVAT task {task_id}."
            )
        else:
            logger.error(f"Failed to upload frame {frame.frame_id} to CVAT.")

    def process_completed_annotations(self) -> None:
        """
        Retrieves, processes, and stores completed annotations from CVAT.
        """
        logger.info("Starting to process completed annotations from CVAT.")

        project_id = self.cvat_service.get_or_create_project(self.project_name)
        if not project_id:
            logger.error(
                f"Could not get CVAT project '{self.project_name}'. Aborting processing."
            )
            return

        completed_tasks = self.cvat_service.get_completed_tasks(project_id)
        if not completed_tasks:
            logger.info("No completed tasks found to process.")
            return

        for task in completed_tasks:
            task_id = task.get("id")
            if not task_id:
                continue

            logger.info(f"Processing completed task {task_id}.")

            annotation_data = self.cvat_service.get_task_annotations(task_id)
            if not annotation_data:
                logger.error(
                    f"Could not retrieve annotations for task {task_id}. Skipping."
                )
                continue

            # In a real implementation, this would parse the XML/JSON.
            logger.info(f"Parsing annotation data for task {task_id} (placeholder).")

            annotation_filename = f"task_{task_id}_annotations.xml"
            annotation_filepath = os.path.join(
                self.annotations_dir, annotation_filename
            )
            try:
                with open(annotation_filepath, "wb") as f:
                    f.write(annotation_data)
                logger.info(f"Successfully saved annotations to {annotation_filepath}")
            except IOError as e:
                logger.error(
                    f"Failed to save annotations for task {task_id} to {annotation_filepath}: {e}"
                )
                continue  # Don't delete the task if we failed to save the data

            logger.info(
                f"Annotations for task {task_id} processed. Deleting task from CVAT."
            )
            delete_success = self.cvat_service.delete_task(task_id)
            if not delete_success:
                logger.warning(
                    f"Failed to delete task {task_id} from CVAT. It may need manual cleanup."
                )

        logger.info("Finished processing completed annotations.")
