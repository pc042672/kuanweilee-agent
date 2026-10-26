#!/bin/bash
# AI-CDP private-server deploy (systemd + nginx, no cloud).
# Usage: sudo ./deploy/server/deploy.sh [--skip-build] [--skip-backend] [--skip-frontend]
#
# Run database migrations FIRST (idempotent), then this script:
#   python deploy/init_db.py --database-url "$DATABASE_URL"   # schema upgrade
# See deploy/server/.env.production for the full env template.
set -euo pipefail

# Configuration (override PROJECT_DIR via env if not deploying from /root/ai-cdp)
PROJECT_DIR="${PROJECT_DIR:-/root/ai-cdp}"
FRONTEND_DIR="${PROJECT_DIR}/frontend"
STATIC_DIR="/var/www/ai-cdp"
VENV_DIR="${PROJECT_DIR}/.venv"
NODE_VERSION="22"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
SKIP_BUILD=false
SKIP_BACKEND=false
SKIP_FRONTEND=false
for arg in "$@"; do
    case $arg in
        --skip-build) SKIP_BUILD=true ;;
        --skip-backend) SKIP_BACKEND=true ;;
        --skip-frontend) SKIP_FRONTEND=true ;;
        --help|-h)
            echo "Usage: $0 [--skip-build] [--skip-backend] [--skip-frontend]"
            echo "  --skip-build     Skip frontend build"
            echo "  --skip-backend   Skip backend venv + service setup"
            echo "  --skip-frontend  Skip frontend entirely"
            exit 0
            ;;
    esac
done

# Must run as root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root or with sudo"
    exit 1
fi

# Check .env
if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
    log_error ".env not found. Run: cp deploy/server/.env.production ${PROJECT_DIR}/.env && vim .env"
    exit 1
fi

# ─── System dependencies ───────────────────────────────────────────
log_info "Checking system dependencies..."

# Python 3.12+
if ! command -v python3 &>/dev/null; then
    log_info "Installing Python 3..."
    apt-get update && apt-get install -y python3 python3-venv python3-pip
fi

# Node.js (for frontend build)
if [[ "${SKIP_FRONTEND}" == "false" ]]; then
    if ! command -v node &>/dev/null; then
        log_info "Installing Node.js ${NODE_VERSION}..."
        curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash -
        apt-get install -y nodejs
    fi
fi

# nginx
if ! command -v nginx &>/dev/null; then
    log_info "Installing nginx..."
    apt-get update && apt-get install -y nginx
fi

# ─── Backend ───────────────────────────────────────────────────────
if [[ "${SKIP_BACKEND}" == "false" ]]; then
    log_info "Setting up Python virtual environment..."
    if [[ ! -f "${VENV_DIR}/bin/python" ]]; then
        python3 -m venv "${VENV_DIR}"
    fi

    log_info "Installing backend dependencies..."
    "${VENV_DIR}/bin/pip" install --upgrade pip
    "${VENV_DIR}/bin/pip" install -r "${PROJECT_DIR}/backend/requirements.lock"

    log_info "Installing systemd service..."
    cp "${PROJECT_DIR}/deploy/server/ai-cdp.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable ai-cdp
    systemctl restart ai-cdp

    sleep 2
    if systemctl is-active --quiet ai-cdp; then
        log_info "Backend service started (127.0.0.1:8000)"
    else
        log_error "Backend service failed to start"
        systemctl status ai-cdp --no-pager
        exit 1
    fi
fi

# ─── Frontend ──────────────────────────────────────────────────────
if [[ "${SKIP_FRONTEND}" == "false" && "${SKIP_BUILD}" == "false" ]]; then
    log_info "Building frontend..."
    mkdir -p "${STATIC_DIR}"
    cd "${FRONTEND_DIR}"

    if [[ ! -d "node_modules" ]]; then
        log_info "Installing npm dependencies..."
        npm ci
    fi

    npx ng build --configuration=production

    log_info "Deploying frontend to ${STATIC_DIR}..."
    rm -rf "${STATIC_DIR:?}"/*
    cp -r dist/frontend/browser/* "${STATIC_DIR}/"

    chown -R www-data:www-data "${STATIC_DIR}"
    find "${STATIC_DIR}" -type d -exec chmod 755 {} \;
    find "${STATIC_DIR}" -type f -exec chmod 644 {} \;

    cd "${PROJECT_DIR}"
fi

# ─── Nginx ─────────────────────────────────────────────────────────
if [[ ! -L "/etc/nginx/sites-enabled/ai-cdp.nginx" ]]; then
    log_info "Linking nginx config..."
    ln -sf "${PROJECT_DIR}/deploy/server/ai-cdp.nginx" /etc/nginx/sites-enabled/
    # Remove default site if it exists
    rm -f /etc/nginx/sites-enabled/default
fi

log_info "Testing nginx..."
if nginx -t; then
    systemctl reload nginx
    log_info "Nginx reloaded"
else
    log_error "Nginx config test failed"
    exit 1
fi

# ─── Done ──────────────────────────────────────────────────────────
echo ""
log_info "Deployment complete!"
echo ""
echo "  Backend:  systemctl status ai-cdp"
echo "  Logs:     journalctl -u ai-cdp -f"
echo "  Nginx:    systemctl status nginx"
echo ""
