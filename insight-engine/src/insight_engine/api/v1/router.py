from fastapi import APIRouter

from insight_engine.api.v1.endpoints import clips, summarize, upload

api_router = APIRouter()
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(summarize.router, tags=["summarize"])
api_router.include_router(clips.router, tags=["clips"])