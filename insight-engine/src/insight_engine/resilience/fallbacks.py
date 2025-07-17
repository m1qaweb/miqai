"""Fallback mechanisms for external service failures."""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FallbackManager:
    """Manages fallback strategies for different services."""
    
    @staticmethod
    async def brave_search_fallback(*args, **kwargs) -> List[Dict[str, Any]]:
        """
        Fallback for Brave Search API failures.
        Returns empty search results with appropriate logging.
        """
        query = kwargs.get('query', args[0] if args else 'unknown')
        logger.warning(f"Brave Search API unavailable, returning empty results for query: {query}")
        
        return []
    
    @staticmethod
    async def video_ai_fallback(*args, **kwargs) -> tuple[str, Dict[str, Any]]:
        """
        Fallback for Video AI service failures.
        Returns a placeholder task ID and empty result.
        """
        file_path = kwargs.get('file_path', args[0] if args else 'unknown')
        logger.warning(f"Video AI service unavailable for file: {file_path}")
        
        fallback_task_id = f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        fallback_result = {
            "status": "fallback",
            "message": "Video AI service unavailable, using fallback response",
            "analysis": {},
            "timestamp": datetime.now().isoformat()
        }
        
        return fallback_task_id, fallback_result
    
    @staticmethod
    async def speech_to_text_fallback(*args, **kwargs) -> str:
        """
        Fallback for Google Cloud Speech-to-Text failures.
        Returns empty transcript with logging.
        """
        video_uri = kwargs.get('video_uri', args[0] if args else 'unknown')
        logger.warning(f"Speech-to-Text service unavailable for video: {video_uri}")
        
        return ""
    
    @staticmethod
    async def video_intelligence_fallback(*args, **kwargs) -> List[str]:
        """
        Fallback for Google Cloud Video Intelligence failures.
        Returns empty labels list with logging.
        """
        video_uri = kwargs.get('video_uri', args[0] if args else 'unknown')
        logger.warning(f"Video Intelligence service unavailable for video: {video_uri}")
        
        return []
    
    @staticmethod
    async def dlp_fallback(text: str, *args, **kwargs) -> str:
        """
        Fallback for Google Cloud DLP failures.
        Uses basic regex patterns for common PII redaction.
        """
        logger.warning("DLP service unavailable, using basic regex redaction")
        
        import re
        
        # Basic email redaction
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_ADDRESS]', text)
        
        # Basic phone number redaction (US format)
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_NUMBER]', text)
        
        # Basic SSN redaction
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
        
        return text
    
    @staticmethod
    async def storage_fallback(*args, **kwargs) -> Optional[Any]:
        """
        Fallback for Google Cloud Storage failures.
        Logs the failure and returns None.
        """
        logger.error("Google Cloud Storage unavailable, operation failed")
        return None
    
    @staticmethod
    async def pubsub_fallback(*args, **kwargs) -> bool:
        """
        Fallback for Google Cloud Pub/Sub failures.
        Logs the failure and returns False to indicate failure.
        """
        logger.error("Google Cloud Pub/Sub unavailable, message not published")
        return False
    
    @staticmethod
    async def health_check_fallback(*args, **kwargs) -> Dict[str, Any]:
        """
        Fallback for health check service failures.
        Returns a degraded health status.
        """
        logger.warning("Health check service unavailable, returning degraded status")
        
        return {
            "status": "degraded",
            "message": "Health check service unavailable",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "external_health_check": "unavailable"
            }
        }


# Convenience functions for common fallback patterns
async def empty_list_fallback(*args, **kwargs) -> List[Any]:
    """Generic fallback that returns an empty list."""
    return []


async def empty_dict_fallback(*args, **kwargs) -> Dict[str, Any]:
    """Generic fallback that returns an empty dictionary."""
    return {}


async def empty_string_fallback(*args, **kwargs) -> str:
    """Generic fallback that returns an empty string."""
    return ""


async def none_fallback(*args, **kwargs) -> None:
    """Generic fallback that returns None."""
    return None


async def false_fallback(*args, **kwargs) -> bool:
    """Generic fallback that returns False."""
    return False