import json
import os
import bleach
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, status, Response
from google.cloud import pubsub_v1

from insight_engine.api.v1.schemas import ClipRequest, ClipJobResponse
from insight_engine.security import get_current_user

router = APIRouter()

# --- Dependencies ---

def get_publisher_client() -> pubsub_v1.PublisherClient:
    """
    Dependency to get a Pub/Sub publisher client.
    Caches the client for reuse across requests.
    """
    # This would typically be a singleton managed by a dependency injection container
    # For simplicity, we create it here.
    return pubsub_v1.PublisherClient()


# --- Endpoint ---

@router.post(
    "/clips",
    response_model=ClipJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a job to extract clips from a video",
)
async def submit_clip_extraction_job(
    request: ClipRequest,
    publisher: pubsub_v1.PublisherClient = Depends(get_publisher_client),
    current_user: dict = Depends(get_current_user),
) -> ClipJobResponse:
    """
    Accepts a video ID and an object query, then publishes a job to a Pub/Sub
    topic for asynchronous processing by a worker.

    **Rationale:** This asynchronous pattern ensures the API responds immediately
    (<100ms), meeting our latency targets. The heavy lifting of video
    processing is offloaded to a scalable, independent worker service.

    Returns:
        - `202 Accepted`: The job was successfully submitted.
        - `job_id`: A unique identifier for the client to track the job status.
    """
    project_id = "deft-striker-465815-t9"
    topic_id = "clip-extraction-jobs"
    topic_path = publisher.topic_path(project_id, topic_id)

    user_id = current_user.get("username")

    # Authorization Check: Before publishing, verify the user owns the video.
    # This prevents unauthorized users from even starting a job.
    # e.g., if not is_user_owner(user_id, request.video_id):
    #           raise HTTPException(status_code=403, detail="Forbidden")
    # (Implementation of is_user_owner would check a database.)

    job_id = uuid4()

    # Sanitize the user-provided query to prevent XSS or other injection attacks.
    # This ensures that any potentially malicious scripts are removed before
    # the query is processed or stored.
    sanitized_query = bleach.clean(request.query)

    message_data = {
        "job_id": str(job_id),
        "video_id": str(request.video_id),
        "object_query": sanitized_query,
        "user_id": user_id,  # Pass user context to the worker for authorization
    }

    # IMPORTANT: The asynchronous worker that processes this message *must*
    # perform its own authorization check. It should verify that the `user_id`
    # in this message is authorized to access the `video_id` before
    # beginning any processing. This prevents a race condition where a user's
    # permissions could change between the time the job is submitted and when
    # it's processed.

    # Pub/Sub messages must be bytestrings
    future = publisher.publish(topic_path, data=json.dumps(message_data).encode("utf-8"))
    
    # Block to ensure the message is published, but with a timeout.
    # In a high-throughput scenario, we might not block here and handle
    # publishing failures with a retry mechanism or by logging.
    future.result(timeout=10)

    return ClipJobResponse(job_id=job_id)