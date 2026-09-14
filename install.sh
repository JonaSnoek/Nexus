#!/bin/bash
# =============================================================================
# NEXUS - Installation Script
# =============================================================================
# Idempotent installer for the NEXUS platform.
# Usage: sudo bash install.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    fatal "This script must be run as root. Use: sudo bash install.sh"
fi

if [[ "$(uname)" != "Linux" ]]; then
    fatal "This script only supports Linux. Detected: $(uname)"
fi

ARCH="$(uname -m)"
if [[ "$ARCH" != "x86_64" ]]; then
    fatal "Only x86_64 architecture is supported. Detected: $ARCH"
fi

info "Pre-flight checks passed (root, Linux, x86_64)"

# ---------------------------------------------------------------------------
# Install Docker
# ---------------------------------------------------------------------------
if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    ok "Docker installed"
else
    ok "Docker already installed: $(docker --version)"
fi

# ---------------------------------------------------------------------------
# Install Docker Compose plugin
# ---------------------------------------------------------------------------
if ! docker compose version &>/dev/null; then
    info "Installing Docker Compose plugin..."
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep -oP '"tag_name":\s*"\K[^"]+')
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ok "Docker Compose installed"
else
    ok "Docker Compose already installed: $(docker compose version --short)"
fi

# ---------------------------------------------------------------------------
# RAM check
# ---------------------------------------------------------------------------
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))
if [[ $TOTAL_RAM_MB -lt 4096 ]]; then
    warn "Only ${TOTAL_RAM_MB}MB RAM detected. Recommended: 4GB+"
    warn "Nexus may run slowly with limited memory."
else
    ok "RAM check passed: ${TOTAL_RAM_MB}MB available"
fi

# ---------------------------------------------------------------------------
# Project directory
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# .env setup
# ---------------------------------------------------------------------------
if [[ ! -f .env ]]; then
    info "Creating .env from .env.example..."
    cp .env.example .env
    ok ".env created"
else
    ok ".env already exists"
fi

generate_secret() {
    python3 -c "import secrets; print(secrets.token_urlsafe(48))" 2>/dev/null \
        || openssl rand -base64 48 | tr -d '\n'
}

# Generate SECRET_KEY if still default
if grep -q "^NEXUS_SECRET_KEY=CHANGE_ME" .env; then
    NEW_KEY=$(generate_secret)
    sed -i "s|^NEXUS_SECRET_KEY=CHANGE_ME|NEXUS_SECRET_KEY=${NEW_KEY}|" .env
    ok "Generated NEXUS_SECRET_KEY"
fi

# Generate POSTGRES_PASSWORD if still default
if grep -q "^POSTGRES_PASSWORD=CHANGE_ME" .env; then
    NEW_PASS=$(generate_secret)
    sed -i "s|^POSTGRES_PASSWORD=CHANGE_ME|POSTGRES_PASSWORD=${NEW_PASS}|" .env
    sed -i "s|^DATABASE_URL=postgresql+asyncpg://nexus:CHANGE_ME@postgres:5432/nexus|DATABASE_URL=postgresql+asyncpg://nexus:${NEW_PASS}@postgres:5432/nexus|" .env
    ok "Generated POSTGRES_PASSWORD"
fi

# Prompt for admin password if not set
ADMIN_PASS=$(grep "^FIRST_ADMIN_PASSWORD=" .env | cut -d'=' -f2-)
if [[ -z "$ADMIN_PASS" ]]; then
    warn "FIRST_ADMIN_PASSWORD is not set."
    read -rp "Enter admin password (leave blank to skip): " ADMIN_PASS_INPUT
    if [[ -n "$ADMIN_PASS_INPUT" ]]; then
        sed -i "s|^FIRST_ADMIN_PASSWORD=.*|FIRST_ADMIN_PASSWORD=${ADMIN_PASS_INPUT}|" .env
        ok "Admin password set"
    else
        warn "Admin password not set. You can set it in .env later."
    fi
fi

# ---------------------------------------------------------------------------
# Load env vars for use in this script
# set -a
# source .env
# set +a

# ---------------------------------------------------------------------------
# Build and start services
# ---------------------------------------------------------------------------
info "Pulling and building Docker images..."
docker compose pull 2>/dev/null || docker-compose pull 2>/dev/null || true
docker compose build 2>/dev/null || docker-compose build 2>/dev/null || true
ok "Images built"

# ---------------------------------------------------------------------------
# Start PostgreSQL first
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Start backend and run migrations
# ---------------------------------------------------------------------------
info "Starting backend..."
docker compose up -d nexus-backend 2>/dev/null || docker-compose up -d nexus-backend 2>/dev/null
sleep 5
ok "Backend started"

# ---------------------------------------------------------------------------
# Start Ollama and pull model
# ---------------------------------------------------------------------------
info "Starting Ollama..."
docker compose up -d ollama 2>/dev/null || docker-compose up -d ollama 2>/dev/null

MODEL=$(grep "^NEXUS_LLM_MODEL=" .env | cut -d'=' -f2-)
MODEL=${MODEL:-qwen3:8b}
info "Pulling LLM model: $MODEL (this may take a while)..."
docker exec nexus-ollama ollama pull "$MODEL" || warn "Failed to pull model $MODEL"
ok "Ollama ready"

# ---------------------------------------------------------------------------
# Start all services
# ---------------------------------------------------------------------------
info "Starting all services..."
docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null
ok "All services started"

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
info "Running health check (up to 60 seconds)..."
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

if $HEALTHY; then
    ok "NEXUS is healthy and running!"
else
    warn "Health check did not pass within 60 seconds."
    warn "Services may still be starting. Check: docker compose logs"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
ADMIN_USER=$(grep "^FIRST_ADMIN_USERNAME=" .env | cut -d'=' -f2-)
ADMIN_USER=${ADMIN_USER:-admin}

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  NEXUS Installation Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  URL:         ${CYAN}http://localhost${NC}"
echo -e "  Admin User:  ${CYAN}${ADMIN_USER}${NC}"
echo ""
echo -e "  Logs:        ${CYAN}docker compose logs -f${NC}"
echo -e "  Stop:        ${CYAN}docker compose down${NC}"
echo -e "  Start:       ${CYAN}docker compose up -d${NC}"
echo -e "  Backup:      ${CYAN}bash backup.sh${NC}"
echo ""
echo -e "${GREEN}============================================================${NC}"
