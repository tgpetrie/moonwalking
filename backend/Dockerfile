FROM node:22-alpine AS frontend-build

WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN VITE_API_BASE= VITE_API_BASE_URL= VITE_API_URL= npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVE_FRONTEND_DIST=1 \
    HOST=0.0.0.0 \
    PORT=5003

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /src/frontend/dist ./frontend/dist/

RUN groupadd --gid 1001 moonwalking \
    && useradd --uid 1001 --gid 1001 --system --create-home moonwalking \
    && mkdir -p /var/lib/moonwalking \
    && chown -R moonwalking:moonwalking /app /var/lib/moonwalking

USER moonwalking
WORKDIR /app/backend

EXPOSE 5003

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import requests; requests.get('http://127.0.0.1:5003/api/health', timeout=5).raise_for_status()"

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5003", "--workers", "1", "--threads", "8", "--timeout", "120"]
