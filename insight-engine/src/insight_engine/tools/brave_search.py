"""Tool for interacting with the Brave Search API."""

import httpx
from insight_engine.agents.models import BraveSearchResult
from insight_engine.config import settings

BRAVE_SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"


async def brave_search_tool(query: str, count: int = 5) -> list[BraveSearchResult]:
    """
    Performs a web search using the Brave Search API.

    Args:
        query: The search query.
        count: The number of results to return.

    Returns:
        A list of BraveSearchResult objects.
    """
    if not settings.BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY environment variable not set.")

    headers = {
        "X-Subscription-Token": settings.BRAVE_API_KEY,
        "Accept": "application/json",
    }
    params = {"q": query, "count": count}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                BRAVE_SEARCH_API_URL, headers=headers, params=params
            )
            response.raise_for_status()
            results = response.json()
            web_results = results.get("web", {}).get("results", [])
            return [BraveSearchResult(**result) for result in web_results]
        except httpx.HTTPStatusError as e:
            print(f"Error calling Brave Search API: {e}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return []
