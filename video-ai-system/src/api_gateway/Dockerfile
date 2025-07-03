# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the main requirements file from the project root
COPY requirements.txt .

# Install all dependencies from the main requirements file
RUN apt-get update && apt-get install -y iproute2 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application source code into the container
COPY ./src .

# Set the PYTHONPATH to the working directory to ensure modules are found
ENV PYTHONPATH=/app

# Command to run the api-gateway application using python -m to ensure path correctness
CMD ["python", "-m", "uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]