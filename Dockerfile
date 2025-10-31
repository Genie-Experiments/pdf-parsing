# Use Python 3.12 slim image for a lightweight base
FROM python:3.12-slim

# Install system dependencies required for building packages like PyMuPDF and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmupdf-dev \
    pkg-config \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv for faster Python package management
RUN pip install uv

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml ./
COPY uv.lock ./

# Copy the entire application
COPY . .

# Install Python dependencies
RUN uv sync

# Create necessary directories
RUN mkdir -p \
    ./Data \
    ./Results \
    ./processed_images_by_dolphin \
    ./pdfs_raw_text \
    ./section_hierarchy_pdfs

# Run app using uv-managed environment
ENTRYPOINT ["uv", "run", "python", "main.py"]

LABEL maintainer="pdf-parsing-app" \
      version="1.0" \
      description="PDF Parsing Pipeline with Dolphin AI Model" \
      python.version="3.12"
