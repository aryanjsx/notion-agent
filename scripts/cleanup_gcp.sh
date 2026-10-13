#!/usr/bin/env bash
# ==============================================================================
# Notion AI Agent - GCP Teardown & Resource Cleanup Script
# ==============================================================================
# Stops or completely destroys deployed GCP resources to ensure ZERO idle costs
# when the system is not in use.
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo " Notion AI Agent - GCP Resource Cleanup / Teardown"
echo "=========================================================="

if [ -z "${GCP_PROJECT_ID:-}" ]; then
  read -rp "Enter your GCP Project ID: " GCP_PROJECT_ID
fi

REGION="${GCP_REGION:-us-central1}"
REPO_NAME="notion-agent-repo"

echo "Target Project: ${GCP_PROJECT_ID}"
echo "Target Region:  ${REGION}"
echo ""
echo "Select cleanup option:"
echo "  [1] STOP SERVICES (Delete Cloud Run services & pause queue; preserves database & data)"
echo "  [2] FULL TEARDOWN (Delete Cloud Run, Cloud Tasks, GCS bucket, Artifact Registry, Secrets)"
read -rp "Enter choice [1 or 2]: " CLEANUP_MODE

gcloud config set project "${GCP_PROJECT_ID}"

# 1. Stop/Delete Cloud Run Services
echo "--> Removing Cloud Run services (notion-agent-api, notion-agent-worker)..."
gcloud run services delete notion-agent-api --region="${REGION}" --quiet 2>/dev/null || echo "notion-agent-api not found or already deleted."
gcloud run services delete notion-agent-worker --region="${REGION}" --quiet 2>/dev/null || echo "notion-agent-worker not found or already deleted."

# 2. Pause or delete Cloud Tasks queue
if [ "${CLEANUP_MODE}" == "1" ]; then
  echo "--> Pausing Cloud Tasks queue..."
  gcloud tasks queues pause notion-agent-tasks --location="${REGION}" 2>/dev/null || echo "Queue not found or already paused."
  echo ""
  echo "=========================================================="
  echo " Services Stopped! Zero compute charges will accrue."
  echo " To restart them later, run ./scripts/setup_gcp.sh"
  echo "=========================================================="
  exit 0
fi

# Full Teardown Mode
echo "--> Deleting Cloud Tasks queue..."
gcloud tasks queues delete notion-agent-tasks --location="${REGION}" --quiet 2>/dev/null || echo "Queue already deleted."

echo "--> Deleting Artifact Registry Docker repository..."
gcloud artifacts repositories delete "${REPO_NAME}" --location="${REGION}" --quiet 2>/dev/null || echo "Repo already deleted."

echo "--> Deleting Secret Manager secrets..."
for secret in NOTION_TOKEN SLACK_BOT_TOKEN SENDGRID_API_KEY NOTION_WEBHOOK_SECRET; do
  gcloud secrets delete "${secret}" --quiet 2>/dev/null || echo "Secret ${secret} not found."
done

echo "--> Deleting Service Account..."
gcloud iam service-accounts delete "notion-agent-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com" --quiet 2>/dev/null || echo "Service account already deleted."

echo "--> Cleaning up Storage Buckets..."
for bucket in $(gsutil ls -p "${GCP_PROJECT_ID}" 2>/dev/null | grep "${GCP_PROJECT_ID}-notion-agent-docs" || true); do
  echo "Removing bucket: ${bucket}"
  gsutil -m rm -r "${bucket}" 2>/dev/null || true
done

echo ""
echo "=========================================================="
echo " Full Teardown Complete! All Notion Agent GCP resources removed."
echo "=========================================================="
