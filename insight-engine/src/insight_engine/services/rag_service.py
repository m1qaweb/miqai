from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from insight_engine.agents.summarization_agent import SummarizationAgent
from insight_engine.agents.rag_utils import RAGInput
from insight_engine.tools.vector_store import VectorStore
from insight_engine.services.redis_service import RedisService, get_redis_service


class RAGService:
    """
    Service for the Retrieval-Augmented Generation (RAG) pipeline.
    """

    def __init__(
        self,
        redis_service: RedisService = Depends(get_redis_service),
    ):
        """
        Initializes the RAG service.

        Args:
            redis_service: The RedisService dependency.
        """
        self.redis_service = redis_service

    async def get_summary_stream(
        self, user_query: str, video_id: str, user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Retrieves context and generates a summary stream, with caching.

        Args:
            user_query: The user's query.
            video_id: The ID of the video to summarize.

        Yields:
            A stream of summary tokens.
        """
        # --- Authorization Check ---
        # Verify that the user is authorized to access the video.
        vector_store = VectorStore()
        vector_store = VectorStore()
        video_metadata = await vector_store.get_video_metadata(video_id)

        if not video_metadata or video_metadata.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to this video.",
            )

        cache_key = f"summary:{video_id}:{user_query}"
        cached_summary = await self.redis_service.get(cache_key)

        if cached_summary:
            yield cached_summary
            return

        summarization_agent = SummarizationAgent(
            vector_store=vector_store, collection_name=video_id
        )
        rag_input = RAGInput(query=user_query)

        full_summary = []
        response_stream = summarization_agent.generate_summary(rag_input)
        async for chunk in response_stream:
            full_summary.append(chunk)
            yield chunk

        # Cache the full response
        await self.redis_service.set(cache_key, "".join(full_summary))
