# Stage 1: Builder
# This stage installs all dependencies, including dev dependencies, into a virtual environment.
FROM python:3.10-slim as builder

WORKDIR /app

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends build-essential

# Install poetry
RUN pip install --no-cache-dir poetry

# Configure poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

# Copy dependency definition files
COPY pyproject.toml poetry.lock* ./

# Copy the application source code so poetry can install it
COPY ./src /app/src

# Install all dependencies, including dev, into the virtual environment
# This creates a self-contained environment that can be copied to the final stage.
RUN poetry install --no-interaction --no-ansi

# ---

# Stage 2: Final Image
# This stage creates the final, lean production image.
FROM python:3.10-slim

WORKDIR /app

# Install production-only system dependencies before switching to non-root user
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user for security and switch to it
RUN useradd --create-home appuser
USER appuser

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Copy the application source code
COPY --chown=appuser:appuser ./src /app/src

# Set the PATH to include the virtual environment's bin directory
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port the app runs on
# Expose the port defined by the PORT environment variable.
# Cloud Run will set this variable, and Uvicorn will bind to it.
EXPOSE 8080

# Command to run the application
# This tells Cloud Run how to start the Uvicorn server.
# --host 0.0.0.0 is required to accept connections from outside the container.
# The port is dynamically set by the $PORT environment variable provided by Cloud Run.
CMD uvicorn src.insight_engine.main:app --host 0.0.0.0 --port ${PORT:-8080}
