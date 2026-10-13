#!/usr/bin/env bash
# ==============================================================================
# Notion AI Agent - GCP Infrastructure Setup Script
# ==============================================================================
# Sets up GCP APIs, builds container images, and deploys serverless resources.
# All compute services are configured with scale-to-zero (min-instances=0).
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo " Notion AI Agent - GCP Infrastructure Setup"
echo "=========================================================="

# 1. Check required environment variables
if [ -z "${GCP_PROJECT_ID:-}" ]; then
  read -rp "Enter your GCP Project ID: " GCP_PROJECT_ID
fi

REGION="${GCP_REGION:-us-central1}"
REPO_NAME="notion-agent-repo"

echo "Using GCP Project: ${GCP_PROJECT_ID}"
echo "Using Region:      ${REGION}"
echo ""

# 2. Configure gcloud project
gcloud config set project "${GCP_PROJECT_ID}"

# 3. Enable necessary Google Cloud APIs
echo "--> Enabling required GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudtasks.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

# 4. Create Artifact Registry Repository (if not exists)
echo "--> Checking Artifact Registry repository..."
if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" >/dev/null 2>&1; then
  echo "Creating Artifact Registry repository: ${REPO_NAME}"
  gcloud artifacts repositories create "${REPO_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Docker repo for Notion AI Agent"
else
  echo "Artifact Registry repository already exists."
fi

# 5. Build and Submit Images using Cloud Build
echo "--> Submitting Cloud Build for API and Worker containers..."
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions=_REGION="${REGION}",_REPO="${REPO_NAME}"

# 6. Retrieve Deployed Service URLs
API_URL=$(gcloud run services describe notion-agent-api --region="${REGION}" --format="value(status.url)" 2>/dev/null || echo "")
WORKER_URL=$(gcloud run services describe notion-agent-worker --region="${REGION}" --format="value(status.url)" 2>/dev/null || echo "")

echo ""
echo "=========================================================="
echo " Setup Completed Successfully!"
echo "=========================================================="
echo "API & Web UI URL: ${API_URL}"
echo "Worker URL:       ${WORKER_URL}"
echo ""
echo "Note: Both services are configured with min-instances=0,"
echo "meaning they scale down to zero when idle and cost \$0."
echo "To completely tear down or stop all services, run: ./scripts/cleanup_gcp.sh"
echo "=========================================================="
