"""
Tests for the streaming RAG (Retrieval-Augmented Generation) pipeline in the unified architecture.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from insight_engine.services.rag_service import process_query_stream

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

DUMMY_FILE_PATH = "/fake/video.mp4"
DUMMY_QUERY = "What is this video about?"
DUMMY_TASK_ID = "task-12345"


@pytest.fixture
def mock_redis_pool(mocker):
    """Fixture to mock the arq Redis pool and the job object."""
    mock_job = AsyncMock()
    mock_job.job_id = DUMMY_TASK_ID
    mock_job.info.return_value = AsyncMock(success=True)
    mock_job.result.return_value = {"transcript": "This is the transcript."}

    mock_pool = AsyncMock()
    mock_pool.enqueue_job.return_value = mock_job
    return mock_pool


@pytest.fixture
def mock_vector_store(mocker):
    """Fixture to mock the VectorStoreService."""
    with patch("insight_engine.services.vector_store_service.QdrantClient"):
        mock_store_instance = MagicMock()
        mock_store_instance.upsert_documents = MagicMock()
        mocker.patch(
            "insight_engine.services.rag_service.VectorStoreService",
            return_value=mock_store_instance,
        )
        yield mock_store_instance


@pytest.fixture
def mock_rag_chain(mocker):
    """Fixture to mock the RAGChain for streaming."""
    mock_chain_instance = MagicMock()

    async def stream_generator():
        yield "This "
        yield "is "
        yield "a "
        yield "streamed "
        yield "answer."

    mock_chain_instance.stream = AsyncMock(return_value=stream_generator())
    mocker.patch(
        "insight_engine.services.rag_service.RAGChain", return_value=mock_chain_instance
    )
    return mock_chain_instance


@pytest.fixture
def mock_embeddings(mocker):
    """Fixture to mock the embedding model."""
    mock_embed_instance = MagicMock()
    mock_embed_instance.embed_documents.return_value = [[0.1, 0.2, 0.3]]
    mocker.patch(
        "insight_engine.services.rag_service.GoogleGenerativeAIEmbeddings",
        return_value=mock_embed_instance,
    )
    mocker.patch(
        "insight_engine.services.summarization_chain.GoogleGenerativeAIEmbeddings",
        return_value=mock_embed_instance,
    )
    return mock_embed_instance


@pytest.mark.usefixtures("mock_embeddings")
class TestStreamingRAGPipeline:

    async def test_streaming_rag_service_success(
        self, mock_redis_pool, mock_vector_store, mock_rag_chain
    ):
        """
        Verify the full streaming RAG pipeline yields correct SSE messages.
        """
        # Act
        generator = process_query_stream(
            DUMMY_FILE_PATH, DUMMY_QUERY, mock_redis_pool, BackgroundTasks()
        )
        results = [json.loads(item.replace("data: ", "")) async for item in generator]

        # Assert
        assert results[0] == {"status": "Queueing video for analysis..."}
        assert results[1] == {
            "status": "Analysis in progress...",
            "task_id": DUMMY_TASK_ID,
        }

        tokens = [r["token"] for r in results if "token" in r]
        assert "".join(tokens) == "This is a streamed answer."

        assert results[-1] == {"status": "done"}

        mock_redis_pool.enqueue_job.assert_awaited_once_with(
            "analyze_video", file_path=DUMMY_FILE_PATH
        )
        mock_rag_chain.stream.assert_awaited_once_with(question=DUMMY_QUERY)

    async def test_streaming_rag_service_handles_job_failure(self, mock_redis_pool):
        """
        Verify the streaming service yields an error if the arq job fails.
        """
        # Arrange
        mock_job = AsyncMock()
        mock_job.job_id = DUMMY_TASK_ID
        mock_job.info.return_value = AsyncMock(
            success=False, result=ValueError("Job failed")
        )
        mock_redis_pool.enqueue_job.return_value = mock_job

        # Act
        generator = process_query_stream(
            DUMMY_FILE_PATH, DUMMY_QUERY, mock_redis_pool, BackgroundTasks()
        )
        results = [json.loads(item.replace("data: ", "")) async for item in generator]

        # Assert
        assert "error" in results[-2]
        assert "Analysis task failed" in results[-2]["error"]
        assert results[-1] == {"status": "done"}
