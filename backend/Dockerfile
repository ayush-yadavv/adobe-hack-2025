# Stage 1: Build the application
FROM python:3.10-slim AS builder

WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install -r requirements.txt

# Stage 2: Runtime image
FROM python:3.10-slim AS app

WORKDIR /app

# Install ffmpeg for audio processing
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Create the storage and db directories
RUN mkdir -p /app/storage
RUN mkdir -p /app/db

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Set PYTHONPATH to ensure modules are found
ENV PYTHONPATH=/usr/local/lib/python3.10/site-packages:$PYTHONPATH

# Command to run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
