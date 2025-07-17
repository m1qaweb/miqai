"""
This module provides a client for interacting with Google Cloud Pub/Sub.
It encapsulates the logic for publishing messages to a specified topic,
which is essential for the asynchronous clip extraction pipeline.
"""
import os
from google.cloud import pubsub_v1
from insight_engine.resilience import gcp_resilient
from insight_engine.resilience.fallbacks import FallbackManager

class PubSubClient:
    """A client for publishing messages to Google Cloud Pub/Sub."""

    def __init__(self, project_id: str):
        """
        Initializes the Pub/Sub client.

        Args:
            project_id: The GCP project ID.
        """
        self.publisher = pubsub_v1.PublisherClient()
        self.project_id = project_id

    @gcp_resilient("pubsub_publish", fallback=FallbackManager.pubsub_fallback)
    async def publish_message(self, topic_name: str, message: bytes):
        """
        Publishes a message to a specified Pub/Sub topic with resilience patterns.

        Args:
            topic_name: The name of the topic to publish to.
            message: The message to publish, as bytes.
            
        Returns:
            Message ID if successful, None if fallback is used.
        """
        topic_path = self.publisher.topic_path(self.project_id, topic_name)
        future = self.publisher.publish(topic_path, message)
        return future.result()
    
    def publish_message_sync(self, topic_name: str, message: bytes):
        """
        Synchronous version of publish_message for backward compatibility.
        
        Args:
            topic_name: The name of the topic to publish to.
            message: The message to publish, as bytes.
            
        Returns:
            Message ID if successful.
        """
        import asyncio
        return asyncio.run(self.publish_message(topic_name, message))
