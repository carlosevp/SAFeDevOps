# Root Dockerfile: Railway (and similar) build from repo root; monorepo has no single package.json/requirements.txt there.
# This image runs the FastAPI backend only. Deploy the Vite frontend separately (e.g. Railway static, Vercel, Netlify).

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/ /app/

EXPOSE 8000

# Railway sets PORT; default for local docker run
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
