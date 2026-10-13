"""Google Secret Manager service with local environment variable fallback."""

import logging
import os

from google.cloud import secretmanager

from app.config import settings

logger = logging.getLogger(__name__)


class SecretsService:
    """Retrieves secrets from GCP Secret Manager or local environment."""

    def __init__(self) -> None:
        self.use_mock = False
        self.client: secretmanager.SecretManagerServiceClient | None = None

        if settings.gcp_project_id and settings.gcp_project_id != "local-dev-project":
            try:
                self.client = secretmanager.SecretManagerServiceClient()
                logger.info("Connected to GCP Secret Manager.")
            except Exception as e:
                logger.warning(
                    "Failed to connect to Secret Manager (%s). Using local env secrets.",
                    e,
                )
                self.use_mock = True
        else:
            self.use_mock = True

    def get_secret(self, secret_id: str, default: str | None = None) -> str | None:
        """Fetch secret string by ID."""
        # 1. Check local environment first if mock or as fallback
        env_val = os.getenv(secret_id.upper().replace("-", "_"))
        if env_val:
            return env_val

        # Check settings
        attr_name = secret_id.lower().replace("-", "_")
        if hasattr(settings, attr_name) and getattr(settings, attr_name):
            return getattr(settings, attr_name)

        if self.use_mock or not self.client:
            return default

        try:
            name = f"projects/{settings.gcp_project_id}/secrets/{secret_id}/versions/latest"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.warning(
                "Could not access secret %s from Secret Manager: %s", secret_id, e
            )
            return default


_secrets_service_instance: SecretsService | None = None


def get_secrets_service() -> SecretsService:
    global _secrets_service_instance
    if _secrets_service_instance is None:
        _secrets_service_instance = SecretsService()
    return _secrets_service_instance
