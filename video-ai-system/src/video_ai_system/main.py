from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

from video_ai_system.services.pipeline_service import PipelineService

# --- Application Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan. The startup logic is here.
    """
    pipeline_service = PipelineService()
    pipeline_service.load_from_config("config/development.json")
    app.state.pipeline_service = pipeline_service
    yield
    print("Application shutting down.")

# --- Application Setup ---
app = FastAPI(
    title="Video AI Analysis System",
    description="A modular system for self-supervised video analysis.",
    version="0.1.0",
    lifespan=lifespan
)

# --- Dependency Injection ---
def get_pipeline_service() -> PipelineService:
    return app.state.pipeline_service

# --- Metrics ---
instrumentator = Instrumentator().instrument(app)
instrumentator.expose(app)

# --- API Endpoints ---
class FrameProcessingRequest(BaseModel):
    data: dict

class FrameProcessingResponse(BaseModel):
    status: str
    result: list

@app.get("/health", tags=["Monitoring"])
def get_health():
    return {"status": "ok"}

@app.post("/process_frame", response_model=FrameProcessingResponse, tags=["Processing"])
def process_frame(
    request: FrameProcessingRequest,
    pipeline_service: PipelineService = Depends(get_pipeline_service)
):
    """
    Processes a request through the entire module pipeline using the PipelineService.
    """
    try:
        final_results = pipeline_service.execute(request.data)
        
        # Convert numpy arrays in results to lists for JSON serialization
        serializable_results = []
        for result in final_results:
            if hasattr(result, 'tolist'):
                serializable_results.append(result.tolist())
            else:
                serializable_results.append(result)

        return {"status": "success", "result": serializable_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))