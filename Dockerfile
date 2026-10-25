FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies for OCR & image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Generate default sample documents during image build
RUN python -m app.sample_generator

# Expose FastAPI (8000) and Streamlit (8501) ports
EXPOSE 8000 8501

# Default launch command: Streamlit UI
CMD ["streamlit", "run", "web_ui.py", "--server.port=8501", "--server.address=0.0.0.0"]
