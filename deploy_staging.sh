#!/usr/bin/env bash

# Exit immediately if any command exits with a non-zero status
set -o errexit
set -o pipefail
set -o nounset

# 1. Parse branch name argument
if [ -z "${1:-}" ]; then
  echo "Error: Branch name not specified."
  echo "Usage: ./deploy_staging.sh <branch_name>"
  exit 1
fi

BRANCH_NAME="$1"

echo "==========================================="
echo "Starting Staging Deployment for branch: $BRANCH_NAME"
echo "==========================================="

# Ensure we are running from repository root
if [ ! -d ".git" ]; then
  echo "Error: Must be run from the repository root directory."
  exit 1
fi

# 2. Checkout the specified branch
echo ">>> Fetching latest changes from remote..."
git fetch origin

echo ">>> Checking out branch: $BRANCH_NAME..."
git checkout "$BRANCH_NAME"

echo ">>> Pulling latest updates..."
git pull origin "$BRANCH_NAME"

# Ensure script itself is executable
chmod +x "$0"

# 3. Rebuild and restart containers
echo ">>> Stopping existing Docker Compose services..."
docker compose down

echo ">>> Rebuilding and launching Docker Compose services..."
docker compose up -d --build

# 4. Status Verification Loop
echo ">>> Verifying service health..."

MAX_RETRIES=15
RETRY_INTERVAL=5
backend_healthy=false
frontend_healthy=false

echo "Waiting for services to become healthy..."
for ((i=1; i<=MAX_RETRIES; i++)); do
  echo "Checking status (Attempt $i/$MAX_RETRIES)..."

  # Check backend health
  BE_RESPONSE=$(curl -s -f http://localhost:8750/health 2>/dev/null || true)
  if [ -n "$BE_RESPONSE" ]; then
    if echo "$BE_RESPONSE" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
      echo "  [OK] Backend API (and DB connection) is healthy."
      backend_healthy=true
    else
      echo "  [WARNING] Backend API responded, but status is not 'ok':"
      echo "    $BE_RESPONSE"
    fi
  else
    echo "  [...] Backend API is not responding yet."
  fi

  # Check frontend health
  FE_RESPONSE=$(curl -s -f http://localhost:8760/ 2>/dev/null || true)
  if [ -n "$FE_RESPONSE" ]; then
    if echo "$FE_RESPONSE" | grep -q -i "Rankify"; then
      echo "  [OK] Frontend UI is serving files correctly."
      frontend_healthy=true
    else
      echo "  [WARNING] Frontend UI responded, but page title/content doesn't contain 'Rankify'."
    fi
  else
    echo "  [...] Frontend UI is not responding yet."
  fi

  if [ "$backend_healthy" = true ] && [ "$frontend_healthy" = true ]; then
    break
  fi

  sleep $RETRY_INTERVAL
done

# 5. Output results and diagnostics
if [ "$backend_healthy" = false ] || [ "$frontend_healthy" = false ]; then
  echo ""
  echo "==========================================="
  echo "ERROR: Deployment verification FAILED!"
  echo "==========================================="
  echo ">>> Showing Docker Compose service status:"
  docker compose ps
  echo ""
  echo ">>> Showing last 30 lines of backend container logs:"
  docker compose logs --tail=30 backend
  echo ""
  echo ">>> Showing last 30 lines of frontend container logs:"
  docker compose logs --tail=30 frontend
  exit 1
else
  echo ">>> Running database migrations via Alembic..."
  if docker compose exec -T backend alembic upgrade head; then
    echo "  [OK] Database migrations applied successfully."
  else
    echo "  [ERROR] Database migrations failed!"
    echo ">>> Showing last 30 lines of backend container logs:"
    docker compose logs --tail=30 backend
    exit 1
  fi

  echo ""
  echo "==========================================="
  echo "SUCCESS: Deployment completed successfully!"
  echo "==========================================="
  echo "Frontend UI: http://localhost:8760"
  echo "Backend API: http://localhost:8750"
  echo "API Docs:    http://localhost:8750/docs"
  echo "==========================================="
fi
