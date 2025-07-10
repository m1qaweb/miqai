import asyncio
import json
from typing import AsyncGenerator, List, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.documents import Document
from pydantic import ValidationError

from insight_engine.agents.agent import RAGInput, run_rag_agent

# --- Mock Fixtures ---

@pytest.fixture
def mock_llm(mocker):
    """Mocks the BaseChatModel to stream a predefined response."""
    mock = mocker.AsyncMock()

    async def stream_chunks(*args, **kwargs) -> AsyncGenerator[str, None]:
        for chunk in ["Lang", "Chain", " is", " great", "."]:
            yield chunk
            await asyncio.sleep(0.01)

    mock.astream = stream_chunks
    # Add the 'astream' method to the mock's spec
    mocker.patch('langchain_core.language_models.BaseChatModel.astream', new=stream_chunks)
    return mock

@pytest.fixture
def mock_retriever(mocker):
    """Mocks the VectorStoreRetriever."""
    mock = mocker.AsyncMock()
    mock.ainvoke = AsyncMock(
        return_value=[
            Document(page_content="Doc 1: LangChain"),
            Document(page_content="Doc 2: RAG"),
        ]
    )
    # Add the 'ainvoke' method to the mock's spec
    mocker.patch('langchain_core.vectorstores.VectorStoreRetriever.ainvoke', new=mock.ainvoke)
    return mock

@pytest.fixture
def mock_failing_retriever(mocker):
    """Mocks a retriever that raises an exception."""
    mock = mocker.AsyncMock()
    mock.ainvoke.side_effect = Exception("Vector DB connection error")
    mocker.patch('langchain_core.vectorstores.VectorStoreRetriever.ainvoke', new=mock.ainvoke)
    return mock


# --- Test Cases ---

@pytest.mark.asyncio
async def test_run_rag_agent_success_stream(mock_llm, mock_retriever):
    """
    Tests the successful execution of the RAG agent, verifying the streamed response.
    """
    # Arrange
    agent_input = RAGInput(query="What is LangChain?")
    full_response = []

    # Act
    async for chunk in run_rag_agent(agent_input, mock_llm, mock_retriever):
        full_response.append(chunk)

    # Assert
    assert "".join(full_response) == "LangChain is great."
    mock_retriever.ainvoke.assert_awaited_once_with("What is LangChain?")
    # We can't easily assert the call to the chain astream, but we know it was called
    # because we received the streamed response from the mock_llm.

@pytest.mark.asyncio
async def test_run_rag_agent_retriever_failure(mock_llm, mock_failing_retriever, caplog):
    """
    Tests how the agent handles an exception during document retrieval.
    """
    # Arrange
    agent_input = RAGInput(query="A query that will fail.")
    results = []

    # Act
    async for chunk in run_rag_agent(agent_input, mock_llm, mock_failing_retriever):
        results.append(chunk)

    # Assert
    assert len(results) == 1
    error_output = json.loads(results[0])
    assert "error" in error_output
    assert error_output["error"] == "An unexpected error occurred."

    # Check logs for the exception
    assert "An error occurred during RAG agent execution" in caplog.text
    assert "Vector DB connection error" in caplog.text

def test_rag_input_validation():
    """
    Tests the Pydantic validation for the RAGInput model.
    """
    # Valid data
    try:
        RAGInput(query="test", chat_history=[{"role": "user", "content": "hi"}])
    except ValidationError as e:
        pytest.fail(f"Validation failed unexpectedly: {e}")

    # Invalid data - missing query
    with pytest.raises(ValidationError):
        RAGInput(chat_history=[])  # type: ignore

    # Invalid data - wrong type for chat_history
    with pytest.raises(ValidationError):
        RAGInput(query="test", chat_history="not a list")  # type: ignore