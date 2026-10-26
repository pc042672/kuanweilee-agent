#!/bin/bash
# AI-CDP GCP Deployment Script (database-agnostic: PostgreSQL 12+)
#
# Deploys the app to Cloud Run against an EXISTING PostgreSQL 12+ database
# (Cloud SQL, self-hosted, or any reachable instance). Database provisioning
# is intentionally out of scope — point --database-url at your instance.
#
#   1. Enable APIs
#   2. Init database + run migrations (via --database-url)
#   3. Build + deploy Cloud Run backend
#
# TODO(cloud-sql): add optional Cloud SQL provisioning, e.g.:
#   gcloud sql instances create aicdp --database-version=POSTGRES_12 \
#       --region=$REGION --tier=db-custom-2-8192
#   gcloud sql databases create aicdp --instance=aicdp
# Then deploy with --cloudsql-instance PROJECT:REGION:INSTANCE: migrations use
# --database-url as given (public IP), Cloud Run gets the same URL rewritten
# to the /cloudsql unix socket.
#
# Legacy AlloyDB stack (cluster + VPC peering + Auth Proxy):
#   deploy/legacy/deploy-alloydb.sh / teardown-alloydb.sh
#
# Usage:
#   ./deploy/gcp/deploy.sh --project PROJECT_ID --database-url "postgresql+psycopg2://user:pass@host:5432/aicdp" --admin-email EMAIL
#
# Prerequisites:
#   - gcloud CLI authenticated (gcloud auth login)
#   - Docker installed (for Cloud Run build)
#   - PostgreSQL 12+ reachable from this machine (for migrations) and from
#     Cloud Run (private IP + VPC connector, public IP, or Cloud SQL connector)

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────
REGION="us-central1"
SERVICE_NAME="ai-cdp-backend"
ADMIN_EMAIL=""
ADMIN_NAME="Admin"
SITE_NAME="Default Site"
SKIP_DEPLOY=false
SKIP_MIGRATIONS=false
DATABASE_URL="${DATABASE_URL:-}"
GEMINI_API_KEY="${GEMINI_API_KEY:-}"
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}"
GP_PASSWORD="${GP_PASSWORD:-}"
JWT_SECRET="${JWT_SECRET:-}"
ENABLE_MODEL_GUARD=false
APP_ENV="prod"
VPC_CONNECTOR=""
CLOUDSQL_INSTANCE=""
MIN_INSTANCES=1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
info() { echo -e "${CYAN}[→]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Parse Args ────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --project)       PROJECT_ID="$2"; shift 2 ;;
        --region)        REGION="$2"; shift 2 ;;
        --database-url)  DATABASE_URL="$2"; shift 2 ;;
        --admin-email)   ADMIN_EMAIL="$2"; shift 2 ;;
        --admin-name)    ADMIN_NAME="$2"; shift 2 ;;
        --site-name)     SITE_NAME="$2"; shift 2 ;;
        --vpc-connector) VPC_CONNECTOR="$2"; shift 2 ;;
        --cloudsql-instance) CLOUDSQL_INSTANCE="$2"; shift 2 ;;
        --min-instances) MIN_INSTANCES="$2"; shift 2 ;;
        --skip-deploy)   SKIP_DEPLOY=true; shift ;;
        --skip-migrations) SKIP_MIGRATIONS=true; shift ;;
        --skip-infra)    shift ;;  # back-compat no-op (infra is no longer provisioned here)
        --gemini-key)    GEMINI_API_KEY="$2"; shift 2 ;;
        --google-client-id) GOOGLE_CLIENT_ID="$2"; shift 2 ;;
        --jwt-secret)    JWT_SECRET="$2"; shift 2 ;;
        --enable-model-guard) ENABLE_MODEL_GUARD=true; shift ;;
        --env)           APP_ENV="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 --project PROJECT_ID --database-url URL [options]"
            echo ""
            echo "Options:"
            echo "  --project        GCP project ID (required)"
            echo "  --region         GCP region (default: us-central1)"
            echo "  --database-url   PostgreSQL URL, postgresql+psycopg2://user:pass@host:5432/db"
            echo "                   (or set DATABASE_URL env var; required)"
            echo "  --admin-email    Admin user email (required on first deploy)"
            echo "  --admin-name     Admin display name (default: Admin)"
            echo "  --site-name      Default site name (default: Default Site)"
            echo "  --vpc-connector  Serverless VPC connector name (if DB is on private IP)"
            echo "  --cloudsql-instance  Cloud SQL connection name PROJECT:REGION:INSTANCE (mounts /cloudsql socket)"
            echo "  --min-instances  Cloud Run min instances (default: 1; 0 = scale to zero)"
            echo "  --gemini-key     Gemini API key (or set GEMINI_API_KEY env var)"
            echo "  --google-client-id  Google OAuth client ID (or env var)"
            echo "  --jwt-secret     JWT signing secret (auto-generated if not set)"
            echo "  --enable-model-guard  Enable PII model guard plugin"
            echo "  --env            Environment: dev, staging, prod (default: prod)"
            echo "  --skip-migrations  Skip DB init/migrations (just deploy app)"
            echo "  --skip-deploy    Skip Cloud Run deploy (just run migrations)"
            echo ""
            echo "Env GP_HOST/GP_PORT/GP_USER/GP_PASSWORD/GP_DBNAME/GP_READONLY_USER, if set,"
            echo "are forwarded as the Greenplum fallback (GP_PASSWORD via Secret Manager)."
            exit 0
            ;;
        *) err "Unknown option: $1" ;;
    esac
done

[[ -z "${PROJECT_ID:-}" ]] && err "--project is required"
[[ -z "${DATABASE_URL}" ]] && err "--database-url is required (or set DATABASE_URL env var)"

# ── Set GCP Project ───────────────────────────────────────────────────
info "Setting project to ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" --quiet

info "Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    aiplatform.googleapis.com \
    cloudtrace.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com \
    ${CLOUDSQL_INSTANCE:+sqladmin.googleapis.com sql-component.googleapis.com} \
    --quiet

# ══════════════════════════════════════════════════════════════════════
# PHASE 1: Database Init + Migrations
# ══════════════════════════════════════════════════════════════════════

if [[ "${SKIP_MIGRATIONS}" == "false" ]]; then
    INIT_ARGS=(--database-url "${DATABASE_URL}")
    if [[ -n "${ADMIN_EMAIL}" ]]; then
        INIT_ARGS+=(--admin-email "${ADMIN_EMAIL}" --admin-name "${ADMIN_NAME}" --site-name "${SITE_NAME}")
    fi

    info "Running database migrations..."
    cd "${PROJECT_ROOT}"
    python3 deploy/init_db.py "${INIT_ARGS[@]}"
    log "Database ready"
fi

# ══════════════════════════════════════════════════════════════════════
# PHASE 2: Cloud Run Deployment
# ══════════════════════════════════════════════════════════════════════

if [[ "${SKIP_DEPLOY}" == "false" ]]; then

    # Store secrets in Secret Manager
    _store_secret() {
        local name="$1" value="$2"
        if [[ -n "${value}" ]]; then
            echo -n "${value}" | gcloud secrets create "${name}" --data-file=- --quiet 2>/dev/null \
                || echo -n "${value}" | gcloud secrets versions add "${name}" --data-file=- --quiet 2>/dev/null
            log "Secret '${name}' stored"
        fi
    }

    # Auto-generate JWT_SECRET if not provided
    if [[ -z "${JWT_SECRET}" ]]; then
        JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        log "Auto-generated JWT_SECRET"
    fi

    _store_secret "gemini-api-key" "${GEMINI_API_KEY}"
    _store_secret "jwt-secret" "${JWT_SECRET}"
    _store_secret "google-client-id" "${GOOGLE_CLIENT_ID}"
    # DB URL (incl. password) lives in Secret Manager, not a plain env var —
    # run.viewer must not be able to read credentials from the service spec.
    RUN_DATABASE_URL="${DATABASE_URL}"
    if [[ -n "${CLOUDSQL_INSTANCE}" ]]; then
        # user:pass@host:port/db?... -> user:pass@/db?host=/cloudsql/INSTANCE
        _db="${DATABASE_URL##*@}"; _db="${_db#*/}"
        RUN_DATABASE_URL="${DATABASE_URL%@*}@/${_db%%\?*}?host=/cloudsql/${CLOUDSQL_INSTANCE}"
    fi
    _store_secret "aicdp-database-url" "${RUN_DATABASE_URL}"
    _store_secret "gp-password" "${GP_PASSWORD}"

    # Build env vars
    ENV_VARS="APP_ENV=${APP_ENV}"
    ENV_VARS="${ENV_VARS},GCP_PROJECT_ID=${PROJECT_ID}"
    ENV_VARS="${ENV_VARS},GCP_LOCATION=${REGION}"
    ENV_VARS="${ENV_VARS},LOG_LEVEL=INFO"
    ENV_VARS="${ENV_VARS},ENABLE_CLOUD_LOGGING=true"
    ENV_VARS="${ENV_VARS},ENABLE_CLOUD_TRACE=true"
    [[ -n "${GEMINI_API_KEY}" ]] && ENV_VARS="${ENV_VARS},GEMINI_API_KEY=${GEMINI_API_KEY}"
    [[ -n "${JWT_SECRET}" ]] && ENV_VARS="${ENV_VARS},JWT_SECRET=${JWT_SECRET}"
    [[ -n "${GOOGLE_CLIENT_ID}" ]] && ENV_VARS="${ENV_VARS},GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}"
    # Greenplum env fallback (used when the site has no data_sources row)
    for v in GP_HOST GP_PORT GP_USER GP_DBNAME GP_READONLY_USER; do
        if [[ -n "${!v:-}" ]]; then ENV_VARS="${ENV_VARS},${v}=${!v}"; fi
    done
    [[ "${ENABLE_MODEL_GUARD}" == "true" ]] && ENV_VARS="${ENV_VARS},ENABLE_MODEL_GUARD=true"

    SECRETS="DATABASE_URL=aicdp-database-url:latest"
    [[ -n "${GP_PASSWORD}" ]] && SECRETS="${SECRETS},GP_PASSWORD=gp-password:latest"

    DEPLOY_ARGS=(
        --source="${PROJECT_ROOT}"
        --region="${REGION}"
        --platform=managed
        --allow-unauthenticated
        --cpu=2 --memory=2Gi
        --min-instances="${MIN_INSTANCES}" --max-instances=10
        --timeout=600
        --concurrency=20
        --no-cpu-throttling
        --execution-environment=gen2
        --set-env-vars="${ENV_VARS}"
        --set-secrets="${SECRETS}"
        --quiet
    )
    [[ -n "${CLOUDSQL_INSTANCE}" ]] && DEPLOY_ARGS+=(--add-cloudsql-instances="${CLOUDSQL_INSTANCE}")
    if [[ -n "${VPC_CONNECTOR}" ]]; then
        DEPLOY_ARGS+=(--vpc-connector="${VPC_CONNECTOR}" --vpc-egress=private-ranges-only)
    fi

    info "Building and deploying to Cloud Run..."
    gcloud run deploy "${SERVICE_NAME}" "${DEPLOY_ARGS[@]}"

    SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
        --region="${REGION}" --format="value(status.url)")
    log "Cloud Run deployed: ${SERVICE_URL}"

    # Set CORS_ORIGINS to the service URL
    info "Setting CORS_ORIGINS to ${SERVICE_URL}..."
    gcloud run services update "${SERVICE_NAME}" \
        --region="${REGION}" \
        --update-env-vars="CORS_ORIGINS=${SERVICE_URL}" \
        --quiet
    log "CORS_ORIGINS set"

    # ── Post-Deploy Verification ─────────────────────────────────────
    info "Running deployment verification..."
    VERIFY_PASS=true

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/health" 2>/dev/null)
    if [[ "${HTTP_CODE}" == "200" ]]; then
        log "Health check: OK"
    else
        warn "Health check: FAILED (HTTP ${HTTP_CODE})"
        VERIFY_PASS=false
    fi

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/api/ontology" 2>/dev/null)
    if [[ "${HTTP_CODE}" == "401" ]]; then
        log "Auth enforcement: OK (401 without JWT)"
    elif [[ "${HTTP_CODE}" == "200" ]]; then
        warn "Auth enforcement: FAILED — API accessible without auth! Check DEV_USER_EMAIL is not set."
        VERIFY_PASS=false
    else
        warn "Auth enforcement: unexpected HTTP ${HTTP_CODE}"
    fi

    CONTENT_TYPE=$(curl -s -o /dev/null -w "%{content_type}" "${SERVICE_URL}/" 2>/dev/null)
    if [[ "${CONTENT_TYPE}" == *"text/html"* ]]; then
        log "Frontend SPA: OK"
    else
        warn "Frontend SPA: not serving HTML (got ${CONTENT_TYPE})"
    fi

    if [[ "${VERIFY_PASS}" == "true" ]]; then
        log "All verification checks passed"
    else
        warn "Some verification checks failed — review above"
    fi

fi

# ══════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════

echo ""
echo -e "${GREEN}═══ Deployment Complete ═══${NC}"
echo ""
echo "  Project:    ${PROJECT_ID}"
echo "  Region:     ${REGION}"
echo "  Database:   ${DATABASE_URL%%@*}@…  (PostgreSQL 12+)"
if [[ "${SKIP_DEPLOY}" == "false" ]]; then
    echo "  Cloud Run:  ${SERVICE_URL:-not deployed}"
fi
if [[ -n "${ADMIN_EMAIL}" ]]; then
    echo "  Admin:      ${ADMIN_EMAIL} (owner)"
fi
echo ""
echo "Next steps:"
if [[ -z "${GOOGLE_CLIENT_ID}" ]]; then
    echo "  1. Set GOOGLE_CLIENT_ID for OAuth:  gcloud run services update ${SERVICE_NAME} --region=${REGION} --update-env-vars GOOGLE_CLIENT_ID=..."
fi
echo "  • Custom domain:       gcloud run domain-mappings create --service ${SERVICE_NAME} --domain your.domain"
echo "  • Redeploy (app only): ./deploy/gcp/deploy.sh --project ${PROJECT_ID} --database-url ... --skip-migrations"
echo "  • Schema upgrade:      ./deploy/gcp/deploy.sh --project ${PROJECT_ID} --database-url ... --skip-deploy"
echo ""
