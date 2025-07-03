import uuid
from typing import Any, Dict, List

import qdrant_client
from pydantic import BaseModel, Field
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    PointStruct,
    Range,
    ScoredPoint,
    VectorParams,
)

from video_ai_system.config import settings


class Detection(BaseModel):
    """Represents a single object detection."""

    box: List[float] = Field(description="Bounding box coordinates [x1, y1, x2, y2]")
    label: str = Field(description="Class label of the detected object")
    score: float = Field(description="Confidence score of the detection")


class FramePayload(BaseModel):
    """
    Qdrant payload schema for a single video frame's analysis result.
    """

    video_path: str = Field(description="Path or URL of the source video")
    frame_number: int = Field(description="The frame number in the video")
    timestamp: float = Field(description="Timestamp of the frame in seconds")
    model_version: str = Field(description="Version of the model used for inference")
    detections: List[Detection] = Field(description="List of raw object detections")

    # Optional field for any other metadata
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class FramePoint(BaseModel):
    """
    Represents a single point to be upserted to Qdrant.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vector: List[float]
    payload: FramePayload


class VectorDBService:
    def __init__(self):
        self.client = qdrant_client.QdrantClient(host=settings.qdrant.host, port=settings.qdrant.port)
        self.collection_name = settings.qdrant.collection
        self.embedding_dim = settings.qdrant.embedding_dimension

    def initialize_collection(self):
        """
        Creates the Qdrant collection if it doesn't already exist.
        This should be called on worker startup.
        """
        try:
            self.client.get_collection(collection_name=self.collection_name)
            print(f"Collection '{self.collection_name}' already exists.")
        except Exception:
            print(f"Collection '{self.collection_name}' not found. Creating...")
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.embedding_dim, distance=Distance.COSINE),
            )
            print("Collection created successfully.")

    def upsert_points(self, points: List[FramePoint]):
        """
        Upserts a batch of points into the Qdrant collection.
        """
        if not points:
            return

        point_structs = [
            PointStruct(id=p.id, vector=p.vector, payload=p.payload.model_dump()) for p in points
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            wait=False,  # Fire-and-forget for performance
            points=point_structs,
        )
        print(f"Upserted {len(points)} points to '{self.collection_name}'.")

    def get_embeddings_by_timestamp(self, start_ts: float, end_ts: float) -> List[ScoredPoint]:
        """
        Retrieves points from the Qdrant collection within a specified timestamp range.

        Args:
            start_ts (float): The start of the time window (as a Unix timestamp).
            end_ts (float): The end of the time window (as a Unix timestamp).

        Returns:
            A list of ScoredPoint objects matching the time range.
        """
        print(f"Fetching embeddings from {start_ts} to {end_ts}")
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=10000,  # Set a reasonable limit for a single query
            with_payload=True,
            with_vectors=True,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="timestamp",
                        range=Range(gte=start_ts, lte=end_ts),
                    )
                ]
            ),
        )
        print(f"Found {len(points)} points in the time range.")
        return points