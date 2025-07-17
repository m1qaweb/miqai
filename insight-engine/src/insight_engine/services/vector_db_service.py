import os
from typing import List, Optional
import logging

from qdrant_client import QdrantClient, models
from insight_engine.resilience import database_resilient

logger = logging.getLogger(__name__)


class VectorDBService:
    """
    A service to interact with the Qdrant vector database.
    """

    def __init__(self, host: Optional[str] = None, port: Optional[int] = 6333):
        """
        Initializes the Qdrant client.

        Args:
            host: The Qdrant host. Defaults to the QDRANT_HOST env variable.
            port: The Qdrant port. Defaults to 6333.
        """
        self.host = host or os.environ["QDRANT_HOST"]
        self.port = port
        self.client = QdrantClient(host=self.host, port=self.port)

    @database_resilient("qdrant_search", fallback=lambda *args, **kwargs: [])
    async def similarity_search(
        self, collection_name: str, query_vector: List[float], limit: int = 5
    ) -> List[models.ScoredPoint]:
        """
        Performs a similarity search in the vector database with resilience patterns.

        Args:
            collection_name: The name of the collection to search in.
            query_vector: The vector to search for.
            limit: The maximum number of results to return.

        Returns:
            A list of search results.
        """
        return self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
        )
