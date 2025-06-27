FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .

RUN pip install --no-cache-dir ".[dev]"
RUN pip install opentelemetry-instrumentation-fastapi

ENV PYTHONPATH=/app/src

COPY . .

CMD ["uvicorn", "video_ai_system.main:app", "--host", "0.0.0.0", "--port", "8000"]