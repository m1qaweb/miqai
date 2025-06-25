import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, APIRouter, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from prometheus_fastapi_instrumentator import Instrumentator
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, HttpUrl, Field
from enum import Enum
import arq
from arq.jobs import Job
from arq.connections import RedisSettings
from typing import Tuple

# Observability imports
from opentelemetry_instrumentation_fastapi import FastAPIInstrumentor
from .tracing import configure_tracing

from video_ai_system.config import settings
from video_ai_system.security import get_api_key
from video_ai_system.services.inference_service import InferenceService
from video_ai_system.services.model_registry_service import ModelRegistryService
from video_ai_system.services.active_learning_service import (
    ActiveLearningService,
    LowConfidenceFrame,
)
from video_ai_system.services.drift_detection_service import DriftDetectionService
from video_ai_system.services.vector_db_service import VectorDBService
from video_ai_system.services.analytics_service import AnalyticsService
from qdrant_client import QdrantClient

# --- Pydantic Models for API ---

class VideoListResponse(BaseModel):
    videos: List[str]

class Detection(BaseModel):
    label: str
    confidence: float
    box: Tuple[float, float, float, float] # (x1, y1, x2, y2)

class FrameData(BaseModel):
    frame_number: int
    timestamp: float
    detections: List[Detection]

class FrameDataResponse(BaseModel):
    video_id: str
    frames: List[FrameData]

class AnalyzeRequest(BaseModel):
    """
    Specifies the video to be analyzed by providing its local file path.
    The model is strict, preventing unexpected fields.
    """
    file_path: str
    callback_url: Optional[HttpUrl] = None

    class Config:
        extra = 'forbid'

class AnalyzeResponse(BaseModel):
    """
    Confirms the task was accepted.
    """
    task_id: str
    status_endpoint: str

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None
    error_message: Optional[str] = None

class TimeWindow(BaseModel):
    start_time: float
    end_time: float

class DriftCheckRequest(BaseModel):
    reference_window: TimeWindow
    comparison_window: TimeWindow

class ModelRegistrationRequest(BaseModel):
    model_name: str
    path: str
    metadata: Optional[Dict] = Field(default_factory=dict)

class ModelActivationRequest(BaseModel):
    model_name: str
    version: int

class ModelEntryResponse(BaseModel):
    model_name: str
    version: int
    path: str
    status: str
    creation_timestamp: str
    metadata: Dict

# --- Application Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan, including service initialization.
    """
    # Configure OpenTelemetry
    configure_tracing("video-ai-system-api")

    # Initialize ARQ Redis pool
    app.state.redis_pool = await arq.create_pool(RedisSettings.from_dsn(str(settings.REDIS_DSN)))

    # Initialize services
    model_registry = ModelRegistryService(registry_path=str(settings.MODEL_REGISTRY_PATH))
    app.state.model_registry_service = model_registry

    # Initialize InferenceService with the production model
    production_model = model_registry.get_production_model(model_name=settings.DEFAULT_MODEL_NAME)
    if not production_model:
        logging.warning(
            f"No production model found for '{settings.DEFAULT_MODEL_NAME}'. "
            "The InferenceService will not be available until a model is activated."
        )
        app.state.inference_service = None
    else:
        app.state.inference_service = InferenceService(model_path=production_model["path"])

    # Initialize Qdrant client and other services
    app.state.qdrant_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    app.state.vector_db_service = VectorDBService()
    app.state.active_learning_service = ActiveLearningService(
        qdrant_client=app.state.qdrant_client,
        collection_name=settings.QDRANT_COLLECTION,
    )
    app.state.drift_detection_service = DriftDetectionService(
        vector_db_service=app.state.vector_db_service,
        pca_components=settings.PCA_COMPONENTS,
        drift_threshold=settings.DRIFT_THRESHOLD,
    )
    app.state.analytics_service = AnalyticsService(vector_db_service=app.state.vector_db_service)

    yield

    # --- Teardown Logic ---
    logging.info("Application shutting down. Closing Redis pool.")
    await app.state.redis_pool.close()


# --- Application Setup ---
app = FastAPI(
    title="Video AI Analysis System",
    description="A modular system for self-supervised video analysis.",
    version="0.1.0",
    lifespan=lifespan,
)

# Instrument the app with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


# --- Dependency Injection ---
def get_model_registry_service(request: Request) -> ModelRegistryService:
    return request.app.state.model_registry_service

def get_inference_service(request: Request) -> InferenceService:
    if request.app.state.inference_service is None:
        raise HTTPException(
            status_code=503,
            detail="InferenceService is not available. No production model is active."
        )
    return request.app.state.inference_service

def get_redis_pool(request: Request) -> arq.ArqRedis:
    return request.app.state.redis_pool

def get_active_learning_service(request: Request) -> ActiveLearningService:
    return request.app.state.active_learning_service

def get_drift_detection_service(request: Request) -> DriftDetectionService:
    return request.app.state.drift_detection_service

def get_analytics_service(request: Request) -> AnalyticsService:
    return request.app.state.analytics_service


# --- Metrics ---
instrumentator = Instrumentator().instrument(app)
instrumentator.expose(app)


# --- API Endpoints ---
api_router = APIRouter(dependencies=[Depends(get_api_key)])

@api_router.get("/health", tags=["Monitoring"])
def get_health():
    return {"status": "ok"}

@api_router.post("/analyze", response_model=AnalyzeResponse, status_code=202, tags=["Analysis"])
async def analyze(
    request: AnalyzeRequest,
    redis: arq.ArqRedis = Depends(get_redis_pool)
):
    """
    Submits a video for asynchronous analysis.
    """
    job = await redis.enqueue_job(
        "analyze_video",
        file_path=request.file_path,
        callback_url=str(request.callback_url) if request.callback_url else None,
    )
    # Note: The status_endpoint should reflect the new API prefix
    return AnalyzeResponse(
        task_id=job.job_id,
        status_endpoint=f"/api/v1/results/{job.job_id}"
    )

@api_router.get("/results/{task_id}", response_model=TaskStatusResponse, tags=["Analysis"])
async def get_results(
    task_id: str,
    redis: arq.ArqRedis = Depends(get_redis_pool)
):
    """
    Retrieves the status and results of an analysis task.
    """
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
    request: ModelRegistrationRequest,
    service: ModelRegistryService = Depends(get_model_registry_service),
):
    """
    Registers a new model version.
    """
    try:
        new_model = service.register_model(
            model_name=request.model_name,
            path=request.path,
            metadata=request.metadata,
        )
        return new_model
    except Exception as e:
        logging.exception("Failed to register model.")
        raise HTTPException(status_code=500, detail=str(e))

@registry_router.get("/models", response_model=List[ModelEntryResponse])
def list_models_endpoint(
    model_name: Optional[str] = None,
    service: ModelRegistryService = Depends(get_model_registry_service),
):
    """
    Lists all registered models, with an option to filter by name.
    """
    return service.list_models(model_name=model_name)

@registry_router.put("/models/activate", response_model=ModelEntryResponse)
def activate_model_endpoint(
    request: ModelActivationRequest,
    service: ModelRegistryService = Depends(get_model_registry_service),
    app_request: Request = None
):
    """
    Activates a specific model version for production use.
    This will also trigger a reload of the InferenceService.
    """
    updated_model = service.activate_model_version(
        model_name=request.model_name, version=request.version
    )
    if not updated_model:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{request.model_name}' version {request.version} not found."
        )
    
    # Hot-reload the inference service with the new model
    logging.info(f"Reloading InferenceService with new production model: {updated_model['path']}")
    app_request.app.state.inference_service = InferenceService(model_path=updated_model["path"])

    return updated_model

api_router.include_router(registry_router)

# --- Active Learning Router ---
active_learning_router = APIRouter(prefix="/active-learning", tags=["Active Learning"])

@active_learning_router.get(
    "/low-confidence-frames",
    response_model=List[LowConfidenceFrame],
    tags=["Active Learning"],
)
def get_low_confidence_frames(
    confidence_threshold: float = settings.LOW_CONFIDENCE_THRESHOLD,
    limit: int = 100,
    service: ActiveLearningService = Depends(get_active_learning_service),
):
    """
    Retrieves video frames with low-confidence object detections.
    """
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
    request: DriftCheckRequest,
    service: DriftDetectionService = Depends(get_drift_detection_service),
):
    """
    Triggers a drift detection analysis between two specified time windows.
    """
    try:
        result = service.check_drift(
            start_time_ref=request.reference_window.start_time,
            end_time_ref=request.reference_window.end_time,
            start_time_comp=request.comparison_window.start_time,
            end_time_comp=request.comparison_window.end_time,
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
    service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Retrieves a list of all unique processed video IDs.
    """
    try:
        video_ids = await service.get_unique_video_ids()
        return VideoListResponse(videos=video_ids)
    except Exception as e:
        logging.exception("Failed to retrieve video list.")
        raise HTTPException(status_code=500, detail=str(e))

@analytics_router.get("/videos/{video_id:path}/frames", response_model=FrameDataResponse)
async def get_video_frames(
    video_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Retrieves all frame data for a specific video.
    The `video_id` is captured as a path to handle filenames with special characters.
    """
    try:
        frames = await service.get_frames_for_video(video_id)
        if not frames:
            raise HTTPException(status_code=404, detail=f"No data found for video: {video_id}")
        
        # Manually construct the response to handle nested Pydantic models
        # This is a workaround for potential issues with FastAPI's automatic response model parsing
        # when dealing with complex nested structures from different services.
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
        raise # Re-raise HTTPException to preserve status code and detail
    except Exception as e:
        logging.exception(f"Failed to retrieve frames for video: {video_id}")
        raise HTTPException(status_code=500, detail=str(e))

api_router.include_router(analytics_router)


# --- Shadow Testing Router ---
import httpx
from datetime import datetime, timedelta

shadow_testing_router = APIRouter(prefix="/shadow-testing", tags=["Shadow Testing"])

@shadow_testing_router.get("/results")
async def get_shadow_test_results(
    candidate_model_id: Optional[str] = None,
    time_range: str = "24h",
    limit: int = 100,
):
    """
    Retrieves shadow testing comparison logs from Loki.
    """
    if not settings.LOKI_API_URL:
        raise HTTPException(
            status_code=501,
            detail="Loki API URL is not configured. This feature is unavailable."
        )

    # Calculate time range
    try:
        # Simple parsing for 'h' (hours) and 'd' (days)
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

    # Construct LogQL query
    logql_query = f'{{app="video-ai-system"}} | json | message="shadow_test_result"'
    if candidate_model_id:
        # Sanitize model_id to prevent injection
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
            
            # Extract and format the log entries
            results = []
            if loki_response.get("data", {}).get("result"):
                for stream in loki_response["data"]["result"]:
                    for value_pair in stream.get("values", []):
                        # value_pair is [timestamp_str, log_line_str]
                        # The actual log content is in the second element
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


# Mount the main API router
app.include_router(api_router, prefix="/api/v1")


# --- Static Files Hosting ---
# This section serves the static frontend assets from the /app/static directory
# within the Docker container. It must be mounted at the root.

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Request) -> FileResponse:
        try:
            return await super().get_response(path, scope)
        except HTTPException as ex:
            if ex.status_code == 404:
                # For SPA routing, serve index.html on 404
                return await super().get_response("index.html", scope)
            raise ex

STATIC_FILES_DIR = "/app/static"

if os.path.exists(STATIC_FILES_DIR):
    app.mount(
        "/",
        SPAStaticFiles(directory=STATIC_FILES_DIR, html=True),
        name="static-frontend",
    )
else:
    logging.warning(
        f"Static files directory not found at '{STATIC_FILES_DIR}'. "
        "The frontend will not be served. This is expected during local "
        "development if the frontend has not been built and placed in this "
        "directory."
    )
