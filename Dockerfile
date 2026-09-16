# Multi-stage build: build the React frontend with Node, then run it all
# from a slim Python image via FastAPI (which serves frontend/dist as
# static files - see backend/main.py). This mirrors the "one deployable
# service" architecture used locally, just containerized for Render/Railway.

FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# psycopg[binary] and Pillow need no extra system libs on this base image;
# if that ever changes, add build-essential/libpq-dev here.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY db/ ./db/
COPY categorize/ ./categorize/
COPY voice/ ./voice/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
