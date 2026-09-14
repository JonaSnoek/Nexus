#!/bin/bash
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

BACKUP_DIR=$(ls -d ./.update-backup-* 2>/dev/null | sort | tail -1)
if [[ -z "$BACKUP_DIR" ]]; then
    warn "Kein Backup gefunden. Rollback auf vorherigen Commit."
else
    info "Backup gefunden: $BACKUP_DIR"
    cp "$BACKUP_DIR/.env.bak" .env 2>/dev/null || true
    ok ".env aus Backup wiederhergestellt"
fi

info "Aktuellen Commit anzeigen..."
CURRENT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
PREV=$(git rev-parse --short HEAD~1 2>/dev/null || echo "unknown")
info "Jetzt: $CURRENT -> Vorher: $PREV"

if [[ "$CURRENT" == "$PREV" ]]; then
    info "Kein vorheriger Commit verfuegbar."
fi

info "Letzten Commit zuruecksetzen..."
if git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    git reset --hard HEAD~1
else
    info "Kein aelterer Commit vorhanden - bleibe auf aktuellem Stand."
fi

ROLLBACK_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

info "Images bauen..."
docker compose build --no-cache 2>&1 | tail -1

info "Container neu starten (Volumes bleiben erhalten)..."
docker compose up -d --force-recreate 2>/dev/null

info "Healthcheck..."
HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf "http://localhost/api/health" >/dev/null 2>&1; then HEALTHY=true; break; fi
    sleep 2
done

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -z "$SERVER_IP" ]] && SERVER_IP=$(ip -4 route get 8.8.8.8 2>/dev/null | awk '{print $7; exit}')
[[ -z "$SERVER_IP" ]] && SERVER_IP="localhost"

if [[ "$HEALTHY" == "true" ]]; then
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
fi