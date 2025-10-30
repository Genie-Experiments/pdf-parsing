# Use Python 3.12 slim image for a lightweight base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv for faster Python package management
RUN pip install uv

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml ./

# Copy the entire application
COPY . .

# Install Python dependencies using uv
RUN uv sync

# Create necessary directories
RUN mkdir -p \
    ./Data \
    ./Results \
    ./processed_images_by_dolphin \
    ./pdfs_raw_text \
    ./section_hierarchy_pdfs

# Set the entry point
ENTRYPOINT ["python", "main.py"]

# Labels for metadata
LABEL maintainer="pdf-parsing-app" \
      version="1.0" \
      description="PDF Parsing Pipeline with Dolphin AI Model" \
      python.version="3.12"
