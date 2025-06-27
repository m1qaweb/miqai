import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from prometheus_fastapi_instrumentator import Instrumentator
import arq
from arq.connections import RedisSettings
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from qdrant_client import QdrantClient

from video_ai_system.config import settings
from video_ai_system.tracing import configure_tracing
from video_ai_system.api.routes import api_router
from video_ai_system.services.model_registry_service import ModelRegistryService
from video_ai_system.services.inference_service import InferenceService
from video_ai_system.services.vector_db_service import VectorDBService
from video_ai_system.services.active_learning_service import ActiveLearningService
from video_ai_system.services.drift_detection_service import DriftDetectionService
from video_ai_system.services.analytics_service import AnalyticsService

# --- Application Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan, including service initialization.
    """
    logging.info("Application startup...")
    configure_tracing("video-ai-system-api")
    logging.info("Tracing configured.")

    # Initialize services and store them in a central dictionary
    app.state.services = {}

    # ARQ Redis pool
    app.state.redis_pool = await arq.create_pool(RedisSettings.from_dsn(str(settings.REDIS_DSN)))
    logging.info("Redis pool created.")

    # Model Registry
    model_registry = ModelRegistryService(registry_path=str(settings.MODEL_REGISTRY_PATH))
    app.state.services["model_registry"] = model_registry
    logging.info("ModelRegistryService initialized.")

    # Inference Service
    production_model = model_registry.get_production_model(model_name=settings.inference.default_model_name)
    inference_service = InferenceService()
    if production_model:
        inference_service.load_model(production_model["path"])
        logging.info(f"InferenceService initialized with model: {production_model['path']}")
    else:
        logging.warning(
            f"No production model found for '{settings.inference.default_model_name}'. "
            "The InferenceService will not be available until a model is activated."
        )
    app.state.services["inference"] = inference_service

    # Qdrant client and Vector DB Service
    qdrant_client = QdrantClient(host=settings.qdrant.host, port=settings.qdrant.port)
    app.state.services["vector_db"] = VectorDBService(client=qdrant_client, collection_name=settings.qdrant.collection)
    logging.info("VectorDBService initialized.")

    # Other services
    app.state.services["active_learning"] = ActiveLearningService(
        qdrant_client=qdrant_client,
        collection_name=settings.qdrant.collection,
    )
    logging.info("ActiveLearningService initialized.")
    
    app.state.services["drift_detection"] = DriftDetectionService(
        vector_db_service=app.state.services["vector_db"],
        pca_components=settings.drift_detection.pca_components,
        drift_threshold=settings.drift_detection.drift_threshold,
    )
    logging.info("DriftDetectionService initialized.")

    app.state.services["analytics"] = AnalyticsService(vector_db_service=app.state.services["vector_db"])
    logging.info("AnalyticsService initialized.")

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

# Instrument the app with OpenTelemetry and Prometheus
FastAPIInstrumentor.instrument_app(app)
instrumentator = Instrumentator().instrument(app)
instrumentator.expose(app)

# Mount the main API router
app.include_router(api_router, prefix="/api/v1")

# --- Static Files Hosting ---
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
        "The frontend will not be served."
    )
