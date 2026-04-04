#!/bin/bash
set -euo pipefail

# Load environment
if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in values."
  exit 1
fi

export $(grep -v '^#' .env | xargs)

echo "Pulling latest images..."
docker compose pull

echo "Starting services..."
docker compose up -d --remove-orphans

echo "Waiting for backend health check..."
sleep 5
curl -sf http://localhost:8001/health || { echo "Backend health check failed"; exit 1; }

echo "Deploy complete."
