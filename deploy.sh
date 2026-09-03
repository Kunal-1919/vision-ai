#!/usr/bin/env bash
# ==============================================================================
# VisionAI Enterprise — One-Shot Automated Docker Deployment Script
# Usage: ./deploy.sh [uat|prod]
# ==============================================================================

set -euo pipefail

# ANSI Color Codes
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              VisionAI Enterprise — Docker Deployment               ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 1. Parameter Validation
TARGET_ENV="${1:-}"

if [[ "$TARGET_ENV" != "uat" && "$TARGET_ENV" != "prod" ]]; then
  echo -e "${RED}❌ Error: Environment parameter required!${NC}"
  echo -e "${YELLOW}Usage:${NC} ./deploy.sh [uat|prod]"
  echo -e "  - uat  : Deploy to UAT environment (reads env.uat / .env.uat)"
  echo -e "  - prod : Deploy to Production environment (reads env.prod / .env.prod)"
  exit 1
fi

ENV_UPPER=$(echo "$TARGET_ENV" | tr '[:lower:]' '[:upper:]')

# 2. Environment File Resolution
ENV_FILE=""
if [[ -f "env.${TARGET_ENV}" ]]; then
  ENV_FILE="env.${TARGET_ENV}"
elif [[ -f ".env.${TARGET_ENV}" ]]; then
  ENV_FILE=".env.${TARGET_ENV}"
else
  echo -e "${RED}❌ Error: Environment configuration file 'env.${TARGET_ENV}' or '.env.${TARGET_ENV}' not found!${NC}"
  exit 1
fi

echo -e "➜ Target Environment: ${GREEN}${ENV_UPPER}${NC}"
echo -e "➜ Environment File  : ${GREEN}${ENV_FILE}${NC}"

# Extract PORT from env file
PORT=$(grep -E "^PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '\r" ' || echo "")
if [[ -z "$PORT" ]]; then
  if [[ "$TARGET_ENV" == "prod" ]]; then
    PORT=8080
  else
    PORT=8088
  fi
fi

CONTAINER_NAME="visionai-${TARGET_ENV}"
IMAGE_NAME="visionai:${TARGET_ENV}"

echo -e "➜ Container Name    : ${GREEN}${CONTAINER_NAME}${NC}"
echo -e "➜ Target Port       : ${GREEN}${PORT}${NC}"
echo ""

# 3. Check Docker Prerequisites
if ! docker info > /dev/null 2>&1; then
  echo -e "${RED}❌ Error: Docker daemon is not running! Please start Docker and try again.${NC}"
  exit 1
fi

# ==============================================================================
# PHASE 1: UNDEPLOY FLOW (Clean up existing containers/instances)
# ==============================================================================
echo -e "${YELLOW}🧹 [Phase 1/3] Executing Undeploy Flow...${NC}"

if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}$"; then
  echo -e "  ➜ Stopping container '${CONTAINER_NAME}'..."
  docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  
  echo -e "  ➜ Removing container '${CONTAINER_NAME}'..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  echo -e "  ${GREEN}✓ Old container '${CONTAINER_NAME}' removed.${NC}"
else
  echo -e "  ${GREEN}✓ No existing container named '${CONTAINER_NAME}' found.${NC}"
fi

echo ""

# ==============================================================================
# PHASE 2: DEPLOY FLOW (Build Image & Launch Container)
# ==============================================================================
echo -e "${CYAN}🚀 [Phase 2/3] Executing Deploy Flow...${NC}"

echo -e "  ➜ Building Docker image '${IMAGE_NAME}'..."
docker build -t "${IMAGE_NAME}" -f Dockerfile .

echo -e "  ➜ Starting container '${CONTAINER_NAME}' on port ${PORT}..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  --env-file "${ENV_FILE}" \
  -e "PORT=${PORT}" \
  -e "ENV=${TARGET_ENV}" \
  -p "${PORT}:${PORT}" \
  -v "$(pwd)/data:/app/data" \
  "${IMAGE_NAME}" >/dev/null

echo -e "  ${GREEN}✓ Container '${CONTAINER_NAME}' started successfully.${NC}"
echo ""

# ==============================================================================
# PHASE 3: AUTOMATED HEALTH CHECK VERIFICATION
# ==============================================================================
echo -e "${CYAN}🏥 [Phase 3/3] Performing Health Verification...${NC}"

HEALTH_URL="http://localhost:${PORT}/api/health"
MAX_ATTEMPTS=20
SLEEP_SECONDS=2
ATTEMPT=1
HEALTH_PASSED=0

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
  echo -n "  ➜ Polling health check (${ATTEMPT}/${MAX_ATTEMPTS}) at ${HEALTH_URL}... "
  
  HTTP_STATUS=$(curl -s -o /tmp/health_response.json -w "%{http_code}" "${HEALTH_URL}" || echo "000")
  
  if [[ "$HTTP_STATUS" == "200" ]]; then
    echo -e "${GREEN}SUCCESS (HTTP 200 OK)${NC}"
    HEALTH_PASSED=1
    break
  else
    echo -e "${YELLOW}Waiting (HTTP ${HTTP_STATUS})...${NC}"
    sleep $SLEEP_SECONDS
    ATTEMPT=$((ATTEMPT + 1))
  fi
done

if [[ $HEALTH_PASSED -eq 1 ]]; then
  echo ""
  echo -e "${GREEN}====================================================================${NC}"
  echo -e "${GREEN}🎉 ONE-SHOT DEPLOYMENT SUCCESSFUL FOR ${ENV_UPPER}!${NC}"
  echo -e "${GREEN}====================================================================${NC}"
  echo -e "➜ Environment : ${CYAN}${ENV_UPPER}${NC}"
  echo -e "➜ App URL     : ${CYAN}http://localhost:${PORT}${NC}"
  echo -e "➜ API Docs    : ${CYAN}http://localhost:${PORT}/docs${NC}"
  echo -e "➜ Health Check: ${CYAN}http://localhost:${PORT}/api/health${NC}"
  echo -e "${GREEN}====================================================================${NC}"
  exit 0
else
  echo ""
  echo -e "${RED}❌ Error: Health check timed out or failed!${NC}"
  echo -e "${YELLOW}Container Logs (${CONTAINER_NAME}):${NC}"
  docker logs --tail 30 "${CONTAINER_NAME}"
  exit 1
fi
