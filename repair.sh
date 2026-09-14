#!/bin/bash
# =============================================================================
# NEXUS - Repair Script
# =============================================================================
# Usage: sudo bash repair.sh
#
# Diagnoses and repairs an existing NEXUS installation WITHOUT deleting data:
#  - checks disk space (prunes only the unused Docker build cache if low)
#  - never touches or removes Docker volumes
#  - identifies the PostgreSQL volume and makes sure existing data is used
#  - starts the stack and runs healthchecks
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
fatal() { error "$1"; exit 1; }

if [[ $EUID -ne 0 ]]; then fatal "Als Root ausfuehren: sudo bash repair.sh"; fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  NEXUS Repair${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

MIN_FREE_GB=3

# -----------------------------------------------------------------------------
# 1: Disk space
# -----------------------------------------------------------------------------
DISK_OK="FAIL"
FREE_KB=$(df -Pk / | awk 'NR==2 {print $4}')
FREE_GB=$((FREE_KB / 1024 / 1024))
info "Freier Speicher: ${FREE_GB}GB (Minimum fuer Operationen: ${MIN_FREE_GB}GB)"
if (( FREE_GB >= MIN_FREE_GB )); then
    DISK_OK="OK"
    ok "Genuegend Speicherplatz"
else
    warn "Wenig Speicher. Entferne ausschliesslich den ungenutzten Docker-Build-Cache..."
    if docker builder prune -af >/dev/null 2>&1; then
        FREE_KB=$(df -Pk / | awk 'NR==2 {print $4}')
        FREE_GB=$((FREE_KB / 1024 / 1024))
        ok "Build-Cache bereinigt - jetzt ${FREE_GB}GB frei"
        if (( FREE_GB >= MIN_FREE_GB )); then DISK_OK="OK"; fi
    else
        warn "Build-Cache-Bereinigung fehlgeschlagen"
    fi
fi

# -----------------------------------------------------------------------------
# 2: Docker
# -----------------------------------------------------------------------------
DOCKER_OK="FAIL"
if docker info >/dev/null 2>&1; then
    DOCKER_OK="OK"; ok "Docker laeuft"
else
    warn "Docker laeuft nicht - starte Docker..."
    systemctl start docker 2>/dev/null || service docker start 2>/dev/null || true
    sleep 3
    if docker info >/dev/null 2>&1; then DOCKER_OK="OK"; ok "Docker gestartet"; fi
fi

# -----------------------------------------------------------------------------
# 3: Compose file
# -----------------------------------------------------------------------------
COMPOSE_OK="FAIL"
if [[ -f docker-compose.yml ]]; then
    if docker compose config >/dev/null 2>&1; then
        COMPOSE_OK="OK"; ok "docker-compose.yml gueltig"
    else
        warn "docker-compose.yml ungueltig"
    fi
else
    warn "docker-compose.yml fehlt"
fi

# -----------------------------------------------------------------------------
# 4: Container status
# -----------------------------------------------------------------------------
info "Container-Status:"
docker ps -a --filter "name=nexus-" --format "  {{.Names}}: {{.Status}}" 2>/dev/null || echo "  keine Container gefunden"

# -----------------------------------------------------------------------------
# 5 + 6: PostgreSQL + volume identification
# -----------------------------------------------------------------------------
PG_OK="FAIL"
if docker volume inspect nexus-postgres-data >/dev/null 2>&1; then
    PG_VOL=$(docker volume inspect nexus-postgres-data --format '{{.Name}} @ {{.Mountpoint}}')
    ok "PostgreSQL-Volume gefunden: ${PG_VOL} (Daten werden verwendet)"
else
    warn "PostgreSQL-Volume fehlt - wird beim Start neu angelegt (Datenbank wird dann initialisiert)."
fi

DB_CONTAINER=$(docker ps -a --filter "name=nexus-postgres" --format '{{.Names}}' | head -1)
if [[ -n "$DB_CONTAINER" ]]; then
    if docker inspect --format='{{.State.Health.Status}}' nexus-postgres 2>/dev/null | grep -q "healthy"; then
        PG_OK="OK"; ok "PostgreSQL ist gesund"
    else
        warn "PostgreSQL laeuft nicht / ist nicht gesund"
    fi
else
    warn "PostgreSQL-Container fehlt"
fi

# -----------------------------------------------------------------------------
# 7 + 8: Cleanup then start (rebuild only if containers are stale/unhealthy)
# -----------------------------------------------------------------------------
FRONTEND_IMG_HEALTHY=$(docker inspect --format='{{.State.Health.Status}}' nexus-frontend 2>/dev/null || echo "missing")
if [[ "$FRONTEND_IMG_HEALTHY" != "healthy" ]]; then
    info "Frontend ist nicht gesund (${FRONTEND_IMG_HEALTHY:-unbekannt}) - baue Images neu (mit Cache)..."
    docker compose build 2>&1 | tail -2 || true
fi

info "NEXUS starten..."
if ! docker compose up -d 2>&1 | tail -5; then
    warn "Compose-Start unvollstaendig - pruefe Logs: docker compose ps"
fi

info "PostgreSQL-Start abwarten (bis zu 90s)..."
PG_HEALTHY=false
for i in $(seq 1 45); do
    if docker inspect --format='{{.State.Health.Status}}' nexus-postgres 2>/dev/null | grep -q "healthy"; then
        PG_HEALTHY=true; break
    fi
    if docker inspect --format='{{.State.Status}}' nexus-postgres 2>/dev/null | grep -q "running"; then
        # healthcheck start_period kann laufen - pruefe ob Prozess noch crash-loopt
        true
    fi
    sleep 2
done
if $PG_HEALTHY; then
    PG_OK="OK"; ok "PostgreSQL ist gesund"
else
    warn "PostgreSQL nicht gesund. Root-Dateisystem evtl. voll. Diagnose:"
    echo "  df -h /"
    echo "  docker logs nexus-postgres --tail 30"
fi

# -----------------------------------------------------------------------------
# 9: Healthchecks
# -----------------------------------------------------------------------------
info "Healthchecks abwarten (Backend/Frontend bis zu 90s)..."
STATUS_FRONTEND="FAIL"; STATUS_BACKEND="FAIL"; STATUS_DB="FAIL"; STATUS_OLLAMA="FAIL"
HEALTHY=false
for i in $(seq 1 45); do
    curl -sf "http://localhost/api/health" >/dev/null 2>&1 && STATUS_BACKEND="OK"
    curl -sf "http://localhost/" >/dev/null 2>&1 && STATUS_FRONTEND="OK"
    if [[ "$STATUS_BACKEND" == "OK" ]] && [[ "$STATUS_FRONTEND" == "OK" ]]; then HEALTHY=true; break; fi
    sleep 2
done

if docker exec nexus-postgres pg_isready >/dev/null 2>&1 || docker exec nexus-postgres pg_isready -U nexus -d nexus >/dev/null 2>&1; then
    STATUS_DB="OK"
fi
docker exec nexus-ollama ollama list >/dev/null 2>&1 && STATUS_OLLAMA="OK"

# -----------------------------------------------------------------------------
# 10: Port 80 + Proxy container health
# -----------------------------------------------------------------------------
HTTP_OK="FAIL"
if curl -sf "http://localhost/" >/dev/null 2>&1; then
    HTTP_OK="OK"
else
    if command -v ss &>/dev/null; then
        if ss -tlnp 2>/dev/null | grep -q ":80 "; then HTTP_OK="OK"
        else
            warn "Port 80 ist nicht belegt - Caddy laeuft nicht."
            echo "  Pruefe: docker compose logs nexus-caddy --tail 30"
        fi
    fi
fi
STATUS_CADDY=$(docker inspect --format='{{.State.Health.Status}}' nexus-caddy 2>/dev/null || echo "missing")

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -z "$SERVER_IP" ]] && SERVER_IP=$(ip -4 route get 8.8.8.8 2>/dev/null | awk '{print $7; exit}')
[[ -z "$SERVER_IP" ]] && SERVER_IP="localhost"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  NEXUS Repair - Zusammenfassung${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "  Disk:        ${DISK_OK}"
echo -e "  Docker:      ${DOCKER_OK}"
echo -e "  Compose:     ${COMPOSE_OK}"
echo -e "  PostgreSQL:  ${STATUS_DB}"
echo -e "  Ollama:      ${STATUS_OLLAMA}"
echo -e "  Backend:     ${STATUS_BACKEND}"
echo -e "  Frontend:    ${STATUS_FRONTEND}"
echo -e "  HTTP (Port 80): ${HTTP_OK}"
echo ""
echo -e "  NEXUS:       http://${SERVER_IP}"
echo -e "${CYAN}========================================${NC}"

if [[ "$STATUS_BACKEND" != "OK" ]] || [[ "$STATUS_DB" != "OK" ]]; then
    echo ""
    warn "Noch Probleme vorhanden. Taetigkeiten:"
    echo "  df -h /                               # Speicher pruefen"
    echo "  docker system df                      # Docker-Speicher"
    echo "  docker image prune -af                # unbenutzte Images (keine Volumes)"
    echo "  docker logs nexus-postgres --tail 30"
    echo "  docker logs nexus-backend --tail 30"
    exit 1
fi

if [[ "$STATUS_FRONTEND" != "OK" ]] || [[ "$HTTP_OK" != "OK" ]] || [[ "$STATUS_CADDY" != "healthy" ]]; then
    echo ""
    warn "Frontend/Proxy-Problem. Taetigkeiten:"
    echo "  docker compose logs nexus-frontend --tail 30"
    echo "  docker compose logs nexus-caddy --tail 30"
    echo "  docker exec nexus-frontend curl -fsS http://localhost/   # intern testen"
    exit 1
fi