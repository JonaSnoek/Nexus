#!/bin/bash
# =============================================================================
# NEXUS - Health Check Script
# =============================================================================
# Checks the status of all NEXUS services.
# Usage: bash healthcheck.sh
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
fail()    { echo -e "${RED}[FAIL]${NC}  $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  NEXUS Health Check${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

CHECKS_PASSED=0
CHECKS_FAILED=0

check_container() {
    local name="$1"
    local status
    status=$(docker inspect --format='{{.State.Status}}' "$name" 2>/dev/null || echo "not_found")
    if [[ "$status" == "running" ]]; then
        local health
        health=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "none")
        if [[ "$health" == "healthy" ]] || [[ "$health" == "none" ]]; then
            ok "$name: running ($health)"
            CHECKS_PASSED=$((CHECKS_PASSED + 1))
        else
            warn "$name: running but $health"
            CHECKS_PASSED=$((CHECKS_PASSED + 1))
        fi
    elif [[ "$status" == "not_found" ]]; then
        fail "$name: not found"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
    else
        fail "$name: $status"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
    fi
}

# --- Docker containers ---
info "Checking Docker containers..."
echo ""
check_container "nexus-frontend"
check_container "nexus-backend"
check_container "nexus-postgres"
check_container "nexus-ollama"
check_container "nexus-caddy"

# --- API health endpoint ---
echo ""
info "Checking API health endpoint..."
if curl -sf http://localhost/api/health &>/dev/null; then
    ok "API health endpoint: responding"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    # Try backend directly
    if curl -sf http://localhost:8000/api/health &>/dev/null; then
        ok "Backend health endpoint: responding (direct)"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        fail "API health endpoint: not responding"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
    fi
fi

# --- Database connectivity ---
echo ""
info "Checking database connectivity..."
if docker exec nexus-postgres pg_isready -U nexus -d nexus &>/dev/null; then
    ok "PostgreSQL: accepting connections"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    fail "PostgreSQL: not accepting connections"
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
fi

# --- Ollama status ---
echo ""
info "Checking Ollama status..."
if curl -sf http://localhost:11434/api/tags &>/dev/null; then
    ok "Ollama: API responding"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
    echo ""
    info "Available models:"
    docker exec nexus-ollama ollama list 2>/dev/null || echo "  (unable to list models)"
elif docker exec nexus-ollama ollama list &>/dev/null; then
    ok "Ollama: responding (internal)"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    fail "Ollama: not responding"
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
fi

# --- Summary ---
echo ""
echo -e "${CYAN}============================================================${NC}"
TOTAL=$((CHECKS_PASSED + CHECKS_FAILED))
if [[ $CHECKS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}  All checks passed! (${CHECKS_PASSED}/${TOTAL})${NC}"
else
    echo -e "${YELLOW}  Checks: ${CHECKS_PASSED} passed, ${CHECKS_FAILED} failed (${TOTAL} total)${NC}"
fi
echo -e "${CYAN}============================================================${NC}"
echo ""

exit $CHECKS_FAILED
