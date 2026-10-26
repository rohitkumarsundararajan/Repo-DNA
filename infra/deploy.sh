#!/usr/bin/env bash
# Usage: ./deploy.sh        (run inside /opt/repodna/app/infra)
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Pulling latest code"
git pull --ff-only

WORKERS=$(grep -E '^WORKER_REPLICAS=' .env | cut -d= -f2 || true)
WORKERS=${WORKERS:-1}

echo "==> Building and starting (workers: $WORKERS)"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --scale analysis-worker="$WORKERS"

echo "==> Cleaning old images"
docker image prune -f

echo "==> Status"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps