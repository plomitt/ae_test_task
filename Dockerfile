# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src" \
    HOST=0.0.0.0 \
    PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.6.1

# Set work directory
WORKDIR /app

# Copy poetry files
COPY pyproject.toml poetry.lock* README.md ./

# Configure poetry
RUN poetry config virtualenvs.create false

# Copy application code
COPY src/ ./src/

# Install dependencies
RUN poetry install

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/weather/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "yr_forecast.main"]