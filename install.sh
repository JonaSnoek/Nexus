#!/bin/bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
fatal() { error "$1"; exit 1; }

if [[ $EUID -ne 0 ]]; then fatal "Als Root ausfuehren: sudo bash install.sh"; fi
[[ "$(uname)" == "Linux" ]] || fatal "Nur Linux unterstuetzt."
[[ "$(uname -m)" == "x86_64" ]] || fatal "Nur x86_64 unterstuetzt."

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -z "$SERVER_IP" ]] && SERVER_IP=$(ip -4 route get 8.8.8.8 2>/dev/null | awk '{print $7; exit}')
[[ -z "$SERVER_IP" ]] && SERVER_IP="localhost"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- Docker ----------
if ! command -v docker &>/dev/null; then
    info "Docker installieren..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker && systemctl start docker
    ok "Docker installiert"
else
    ok "Docker: $(docker --version)"
fi

if ! docker compose version &>/dev/null; then
    fatal "Docker Compose Plugin fehlt. Installiere es manuell."
fi
ok "Docker Compose: $(docker compose version --short)"

# ---------- RAM ----------
TOTAL_RAM_MB=$(($(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024))
[[ $TOTAL_RAM_MB -lt 4096 ]] && warn "Nur ${TOTAL_RAM_MB}MB RAM (empfohlen: 4GB+)"

# ---------- .env ----------
if [[ ! -f .env ]]; then
    cp .env.example .env
    ok ".env erstellt"
else
    ok ".env existiert bereits"
fi

gen_secret() { python3 -c "import secrets;print(secrets.token_urlsafe(48))" 2>/dev/null || openssl rand -base64 48 | tr -d '\n'; }

if grep -q "^NEXUS_SECRET_KEY=CHANGE_ME" .env; then
    sed -i "s|^NEXUS_SECRET_KEY=CHANGE_ME|NEXUS_SECRET_KEY=$(gen_secret)|" .env
    ok "SECRET_KEY generiert"
fi

if grep -q "^POSTGRES_PASSWORD=CHANGE_ME" .env; then
    NEW_PG=$(gen_secret)
    sed -i "s|^POSTGRES_PASSWORD=CHANGE_ME|POSTGRES_PASSWORD=${NEW_PG}|" .env
    sed -i "s|nexus:CHANGE_ME@|nexus:${NEW_PG}@|" .env
    ok "POSTGRES_PASSWORD generiert"
fi

ADMIN_PASS=$(grep "^FIRST_ADMIN_PASSWORD=" .env | cut -d'=' -f2-)
if [[ -z "$ADMIN_PASS" ]]; then
    warn "FIRST_ADMIN_PASSWORD ist leer."
    read -rp "Admin-Passwort eingeben (leer = ueberspringen): " ADMIN_PASS_INPUT
    if [[ -n "$ADMIN_PASS_INPUT" ]]; then
        sed -i "s|^FIRST_ADMIN_PASSWORD=.*|FIRST_ADMIN_PASSWORD=${ADMIN_PASS_INPUT}|" .env
        ok "Admin-Passwort gesetzt"
    fi
fi

# ---------- Firewall ----------
if command -v ufw &>/dev/null; then
    if ufw status 2>/dev/null | grep -q "active"; then
        if ! ufw status 2>/dev/null | grep -q "80/tcp.*ALLOW"; then
            info "UFW: Port 80 freigeben..."
            ufw allow 80/tcp comment "NEXUS HTTP" >/dev/null 2>&1
            ok "Port 80 in UFW freigegeben"
        else
            ok "Port 80 ist bereits in UFW erlaubt"
        fi
    else
        ok "UFW nicht aktiv - kein Eingriff noetig"
    fi
elif command -v firewall-cmd &>/dev/null; then
    if firewall-cmd --state 2>/dev/null | grep -q "running"; then
        firewall-cmd --permanent --add-port=80/tcp >/dev/null 2>&1 && firewall-cmd --reload >/dev/null 2>&1
        ok "Firewalld: Port 80 freigegeben"
    fi
fi

# ---------- Build & Start ----------
info "Docker-Images bauen..."
docker compose build --no-cache 2>&1 | tail -1
ok "Images gebaut"

info "PostgreSQL starten..."
docker compose up -d postgres 2>/dev/null
RETRIES=30
until docker inspect --format='{{.State.Health.Status}}' nexus-postgres 2>/dev/null | grep -q "healthy"; do
    RETRIES=$((RETRIES - 1))
    [[ $RETRIES -le 0 ]] && fatal "PostgreSQL startet nicht"
    sleep 2
done
ok "PostgreSQL gesund"

info "Backend starten..."
docker compose up -d nexus-backend 2>/dev/null
sleep 3
ok "Backend gestartet"

info "Ollama starten..."
docker compose up -d ollama 2>/dev/null
sleep 2
MODEL=$(grep "^NEXUS_LLM_MODEL=" .env | cut -d'=' -f2-)
MODEL=${MODEL:-qwen3:8b}
info "Modell '$MODEL' wird geladen (kann dauern)..."
docker exec nexus-ollama ollama pull "$MODEL" >/dev/null 2>&1 || warn "Modell-Pull fehlgeschlagen"
ok "Ollama bereit"

info "Alle Services starten..."
docker compose up -d 2>/dev/null
ok "Alle Services gestartet"

# ---------- Healthcheck ----------
info "Healthcheck (bis zu 60s)..."
HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf "http://localhost/api/health" >/dev/null 2>&1; then HEALTHY=true; break; fi
    sleep 2
done

# ---------- Status ----------
STATUS_FRONTEND="FAIL"; STATUS_BACKEND="FAIL"; STATUS_DB="FAIL"; STATUS_OLLAMA="FAIL"; STATUS_PROXY="FAIL"
curl -sf "http://localhost/" >/dev/null 2>&1 && STATUS_FRONTEND="OK"
curl -sf "http://localhost/api/health" >/dev/null 2>&1 && STATUS_BACKEND="OK"
docker exec nexus-postgres pg_isready -U nexus -d nexus >/dev/null 2>&1 && STATUS_DB="OK"
docker exec nexus-ollama ollama list >/dev/null 2>&1 && STATUS_OLLAMA="OK"
docker inspect --format='{{.State.Status}}' nexus-caddy 2>/dev/null | grep -q "running" && STATUS_PROXY="OK"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  NEXUS Installation abgeschlossen${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  NEXUS:    ${CYAN}http://${SERVER_IP}${NC}"
echo -e "  API:      ${CYAN}http://${SERVER_IP}/api/health${NC}"
echo ""
echo -e "  Frontend: ${STATUS_FRONTEND}"
echo -e "  Backend:  ${STATUS_BACKEND}"
echo -e "  Database: ${STATUS_DB}"
echo -e "  Ollama:   ${STATUS_OLLAMA}"
echo -e "  Proxy:    ${STATUS_PROXY}"
echo ""
echo -e "  Login:    ${CYAN}admin${NC} / dein eingegebenes Passwort"
echo -e "  Update:   ${CYAN}sudo ./update.sh${NC}"
echo -e "  Rollback: ${CYAN}sudo ./rollback.sh${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"