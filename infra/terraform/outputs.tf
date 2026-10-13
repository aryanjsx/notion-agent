output "api_service_url" {
  description = "The publicly accessible URL of the Notion Agent API & Web UI"
  value       = google_cloud_run_v2_service.api_service.uri
}

output "worker_service_url" {
  description = "The internal URL of the asynchronous execution worker"
  value       = google_cloud_run_v2_service.worker_service.uri
}

output "storage_bucket_name" {
  description = "The Cloud Storage bucket for document attachments"
  value       = google_storage_bucket.attachments_bucket.name
}

output "tasks_queue_name" {
  description = "The Cloud Tasks queue name"
  value       = google_cloud_tasks_queue.task_queue.name
}

output "service_account_email" {
  description = "Service account running the agent"
  value       = google_service_account.agent_sa.email
}

output "artifact_registry_repo" {
  description = "Artifact Registry Docker repository"
  value       = google_artifact_registry_repository.repo.name
}
