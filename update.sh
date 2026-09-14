#!/bin/bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
fatal() { error "$1"; exit 1; }

if [[ $EUID -ne 0 ]]; then fatal "Als Root: sudo ./update.sh"; fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- Snapshot ----------
PREV_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
info "Vorherige Version: $PREV_COMMIT"

# ---------- Config sichern ----------
BACKUP_DIR="$SCRIPT_DIR/.update-backup-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp .env "$BACKUP_DIR/.env.bak" 2>/dev/null || true
ok "Konfiguration gesichert nach: $BACKUP_DIR"

# ---------- Git Pull ----------
info "Git pull..."
git pull origin main 2>&1 | head -3
NEW_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

if [[ "$PREV_COMMIT" == "$NEW_COMMIT" ]]; then
    ok "Keine Aenderungen"
    echo -e "\n${GREEN}NEXUS ist aktuell (${NEW_COMMIT})${NC}"
    exit 0
fi

# ---------- Build ----------
info "Docker-Images bauen..."
docker compose build --no-cache 2>&1 | tail -1

# ---------- DB Migration ----------
info "Datenbankmigration..."
docker compose run --rm nexus-backend python -m alembic upgrade head 2>&1 || warn "Migration: nichts zu tun oder Fehler"

# ---------- Container neustarten ----------
info "Container neu starten..."
docker compose up -d --force-recreate 2>/dev/null

# ---------- Ollama Modell ----------
MODEL=$(grep "^NEXUS_LLM_MODEL=" .env | cut -d'=' -f2-)
MODEL=${MODEL:-qwen3:8b}
docker exec nexus-ollama ollama pull "$MODEL" >/dev/null 2>&1 || true

# ---------- Healthcheck ----------
info "Healthcheck..."
HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf "http://localhost/api/health" >/dev/null 2>&1; then HEALTHY=true; break; fi
    sleep 2
done

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -z "$SERVER_IP" ]] && SERVER_IP=$(ip -4 route get 8.8.8.8 2>/dev/null | awk '{print $7; exit}')
[[ -z "$SERVER_IP" ]] && SERVER_IP="localhost"

STATUS_FRONTEND="FAIL"; STATUS_BACKEND="FAIL"; STATUS_DB="FAIL"; STATUS_OLLAMA="FAIL"
curl -sf "http://localhost/" >/dev/null 2>&1 && STATUS_FRONTEND="OK"
curl -sf "http://localhost/api/health" >/dev/null 2>&1 && STATUS_BACKEND="OK"
docker exec nexus-postgres pg_isready -U nexus -d nexus >/dev/null 2>&1 && STATUS_DB="OK"
docker exec nexus-ollama ollama list >/dev/null 2>&1 && STATUS_OLLAMA="OK"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  NEXUS Update abgeschlossen${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  Vorher: ${YELLOW}${PREV_COMMIT}${NC}"
echo -e "  Jetzt:  ${CYAN}${NEW_COMMIT}${NC}"
echo ""
echo -e "  Frontend: ${STATUS_FRONTEND}"
echo -e "  Backend:  ${STATUS_BACKEND}"
echo -e "  Database: ${STATUS_DB}"
echo -e "  Ollama:   ${STATUS_OLLAMA}"
echo ""
echo -e "  NEXUS: ${CYAN}http://${SERVER_IP}${NC}"
echo -e "${GREEN}========================================${NC}"

if [[ "$STATUS_BACKEND" == "FAIL" ]]; then
    echo ""
    warn "Backend ist nicht erreichbar."
    echo "  Log: docker compose logs nexus-backend --tail 30"
    echo "  Rollback: sudo ./rollback.sh"
fi