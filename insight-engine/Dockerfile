# Use a slim Python base image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Create a non-root user
RUN useradd --create-home appuser
USER appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy start script and make it executable
COPY ./scripts/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose the port the app runs on
EXPOSE 8080

# Define the command to run the application
CMD ["/app/start.sh"]
