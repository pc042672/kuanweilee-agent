#!/bin/bash
# Quick redeploy script — app-only deploy to Cloud Run (infra already exists)
#
# Usage:
#   ./deploy/redeploy.sh
#
# Convenience wrapper around the legacy AlloyDB deploy with saved parameters.
# The current production stack still runs on AlloyDB; once it moves to
# PostgreSQL/Cloud SQL, switch this to deploy/gcp/deploy.sh --skip-migrations.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load GEMINI_API_KEY from .env if not already set (handles `export KEY=` and quotes)
if [[ -z "${GEMINI_API_KEY:-}" && -f "${SCRIPT_DIR}/../.env" ]]; then
  GEMINI_API_KEY="$(grep -E '^(export )?GEMINI_API_KEY=' "${SCRIPT_DIR}/../.env" | head -1 | cut -d= -f2- | tr -d '"'"'")"
fi

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "ERROR: GEMINI_API_KEY not set (export it or add to .env)" >&2
  exit 1
fi

# Secret travels via environment, not argv (avoids ps/cmdline exposure)
export GEMINI_API_KEY
exec "${SCRIPT_DIR}/legacy/deploy-alloydb.sh" \
  --project gen-lang-client-0415822016 \
  --region us-central1 \
  --skip-infra
