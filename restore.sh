#!/bin/bash
# =============================================================================
# NEXUS - Restore Script
# =============================================================================
# Restores NEXUS from a backup archive.
# Usage: sudo bash restore.sh [backup_file.tar.gz]
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
    fatal "This script must be run as root. Use: sudo bash restore.sh"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BACKUP_DIR="${BACKUP_DIR:-./backups}"

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  NEXUS Restore${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# --- List available backups ---
BACKUP_FILE="${1:-}"
if [[ -z "$BACKUP_FILE" ]]; then
    info "Available backups:"
    echo ""
    if [[ -d "$BACKUP_DIR" ]]; then
        ls -lh "${BACKUP_DIR}"/*.tar.gz 2>/dev/null || {
            warn "No backup archives found in ${BACKUP_DIR}"
            exit 1
        }
    else
        fatal "Backup directory ${BACKUP_DIR} does not exist."
    fi
    echo ""
    read -rp "Enter the backup archive path: " BACKUP_FILE
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    fatal "Backup file not found: $BACKUP_FILE"
fi

# --- Confirmation ---
echo ""
echo -e "${RED}WARNING: This will overwrite the current database and configuration!${NC}"
read -rp "Are you sure you want to restore from $(basename "$BACKUP_FILE")? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    info "Restore cancelled."
    exit 0
fi

# --- Extract archive ---
info "Extracting backup..."
RESTORE_DIR=$(mktemp -d)
tar -xzf "$BACKUP_FILE" -C "$RESTORE_DIR"
EXTRACTED_DIR=$(ls "$RESTORE_DIR")
RESTORE_PATH="${RESTORE_DIR}/${EXTRACTED_DIR}"
ok "Backup extracted"

# --- Stop containers ---
info "Stopping containers..."
docker compose stop 2>/dev/null || docker-compose stop 2>/dev/null
ok "Containers stopped"

# --- Restore database ---
if [[ -f "${RESTORE_PATH}/database.sql.gz" ]]; then
    info "Restoring database..."
    docker compose up -d postgres 2>/dev/null || docker-compose up -d postgres 2>/dev/null
    sleep 5

    # Wait for postgres
    RETRIES=30
    until docker inspect --format='{{.State.Health.Status}}' nexus-postgres 2>/dev/null | grep -q "healthy"; do
        RETRIES=$((RETRIES - 1))
        if [[ $RETRIES -le 0 ]]; then
            fatal "PostgreSQL failed to start for restore"
        fi
        echo -n "."
        sleep 2
    done
    echo ""

    # Load current env for postgres credentials
    if [[ -f .env ]]; then
        set -a
        source .env
        set +a
    fi

    # Drop and recreate database
    docker exec nexus-postgres psql -U "${POSTGRES_USER:-nexus}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-nexus};"
    docker exec nexus-postgres psql -U "${POSTGRES_USER:-nexus}" -d postgres -c "CREATE DATABASE ${POSTGRES_DB:-nexus};"

    # Restore dump
    gunzip -c "${RESTORE_PATH}/database.sql.gz" | docker exec -i nexus-postgres psql -U "${POSTGRES_USER:-nexus}" -d "${POSTGRES_DB:-nexus}" &>/dev/null
    ok "Database restored"
else
    warn "No database dump found in backup. Skipping."
fi

# --- Restore .env ---
if [[ -f "${RESTORE_PATH}/.env" ]]; then
    info "Restoring .env file..."
    cp "${RESTORE_PATH}/.env" .env
    ok ".env restored"
else
    warn "No .env found in backup. Keeping current .env."
fi

# --- Restore config ---
if [[ -d "${RESTORE_PATH}/config" ]]; then
    info "Restoring config directory..."
    rm -rf config
    cp -r "${RESTORE_PATH}/config" config
    ok "Config restored"
else
    warn "No config directory found in backup. Keeping current config."
fi

# --- Cleanup ---
rm -rf "$RESTORE_DIR"

# --- Start services ---
info "Starting all services..."
docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null
ok "Services started"

# --- Health check ---
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
    echo -e "${GREEN}  Restore Complete!${NC}"
    echo -e "${GREEN}============================================================${NC}"
else
    echo -e "${YELLOW}============================================================${NC}"
    echo -e "${YELLOW}  Restore Complete (health check pending)${NC}"
    echo -e "${YELLOW}============================================================${NC}"
fi
echo ""
echo -e "  URL:    ${CYAN}http://localhost${NC}"
echo -e "  Logs:   ${CYAN}docker compose logs -f${NC}"
echo ""
