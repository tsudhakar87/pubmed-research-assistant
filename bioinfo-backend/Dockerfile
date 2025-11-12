# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better layer caching)
COPY requirements.txt .

# Install Python dependencies
# Use --upgrade to ensure we get the latest compatible versions
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Verify critical packages are installed
RUN python -c "import fastapi; import uvicorn; import gunicorn; print('All packages installed successfully')"

# Copy application code
COPY src/ ./src/

# Create non-root user for security and set ownership
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENVIRONMENT=production
ENV PORT=8080

# Switch to non-root user
USER appuser

# Expose the port
EXPOSE 8080

# Health check to verify the app starts correctly
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:${PORT}/api/v1/health', timeout=2)" || exit 1

# Use gunicorn with uvicorn workers for production
CMD exec gunicorn src.api.main:app \
    --bind :$PORT \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
