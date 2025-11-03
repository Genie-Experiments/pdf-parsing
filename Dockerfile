# ============================================================
# Base image: Python 3.12 (full, not slim)
# ============================================================
FROM python:3.12

# Set working directory
WORKDIR /app

# Copy dependency files first (for better build caching)
COPY pyproject.toml ./
COPY uv.lock ./

# OPTIONAL: If you already have requirements.txt locally, copy it
COPY requirements.txt ./

# ============================================================
# Install system dependencies (especially for OpenCV)
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Install Python dependencies using pip
# ============================================================

# If you already have a requirements.txt, uncomment this:
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================
# Copy the application source code
# ============================================================
COPY . .

# ============================================================
# Create required directories
# ============================================================
RUN mkdir -p \
    ./Data \
    ./Results \
    ./processed_images_by_dolphin \
    ./pdfs_raw_text \
    ./section_hierarchy_pdfs

# ============================================================
# Default command to run the app
# ============================================================
ENTRYPOINT ["python", "main.py"]

# ============================================================
# Metadata
# ============================================================
LABEL maintainer="pdf-parsing-app" \
      version="1.0" \
      description="PDF Parsing Pipeline with Dolphin AI Model" \
      python.version="3.12"
