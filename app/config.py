"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable bindings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_env: str = "development"
    debug: bool = False
    api_port: int = 8080
    worker_port: int = 8081

    # Google Cloud Platform
    gcp_project_id: str = "local-dev-project"
    gcp_region: str = "us-central1"
    firestore_database: str = "(default)"
    gcs_bucket_name: str = "notion-agent-docs"
    cloud_tasks_queue: str = "notion-agent-tasks"
    worker_service_url: str | None = "http://localhost:8081/worker/execute"

    # Notion
    notion_api_key: str | None = None  # Single-user internal integration token
    notion_api_version: str = "2022-06-28"
    notion_oauth_client_id: str | None = None
    notion_oauth_client_secret: str | None = None
    notion_redirect_uri: str | None = None
    notion_rate_limit_rps: float = 3.0  # Respect Notion ~3 req/s limit

    # Gemini & Vertex AI
    use_vertex_ai: bool = False
    gemini_api_key: str | None = None
    gemini_planner_model: str = "gemini-2.5-pro"
    gemini_executor_model: str = "gemini-2.5-flash"
    max_tokens_per_task: int = 150000

    # Notification Channels
    default_notify_channels: list[str] = ["notion_comment"]
    slack_webhook_url: str | None = None
    sendgrid_api_key: str | None = None
    notification_from_email: str = "noreply@notionagent.internal"

    # Agent Constraints & Safety
    max_steps_per_task: int = 20
    step_timeout_seconds: int = 60
    task_timeout_seconds: int = 600
    confirm_destructive_actions: bool = True  # Always confirm deletions/archivals


settings = Settings()
