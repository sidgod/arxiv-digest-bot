# Multi-stage build for arXiv Digest Bot
# Optimized for Raspberry Pi (ARM64)

FROM python:3.11-slim-bookworm as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim-bookworm

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN useradd -m -u 1000 arxiv && \
    mkdir -p /app/data && \
    chown -R arxiv:arxiv /app

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=arxiv:arxiv src/ ./src/

# Switch to non-root user
USER arxiv

# Default data directory
ENV DATA_DIR=/app/data

# Entry point
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--mode=digest"]
