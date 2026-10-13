# ==============================================================================
# Notion AI Agent - GCP Infrastructure Setup Script (PowerShell)
# ==============================================================================
# Sets up GCP APIs, builds container images, and deploys serverless resources.
# All compute services are configured with scale-to-zero (min-instances=0).
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Notion AI Agent - GCP Infrastructure Setup (Windows/PowerShell)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ProjectId = $env:GCP_PROJECT_ID
if (-not $ProjectId) {
    $ProjectId = Read-Host "Enter your GCP Project ID"
}

$Region = $env:GCP_REGION
if (-not $Region) {
    $Region = "us-central1"
}

$RepoName = "notion-agent-repo"

Write-Host "Using GCP Project: $ProjectId"
Write-Host "Using Region:      $Region"

# 1. Set gcloud project
gcloud config set project $ProjectId

# 2. Enable necessary Google Cloud APIs
Write-Host "`n--> Enabling required GCP APIs..." -ForegroundColor Yellow
gcloud services enable `
    run.googleapis.com `
    cloudtasks.googleapis.com `
    firestore.googleapis.com `
    storage.googleapis.com `
    secretmanager.googleapis.com `
    aiplatform.googleapis.com `
    artifactregistry.googleapis.com `
    cloudbuild.googleapis.com

# 3. Create Artifact Registry Repository (if not exists)
Write-Host "`n--> Checking Artifact Registry repository..." -ForegroundColor Yellow
$repoCheck = gcloud artifacts repositories describe $RepoName --location=$Region 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Artifact Registry repository: $RepoName"
    gcloud artifacts repositories create $RepoName `
        --repository-format=docker `
        --location=$Region `
        --description="Docker repo for Notion AI Agent"
} else {
    Write-Host "Artifact Registry repository already exists."
}

# 4. Build and Submit Images using Cloud Build
Write-Host "`n--> Submitting Cloud Build for API and Worker containers..." -ForegroundColor Yellow
gcloud builds submit `
    --config=cloudbuild.yaml `
    --substitutions=_REGION="$Region",_REPO="$RepoName"

# 5. Retrieve Deployed Service URLs
$ApiUrl = gcloud run services describe notion-agent-api --region=$Region --format="value(status.url)" 2>$null
$WorkerUrl = gcloud run services describe notion-agent-worker --region=$Region --format="value(status.url)" 2>$null

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " Setup Completed Successfully!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "API & Web UI URL: $ApiUrl"
Write-Host "Worker URL:       $WorkerUrl"
Write-Host "`nNote: Both Cloud Run services are configured with min-instances=0 (scale-to-zero)."
Write-Host "When idle, compute cost is $0."
Write-Host "To completely tear down or stop all services, run: .\scripts\cleanup_gcp.ps1"
Write-Host "==========================================================" -ForegroundColor Green
