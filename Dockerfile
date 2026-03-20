# ============================================================
# Stage 1: Build frontend
# ============================================================
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN corepack enable && corepack prepare pnpm@latest --activate && pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# ============================================================
# Stage 2: Build backend
# ============================================================
FROM python:3.12-slim AS backend

WORKDIR /app

# Install dependencies
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir -e . 2>/dev/null || pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "httpx>=0.27.0" \
    "python-jose[cryptography]>=3.3.0" \
    "authlib>=1.3.0" \
    "itsdangerous>=2.2.0" \
    "python-multipart>=0.0.9" \
    "websockets>=13.0" \
    "redis>=5.0.0" \
    "pydantic>=2.9.0" \
    "pydantic-settings>=2.5.0" \
    "sqlalchemy>=2.0.0" \
    "aiosqlite>=0.20.0" \
    "alembic>=1.13.0"

# Copy backend code
COPY backend/app ./app

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist ./static

# Create data directory
RUN mkdir -p /app/data

# Environment
ENV DATABASE_URL=sqlite+aiosqlite:///./data/app.db
ENV DEBUG=false

EXPOSE 8000

VOLUME ["/app/data"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
