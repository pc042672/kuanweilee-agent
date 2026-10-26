#!/bin/bash
# AI-CDP GCP Deployment Script
#
# Deploys the full stack to a GCP project:
#   1. Enable APIs
#   2. Create AlloyDB cluster + instance (if not exists)
#   3. Init database + run migrations
#   4. Build + deploy Cloud Run backend
#   5. Deploy frontend to Cloud Storage (optional)
#
# Usage:
#   ./deploy/legacy/deploy-alloydb.sh --project PROJECT_ID --region REGION --admin-email EMAIL
#   ./deploy/gcp/deploy.sh --project gen-lang-client-0415822016 --region us-central1 --admin-email admin@example.com
#
# Prerequisites:
#   - gcloud CLI authenticated (gcloud auth login)
#   - gcloud auth application-default login (for AlloyDB Auth Proxy)
#   - Docker installed (for Cloud Run build)

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────
REGION="us-central1"
CLUSTER_NAME="aicdp"
INSTANCE_NAME="aicdp-primary"
DB_NAME="aicdp"
DB_PASSWORD="AiCdp-Dev-2026!"
SERVICE_NAME="ai-cdp-backend"
CPU_COUNT=2
ADMIN_EMAIL=""
ADMIN_NAME="Admin"
SITE_NAME="Default Site"
SKIP_INFRA=false
SKIP_DEPLOY=false
GEMINI_API_KEY="${GEMINI_API_KEY:-}"
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}"
JWT_SECRET="${JWT_SECRET:-}"
ENABLE_MODEL_GUARD=false
APP_ENV="prod"

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
        --admin-email)   ADMIN_EMAIL="$2"; shift 2 ;;
        --admin-name)    ADMIN_NAME="$2"; shift 2 ;;
        --site-name)     SITE_NAME="$2"; shift 2 ;;
        --db-password)   DB_PASSWORD="$2"; shift 2 ;;
        --skip-infra)    SKIP_INFRA=true; shift ;;
        --skip-deploy)   SKIP_DEPLOY=true; shift ;;
        --gemini-key)    GEMINI_API_KEY="$2"; shift 2 ;;
        --google-client-id) GOOGLE_CLIENT_ID="$2"; shift 2 ;;
        --jwt-secret)    JWT_SECRET="$2"; shift 2 ;;
        --enable-model-guard) ENABLE_MODEL_GUARD=true; shift ;;
        --env)           APP_ENV="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 --project PROJECT_ID --region REGION --admin-email EMAIL"
            echo ""
            echo "Options:"
            echo "  --project       GCP project ID (required)"
            echo "  --region        GCP region (default: us-central1)"
            echo "  --admin-email   Admin user email (required on first deploy)"
            echo "  --admin-name    Admin display name (default: Admin)"
            echo "  --site-name     Default site name (default: Default Site)"
            echo "  --db-password   AlloyDB password (default: auto-generated)"
            echo "  --gemini-key    Gemini API key (or set GEMINI_API_KEY env var)"
            echo "  --google-client-id  Google OAuth client ID (or set GOOGLE_CLIENT_ID env var)"
            echo "  --jwt-secret    JWT signing secret (auto-generated if not set)"
            echo "  --enable-model-guard  Enable PII model guard plugin"
            echo "  --env               Environment: dev, staging, prod (default: prod)"
            echo "  --skip-infra    Skip AlloyDB + VPC setup (just deploy app)"
            echo "  --skip-deploy   Skip Cloud Run deploy (just setup infra + DB)"
            exit 0
            ;;
        *) err "Unknown option: $1" ;;
    esac
done

[[ -z "${PROJECT_ID:-}" ]] && err "--project is required"

# ── Set GCP Project ───────────────────────────────────────────────────
info "Setting project to ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" --quiet

# ══════════════════════════════════════════════════════════════════════
# PHASE 1: Infrastructure (AlloyDB + VPC)
# ══════════════════════════════════════════════════════════════════════

if [[ "${SKIP_INFRA}" == "false" ]]; then

    info "Enabling required APIs..."
    gcloud services enable \
        alloydb.googleapis.com \
        servicenetworking.googleapis.com \
        run.googleapis.com \
        artifactregistry.googleapis.com \
        secretmanager.googleapis.com \
        aiplatform.googleapis.com \
        cloudtrace.googleapis.com \
        logging.googleapis.com \
        monitoring.googleapis.com \
        --quiet

    # VPC Peering (for AlloyDB private connectivity)
    if ! gcloud compute addresses describe alloydb-ip-range --global --quiet 2>/dev/null; then
        info "Creating VPC peering IP range..."
        gcloud compute addresses create alloydb-ip-range \
            --global --purpose=VPC_PEERING --prefix-length=16 --network=default

        info "Establishing VPC peering..."
        gcloud services vpc-peerings connect \
            --service=servicenetworking.googleapis.com \
            --ranges=alloydb-ip-range --network=default
    else
        log "VPC peering already configured"
    fi

    # AlloyDB Cluster
    if ! gcloud alloydb clusters describe "${CLUSTER_NAME}" --region="${REGION}" --quiet 2>/dev/null; then
        info "Creating AlloyDB cluster '${CLUSTER_NAME}'..."
        gcloud alloydb clusters create "${CLUSTER_NAME}" \
            --region="${REGION}" --network=default --password="${DB_PASSWORD}" --quiet
        log "Cluster created"
    else
        log "Cluster '${CLUSTER_NAME}' already exists"
    fi

    # AlloyDB Instance
    if ! gcloud alloydb instances describe "${INSTANCE_NAME}" --cluster="${CLUSTER_NAME}" --region="${REGION}" --quiet 2>/dev/null; then
        info "Creating AlloyDB instance '${INSTANCE_NAME}' (${CPU_COUNT} vCPU)..."
        gcloud alloydb instances create "${INSTANCE_NAME}" \
            --cluster="${CLUSTER_NAME}" --region="${REGION}" \
            --instance-type=PRIMARY --cpu-count="${CPU_COUNT}" --quiet
        log "Instance created"

        info "Enabling public IP (for local admin access)..."
        gcloud alloydb instances update "${INSTANCE_NAME}" \
            --cluster="${CLUSTER_NAME}" --region="${REGION}" \
            --assign-inbound-public-ip=ASSIGN_IPV4 \
            --database-flags="password.enforce_complexity=on" --quiet
        log "Public IP enabled"
    else
        log "Instance '${INSTANCE_NAME}' already exists"
    fi

    # Get instance IP
    INSTANCE_IP=$(gcloud alloydb instances describe "${INSTANCE_NAME}" \
        --cluster="${CLUSTER_NAME}" --region="${REGION}" \
        --format="value(ipAddress)")
    log "AlloyDB instance IP: ${INSTANCE_IP}"

fi

# ══════════════════════════════════════════════════════════════════════
# PHASE 2: Database Init + Migrations
# ══════════════════════════════════════════════════════════════════════

info "Setting up AlloyDB Auth Proxy..."
PROXY_PID=""

cleanup_proxy() {
    if [[ -n "${PROXY_PID}" ]]; then
        kill "${PROXY_PID}" 2>/dev/null || true
    fi
}
trap cleanup_proxy EXIT

# Download proxy if not cached
PROXY_BIN="/tmp/alloydb-auth-proxy"
if [[ ! -x "${PROXY_BIN}" ]]; then
    ARCH=$(uname -m)
    case "${ARCH}" in
        x86_64)  PROXY_ARCH="amd64" ;;
        arm64|aarch64) PROXY_ARCH="arm64" ;;
        *) err "Unsupported architecture: ${ARCH}" ;;
    esac
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    info "Downloading AlloyDB Auth Proxy (${OS}/${PROXY_ARCH})..."
    curl -sL -o "${PROXY_BIN}" \
        "https://storage.googleapis.com/alloydb-auth-proxy/v1.12.2/alloydb-auth-proxy.${OS}.${PROXY_ARCH}"
    chmod +x "${PROXY_BIN}"
fi

INSTANCE_URI="projects/${PROJECT_ID}/locations/${REGION}/clusters/${CLUSTER_NAME}/instances/${INSTANCE_NAME}"
"${PROXY_BIN}" "${INSTANCE_URI}" --port=15432 --public-ip &
PROXY_PID=$!
sleep 5

# Create database if not exists
info "Ensuring database '${DB_NAME}' exists..."
python3 -c "
import psycopg2
conn = psycopg2.connect(host='127.0.0.1', port=15432, user='postgres', password='${DB_PASSWORD}', dbname='postgres')
conn.autocommit = True
cur = conn.cursor()
cur.execute(\"SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'\")
if not cur.fetchone():
    cur.execute('CREATE DATABASE ${DB_NAME}')
    print('  Database created')
else:
    print('  Database already exists')
conn.close()
"

# Run migrations
DB_URL="postgresql+psycopg2://postgres:${DB_PASSWORD}@127.0.0.1:15432/${DB_NAME}"
INIT_ARGS="--database-url ${DB_URL}"
if [[ -n "${ADMIN_EMAIL}" ]]; then
    INIT_ARGS="${INIT_ARGS} --admin-email ${ADMIN_EMAIL} --admin-name '${ADMIN_NAME}' --site-name '${SITE_NAME}'"
fi

info "Running database migrations..."
cd "${PROJECT_ROOT}"
eval python3 deploy/init_db.py ${INIT_ARGS}
log "Database ready"

# ══════════════════════════════════════════════════════════════════════
# PHASE 3: Cloud Run Deployment
# ══════════════════════════════════════════════════════════════════════

if [[ "${SKIP_DEPLOY}" == "false" ]]; then

    # Store DB password in Secret Manager
    if ! gcloud secrets describe aicdp-db-password --quiet 2>/dev/null; then
        info "Creating secret 'aicdp-db-password'..."
        echo -n "${DB_PASSWORD}" | gcloud secrets create aicdp-db-password --data-file=- --quiet
    else
        log "Secret 'aicdp-db-password' already exists"
    fi

    # Get VPC connector (or create one)
    CONNECTOR_NAME="aicdp-connector"
    if ! gcloud compute networks vpc-access connectors describe "${CONNECTOR_NAME}" --region="${REGION}" --quiet 2>/dev/null; then
        info "Creating Serverless VPC connector..."
        gcloud compute networks vpc-access connectors create "${CONNECTOR_NAME}" \
            --region="${REGION}" --network=default \
            --range="10.8.0.0/28" --min-instances=2 --max-instances=10 --quiet
        log "VPC connector created"
    else
        log "VPC connector already exists"
    fi

    # Build + Deploy to Cloud Run
    ALLOYDB_IP=$(gcloud alloydb instances describe "${INSTANCE_NAME}" \
        --cluster="${CLUSTER_NAME}" --region="${REGION}" \
        --format="value(ipAddress)")
    CLOUD_RUN_DB_URL="postgresql+psycopg2://postgres:${DB_PASSWORD}@${ALLOYDB_IP}:5432/${DB_NAME}"

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

    # Build env vars
    ENV_VARS="APP_ENV=${APP_ENV}"
    ENV_VARS="${ENV_VARS},DATABASE_URL=${CLOUD_RUN_DB_URL}"
    ENV_VARS="${ENV_VARS},GCP_PROJECT_ID=${PROJECT_ID}"
    ENV_VARS="${ENV_VARS},GCP_LOCATION=${REGION}"
    ENV_VARS="${ENV_VARS},LOG_LEVEL=INFO"
    ENV_VARS="${ENV_VARS},ENABLE_CLOUD_LOGGING=true"
    ENV_VARS="${ENV_VARS},ENABLE_CLOUD_TRACE=true"
    [[ -n "${GEMINI_API_KEY}" ]] && ENV_VARS="${ENV_VARS},GEMINI_API_KEY=${GEMINI_API_KEY}"
    [[ -n "${JWT_SECRET}" ]] && ENV_VARS="${ENV_VARS},JWT_SECRET=${JWT_SECRET}"
    [[ -n "${GOOGLE_CLIENT_ID}" ]] && ENV_VARS="${ENV_VARS},GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}"
    [[ "${ENABLE_MODEL_GUARD}" == "true" ]] && ENV_VARS="${ENV_VARS},ENABLE_MODEL_GUARD=true"

    info "Building and deploying to Cloud Run..."
    gcloud run deploy "${SERVICE_NAME}" \
        --source="${PROJECT_ROOT}" \
        --region="${REGION}" \
        --platform=managed \
        --allow-unauthenticated \
        --cpu=2 --memory=2Gi \
        --min-instances=1 --max-instances=10 \
        --timeout=600 \
        --concurrency=20 \
        --cpu-throttling=false \
        --execution-environment=gen2 \
        --vpc-connector="${CONNECTOR_NAME}" \
        --vpc-egress=private-ranges-only \
        --set-env-vars="${ENV_VARS}" \
        --quiet

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

    # 1. Health check
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/health" 2>/dev/null)
    if [[ "${HTTP_CODE}" == "200" ]]; then
        log "Health check: OK"
    else
        warn "Health check: FAILED (HTTP ${HTTP_CODE})"
        VERIFY_PASS=false
    fi

    # 2. Auth enforcement (should return 401 without JWT)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/api/ontology" 2>/dev/null)
    if [[ "${HTTP_CODE}" == "401" ]]; then
        log "Auth enforcement: OK (401 without JWT)"
    elif [[ "${HTTP_CODE}" == "200" ]]; then
        warn "Auth enforcement: FAILED — API accessible without auth! Check DEV_USER_EMAIL is not set."
        VERIFY_PASS=false
    else
        warn "Auth enforcement: unexpected HTTP ${HTTP_CODE}"
    fi

    # 3. Frontend SPA served
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
echo "  AlloyDB:    ${CLUSTER_NAME} / ${INSTANCE_NAME}"
echo "  Database:   ${DB_NAME}"
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
echo "  • Custom domain:    gcloud run domain-mappings create --service ${SERVICE_NAME} --domain your.domain"
echo "  • Redeploy (app only): ./deploy/legacy/deploy-alloydb.sh --project ${PROJECT_ID} --region ${REGION} --skip-infra"
echo "  • Schema upgrade:      ./deploy/legacy/deploy-alloydb.sh --project ${PROJECT_ID} --region ${REGION} --skip-deploy"
echo ""
