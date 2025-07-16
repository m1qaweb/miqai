from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from insight_engine.api.v1.router import api_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"status": "ok"}


app.include_router(api_router, prefix="/v1")
