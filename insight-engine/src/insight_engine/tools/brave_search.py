"""Tool for interacting with the Brave Search API."""

import httpx
import logging
from insight_engine.agents.models import BraveSearchResult
from insight_engine.config import settings
from insight_engine.resilience import http_resilient
from insight_engine.resilience.fallbacks import FallbackManager

logger = logging.getLogger(__name__)

BRAVE_SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"


@http_resilient("brave_search", fallback=FallbackManager.brave_search_fallback)
async def _brave_search_api_call(query: str, count: int) -> list[dict]:
    """Internal function to make the actual API call."""
    if not settings.BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY environment variable not set.")

    headers = {
        "X-Subscription-Token": settings.BRAVE_API_KEY,
        "Accept": "application/json",
    }
    params = {"q": query, "count": count}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            BRAVE_SEARCH_API_URL, headers=headers, params=params
        )
        response.raise_for_status()
        results = response.json()
        return results.get("web", {}).get("results", [])


async def brave_search_tool(query: str, count: int = 5) -> list[BraveSearchResult]:
    """
    Performs a web search using the Brave Search API with resilience patterns.

    Args:
        query: The search query.
        count: The number of results to return.

    Returns:
        A list of BraveSearchResult objects.
    """
    try:
        web_results = await _brave_search_api_call(query, count)
        return [BraveSearchResult(**result) for result in web_results]
    except Exception as e:
        logger.error(f"Brave Search API call failed: {e}")
        # Return empty list as fallback
        return []
