#!/bin/bash
set -euo pipefail

# Load environment
if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in values."
  exit 1
fi

export $(grep -v '^#' .env | xargs)

echo "Pulling latest base images..."
docker compose pull --ignore-buildable

echo "Building frontend and backend images..."
docker compose build --no-cache frontend backend

echo "Starting services..."
docker compose up -d --remove-orphans

echo "Waiting for backend health check..."
for i in $(seq 1 12); do
  if docker compose exec backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    echo "Backend is healthy."
    break
  fi
  echo "  attempt $i/12 — waiting 5s..."
  sleep 5
done

echo "Waiting for frontend health check..."
for i in $(seq 1 18); do
  if docker compose exec frontend wget -qO- http://localhost:3000 > /dev/null 2>&1; then
    echo "Frontend is healthy."
    break
  fi
  echo "  attempt $i/18 — waiting 5s..."
  sleep 5
done

echo "Deploy complete."
