# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for frontend build
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY services/agent-core/pyproject.toml ./

# Generate requirements and install
RUN python -c "import tomllib; p=tomllib.load(open('pyproject.toml','rb')); open('/tmp/requirements.txt','w').write('\n'.join(p['project']['dependencies']))" \
    && pip install --timeout 120 --retries 8 --no-cache-dir --prefix=/install -r /tmp/requirements.txt

# Copy source and install package
COPY services/agent-core/src ./src
RUN pip install --no-cache-dir --prefix=/install --no-deps -e .

# Frontend build stage
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY services/agent-core/frontend/package*.json ./
RUN npm install
COPY services/agent-core/frontend ./
RUN npm run build

# Runtime stage
FROM python:3.11-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r aria && useradd -r -g aria -d /app -s /sbin/nologin aria

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=aria:aria services/agent-core/src ./src
COPY --chown=aria:aria tools ./tools
COPY --chown=aria:aria skills ./skills

# Copy frontend build
COPY --from=frontend-builder /dist ./dashboard

# Create data directories
RUN mkdir -p /app/.data/agent-core /app/.data/agent-core/history /app/.data/agent-core/audit \
    /app/.data/agent-core/notes /app/.data/agent-core/todos /app/.data/agent-core/state \
    /app/.data/agent-core/skill_learning /app/.data/agent-core/consolidation \
    /app/.data/agent-core/tool-proposals /app/.data/agent-core/generated-tools \
    /app/.data/agent-core/skill_learning /app/.data/agent-core/workspace \
    /app/.data/agent-core/vector_index /app/.data/agent-core/consolidation \
    && chown -R aria:aria /app/.data

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER aria

# Expose port
EXPOSE 8000

# Use gunicorn with uvicorn workers for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UVICORN_WORKERS=1

CMD ["gunicorn", "agent_core.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--no-control-socket", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
