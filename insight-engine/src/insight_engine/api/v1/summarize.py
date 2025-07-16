"""API endpoints for video summarization."""

import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
import os

from insight_engine.dependencies import get_rag_service, get_multimodal_extractor
from insight_engine.security import get_current_user
from insight_engine.services.multimodal_extractor import MultimodalExtractor
from insight_engine.services.rag_service import RAGService

router = APIRouter()


@router.post("/process")
async def process_video_for_rag(
    video_uri: str = Query(..., description="The GCS URI of the video to process."),
    rag_service: RAGService = Depends(get_rag_service),
    extractor: MultimodalExtractor = Depends(get_multimodal_extractor),
):
    """
    Processes a video, extracts data, and stores it in the vector store.
    """
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        raise ValueError("GCP_PROJECT_ID environment variable not set.")
    extracted_data = await extractor.extract_data(video_uri, project_id)
    video_id = video_uri.split("/")[-1]  # Extract a unique ID from the URI
    rag_service.process_and_store(extracted_data.transcript, video_id)
    return {"status": "processing_complete", "video_id": video_id}


@router.get(
    "/",
    summary="Generate a summary for a video",
)
async def summarize_video(
    video_id: str = Query(..., description="The unique ID of the video."),
    q: str = Query(..., description="The user query for summarization."),
    rag_service: RAGService = Depends(get_rag_service),
    _: str = Depends(get_current_user),
) -> StreamingResponse:
    """
    Generates a text summary for a video specified by its GCS URI.
    This endpoint returns a `StreamingResponse` with Server-Sent Events (SSE).
    """

    async def sse_generator() -> AsyncGenerator[str, None]:
        """SSE generator to stream the RAG summary."""
        try:
            summary = rag_service.generate_summary(q, video_id)
            summary_payload = {"summary": summary}
            yield f"data: {json.dumps(summary_payload)}\n\n"
        except Exception as e:
            error_payload = {"error": f"An error occurred: {str(e)}"}
            yield f"data: {json.dumps(error_payload)}\n\n"
        finally:
            yield "data: END_OF_STREAM\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")