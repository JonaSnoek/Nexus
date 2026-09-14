#!/bin/bash
# =============================================================================
# NEXUS - Rollback Script
# =============================================================================
# Usage: sudo bash rollback.sh
#
# Rolls back to the previous Git commit. Restores .env from the latest
# update-backup if one exists. NEVER deletes the database or any volume.
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
fatal() { error "$1"; exit 1; }

if [[ $EUID -ne 0 ]]; then fatal "Als Root: sudo ./rollback.sh"; fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

git rev-parse --git-dir >/dev/null 2>&1 || fatal "Kein Git-Repository vorhanden."

# --- Restore latest .env backup from update.sh ---
ENV_BAK=$(ls ./.env.bak-* 2>/dev/null | sort | tail -1)
if [[ -n "$ENV_BAK" ]]; then
    info "Konfiguration aus Backup wiederhergestellt: $ENV_BAK"
    cp "$ENV_BAK" .env
    ok ".env wiederhergestellt"
else
    warn "Kein .env-Backup gefunden. .env bleibt unveraendert."
fi

# --- Stop current stack (containers only, volumes untouched) ---
info "Container stoppen (Volumes bleiben erhalten)..."
docker compose stop 2>/dev/null || true

# --- Rollback ---
CURRENT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
info "Aktueller Commit: $CURRENT"

if git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    PREV=$(git rev-parse --short HEAD~1)
    info "Setze zurueck auf: $PREV"
    git reset --hard HEAD~1
else
    PREV="$CURRENT"
    warn "Kein aelterer Commit vorhanden - bleibe auf aktuellem Stand."
fi

ROLLBACK_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

info "Images bauen und Container starten (keine Volumes beruehrt)..."
docker compose up -d --build 2>&1 | tail -5
ok "Container neu gestartet"

info "Healthcheck..."
HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf "http://localhost/api/health" >/dev/null 2>&1; then HEALTHY=true; break; fi
    sleep 2
done

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -z "$SERVER_IP" ]] && SERVER_IP=$(ip -4 route get 8.8.8.8 2>/dev/null | awk '{print $7; exit}')
[[ -z "$SERVER_IP" ]] && SERVER_IP="localhost"

if $HEALTHY; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Rollback erfolgreich${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "  Version: ${CYAN}${ROLLBACK_COMMIT}${NC}"
    echo -e "  NEXUS:   ${CYAN}http://${SERVER_IP}${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    warn "Backend nach Rollback nicht erreichbar."
    docker compose ps 2>/dev/null
    echo ""
    warn "Diagnose:"
    echo "  docker compose logs nexus-postgres --tail 30"
    echo "  docker compose logs nexus-backend --tail 30"
    echo "  df -h /"
    exit 1
fi