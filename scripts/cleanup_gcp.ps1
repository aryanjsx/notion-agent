# ==============================================================================
# Notion AI Agent - GCP Teardown & Resource Cleanup Script (PowerShell)
# ==============================================================================
# Stops or completely destroys deployed GCP resources to ensure ZERO idle costs
# when the system is not in use.
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Notion AI Agent - GCP Resource Cleanup / Teardown" -ForegroundColor Cyan
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

Write-Host "Target Project: $ProjectId"
Write-Host "Target Region:  $Region"
Write-Host ""
Write-Host "Select cleanup option:"
Write-Host "  [1] STOP SERVICES (Delete Cloud Run services & pause queue; preserves database & data)"
Write-Host "  [2] FULL TEARDOWN (Delete Cloud Run, Cloud Tasks, GCS bucket, Artifact Registry, Secrets)"
$Choice = Read-Host "Enter choice [1 or 2]"

gcloud config set project $ProjectId

# 1. Stop/Delete Cloud Run Services
Write-Host "`n--> Removing Cloud Run services (notion-agent-api, notion-agent-worker)..." -ForegroundColor Yellow
gcloud run services delete notion-agent-api --region=$Region --quiet 2>$null
gcloud run services delete notion-agent-worker --region=$Region --quiet 2>$null

if ($Choice -eq "1") {
    Write-Host "`n--> Pausing Cloud Tasks queue..." -ForegroundColor Yellow
    gcloud tasks queues pause notion-agent-tasks --location=$Region 2>$null
    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host " Services Stopped! Zero compute charges will accrue." -ForegroundColor Green
    Write-Host " To restart them later, run .\scripts\setup_gcp.ps1" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    exit 0
}

# Full Teardown Mode
Write-Host "`n--> Deleting Cloud Tasks queue..." -ForegroundColor Yellow
gcloud tasks queues delete notion-agent-tasks --location=$Region --quiet 2>$null

Write-Host "`n--> Deleting Artifact Registry Docker repository..." -ForegroundColor Yellow
gcloud artifacts repositories delete $RepoName --location=$Region --quiet 2>$null

Write-Host "`n--> Deleting Secret Manager secrets..." -ForegroundColor Yellow
$secrets = @("NOTION_TOKEN", "SLACK_BOT_TOKEN", "SENDGRID_API_KEY", "NOTION_WEBHOOK_SECRET")
foreach ($sec in $secrets) {
    gcloud secrets delete $sec --quiet 2>$null
}

Write-Host "`n--> Deleting Service Account..." -ForegroundColor Yellow
gcloud iam service-accounts delete "notion-agent-sa@${ProjectId}.iam.gserviceaccount.com" --quiet 2>$null

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " Full Teardown Complete! All Notion Agent GCP resources removed." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
