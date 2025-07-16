"""
This module provides an interface to interact with a Qdrant vector store.
It encapsulates the logic for creating collections, upserting vectors, and performing
similarity searches, which are essential for the RAG pipeline.
"""
import uuid
from typing import List, Optional

from qdrant_client import QdrantClient, models

class VectorStore:
    """A client for interacting with a Qdrant vector database."""

    def __init__(self, host: str = "localhost", port: int = 6333):
        """
        Initializes the Qdrant client.

        Args:
            host: The hostname of the Qdrant instance.
            port: The port number of the Qdrant instance.
        """
        self._host = host
        self._port = port
        self._client = None

    @property
    def client(self):
        """
        Lazily initializes and returns the Qdrant client.
        This ensures the application can start even if Qdrant is not immediately available.
        """
        if self._client is None:
            try:
                self._client = QdrantClient(host=self._host, port=self._port)
            except Exception as e:
                # In a production environment, you'd want to handle this more gracefully.
                # For now, we'll re-raise the exception to make the issue visible.
                print(f"Error connecting to Qdrant: {e}")
                raise
        return self._client

    def recreate_collection(self, collection_name: str, vector_size: int):
        """
        Creates a new collection in Qdrant if it doesn't already exist.

        Args:
            collection_name: The name of the collection to create.
            vector_size: The dimensionality of the vectors that will be stored.
        """
        self.client.recreate_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    def upsert(self, collection_name: str, vectors: List[List[float]], payloads: List[dict]):
        """
        Upserts (inserts or updates) vectors into a specified collection.

        Args:
            collection_name: The name of the collection.
            vectors: A list of vector embeddings.
            payloads: A list of metadata dictionaries corresponding to each vector.
        """
        self.client.upsert(
            collection_name=collection_name,
            points=models.Batch(
                ids=[str(uuid.uuid4()) for _ in vectors],
                vectors=vectors,
                payloads=payloads,
            ),
            wait=True,
        )

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[models.ScoredPoint]:
        """
        Performs a similarity search in the specified collection.

        Args:
            collection_name: The name of the collection to search in.
            query_vector: The vector to search with.
            limit: The maximum number of results to return.
            score_threshold: An optional threshold to filter results by score.

        Returns:
            A list of ScoredPoint objects representing the search results.
        """
        return self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )

    async def get_video_metadata(self, collection_name: str) -> Optional[dict]:
        """
        Retrieves the metadata of the first point in a collection.

        Args:
            collection_name: The name of the collection (video_id).

        Returns:
            The payload of the first point, or None if not found.
        """
        try:
            points, _ = self.client.scroll(
                collection_name=collection_name,
                limit=1,
                with_payload=True,
            )
            if points:
                return points[0].payload
            return None
        except Exception:
            # If the collection doesn't exist or there's an error, return None.
            return None
