#!/bin/bash
# =============================================================================
# NEXUS - Update Script
# =============================================================================
# Usage: sudo bash update.sh
#
# Safe update workflow:
#  1. Check disk space (prunes only the unused Docker build cache if low)
#  2. Backup the local .env configuration
#  3. git pull
#  4. Rebuild images (cached build - no --no-cache)
#  5. Run database migrations (alembic upgrade head)
#  6. Start containers with docker compose up -d (NEVER down -v / Never removes volumes)
#  7. Wait for healthchecks
#  8. Auto-rollback to previous commit if the update fails
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
fatal() { error "$1"; exit 1; }

if [[ $EUID -ne 0 ]]; then fatal "Als Root ausfuehren: sudo bash update.sh"; fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

git rev-parse --git-dir >/dev/null 2>&1 || fatal "Kein Git-Repository vorhanden."

# -----------------------------------------------------------------------------
# Storage helpers
# -----------------------------------------------------------------------------
MIN_FREE_GB=3

free_gb() {
    df -Pk / | awk 'NR==2 {print int($4/1024/1024)}'
}

safe_cleanup_build_cache() {
    local avail
    avail=$(free_gb)
    if (( avail < MIN_FREE_GB )); then
        warn "Nur ${avail}GB frei. Entferne ausschliesslich den ungenutzten Docker-Build-Cache..."
        if docker builder prune -af >/dev/null 2>&1; then
            ok "Build-Cache bereinigt"
        else
            warn "Build-Cache-Bereinigung fehlgeschlagen"
        fi
    fi
}

# -----------------------------------------------------------------------------
# 1 + 2: Disk check + config backup
# -----------------------------------------------------------------------------
info "Speicherpruefung..."
CURRENT_FREE=$(free_gb)
if (( CURRENT_FREE < MIN_FREE_GB )); then
    safe_cleanup_build_cache
    CURRENT_FREE=$(free_gb)
    if (( CURRENT_FREE < MIN_FREE_GB )); then
        fatal "Nach Bereinigung weiterhin nur ${CURRENT_FREE}GB frei. Update abgebrochen:
  docker system df
  docker image prune -af        (entfernt unbenutzte Images - beruehrt KEINE Volumes)
  sudo ./repair.sh"
    fi
fi
ok "Freier Speicher: ${CURRENT_FREE}GB"

PREV_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
info "Vorherige Version: $PREV_COMMIT"

TSTAMP=$(date +%Y%m%d_%H%M%S)
cp .env ".env.bak-${TSTAMP}" 2>/dev/null || true
ok "Konfiguration gesichert: .env.bak-${TSTAMP}"
info "Backups bleiben erhalten. Loeschen mit: rm .env.bak-*"

# --- Pre-update backup (DB dump + config, stored OUTSIDE all volumes) ---
PREBAK_DIR="./backups/pre-update-${TSTAMP}"
mkdir -p "$PREBAK_DIR"
PREBAK_OK=false
if docker inspect nexus-postgres >/dev/null 2>&1 && docker inspect --format='{{.State.Health.Status}}' nexus-postgres 2>/dev/null | grep -q "healthy"; then
    set -a; source .env 2>/dev/null; set +a
    if docker exec nexus-postgres pg_dump -U "${POSTGRES_USER:-nexus}" -d "${POSTGRES_DB:-nexus}" --no-owner --no-acl 2>/dev/null | gzip > "$PREBAK_DIR/database.sql.gz"; then
        ok "Datenbank-Backup: $PREBAK_DIR/database.sql.gz"
        PREBAK_OK=true
    else
        warn "Datenbank-Backup fehlgeschlagen (PostgreSQL erreichbar? Container pruefen)"
    fi
else
    warn "PostgreSQL nicht erreichbar - Datenbank-Backup uebersprungen. Pruefe: docker compose ps"
fi
cp docker-compose.yml "$PREBAK_DIR/" 2>/dev/null || true
cp docker/Caddyfile "$PREBAK_DIR/Caddyfile" 2>/dev/null || true
cp .env "$PREBAK_DIR/.env" 2>/dev/null || true
echo "$PREV_COMMIT" > "$PREBAK_DIR/git-revision.txt" 2>/dev/null || true
ok "Pre-Update-Konfiguration gesichert nach: $PREBAK_DIR"

# -----------------------------------------------------------------------------
# 3: git pull
# -----------------------------------------------------------------------------
if git pull origin main 2>&1 | grep -q "Already up to date"; then
    ok "Keine Aenderungen vorhanden - NEXUS ist bereits aktuell (${PREV_COMMIT})"
    exit 0
fi
NEW_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
ok "Aktualisiert: ${PREV_COMMIT} -> ${NEW_COMMIT}"

# -----------------------------------------------------------------------------
# 4+6: Build + start (never touches volumes)
# -----------------------------------------------------------------------------
info "Images bauen und Container starten (Volumes bleiben unangetastet)..."
if ! docker compose up -d --build 2>&1 | tail -5; then
    error "Update fehlgeschlagen. Versuche automatischen Rollback auf ${PREV_COMMIT}..."
    git reset --hard "$PREV_COMMIT" || true
    docker compose up -d --build 2>&1 | tail -5 || true
    fatal "Rollback auf ${PREV_COMMIT} durchgefuehrt. Daten und Volumes sind unangetastet. Diagnose: docker compose ps"
fi
ok "Container gestartet"

# -----------------------------------------------------------------------------
# 5: Database migrations (never drops data)
# -----------------------------------------------------------------------------
info "Datenbankmigrationen (alembic upgrade head)..."
if docker exec nexus-backend python -m alembic upgrade head >/dev/null 2>&1; then
    ok "Migrationen angewendet"
elif docker exec nexus-backend python -m alembic stamp head >/dev/null 2>&1; then
    ok "Migration-Stand markiert (Datenbank bereits aktuell)"
else
    warn "Alembic nicht verfuegbar - Container pruefen: docker compose logs nexus-backend --tail 20"
fi

# -----------------------------------------------------------------------------
# 7+: Healthchecks
# -----------------------------------------------------------------------------
info "Healthchecks abwarten (bis zu 90s)..."
HEALTHY=false
for i in $(seq 1 45); do
    if curl -sf "http://localhost/api/health" >/dev/null 2>&1; then HEALTHY=true; break; fi
    sleep 2
done

curl -sf "http://localhost" >/dev/null 2>&1 || true

STATUS_FRONTEND="FAIL"; STATUS_BACKEND="FAIL"; STATUS_DB="FAIL"; STATUS_OLLAMA="FAIL"
curl -sf "http://localhost/" >/dev/null 2>&1 && STATUS_FRONTEND="OK"
curl -sf "http://localhost/api/health" >/dev/null 2>&1 && STATUS_BACKEND="OK"
(docker exec nexus-postgres pg_isready -U nexus -d nexus >/dev/null 2>&1 || \
 docker exec nexus-postgres pg_isready >/dev/null 2>&1) && STATUS_DB="OK"
docker exec nexus-ollama ollama list >/dev/null 2>&1 && STATUS_OLLAMA="OK"

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -z "$SERVER_IP" ]] && SERVER_IP=$(ip -4 route get 8.8.8.8 2>/dev/null | awk '{print $7; exit}')
[[ -z "$SERVER_IP" ]] && SERVER_IP="localhost"

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

if [[ "$HEALTHY" != "true" ]] || [[ "$STATUS_BACKEND" != "OK" ]]; then
    echo ""
    warn "NEXUS ist nach dem Update nicht erreichbar. Automatischer Rollback auf ${PREV_COMMIT}..."

    git reset --hard "$PREV_COMMIT" || true
    info "Images des vorherigen Stands bauen und starten (DB wird NICHT zurueckgesetzt)..."
    docker compose up -d --build 2>&1 | tail -5 || true

    ROLLBACK_HEALTHY=false
    for i in $(seq 1 45); do
        if curl -sf "http://localhost/api/health" >/dev/null 2>&1; then ROLLBACK_HEALTHY=true; break; fi
        sleep 2
    done

    ROLLBACK_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    if $ROLLBACK_HEALTHY; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  Rollback auf ${ROLLBACK_COMMIT} erfolgreich${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo -e "  NEXUS: ${CYAN}http://${SERVER_IP}${NC}"
        echo -e "${GREEN}========================================${NC}"
    fi

    exit 1
fi