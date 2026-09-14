#!/bin/bash
# =============================================================================
# NEXUS - Update Script
# =============================================================================
# Safely updates the NEXUS installation.
# Usage: sudo bash update.sh
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }
fatal()   { error "$1"; exit 1; }

if [[ $EUID -ne 0 ]]; then
    fatal "This script must be run as root. Use: sudo bash update.sh"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f .env ]]; then
    fatal ".env file not found. Run install.sh first."
fi

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  NEXUS Update${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# Step 1: Stop containers (preserve volumes)
info "Stopping containers (volumes preserved)..."
docker compose stop 2>/dev/null || docker-compose stop 2>/dev/null
ok "Containers stopped"

# Step 2: Pull latest code
info "Pulling latest code from git..."
git pull origin main || git pull origin master || warn "No remote updates or git pull failed"
ok "Code updated"

# Step 3: Rebuild images
info "Rebuilding Docker images..."
docker compose build --no-cache 2>/dev/null || docker-compose build --no-cache 2>/dev/null
ok "Images rebuilt"

# Step 4: Start PostgreSQL and wait
info "Starting PostgreSQL..."
docker compose up -d postgres 2>/dev/null || docker-compose up -d postgres 2>/dev/null
info "Waiting for PostgreSQL to be healthy..."
RETRIES=30
until docker inspect --format='{{.State.Health.Status}}' nexus-postgres 2>/dev/null | grep -q "healthy"; do
    RETRIES=$((RETRIES - 1))
    if [[ $RETRIES -le 0 ]]; then
        fatal "PostgreSQL failed to start within 60 seconds"
    fi
    echo -n "."
    sleep 2
done
echo ""
ok "PostgreSQL is healthy"

# Step 5: Start backend and run migrations
info "Starting backend..."
docker compose up -d nexus-backend 2>/dev/null || docker-compose up -d nexus-backend 2>/dev/null
sleep 5
ok "Backend started"

# Step 6: Pull updated LLM model if needed
info "Checking Ollama model..."
docker compose up -d ollama 2>/dev/null || docker-compose up -d ollama 2>/dev/null
sleep 3

MODEL=$(grep "^NEXUS_LLM_MODEL=" .env | cut -d'=' -f2-)
MODEL=${MODEL:-qwen3:8b}
if docker exec nexus-ollama ollama list 2>/dev/null | grep -q "$MODEL"; then
    info "Model $MODEL already present, pulling updates..."
    docker exec nexus-ollama ollama pull "$MODEL" || warn "Model pull failed"
else
    info "Pulling new model: $MODEL..."
    docker exec nexus-ollama ollama pull "$MODEL" || warn "Model pull failed"
fi
ok "Ollama ready"

# Step 7: Start all services
info "Starting all services..."
docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null
ok "All services started"

# Step 8: Health check
info "Running health check..."
HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost/api/health &>/dev/null; then
        HEALTHY=true
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

echo ""
if $HEALTHY; then
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}  NEXUS Update Complete!${NC}"
    echo -e "${GREEN}============================================================${NC}"
else
    echo -e "${YELLOW}============================================================${NC}"
    echo -e "${YELLOW}  NEXUS Update Complete (health check pending)${NC}"
    echo -e "${YELLOW}============================================================${NC}"
fi
echo ""
echo -e "  URL:    ${CYAN}http://localhost${NC}"
echo -e "  Logs:   ${CYAN}docker compose logs -f${NC}"
echo ""
