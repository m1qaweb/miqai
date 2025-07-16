"""
This module provides a client for interacting with Google Cloud Pub/Sub.
It encapsulates the logic for publishing messages to a specified topic,
which is essential for the asynchronous clip extraction pipeline.
"""
import os
from google.cloud import pubsub_v1

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

    def publish_message(self, topic_name: str, message: bytes):
        """
        Publishes a message to a specified Pub/Sub topic.

        Args:
            topic_name: The name of the topic to publish to.
            message: The message to publish, as bytes.
        """
        topic_path = self.publisher.topic_path(self.project_id, topic_name)
        future = self.publisher.publish(topic_path, message)
        return future.result()
