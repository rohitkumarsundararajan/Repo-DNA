# Build context is the REPO ROOT (see infra/docker-compose.yml), so the image can
# carry contract/ (the JSON schemas). The folder layout inside the image mirrors
# the repository, which keeps every "find contract/ relative to this file" path working:
#   /app/contract/...                                  <- schemas
#   /app/backend/analysis-worker/repodna_worker/...    <- code
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git nodejs npm \
    && npm install --global madge@8.0.0 \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend/analysis-worker

COPY backend/analysis-worker/requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY contract /app/contract
COPY backend/analysis-worker/repodna_worker ./repodna_worker

# Runs as root on purpose: the worker needs the Docker socket to start sandbox containers.
CMD ["python", "-m", "repodna_worker.consumer.worker"]
