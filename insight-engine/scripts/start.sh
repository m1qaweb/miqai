#!/bin/bash

# Start the Uvicorn server in the background
uvicorn src.insight_engine.main:app --host 0.0.0.0 --port 8080 &

# Start the Arq worker
arq src.insight_engine.worker.WorkerSettings
