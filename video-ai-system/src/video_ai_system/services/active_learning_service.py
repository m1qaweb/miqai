from qdrant_client import QdrantClient, models
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class LowConfidenceFrame(BaseModel):
    """Data structure for a frame with low-confidence detections."""
    frame_id: str = Field(..., description="Unique identifier for the frame.")
    video_path: str = Field(..., description="Path or identifier of the source video.")
    detections: List[Dict[str, Any]] = Field(..., description="List of low-confidence detections.")
    timestamp: str = Field(..., description="Timestamp of the frame capture.")

class ActiveLearningService:
    """Service for active learning selection strategies."""

    def __init__(self, qdrant_client: QdrantClient, collection_name: str):
        """
        Initializes the service with a Qdrant client and collection name.
        """
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name

    def get_low_confidence_frames(
        self, confidence_threshold: float = 0.5, limit: int = 100
    ) -> List[LowConfidenceFrame]:
        """
        Queries Qdrant for frames with detections below a confidence threshold.

        Args:
            confidence_threshold: The upper bound for detection confidence.
            limit: The maximum number of frames to return.

        Returns:
            A list of LowConfidenceFrame objects.
        """
        search_result = self.qdrant_client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="detections.confidence",
                        range=models.Range(lt=confidence_threshold),
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        
        frames = []
        for record in search_result[0]:
            payload = record.payload
            # Assuming the payload structure matches what's needed for LowConfidenceFrame
            low_confidence_detections = [
                det for det in payload.get("detections", []) if det.get("confidence", 1.0) < confidence_threshold
            ]

            if low_confidence_detections:
                frames.append(
                    LowConfidenceFrame(
                        frame_id=payload.get("frame_id"),
                        video_path=payload.get("video_path"),
                        detections=low_confidence_detections,
                        timestamp=payload.get("timestamp"),
                    )
                )
        return frames