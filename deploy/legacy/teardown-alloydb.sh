#!/bin/bash
# AI-CDP GCP Teardown — removes all deployed resources
#
# Usage:
#   ./deploy/legacy/teardown-alloydb.sh --project PROJECT_ID --region REGION
#
# WARNING: This deletes AlloyDB data permanently!

set -euo pipefail

REGION="us-central1"
CLUSTER_NAME="aicdp"
INSTANCE_NAME="aicdp-primary"
SERVICE_NAME="ai-cdp-backend"
CONNECTOR_NAME="aicdp-connector"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

while [[ $# -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift 2 ;;
        --region)  REGION="$2"; shift 2 ;;
        --help|-h) echo "Usage: $0 --project PROJECT_ID [--region REGION]"; exit 0 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

[[ -z "${PROJECT_ID:-}" ]] && { echo "ERROR: --project required"; exit 1; }

gcloud config set project "${PROJECT_ID}" --quiet

echo -e "${RED}WARNING: This will delete ALL AI-CDP resources in ${PROJECT_ID}${NC}"
read -p "Type 'yes' to confirm: " confirm
[[ "${confirm}" != "yes" ]] && { echo "Aborted."; exit 0; }

echo -e "${YELLOW}Deleting Cloud Run service...${NC}"
gcloud run services delete "${SERVICE_NAME}" --region="${REGION}" --quiet 2>/dev/null || true

echo -e "${YELLOW}Deleting AlloyDB instance...${NC}"
gcloud alloydb instances delete "${INSTANCE_NAME}" \
    --cluster="${CLUSTER_NAME}" --region="${REGION}" --quiet 2>/dev/null || true

echo -e "${YELLOW}Deleting AlloyDB cluster...${NC}"
gcloud alloydb clusters delete "${CLUSTER_NAME}" \
    --region="${REGION}" --force --quiet 2>/dev/null || true

echo -e "${YELLOW}Deleting VPC connector...${NC}"
gcloud compute networks vpc-access connectors delete "${CONNECTOR_NAME}" \
    --region="${REGION}" --quiet 2>/dev/null || true

echo -e "${YELLOW}Deleting secrets...${NC}"
gcloud secrets delete aicdp-db-password --quiet 2>/dev/null || true

echo -e "${GREEN}Teardown complete.${NC}"
