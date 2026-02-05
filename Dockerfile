FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    pkg-config \
    libssl-dev \
    ca-certificates \
    libgl1-mesa-glx \
    libglib2.0-0 \
    scrot \
    python3-tk \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directories
RUN mkdir -p /app/backups /app/media /app/data

# Copy application source
COPY . .

# Environment configuration
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MEGABOT_MEDIA_PATH=/app/media

# Expose ports
EXPOSE 8000
EXPOSE 18790

# Default command
CMD ["python3", "core/orchestrator.py"]
