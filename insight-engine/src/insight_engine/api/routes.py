import logging
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from typing import List, Optional
import json

from insight_engine.config import settings
from insight_engine.security import get_api_key
from insight_engine.services.model_registry_service import ModelRegistryService
from insight_engine.services.storage_service import StorageService
from insight_engine.services.ingestion_service import IngestionService

from insight_engine.api.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ModelRegistrationRequest,
    ModelEntryResponse,
    ModelActivationRequest,
    DriftCheckRequest,
    VideoListResponse,
    FrameDataResponse,
    FrameData,
    Detection,
)

from insight_engine.plugins.manager import PluginManager
from insight_engine.plugins.models import PluginManifest

# --- Plugin Router ---
plugin_router = APIRouter(prefix="/plugins", tags=["Plugins"])


@plugin_router.get("/", response_model=List[PluginManifest])
def list_plugins(
    request: Request,
):
    """
    Lists all available and loaded plugins.
    """
    plugin_manager: PluginManager = request.app.state.plugin_manager
    return plugin_manager.get_all_manifests()


# Main router for the entire API
api_router = APIRouter(dependencies=[Depends(get_api_key)])

api_router.include_router(plugin_router)


# --- Health Check ---
@api_router.get("/health", tags=["Monitoring"])
def get_health():
    return {"status": "ok"}


# --- Analysis Endpoints ---
@api_router.post(
    "/analyze", response_model=AnalyzeResponse, status_code=202, tags=["Analysis"]
)
async def analyze(
    request_data: AnalyzeRequest, request: Request, background_tasks: BackgroundTasks
):
    """
    Submits a video for asynchronous analysis by simulating a file upload
    and triggering a background ingestion task.
    """
    storage_service: StorageService = request.app.state.storage_service
    ingestion_service: IngestionService = request.app.state.ingestion_service

    try:
        # 1. "Upload" the file to our simulated cloud storage
        bucket_path = storage_service.upload_file(request_data.file_path)

        # 2. Trigger the ingestion service to process the file in the background
        background_tasks.add_task(ingestion_service.process_video, bucket_path)

        # In a real serverless architecture, the upload itself would trigger
        # the next step. The task_id might come from a database record
        # created upon upload. For now, we'll return a simple confirmation.
        task_id = f"ingestion-triggered-for-{bucket_path}"

        return AnalyzeResponse(
            task_id=task_id,
            message="File received and ingestion process started.",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start analysis for {request_data.file_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start analysis.")


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
            detail=f"Model '{request_data.model_name}' version {request_data.version} not found.",
        )

    # Hot-reload the inference service with the new model
    logging.info(
        f"Reloading InferenceService with new production model: {updated_model['path']}"
    )
    request.app.state.services["inference"].load_model(updated_model["path"])

    return updated_model


api_router.include_router(registry_router)


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


@analytics_router.get(
    "/videos/{video_id:path}/frames", response_model=FrameDataResponse
)
async def get_video_frames(
    video_id: str,
    request: Request,
):
    service = request.app.state.services["analytics"]
    try:
        frames = await service.get_frames_for_video(video_id)
        if not frames:
            raise HTTPException(
                status_code=404, detail=f"No data found for video: {video_id}"
            )

        frame_data_list = []
        for frame_payload in frames:
            detections = [
                Detection(label=d["label"], confidence=d["score"], box=d["box"])
                for d in frame_payload.get("detections", [])
            ]
            frame_data_list.append(
                FrameData(
                    frame_number=frame_payload["frame_number"],
                    timestamp=frame_payload["timestamp"],
                    detections=detections,
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
            detail="Loki API URL is not configured. This feature is unavailable.",
        )

    try:
        if time_range.endswith("h"):
            hours = int(time_range[:-1])
            start_time = datetime.utcnow() - timedelta(hours=hours)
        elif time_range.endswith("d"):
            days = int(time_range[:-1])
            start_time = datetime.utcnow() - timedelta(days=days)
        else:
            raise ValueError(
                "Invalid time_range format. Use 'h' for hours or 'd' for days."
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    start_timestamp_ns = int(start_time.timestamp() * 1e9)

    logql_query = '{app="video-ai-system"} | json | message="shadow_test_result"'
    if candidate_model_id:
        safe_model_id = candidate_model_id.replace('"', '\"')
        logql_query += f' | candidate_model_id="{safe_model_id}"'

    params = {
        "query": logql_query,
        "limit": limit,
        "start": str(start_timestamp_ns),
        "direction": "backward",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.LOKI_API_URL}/loki/api/v1/query_range", params=params
            )
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
        logging.exception(
            "An unexpected error occurred while fetching shadow test results."
        )
        raise HTTPException(status_code=500, detail=str(e))


api_router.include_router(shadow_testing_router)
