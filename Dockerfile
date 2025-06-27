# Builder for frontend
FROM node:20-slim AS builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Main Python app image
FROM python:3.11-slim AS fastapi
WORKDIR /home/appuser/app

# Create user
RUN useradd --create-home appuser

# Copy only dependency files first for better caching
COPY pyproject.toml ./

# Install dependencies (including opentelemetry-instrumentation-fastapi)
RUN pip install --no-cache-dir ".[dev]" && \
    pip install opentelemetry-instrumentation-fastapi && \
    pip list && pip show opentelemetry-instrumentation-fastapi

# Copy app code
COPY ./src /home/appuser/app/src

# Copy frontend build
COPY --from=builder /app/frontend/build /home/appuser/app/static

# Copy entrypoint
COPY entrypoint.sh /home/appuser/app/entrypoint.sh
RUN chmod +x /home/appuser/app/entrypoint.sh

# Set permissions
RUN chown -R appuser:appuser /home/appuser/app

USER appuser

ENV PYTHONPATH=/home/appuser/app/src

CMD ["/home/appuser/app/entrypoint.sh"]
