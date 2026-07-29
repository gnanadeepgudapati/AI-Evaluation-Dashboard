# Multi-stage build: compile the React frontend, then assemble a lean
# Python runtime image that serves both the API and the built static files.

# ---- Stage 1: build the frontend ----
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend-src
COPY frontend-src/package*.json ./
RUN npm ci
COPY frontend-src/ ./
# Build output goes to ../frontend per vite.config.ts (build.outDir)
RUN npm run build

# ---- Stage 2: production image ----
FROM python:3.12-slim AS production
WORKDIR /app

# Install backend dependencies first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY api/ ./api/
COPY database/ ./database/
COPY evaluation_pipeline/ ./evaluation_pipeline/
COPY metrics/ ./metrics/
COPY providers/ ./providers/
COPY suites/ ./suites/

# Copy the built frontend from stage 1 (never rebuild frontend here)
COPY --from=frontend-builder /app/frontend ./frontend

# Run as a non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

CMD ["uvicorn", "api.dashboard_server:app", "--host", "0.0.0.0", "--port", "8000"]
