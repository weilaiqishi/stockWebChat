# Stage 1: Build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /build/client
COPY client/package.json client/pnpm-lock.yaml* ./
RUN corepack enable && pnpm install --frozen-lockfile || pnpm install
COPY client/ ./
RUN pnpm build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python deps
COPY pyproject.toml ./
RUN uv sync --no-dev

# Copy server code
COPY server/ ./server/
COPY strategies/ ./strategies/
COPY main.py ./

# Copy built frontend
COPY --from=frontend-builder /build/client/dist ./client/dist

# Copy config template if no config exists
COPY config.example.json ./config.example.json

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
