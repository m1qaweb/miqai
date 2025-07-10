"""Unit tests for the tools."""

import pytest
from unittest.mock import AsyncMock, patch
from insight_engine.tools.brave_search import brave_search_tool, BraveSearchResult


@pytest.mark.asyncio
async def test_brave_search_tool_success():
    """Test the brave_search_tool for a successful API call."""
    mock_response = {
        "web": {
            "results": [
                {
                    "title": "Test Title",
                    "url": "https://example.com",
                    "description": "Test description.",
                }
            ]
        }
    }
    with patch("httpx.AsyncClient") as mock_client:
        mock_async_client = mock_client.return_value.__aenter__.return_value
        mock_async_client.get.return_value.status_code = 200
        mock_async_client.get.return_value.json = AsyncMock(return_value=mock_response)
        mock_async_client.get.return_value.raise_for_status = AsyncMock()

        results = await brave_search_tool("test query")
        assert len(results) == 1
        assert isinstance(results[0], BraveSearchResult)
        assert results[0].title == "Test Title"


@pytest.mark.asyncio
async def test_brave_search_tool_error():
    """Test the brave_search_tool for an HTTP error."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_async_client = mock_client.return_value.__aenter__.return_value
        mock_async_client.get.return_value.raise_for_status.side_effect = Exception(
            "HTTP Error"
        )

        results = await brave_search_tool("test query")
        assert len(results) == 0
