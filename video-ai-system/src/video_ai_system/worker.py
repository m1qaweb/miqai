import logging
from arq.connections import RedisSettings

# Observability imports
from opentelemetry_instrumentation_arq import ARQInstrumentor
from .tracing import configure_tracing

from video_ai_system.config import settings
from video_ai_system.services.pipeline_service import PipelineService
from video_ai_system.services.preprocessing_service import VideoPreprocessor
from video_ai_system.services.vector_db_service import VectorDBService

# --- Worker-specific Service Initialization ---
# It's important that the worker initializes its own instances of services
# to avoid sharing state with the API server process.

def startup(ctx):
    """
    This function is called by ARQ on worker startup.
    It initializes all necessary services for the pipeline.
    """
    logging.info("Worker starting up. Configuring tracing and initializing services...")
    # Configure OpenTelemetry
    configure_tracing("video-ai-system-worker")

    # Instrument ARQ
    ARQInstrumentor().instrument()

    # Initialize services required by the pipeline
    preprocessor_config = {
        'HASH_ALGORITHM': settings.PREPROCESSING_HASH_ALGORITHM,
        'HASH_DISTANCE_THRESHOLD': settings.PREPROCESSING_HASH_DISTANCE_THRESHOLD,
        'HASH_SIZE': settings.PREPROCESSING_HASH_SIZE,
        'TARGET_SIZE': (settings.PREPROCESSING_TARGET_WIDTH, settings.PREPROCESSING_TARGET_HEIGHT),
        'CPU_THRESHOLD': settings.PREPROCESSING_CPU_THRESHOLD,
        'THROTTLE_DELAY': settings.PREPROCESSING_THROTTLE_DELAY,
    }
    preprocessor = VideoPreprocessor(preprocessor_config)
    
    vector_db_service = VectorDBService()
    vector_db_service.initialize_collection()

    pipeline_service = PipelineService(
        preprocessor=preprocessor,
        vector_db=vector_db_service,
        inference_service_url=settings.INFERENCE_CLIENT_URL,
        batch_size=settings.PIPELINE_DB_BATCH_SIZE
    )
    
    ctx["pipeline_service"] = pipeline_service
    logging.info("Worker startup complete.")

# --- ARQ Task Definition ---

async def analyze_video(ctx, file_path: str, **kwargs):
    """
    This is the ARQ task function that performs the heavy lifting.
    It delegates the entire workflow to the PipelineService.

    Args:
        ctx: The job context provided by ARQ. Contains the redis connection.
        file_path: The local path to the video file to be analyzed.
        **kwargs: Catches any other parameters, like 'video_id'.
    """
    job_id = ctx['job_id']
    video_id = kwargs.get("video_id", job_id) # Use job_id as a fallback
    pipeline_service: PipelineService = ctx["pipeline_service"]

    logging.info(f"[{job_id}] Starting analysis for video: {file_path}")

    try:
        await pipeline_service.process_video(video_path=file_path, video_id=video_id)

        logging.info(f"[{job_id}] Analysis successful.")
        return {"status": "success", "video_id": video_id, "results_persisted": True}

    except Exception as e:
        logging.critical(f"[{job_id}] Analysis failed: {e}", exc_info=True)
        # The exception will be caught by ARQ and the job status will be set to 'failed'.
        # ARQ will also store the traceback.
        raise

# --- ARQ Worker Settings ---

class WorkerSettings:
    """
    Defines the configuration for the ARQ worker.
    This class is referenced when starting the worker from the CLI.
    """
    on_startup = startup
    functions = [analyze_video]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_DSN)
    # You can add other settings here, like 'max_jobs', 'job_timeout', etc.