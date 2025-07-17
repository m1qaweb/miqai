import json
import logging
import os
import tempfile
from concurrent.futures import TimeoutError
from typing import Dict, Any

import ffmpeg
from google.cloud import pubsub_v1
from google.cloud import storage

from insight_engine.resilience import gcp_resilient
from insight_engine.resilience.fallbacks import FallbackManager

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
SUBSCRIPTION_ID = "clip-extraction-subscription"
VIDEO_BUCKET_NAME = os.getenv("GCS_BUCKET_VIDEOS", "insight-engine-videos")
CLIPS_BUCKET_NAME = os.getenv("GCS_BUCKET_CLIPS", "insight-engine-clips")

# --- Clients ---
# Initialize clients globally to reuse connections
storage_client = storage.Client()
subscriber_client = pubsub_v1.SubscriberClient()


from google.cloud.pubsub_v1.subscriber.message import Message


@gcp_resilient("gcs_download", fallback=FallbackManager.storage_fallback)
async def download_video_from_gcs(source_blob, input_path: str) -> bool:
    """Download video from GCS with resilience patterns."""
    try:
        source_blob.download_to_filename(input_path)
        return True
    except Exception as e:
        logging.error(f"Failed to download video from GCS: {e}")
        return False


@gcp_resilient("gcs_upload", fallback=FallbackManager.storage_fallback)
async def upload_clip_to_gcs(clip_blob, output_path: str) -> bool:
    """Upload clip to GCS with resilience patterns."""
    try:
        clip_blob.upload_from_filename(output_path)
        return True
    except Exception as e:
        logging.error(f"Failed to upload clip to GCS: {e}")
        return False


@gcp_resilient("gcs_exists_check", fallback=lambda *args, **kwargs: False)
async def check_blob_exists(blob) -> bool:
    """Check if blob exists with resilience patterns."""
    try:
        return blob.exists()
    except Exception as e:
        logging.error(f"Failed to check blob existence: {e}")
        return False


import asyncio


async def _process_clip_job_async(message: Message) -> None:
    """
    Async implementation of clip job processing with resilience patterns.
    """
    data_str = message.data.decode("utf-8")
    data = json.loads(data_str)
    logging.info(f"Received job {data.get('job_id')}: {data}")

    video_id = data["video_id"]
    object_query = data["object_query"]

    # --- Mock Vision API Interaction ---
    # In a real implementation, we would call the Vision API here to get
    # object annotations and their timestamps.
    # For this task, we'll use a hardcoded list.
    logging.info(f"[{data['job_id']}] Mocking Vision API call for '{object_query}'...")
    mock_timestamps = [(5.0, 8.5), (12.2, 15.0)]  # (start_sec, end_sec)

    # --- Video Processing ---
    video_blob_name = f"{video_id}.mp4" # Assuming a fixed format for now
    source_bucket = storage_client.bucket(VIDEO_BUCKET_NAME)
    source_blob = source_bucket.blob(video_blob_name)

    # Check if blob exists with resilience patterns
    blob_exists = await check_blob_exists(source_blob)
    if not blob_exists:
        logging.error(f"[{data['job_id']}] Video not found: gs://{VIDEO_BUCKET_NAME}/{video_blob_name}")
        # Acknowledge the message to prevent retries for a non-existent file.
        # A more robust system might move this to a dead-letter queue.
        message.ack()
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.mp4")
        logging.info(f"[{data['job_id']}] Downloading video to {input_path}...")
        
        # Download with resilience patterns
        download_success = await download_video_from_gcs(source_blob, input_path)
        if not download_success:
            logging.error(f"[{data['job_id']}] Failed to download video after retries")
            message.nack()
            return

        for i, (start, end) in enumerate(mock_timestamps):
            output_filename = f"{video_id}_clip_{i+1}.mp4"
            output_path = os.path.join(tmpdir, output_filename)
            
            logging.info(f"[{data['job_id']}] Generating clip {i+1}: {start}s - {end}s")
            
            try:
                (
                    ffmpeg.input(input_path, ss=start)
                    .output(output_path, to=end, c="copy") # Use stream copy for speed
                    .run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
                )
            except ffmpeg.Error as e:
                logging.error(f"[{data['job_id']}] FFmpeg error: {e.stderr.decode()}")
                # Decide on error handling: continue, retry, or fail the job
                continue

            # --- Upload Result to GCS ---
            clips_bucket = storage_client.bucket(CLIPS_BUCKET_NAME)
            destination_blob_name = f"{video_id}/{output_filename}"
            clip_blob = clips_bucket.blob(destination_blob_name)

            logging.info(f"[{data['job_id']}] Uploading clip to gs://{CLIPS_BUCKET_NAME}/{destination_blob_name}")
            
            # Upload with resilience patterns
            upload_success = await upload_clip_to_gcs(clip_blob, output_path)
            if not upload_success:
                logging.error(f"[{data['job_id']}] Failed to upload clip {i+1} after retries")
                # Continue with other clips rather than failing the entire job

    # --- Acknowledge Message ---
    # Acknowledge the message only after all processing is complete.
    logging.info(f"[{data['job_id']}] Job completed successfully.")
    message.ack()


def process_clip_job(message: Message) -> None:
    """
    Callback function to process a single clip extraction job from Pub/Sub.
    This is a sync wrapper around the async implementation.
    """
    try:
        # Run the async function in the event loop
        asyncio.run(_process_clip_job_async(message))
    except Exception as e:
        logging.error(f"Unhandled exception processing message: {e}", exc_info=True)
        # Do not acknowledge the message, so Pub/Sub retries it.
        # Configure a dead-letter topic on the subscription to handle persistent failures.
        message.nack()


def main() -> None:
    """
    Starts the Pub/Sub subscriber to listen for clip extraction jobs.
    """
    if not PROJECT_ID:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")

    subscription_path = subscriber_client.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)
    logging.info(f"Listening for messages on {subscription_path}...")

    streaming_pull_future = subscriber_client.subscribe(
        subscription_path, callback=process_clip_job
    )

    # Wrap in a try/except block to catch exceptions from the subscriber.
    try:
        # The subscriber is non-blocking, so we must keep the main thread alive.
        streaming_pull_future.result()
    except TimeoutError:
        streaming_pull_future.cancel()
        streaming_pull_future.result() # Block until the shutdown is complete
    except Exception as e:
        logging.error(f"Subscriber stopped due to an exception: {e}", exc_info=True)
        streaming_pull_future.cancel()


if __name__ == "__main__":
    main()
