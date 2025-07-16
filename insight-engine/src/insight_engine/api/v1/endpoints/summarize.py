import bleach
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from insight_engine.api.v1.schemas import SummarizationRequest
from insight_engine.services.rag_service import RAGService
from insight_engine.security import get_current_user

router = APIRouter()


async def format_as_sse(stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    """Formats the stream from the RAG service into SSE format."""
    async for chunk in stream:
        yield f"data: {chunk}\n\n"


@router.post("/summarize")
async def summarize_video(
    request: SummarizationRequest,
    rag_service: RAGService = Depends(),
    current_user: dict = Depends(get_current_user),
):
    """
    Accepts a video ID and a query, and streams a summarization response.
    """
    # Authorization: Ensure the user has access to the video_id.
    # This logic should be implemented within the RAGService.
    # For now, we pass the user to the service.
    user_id = current_user.get("username")
    
    # Sanitize the user's query to prevent XSS attacks.
    sanitized_query = bleach.clean(request.query)
    
    summary_stream = rag_service.get_summary_stream(
        user_query=sanitized_query, video_id=request.video_id, user_id=user_id
    )
    return StreamingResponse(
        format_as_sse(summary_stream), media_type="text/event-stream"
    )