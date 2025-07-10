import logging
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from starlette.status import HTTP_401_UNAUTHORIZED

from insight_engine.config import settings

API_KEY_HEADER = "X-API-Key"

api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)

logger = logging.getLogger(__name__)


async def get_api_key(api_key_header: str = Security(api_key_header)):
    """
    Dependency to validate the API key from the request header.

    Args:
        api_key_header: The API key passed in the 'X-API-Key' header.

    Raises:
        HTTPException: If the API key is missing or invalid.

    Returns:
        The validated API key.
    """
    if not settings.api_key:
        logger.critical(
            "API key is not configured on the server. Denying all requests."
        )
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials: API key not configured.",
        )

    if api_key_header == settings.api_key:
        return api_key_header
    else:
        logger.warning("Invalid API key received.")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials: Invalid API key.",
        )
