# ═════════════════════════════════════════════════════════════════════════════
# Dockerfile — DropKey v3.2 Enterprise-Grade Container Image
#
# Features:
# - Multi-stage build for minimal image size
# - Security hardening
# - Non-root user execution
# - Layer caching optimization
# - Health checks included
# - Minimal attack surface
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1: Builder
#
# Purpose: Install dependencies and build artifacts
# This stage is discarded in final image, keeping size minimal
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim as builder

# Set metadata
LABEL maintainer="DropKey Team <team@dropkey.io>"
LABEL version="3.2.0"
LABEL description="Enterprise peer-to-peer file transfer application"

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies needed for compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2: Runtime
#
# Purpose: Minimal runtime image with only necessary files
# Discards build artifacts and compilers
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Set metadata
LABEL maintainer="DropKey Team <team@dropkey.io>"
LABEL version="3.2.0"
LABEL description="Enterprise peer-to-peer file transfer application"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DROPKEY_ENVIRONMENT=production \
    DROPKEY_HOST=0.0.0.0 \
    DROPKEY_PORT=8000

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create app directory
WORKDIR /app

# Create non-root user for security
RUN groupadd -r dropkey && \
    useradd -r -g dropkey -u 1000 -d /app -s /sbin/nologin -c "DropKey application user" dropkey

# Copy application code
# Use .dockerignore to exclude unnecessary files
COPY --chown=dropkey:dropkey . .

# Create necessary directories with proper permissions
RUN mkdir -p \
    /app/logs \
    /app/tmp \
    /app/uploads \
    && chown -R dropkey:dropkey \
    /app/logs \
    /app/tmp \
    /app/uploads \
    && chmod 755 /app/logs /app/tmp /app/uploads

# Set security: remove any setuid/setgid bits
RUN find / -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true

# Switch to non-root user
USER dropkey

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
