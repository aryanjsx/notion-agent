terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# -------------------------------------------------------------
# 1. Enable Required GCP APIs
# -------------------------------------------------------------
locals {
  services = [
    "run.googleapis.com",
    "cloudtasks.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
  ]
}

resource "google_project_service" "enabled_apis" {
  for_each           = toset(locals.services)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# -------------------------------------------------------------
# 2. Artifact Registry for Container Images
# -------------------------------------------------------------
resource "google_artifact_registry_repository" "repo" {
  provider      = google
  location      = var.region
  repository_id = "notion-agent-repo"
  description   = "Docker repository for Notion AI Agent"
  format        = "DOCKER"
  depends_on    = [google_project_service.enabled_apis]
}

# -------------------------------------------------------------
# 3. Dedicated Least-Privilege Service Account
# -------------------------------------------------------------
resource "google_service_account" "agent_sa" {
  account_id   = "notion-agent-sa"
  display_name = "Notion AI Agent Runtime Service Account"
}

locals {
  agent_roles = [
    "roles/datastore.user",              # Firestore read/write
    "roles/storage.objectAdmin",          # Cloud Storage bucket read/write
    "roles/cloudtasks.enqueuer",         # Cloud Tasks task creation
    "roles/secretmanager.secretAccessor", # Read secrets
    "roles/aiplatform.user",             # Gemini Vertex AI calls
    "roles/run.invoker",                 # Cloud Tasks invoking Worker Cloud Run
  ]
}

resource "google_project_iam_member" "agent_sa_roles" {
  for_each = toset(locals.agent_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.agent_sa.email}"
}

# -------------------------------------------------------------
# 4. Google Cloud Storage Bucket (with 7-day auto-cleanup lifecycle)
# -------------------------------------------------------------
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "attachments_bucket" {
  name                        = "${var.project_id}-notion-agent-docs-${random_id.bucket_suffix.hex}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 7 # Auto-delete temporary attachments older than 7 days to eliminate storage costs
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.enabled_apis]
}

# -------------------------------------------------------------
# 5. Firestore Database (Native Mode)
# -------------------------------------------------------------
resource "google_firestore_database" "database" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # Prevent accidental destruction of default database
  deletion_policy = "DELETE"

  depends_on = [google_project_service.enabled_apis]
}

# -------------------------------------------------------------
# 6. Cloud Tasks Queue
# -------------------------------------------------------------
resource "google_cloud_tasks_queue" "task_queue" {
  name     = "notion-agent-tasks"
  location = var.region

  rate_limits {
    max_dispatches_per_second = 10
    max_concurrent_dispatches = 5
  }

  retry_config {
    max_attempts       = 5
    min_backoff        = "10s"
    max_backoff        = "300s"
    max_doublings      = 3
    max_retry_duration = "3600s"
  }

  depends_on = [google_project_service.enabled_apis]
}

# -------------------------------------------------------------
# 7. Secret Manager Secrets
# -------------------------------------------------------------
resource "google_secret_manager_secret" "notion_token" {
  secret_id = "NOTION_TOKEN"
  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret_version" "notion_token_version" {
  count       = var.notion_token != "" ? 1 : 0
  secret      = google_secret_manager_secret.notion_token.id
  secret_data = var.notion_token
}

resource "google_secret_manager_secret" "slack_token" {
  secret_id = "SLACK_BOT_TOKEN"
  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret_version" "slack_token_version" {
  count       = var.slack_bot_token != "" ? 1 : 0
  secret      = google_secret_manager_secret.slack_token.id
  secret_data = var.slack_bot_token
}

resource "google_secret_manager_secret" "sendgrid_key" {
  secret_id = "SENDGRID_API_KEY"
  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret_version" "sendgrid_key_version" {
  count       = var.sendgrid_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.sendgrid_key.id
  secret_data = var.sendgrid_api_key
}

# -------------------------------------------------------------
# 8. Cloud Run Services (Strict min_instance_count = 0 for Zero Idle Cost)
# -------------------------------------------------------------

# API Gateway Service
resource "google_cloud_run_v2_service" "api_service" {
  name     = "notion-agent-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.agent_sa.email
    scaling {
      min_instance_count = 0 # Scale to 0 when no incoming HTTP traffic
      max_instance_count = 10
    }
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/notion-agent-api:latest"
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.attachments_bucket.name
      }
      env {
        name  = "CLOUD_TASKS_QUEUE"
        value = google_cloud_tasks_queue.task_queue.name
      }
      env {
        name  = "CLOUD_TASKS_LOCATION"
        value = var.region
      }
      env {
        name  = "WORKER_SERVICE_URL"
        value = google_cloud_run_v2_service.worker_service.uri
      }
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_project_iam_member.agent_sa_roles
  ]
}

# Allow public unauthenticated access to API Dashboard & Webhooks
resource "google_cloud_run_v2_service_iam_member" "api_public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Worker Service (executes asynchronous AI agent runs triggered by Cloud Tasks)
resource "google_cloud_run_v2_service" "worker_service" {
  name     = "notion-agent-worker"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    timeout         = "300s" # 5-minute execution limit for long LLM document reasoning
    service_account = google_service_account.agent_sa.email
    scaling {
      min_instance_count = 0 # Scale to 0 when idle
      max_instance_count = 5
    }
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/notion-agent-worker:latest"
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.attachments_bucket.name
      }
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_project_iam_member.agent_sa_roles
  ]
}

# Allow Service Account and Cloud Tasks to invoke Worker
resource "google_cloud_run_v2_service_iam_member" "worker_sa_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.worker_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.agent_sa.email}"
}
