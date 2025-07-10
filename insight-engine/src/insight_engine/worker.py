import asyncio
from arq.connections import RedisSettings
from insight_engine.services.clip_generator import ClipGenerator


async def generate_clip_task(ctx, video_uri: str, start_time: float, end_time: float, output_path: str):
    """
    Arq task to generate a video clip.
    """
    clip_generator = ClipGenerator()
    await clip_generator.generate_clip(video_uri, start_time, end_time, output_path)
    return {"status": "completed", "output_path": output_path}


async def startup(ctx):
    """
    Worker startup logic.
    """
    print("Worker starting up...")


async def shutdown(ctx):
    """
    Worker shutdown logic.
    """
    print("Worker shutting down...")


class WorkerSettings:
    """
    Arq worker settings.
    """
    functions = [generate_clip_task]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings()
