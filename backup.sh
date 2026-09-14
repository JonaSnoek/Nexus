#!/bin/bash
# =============================================================================
# NEXUS - Backup Script
# =============================================================================
# Creates a timestamped backup of database, config, and env.
# Usage: sudo bash backup.sh
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
    fatal "This script must be run as root. Use: sudo bash backup.sh"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f .env ]]; then
    fatal ".env file not found. Nothing to back up."
fi

# Load env
set -a
source .env
set +a

BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_NAME="nexus-backup-$(date +%Y%m%d-%H%M%S)"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

mkdir -p "$BACKUP_PATH"

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  NEXUS Backup${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# --- Database dump ---
info "Dumping PostgreSQL database..."
if docker inspect nexus-postgres &>/dev/null; then
    docker exec nexus-postgres pg_dump \
        -U "${POSTGRES_USER:-nexus}" \
        -d "${POSTGRES_DB:-nexus}" \
        --no-owner --no-acl \
        | gzip > "${BACKUP_PATH}/database.sql.gz"
    ok "Database dumped"
else
    warn "PostgreSQL container not found. Skipping database dump."
fi

# --- Disk space check ---
BACKUP_FREE_KB=$(df -Pk . | awk 'NR==2 {print $4}')
BACKUP_FREE_GB=$((BACKUP_FREE_KB / 1024 / 1024))
db_size_mb=0
if docker exec nexus-postgres psql -U "${POSTGRES_USER:-nexus}" -d "${POSTGRES_DB:-nexus}" -Atc "SELECT pg_database_size('${POSTGRES_DB:-nexus}')/1024/1024;" >/tmp/nexus_dbsize 2>/dev/null; then
    db_size_mb=$(cat /tmp/nexus_dbsize 2>/dev/null || echo 0)
fi
rm -f /tmp/nexus_dbsize
if (( BACKUP_FREE_GB < 1 )) || (( BACKUP_FREE_GB * 1024 < db_size_mb )); then
    warn "Wenig Speicher fuer Backup (${BACKUP_FREE_GB}GB frei, DB ca. ${db_size_mb}MB)."
    warn "Backup wird fortgesetzt - pruefe danach: df -h ."
fi

# --- .env ---
info "Backing up .env file..."
cp .env "${BACKUP_PATH}/.env"
ok ".env backed up"

# --- Docker Compose files ---
info "Backing up Docker Compose files..."
cp docker-compose.yml "${BACKUP_PATH}/" 2>/dev/null || true
cp docker-compose.prod.yml "${BACKUP_PATH}/" 2>/dev/null || true
ok "Docker Compose files backed up"

# --- Caddyfile ---
info "Backing up Caddyfile..."
cp docker/Caddyfile "${BACKUP_PATH}/Caddyfile" 2>/dev/null || true
ok "Caddyfile backed up"

# --- Dockerfiles ---
info "Backing up Dockerfiles..."
cp backend/Dockerfile "${BACKUP_PATH}/backend-Dockerfile" 2>/dev/null || true
cp frontend/Dockerfile "${BACKUP_PATH}/frontend-Dockerfile" 2>/dev/null || true
ok "Dockerfiles backed up"

# --- Config directory ---
info "Backing up config directory..."
if [[ -d config ]] && [[ "$(ls -A config 2>/dev/null)" ]]; then
    cp -r config "${BACKUP_PATH}/config"
    ok "Config directory backed up"
else
    warn "Config directory is empty. Skipping."
fi

# --- Create archive ---
info "Creating archive..."
ARCHIVE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
tar -czf "$ARCHIVE" -C "$BACKUP_DIR" "$BACKUP_NAME"
rm -rf "$BACKUP_PATH"
ok "Archive created"

# --- Summary ---
BACKUP_SIZE=$(du -h "$ARCHIVE" | cut -f1)

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Backup Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  Location: ${CYAN}${ARCHIVE}${NC}"
echo -e "  Size:     ${CYAN}${BACKUP_SIZE}${NC}"
echo ""
echo -e "${GREEN}============================================================${NC}"
