# Stage 1: Build Angular frontend
FROM node:22-slim AS frontend
WORKDIR /app
COPY frontend/package.json ./
RUN npm config set engine-strict false && npm install --force
COPY frontend/ ./
RUN npx ng build --configuration production

# Stage 2: Python backend + static frontend
FROM python:3.12-slim
WORKDIR /app

# System dependencies for psycopg2
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Install pinned Python dependencies (regenerate: see header of requirements.lock)
COPY backend/requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# Copy application code
COPY backend/ ./backend/
COPY config/ ./config/

# Copy frontend build output
COPY --from=frontend /app/dist/frontend/browser/ ./static/

# Cloud Run settings
ENV PORT=8080 \
    PYTHONUNBUFFERED=1

# Uvicorn with extended timeout for SSE streaming
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8080", "--timeout-keep-alive", "300"]
