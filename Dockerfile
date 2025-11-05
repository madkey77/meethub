# Standard Python base image (no GPU support for Deepgram API)
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create data directory for database
RUN mkdir -p /app/data

# Run database migrations on startup and start application
CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]
