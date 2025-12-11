FROM python:3.11-slim

# Install system dependencies and Hindi fonts for multi-model PDF generation
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libfontconfig1 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    fonts-dejavu-core \
    fonts-noto \
    fonts-noto-devanagari \
    fonts-liberation \
    fontconfig \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (multi-model support)
COPY app.py .
COPY pdf_generator.py .
COPY docx_generator.py .
COPY index.html .

# Expose port
EXPOSE 8000

# Set environment variables for multi-model configuration
ENV PYTHONUNBUFFERED=1
ENV MODEL_ID=global.anthropic.claude-opus-4-5-20251101-v1:0
ENV BUCKET_NAME=pnb-poc-docs

# Health check for multi-model service
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the multi-model translation service
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]