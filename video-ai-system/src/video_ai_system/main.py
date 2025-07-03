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
from prometheus_client import CollectorRegistry
from video_ai_system.services.comparison_service import ComparisonService

from video_ai_system.config import settings
from video_ai_system.tracing import configure_tracing
from video_ai_system.api.routes import api_router
from video_ai_system.api.governance_routes import router as governance_router
from video_ai_system.services.model_registry_service import ModelRegistryService
from video_ai_system.services.inference_service import InferenceService
from video_ai_system.services.vector_db_service import VectorDBService
from video_ai_system.services.active_learning_service import ActiveLearningService, CVATService
from video_ai_system.services.drift_detection_service import DriftDetectionService
from video_ai_system.services.analytics_service import AnalyticsService
from video_ai_system.services.shadow_testing_service import ShadowTestingService
from video_ai_system.services.audit_service import AuditService
from video_ai_system.services.inference_router import InferenceRouter
from video_ai_system.adaptation_controller import AdaptationController, load_rules_from_yaml

# --- Application Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan, including service initialization
    and background task management for the AdaptationController.
    """
    logging.info("Application startup...")
    configure_tracing("video-ai-system-api")
    logging.info("Tracing configured.")

    # Initialize services and store them in a central dictionary
    app.state.services = {}

    # ARQ Redis pool
    redis_settings = RedisSettings.from_dsn(str(settings.REDIS_DSN))
    app.state.redis_pool = await arq.create_pool(redis_settings)
    logging.info("Redis pool created.")

    # Model Registry
    model_registry = ModelRegistryService(registry_path=str(settings.MODEL_REGISTRY_PATH))
    app.state.services["model_registry"] = model_registry
    logging.info("ModelRegistryService initialized.")

    # Inference Router
    # This would typically be loaded from a more dynamic config
    model_mapping = {
        "NORMAL": "yolov8n-balanced",
        "DEGRADED": "yolov8n-light",
        "CRITICAL": "yolov8n-tiny",
    }
    inference_router = InferenceRouter(
        model_mapping=model_mapping,
        redis_client=app.state.redis_pool,
        model_registry_service=model_registry,
        inference_service=InferenceService() # The router will manage the model loading
    )
    await inference_router.initialize() # Load initial model
    app.state.services["inference_router"] = inference_router
    logging.info("InferenceRouter initialized.")

    # Qdrant client and Vector DB Service
    app.state.services["vector_db"] = VectorDBService()
    logging.info("VectorDBService initialized.")

    # Other services
    cvat_service = CVATService(
        cvat_url=os.environ.get("CVAT_URL", "http://localhost:8080"),
        username=os.environ.get("CVAT_USER", "admin"),
        password=os.environ.get("CVAT_PASSWORD", "password"),
    )
    app.state.services["cvat"] = cvat_service
    app.state.services["active_learning"] = ActiveLearningService(
        qdrant_client=app.state.services["vector_db"].client,
        collection_name=app.state.services["vector_db"].collection_name,
        cvat_service=cvat_service,
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

    # Dependencies for ShadowTestingService
    prometheus_registry = CollectorRegistry()
    comparison_service = ComparisonService()
    app.state.services["comparison"] = comparison_service
    logging.info("ComparisonService initialized.")

    app.state.services["shadow_testing"] = ShadowTestingService(
        inference_service=inference_router.inference_service, # Use the router's service
        logger=logging.getLogger(__name__),
        registry=prometheus_registry,
        comparison_service=comparison_service,
    )
    logging.info("ShadowTestingService initialized.")

    app.state.services["audit"] = AuditService(log_file_path=settings.audit.log_file_path)
    logging.info(f"AuditService initialized with log file at {settings.audit.log_file_path}.")

    # Initialize and start the Adaptation Controller
    rules = load_rules_from_yaml("config/adaptation_rules.yml")
    adaptation_controller = AdaptationController(
        rules=rules,
        inference_router=inference_router,
        prometheus_url=settings.PROMETHEUS_URL,
        poll_interval_seconds=settings.adaptation.poll_interval_seconds,
        cooldown_seconds=settings.adaptation.cooldown_seconds,
    )
    adaptation_controller.start()
    app.state.adaptation_controller = adaptation_controller
    logging.info("AdaptationController started.")

    yield

    # --- Teardown Logic ---
    logging.info("Application shutting down...")
    await app.state.adaptation_controller.stop()
    logging.info("AdaptationController stopped.")
    await app.state.redis_pool.close()
    logging.info("Redis pool closed.")

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
app.include_router(governance_router, prefix="/api/v1/governance")

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
