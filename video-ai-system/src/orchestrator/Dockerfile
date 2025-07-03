# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the main requirements file from the project root
COPY requirements.txt .

# Install all dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application source code into the container
COPY ./src .

# Set the PYTHONPATH to the working directory to ensure modules are found
ENV PYTHONPATH=/app

# Command to run the orchestrator application
# The module path is now correct relative to the source code structure
CMD ["python", "-m", "orchestrator.main"]