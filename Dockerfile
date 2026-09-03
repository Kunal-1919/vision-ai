# VisionAI Enterprise — Production Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies required for OpenCV, PyTorch, Pillow & curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition
COPY requirements.txt .

# Install CPU PyTorch + torchvision first (avoids multi-gigabyte CUDA bloat)
RUN pip install --default-timeout=300 --retries 5 --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu && \
    pip install --default-timeout=300 --retries 5 --no-cache-dir -r requirements.txt

# Copy application source code and initial data structure
COPY app/ ./app/
COPY data/ ./data/

# Expose default port
EXPOSE 8088

# Built-in Docker Container Healthcheck
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8088}/api/health || exit 1

# Launch FastAPI app with Uvicorn ASGI server
CMD ["sh", "-c", "exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8088}"]
