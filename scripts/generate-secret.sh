#!/bin/bash
# =============================================================================
# NEXUS - Helper: generate random secrets
# Usage: bash scripts/generate-secret.sh
#        bash scripts/generate-secret.sh 64
# =============================================================================

set -euo pipefail

LENGTH="${1:-48}"

gen() {
    python3 -c "import secrets; print(secrets.token_urlsafe(${LENGTH}))" 2>/dev/null \
        || openssl rand -base64 ${LENGTH} | tr -d '\n'
}

SECRET=$(gen)

echo ""
echo "${SECRET}"
echo ""
echo "Add to .env:"
echo "  NEXUS_SECRET_KEY=${SECRET}"
echo ""