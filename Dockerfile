# Stage 1: Builder stage to install dependencies
FROM python:3.10-slim as builder

WORKDIR /app

# Install poetry
RUN pip install poetry
ENV PATH="/root/.local/bin:$PATH"

# Copy only the files needed for dependency installation
COPY pyproject.toml poetry.lock* ./

# Install dependencies into a virtual environment
RUN poetry install --no-dev --no-interaction --no-ansi

# Stage 2: Final stage for the production image
FROM python:3.10-slim

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /.venv

# Activate the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application source code
COPY ./src/insight_engine ./src/insight_engine

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "src.insight_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
