"""
Service for interacting with the Qdrant vector database.
"""

import uuid
import logging
from qdrant_client import QdrantClient, models
from typing import List, Dict, Any, Optional
from insight_engine.config import settings
from insight_engine.resilience import database_resilient

logger = logging.getLogger(__name__)


class VectorStoreError(Exception):
    """Custom exception for vector store operations."""

    pass


class VectorStoreService:
    """A service to manage interactions with a Qdrant vector database."""

    def __init__(self, collection_name: Optional[str] = None):
        """
        Initializes the VectorStoreService.

        Args:
            collection_name: The name of the collection to use. If not provided,
                             it defaults to the value from the global settings.
        """
        if not settings.qdrant.url:
            raise VectorStoreError("QDRANT_URL must be set in the environment.")

        self.client = QdrantClient(
            url=settings.qdrant.url, api_key=settings.qdrant.api_key
        )
        self.collection_name = collection_name or settings.qdrant.collection

    @database_resilient("qdrant_create_collection", fallback=lambda *args, **kwargs: None)
    async def create_collection(self, embedding_size: int = 768):
        """
        Creates a new collection if it doesn't already exist with resilience patterns.
        """
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=embedding_size, distance=models.Distance.COSINE
            ),
        )
        logger.info(f"Collection '{self.collection_name}' created successfully.")

    @database_resilient("qdrant_upsert", fallback=lambda *args, **kwargs: None)
    async def upsert_documents(
        self,
        documents: List[Dict[str, Any]],
        vectors: List[List[float]],
        visual_context: Optional[List[str]] = None,
    ):
        """
        Upserts (inserts or updates) documents and their vectors into the collection with resilience patterns.
        """
        if len(documents) != len(vectors):
            raise VectorStoreError(
                "The number of documents must match the number of vectors."
            )

        points = []
        for i, (doc, vector) in enumerate(zip(documents, vectors)):
            payload = doc
            if visual_context and i < len(visual_context):
                payload["visual_context"] = visual_context[i]
            
            points.append(
                models.PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload)
            )

        if not points:
            return

        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        logger.info(f"Upserted {len(points)} points into '{self.collection_name}'.")

    @database_resilient("qdrant_search", fallback=lambda *args, **kwargs: [])
    async def search(
        self, query_vector: List[float], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Searches for similar vectors in the collection with resilience patterns.
        """
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
        )
        return [{"payload": hit.payload, "score": hit.score} for hit in search_result]
