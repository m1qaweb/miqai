"""Main FastAPI application for The Insight Engine."""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from arq import create_pool
from arq.jobs import JobStatus
from fastapi import FastAPI, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse

from insight_engine.api.schemas import (
    ExtractClipsRequest,
    VideoUploadRequest,
    VideoUploadResponse,
)
from insight_engine.services.multimodal_extractor import MultimodalExtractor
from insight_engine.worker import RedisSettings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    """
    app.state.redis = await create_pool(RedisSettings())
    yield
    await app.state.redis.close()


# Create a FastAPI application instance
app = FastAPI(
    title="The Insight Engine API",
    description="API for processing and analyzing video content.",
    version="0.1.0",
    lifespan=lifespan,
)

extractor = MultimodalExtractor()


@app.post(
    "/uploads/request-url/",
    response_model=VideoUploadResponse,
    summary="Request a presigned URL for video upload",
    tags=["Uploads"],
)
async def request_upload_url(
    request: VideoUploadRequest,
) -> VideoUploadResponse:
    """
    Provides a client with a presigned URL to upload a video file to GCS.

    This endpoint is the first step in the video processing pipeline. The client
    receives a URL and a corresponding video ID. The client is expected to
    construct the GCS URI from the video ID and file name for subsequent calls.
    """
    # In a real application, this would call a service to generate a secure,
    # time-limited presigned URL for Google Cloud Storage.
    video_identifier = str(uuid.uuid4())
    object_name = f"{video_identifier}-{request.file_name}"

    # The upload URL is for the client to upload the file.
    upload_url = f"https://storage.googleapis.com/insight-engine-videos/{object_name}?signature=dummy"

    return VideoUploadResponse(video_id=video_identifier, upload_url=upload_url)


@app.get(
    "/analysis/summarize/",
    summary="Generate a summary for a video",
    tags=["Analysis"],
)
async def summarize_video(
    video_uri: str = Query(
        ..., description="The GCS URI of the video to summarize."
    )
) -> StreamingResponse:
    """
    Generates a text summary for a video specified by its GCS URI.

    This endpoint returns a `StreamingResponse` with Server-Sent Events (SSE)
    to provide real-time summary chunks to the client.
    """

    async def sse_generator() -> AsyncGenerator[str, None]:
        """SSE generator to stream extraction results."""
        try:
            # 1. Extract transcript and labels
            extracted_data = await extractor.extract_data(video_uri)

            # 2. Yield transcript chunk
            transcript_payload = {"chunk": extracted_data.transcript}
            yield f"data: {json.dumps(transcript_payload)}\n\n"
            await asyncio.sleep(0.1)

            # 3. Yield visual labels
            labels_payload = {"labels": extracted_data.visual_labels}
            yield f"data: {json.dumps(labels_payload)}\n\n"
            await asyncio.sleep(0.1)

        except Exception as e:
            error_payload = {"error": f"An error occurred: {str(e)}"}
            yield f"data: {json.dumps(error_payload)}\n\n"
        finally:
            # 4. Signal end of stream
            yield "data: END_OF_STREAM\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.post(
    "/analysis/extract-clips/",
    summary="Extract relevant clips from a video",
    status_code=202,
    tags=["Analysis"],
)
async def extract_clips(request: ExtractClipsRequest) -> JSONResponse:
    """
    Enqueues tasks to extract relevant clips from a video.
    """
    job_ids = []
    for clip in request.clips:
        output_path = f"/clips/{uuid.uuid4()}.mp4"
        job = await app.state.redis.enqueue_job(
            "generate_clip_task",
            request.video_uri,
            clip.start_time,
            clip.end_time,
            output_path,
        )
        job_ids.append(job.job_id)

    return JSONResponse(
        content={"job_ids": job_ids, "status": "tasks_enqueued"},
        status_code=202,
    )


@app.get(
    "/analysis/job/{job_id}",
    summary="Get the status of a job",
    tags=["Analysis"],
)
async def get_job_status(job_id: str) -> JSONResponse:
    """
    Checks the status of a background job.

    If the job is finished, it returns the result with a 200 OK status.
    If the job is still in progress or not found, it returns a 202 Accepted status.
    If the job has failed, it returns a 500 Internal Server Error.
    """
    try:
        job_result = await app.state.redis.get_job_result(job_id)
        if job_result.status == JobStatus.complete:
            if job_result.success:
                return JSONResponse(
                    content={"status": "complete", "result": job_result.result},
                    status_code=200,
                )
            else:
                return JSONResponse(
                    content={"status": "failed", "error": str(job_result.result)},
                    status_code=500,
                )
        else:
            # For queued, deferred, or in_progress statuses, treat as "in_progress".
            return JSONResponse(content={"status": "in_progress"}, status_code=202)
    except KeyError:
        # Job not found, assume it's still in progress or will be soon.
        return JSONResponse(content={"status": "in_progress"}, status_code=202)
