from typing import List
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from video_ai_system.services.vector_db_service import VectorDBService


class AnalyticsService:
    """
    Service for handling analytics queries against the vector database.
    """

    def __init__(self, vector_db_service: VectorDBService):
        """
        Initializes the AnalyticsService.

        Args:
            vector_db_service: An instance of the VectorDBService to interact with Qdrant.
        """
        self.db_service = vector_db_service

    async def get_unique_video_ids(self) -> List[str]:
        """
        Retrieves a list of unique video IDs from the vector database.

        This is done by scrolling through all points and collecting the unique
        values from the 'video_path' payload field.

        Returns:
            A list of unique video ID strings.
        """
        all_points = []
        next_offset = None
        while True:
            points, next_offset = self.db_service.client.scroll(
                collection_name=self.db_service.collection_name,
                limit=250,
                with_payload=["video_path"],
                with_vectors=False,
                offset=next_offset,
            )
            all_points.extend(points)
            if next_offset is None:
                break

        unique_video_ids = {point.payload["video_path"] for point in all_points}
        return sorted(list(unique_video_ids))

    async def get_frames_for_video(self, video_id: str) -> List[dict]:
        """
        Retrieves all frame data for a given video ID.

        Args:
            video_id: The unique identifier for the video (e.g., filename).

        Returns:
            A list of dictionaries, where each dictionary represents a frame's data.
        """
        all_points = []
        next_offset = None
        while True:
            points, next_offset = self.db_service.client.scroll(
                collection_name=self.db_service.collection_name,
                limit=1000,
                with_payload=True,
                with_vectors=False,
                offset=next_offset,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="video_path",
                            match=MatchValue(value=video_id),
                        )
                    ]
                ),
            )
            all_points.extend(points)
            if next_offset is None:
                break

        # Sort frames by frame number to ensure correct order
        sorted_points = sorted(all_points, key=lambda p: p.payload["frame_number"])
        return [p.payload for p in sorted_points]
