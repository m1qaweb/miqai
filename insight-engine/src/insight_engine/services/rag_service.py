"""
Service for handling the RAG pipeline for video analysis.
"""

import json
import asyncio
import random
from typing import AsyncGenerator
from fastapi import BackgroundTasks
import arq

from insight_engine.services.summarization_chain import RAGChain
from insight_engine.services.vector_store_service import (
    VectorStoreService,
    VectorStoreError,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings


class RAGServiceError(Exception):
    """Custom exception for RAG service failures."""

    pass


async def process_query_stream(
    file_path: str,
    query: str,
    redis_pool: arq.ArqRedis,
    background_tasks: BackgroundTasks,
) -> AsyncGenerator[str, None]:
    """
    Orchestrates the RAG pipeline and streams the response.
    """
    try:
        # For this simulation, we'll use a hardcoded transcript.
        # In a real system, this would come from the analysis pipeline.
        yield f"data: {json.dumps({'status': 'Generating mock transcript...'})}\n\n"
        transcript = "The video shows a person walking their dog in the park. The dog is a golden retriever. Later, a car drives by on a nearby road."
        
        yield f"data: {json.dumps({'status': 'Processing and ingesting content...'})}\n\n"

        vector_store = VectorStoreService(collection_name="video_insights")

        # Offload the ingestion to a background task
        background_tasks.add_task(
            ingest_multi_modal_content, transcript, file_path, vector_store
        )

        # Allow a moment for ingestion to potentially start
        await asyncio.sleep(1)

        yield f"data: {json.dumps({'status': 'Generating answer...'})}\n\n"
        rag_chain = RAGChain(vector_store=vector_store)

        stream_generator = await rag_chain.stream(question=query)
        async for chunk in stream_generator:
            yield f"data: {json.dumps({'token': chunk})}\n\n"

    except (VectorStoreError, Exception) as e:
        error_message = str(e).replace("\n", " ")
        yield f"data: {json.dumps({'error': error_message})}\n\n"

    yield f"data: {json.dumps({'status': 'done'})}\n\n"


def ingest_multi_modal_content(
    transcript: str, file_path: str, vector_store: VectorStoreService
):
    """
    A background task to handle the embedding and storage of both the
    transcript and simulated visual data.
    """
    print(f"Background task started: Ingesting multi-modal content for {file_path}")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=10)
    documents = text_splitter.create_documents([transcript])

    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

    # Simulate different visual contexts for different parts of the video
    mock_visual_data = {
        0: ["person", "dog", "tree", "park bench"],
        1: ["dog", "golden retriever", "grass"],
        2: ["car", "road", "tree"],
    }

    for i, doc in enumerate(documents):
        text = doc.page_content
        vector = embeddings.embed_query(text)
        metadata = {"source_video": file_path, "chunk_text": text}
        visual_context = mock_visual_data.get(i, []) # Get mock data or an empty list

        vector_store.upsert_documents(
            documents=[metadata], vectors=[vector], visual_context=visual_context
        )

    print(f"Background task finished: Ingestion complete for {file_path}")
