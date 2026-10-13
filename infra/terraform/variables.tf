variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "region" {
  description = "The GCP region to deploy resources into"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment (e.g., prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "notion_token" {
  description = "Notion Internal Integration Token (secret_...)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "slack_bot_token" {
  description = "Slack Bot OAuth Token (xoxb-...)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "sendgrid_api_key" {
  description = "SendGrid API Key for email notifications"
  type        = string
  sensitive   = true
  default     = ""
}

variable "notion_webhook_secret" {
  description = "Secret key for verifying Notion webhook signatures"
  type        = string
  sensitive   = true
  default     = ""
}
