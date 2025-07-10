import asyncio
import os

import functions_framework
import structlog
from cloudevents.http import CloudEvent
from insight_engine.services.multimodal_extractor import extract_multimodal_data

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()


@functions_framework.cloud_event
async def process_video_gcs(cloud_event: CloudEvent) -> None:
    """
    Triggered by a CloudEvent on a GCS bucket, this function initiates
    the multimodal analysis of the uploaded video file.

    Args:
        cloud_event (CloudEvent): The event payload from GCS.
    """
    log = logger.bind(event_id=cloud_event["id"])
    log.info("cloud_event_received", event_data=cloud_event.data)

    try:
        bucket = cloud_event.data["bucket"]
        name = cloud_event.data["name"]
    except KeyError as e:
        log.error("invalid_cloudevent_payload", missing_key=str(e))
        return

    gcs_uri = f"gs://{bucket}/{name}"
    log.info("constructed_gcs_uri", uri=gcs_uri)

    try:
        analysis_result = await extract_multimodal_data(gcs_uri)
        log.info(
            "multimodal_analysis_completed",
            gcs_uri=gcs_uri,
            result=analysis_result.dict(),
        )
    except Exception as e:
        log.error(
            "multimodal_analysis_failed",
            gcs_uri=gcs_uri,
            error=str(e),
            exc_info=True,
        )
        # Depending on requirements, you might want to re-raise,
        # or handle the failure explicitly (e.g., move file to an error bucket)
        raise
