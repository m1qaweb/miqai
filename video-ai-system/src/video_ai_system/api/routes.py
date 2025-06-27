import logging
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
import arq
from arq.jobs import Job
import json

from video_ai_system.config import settings
from video_ai_system.security import get_api_key
from video_ai_system.services.model_registry_service import ModelRegistryService
from video_ai_system.services.active_learning_service import LowConfidenceFrame
from video_ai_system.api.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    TaskStatusResponse,
    TaskStatus,
    ModelRegistrationRequest,
    ModelEntryResponse,
    ModelActivationRequest,
    DriftCheckRequest,
    VideoListResponse,
    FrameDataResponse,
    FrameData,
    Detection,
)

# Main router for the entire API
api_router = APIRouter(dependencies=[Depends(get_api_key)])

# --- Health Check ---
@api_router.get("/health", tags=["Monitoring"])
def get_health():
    return {"status": "ok"}

# --- Analysis Endpoints ---
@api_router.post("/analyze", response_model=AnalyzeResponse, status_code=202, tags=["Analysis"])
async def analyze(
    request_data: AnalyzeRequest,
    request: Request
):
    """
    Submits a video for asynchronous analysis.
    """
    redis: arq.ArqRedis = request.app.state.redis_pool
    job = await redis.enqueue_job(
        "analyze_video",
        file_path=request_data.file_path,
        callback_url=str(request_data.callback_url) if request_data.callback_url else None,
    )
    return AnalyzeResponse(
        task_id=job.job_id,
        status_endpoint=f"/api/v1/results/{job.job_id}"
    )

@api_router.get("/results/{task_id}", response_model=TaskStatusResponse, tags=["Analysis"])
async def get_results(
    task_id: str,
    request: Request
):
    """
    Retrieves the status and results of an analysis task.
    """
    redis: arq.ArqRedis = request.app.state.redis_pool
    job = Job(job_id=task_id, redis=redis)
    status = await job.status()
    result = None
    error_message = None

    if status == 'complete':
        result = await job.result()
        status = TaskStatus.SUCCESS
    elif status == 'failed':
        error_info = await job.result(timeout=1)
        error_message = str(error_info) if error_info else "Job failed without a specific error message."
        status = TaskStatus.FAILED
    elif status == 'in_progress':
        status = TaskStatus.PROCESSING
    else:
        status = TaskStatus.PENDING

    return TaskStatusResponse(
        task_id=task_id,
        status=status,
        result=result,
        error_message=error_message
    )

# --- Model Registry Router ---
registry_router = APIRouter(prefix="/registry", tags=["Model Registry"])

@registry_router.post("/models", response_model=ModelEntryResponse, status_code=201)
def register_model_endpoint(
    request_data: ModelRegistrationRequest,
    request: Request,
):
    service: ModelRegistryService = request.app.state.services["model_registry"]
    try:
        new_model = service.register_model(
            model_name=request_data.model_name,
            path=request_data.path,
            metadata=request_data.metadata,
        )
        return new_model
    except Exception as e:
        logging.exception("Failed to register model.")
        raise HTTPException(status_code=500, detail=str(e))

@registry_router.get("/models", response_model=List[ModelEntryResponse])
def list_models_endpoint(
    request: Request,
    model_name: Optional[str] = None,
):
    service: ModelRegistryService = request.app.state.services["model_registry"]
    return service.list_models(model_name=model_name)

@registry_router.put("/models/activate", response_model=ModelEntryResponse)
def activate_model_endpoint(
    request_data: ModelActivationRequest,
    request: Request,
):
    service: ModelRegistryService = request.app.state.services["model_registry"]
    updated_model = service.activate_model_version(
        model_name=request_data.model_name, version=request_data.version
    )
    if not updated_model:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{request_data.model_name}' version {request_data.version} not found."
        )
    
    # Hot-reload the inference service with the new model
    logging.info(f"Reloading InferenceService with new production model: {updated_model['path']}")
    request.app.state.services["inference"].load_model(updated_model["path"])

    return updated_model

api_router.include_router(registry_router)

# --- Active Learning Router ---
active_learning_router = APIRouter(prefix="/active-learning", tags=["Active Learning"])

@active_learning_router.get(
    "/low-confidence-frames",
    response_model=List[LowConfidenceFrame],
)
def get_low_confidence_frames(
    request: Request,
    confidence_threshold: float = settings.active_learning.low_confidence_threshold,
    limit: int = 100,
):
    service = request.app.state.services["active_learning"]
    try:
        return service.get_low_confidence_frames(
            confidence_threshold=confidence_threshold, limit=limit
        )
    except Exception as e:
        logging.exception("Failed to retrieve low confidence frames.")
        raise HTTPException(status_code=500, detail=str(e))

api_router.include_router(active_learning_router)

# --- Drift Detection Router ---
drift_detection_router = APIRouter(prefix="/drift-detection", tags=["Drift Detection"])

@drift_detection_router.post("/check")
async def check_drift(
    request_data: DriftCheckRequest,
    request: Request,
):
    service = request.app.state.services["drift_detection"]
    try:
        result = service.check_drift(
            start_time_ref=request_data.reference_window.start_time,
            end_time_ref=request_data.reference_window.end_time,
            start_time_comp=request_data.comparison_window.start_time,
            end_time_comp=request_data.comparison_window.end_time,
        )
        return result
    except Exception as e:
        logging.exception("Error during drift detection")
        raise HTTPException(status_code=500, detail=str(e))

api_router.include_router(drift_detection_router)

# --- Analytics Router ---
analytics_router = APIRouter(prefix="/analytics", tags=["Analytics"])

@analytics_router.get("/videos", response_model=VideoListResponse)
async def get_video_list(
    request: Request,
):
    service = request.app.state.services["analytics"]
    try:
        video_ids = await service.get_unique_video_ids()
        return VideoListResponse(videos=video_ids)
    except Exception as e:
        logging.exception("Failed to retrieve video list.")
        raise HTTPException(status_code=500, detail=str(e))

@analytics_router.get("/videos/{video_id:path}/frames", response_model=FrameDataResponse)
async def get_video_frames(
    video_id: str,
    request: Request,
):
    service = request.app.state.services["analytics"]
    try:
        frames = await service.get_frames_for_video(video_id)
        if not frames:
            raise HTTPException(status_code=404, detail=f"No data found for video: {video_id}")
        
        frame_data_list = []
        for frame_payload in frames:
            detections = [Detection(label=d['label'], confidence=d['score'], box=d['box']) for d in frame_payload.get('detections', [])]
            frame_data_list.append(
                FrameData(
                    frame_number=frame_payload['frame_number'],
                    timestamp=frame_payload['timestamp'],
                    detections=detections
                )
            )

        return FrameDataResponse(video_id=video_id, frames=frame_data_list)
    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Failed to retrieve frames for video: {video_id}")
        raise HTTPException(status_code=500, detail=str(e))

api_router.include_router(analytics_router)

# --- Shadow Testing Router ---
shadow_testing_router = APIRouter(prefix="/shadow-testing", tags=["Shadow Testing"])

@shadow_testing_router.get("/results")
async def get_shadow_test_results(
    candidate_model_id: Optional[str] = None,
    time_range: str = "24h",
    limit: int = 100,
):
    if not settings.LOKI_API_URL:
        raise HTTPException(
            status_code=501,
            detail="Loki API URL is not configured. This feature is unavailable."
        )

    try:
        if time_range.endswith('h'):
            hours = int(time_range[:-1])
            start_time = datetime.utcnow() - timedelta(hours=hours)
        elif time_range.endswith('d'):
            days = int(time_range[:-1])
            start_time = datetime.utcnow() - timedelta(days=days)
        else:
            raise ValueError("Invalid time_range format. Use 'h' for hours or 'd' for days.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    start_timestamp_ns = int(start_time.timestamp() * 1e9)

    logql_query = f'{{app="video-ai-system"}} | json | message="shadow_test_result"'
    if candidate_model_id:
        safe_model_id = candidate_model_id.replace('"', '\\"')
        logql_query += f' | candidate_model_id="{safe_model_id}"'
    
    params = {
        "query": logql_query,
        "limit": limit,
        "start": str(start_timestamp_ns),
        "direction": "backward",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.LOKI_API_URL}/loki/api/v1/query_range", params=params)
            response.raise_for_status()
            loki_response = response.json()
            
            results = []
            if loki_response.get("data", {}).get("result"):
                for stream in loki_response["data"]["result"]:
                    for value_pair in stream.get("values", []):
                        results.append(json.loads(value_pair[1]))
            return results

    except httpx.HTTPStatusError as e:
        logging.exception("Error querying Loki API.")
        detail = f"Failed to query Loki. Status: {e.response.status_code}. Response: {e.response.text}"
        raise HTTPException(status_code=503, detail=detail)
    except Exception as e:
        logging.exception("An unexpected error occurred while fetching shadow test results.")
        raise HTTPException(status_code=500, detail=str(e))

api_router.include_router(shadow_testing_router)