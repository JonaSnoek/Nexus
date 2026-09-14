#!/bin/bash
# =============================================================================
# NEXUS - Uninstall Script
# =============================================================================
# Removes NEXUS containers and optionally data.
# Usage: sudo bash uninstall.sh
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

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR]${NC} This script must be run as root. Use: sudo bash uninstall.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${RED}============================================================${NC}"
echo -e "${RED}  NEXUS Uninstall${NC}"
echo -e "${RED}============================================================${NC}"
echo ""
echo -e "${RED}WARNING: This will stop and remove all NEXUS containers!${NC}"
echo ""
read -rp "Are you sure you want to uninstall NEXUS? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    echo -e "${GREEN}Uninstall cancelled.${NC}"
    exit 0
fi

echo ""
read -rp "Remove database volumes (THIS DELETES ALL DATA)? (yes/no): " REMOVE_VOLUMES
read -rp "Remove Docker images? (yes/no): " REMOVE_IMAGES

# --- Stop and remove containers ---
info "Stopping and removing containers..."
docker compose down 2>/dev/null || docker-compose down 2>/dev/null
ok "Containers removed"

# --- Remove volumes ---
if [[ "$REMOVE_VOLUMES" == "yes" ]]; then
    info "Removing volumes..."
    docker compose down -v 2>/dev/null || docker-compose down -v 2>/dev/null
    ok "Volumes removed"
else
    warn "Volumes preserved. Remove manually with: docker volume rm nexus-postgres-data nexus-ollama-data caddy-data caddy-config"
fi

# --- Remove images ---
if [[ "$REMOVE_IMAGES" == "yes" ]]; then
    info "Removing Docker images..."
    docker rmi nexus-frontend nexus-backend 2>/dev/null || true
    docker image prune -f 2>/dev/null || true
    ok "Images removed"
else
    warn "Images preserved. Remove manually with: docker image rm <image_name>"
fi

# --- Remove backup archives ---
echo ""
read -rp "Remove backup archives in ${BACKUP_DIR:-./backups}? (yes/no): " REMOVE_BACKUPS
if [[ "$REMOVE_BACKUPS" == "yes" ]]; then
    info "Removing backups..."
    rm -rf "${BACKUP_DIR:-./backups}"
    ok "Backups removed"
fi

# --- Summary ---
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  NEXUS Uninstalled${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
if [[ "$REMOVE_VOLUMES" != "yes" ]]; then
    echo -e "  ${YELLOW}Database volumes were preserved.${NC}"
    echo -e "  Remove with: docker volume rm nexus-postgres-data nexus-ollama-data"
fi
if [[ "$REMOVE_IMAGES" != "yes" ]]; then
    echo -e "  ${YELLOW}Docker images were preserved.${NC}"
fi
echo ""
echo -e "  To completely remove Docker data, also run:"
echo -e "  ${CYAN}docker system prune -a --volumes${NC}"
echo ""
echo -e "${GREEN}============================================================${NC}"
