# Stage 1: Build the React frontend
FROM node:20-slim AS builder

# Set the working directory for the frontend
WORKDIR /app/frontend

# Copy package configuration files
COPY frontend/package.json frontend/package-lock.json* ./

# Install frontend dependencies
RUN npm install

# Copy the rest of the frontend source code
COPY frontend/ ./

# Build the frontend application
RUN npm run build

# Stage 2: Build the Python backend and serve the frontend
FROM python:3.11-slim

# Create a non-root user
RUN useradd --create-home appuser
USER appuser

# Set the working directory in the container
WORKDIR /home/appuser/app

# Copy the project definition file
COPY pyproject.toml .

# Install poetry and dependencies
RUN pip install --no-cache-dir .

# Copy the rest of the application source code
COPY --chown=appuser:appuser ./src /home/appuser/app/src

# Copy the built frontend assets from the builder stage
COPY --chown=appuser:appuser --from=builder /app/frontend/build /home/appuser/app/static

# Command to run the application
CMD ["uvicorn", "src.video_ai_system.main:app", "--host", "0.0.0.0", "--port", "8000"]