import asyncio
import uuid
from typing import List, Dict, Any, Optional

import vertexai
from qdrant_client import QdrantClient, models
from vertexai.language_models import TextEmbeddingModel

class VectorStore:
    """A service for handling text embeddings and vector database interactions."""

    def __init__(self, project_id: str, location: str, collection_name: str = "video_transcripts"):
        """
        Initializes the VectorStore, setting up the Qdrant client and Vertex AI embedding model.
        """
        vertexai.init(project=project_id, location=location)
        self.qdrant_client = QdrantClient(":memory:")
        self.embedding_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@001")
        self.collection_name = collection_name

        self.qdrant_client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding for the given text using Vertex AI.
        """
        # Run the synchronous SDK call in a thread to avoid blocking the event loop
        def get_sync_embeddings():
            embeddings = self.embedding_model.get_embeddings([text])
            return embeddings[0].values
        
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(None, get_sync_embeddings)
        return embedding

    async def upsert_document(self, document_text: str, metadata: Dict[str, Any]) -> str:
        """
        Generates an embedding for the document and upserts it into the Qdrant collection.

        Args:
            document_text: The text content of the document.
            metadata: A dictionary of metadata associated with the document.

        Returns:
            The unique ID of the upserted document.
        """
        embedding = await self._generate_embedding(document_text)
        doc_id = str(uuid.uuid4())
        
        payload = {"text": document_text, **metadata}

        await asyncio.to_thread(
            self.qdrant_client.upsert,
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
        )
        return doc_id

    async def query(self, query_text: str, top_k: int = 5) -> List[str]:
        """
        Searches the vector database for documents similar to the query text.

        Args:
            query_text: The text to search for.
            top_k: The number of top results to return.

        Returns:
            A list of strings representing the text of the top search results.
        """
        query_embedding = await self._generate_embedding(query_text)
        
        search_result = await asyncio.to_thread(
            self.qdrant_client.search,
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
        )
        
        results = []
        for hit in search_result:
            if hit.payload and "text" in hit.payload:
                results.append(hit.payload["text"])
        return results
