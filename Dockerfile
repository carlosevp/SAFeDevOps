# Single image: Vite SPA + FastAPI (same Railway URL). Set VITE_API_BASE_URL at build only if API is on another host.
# Runtime uses Alpine (musl) for a smaller surface and fewer distro CVEs vs Debian slim; frontend build stage matches.

FROM node:20-alpine AS frontend
RUN apk upgrade --no-cache
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Same-origin on Railway: leave empty so the browser calls /api on this host
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM python:3.12-alpine

WORKDIR /app

RUN apk upgrade --no-cache

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt /app/requirements.txt
# Temporary toolchain for wheels that lack musllinux binaries (e.g. some uvicorn/pydantic builds).
RUN apk add --no-cache --virtual .build-deps gcc musl-dev linux-headers \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && apk del .build-deps

COPY backend/ /app/
COPY --from=frontend /fe/dist /app/spa_dist

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
