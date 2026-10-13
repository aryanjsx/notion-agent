"""Google Cloud Storage service with local filesystem fallback."""

import logging
from pathlib import Path

from google.cloud import storage  # type: ignore[attr-defined]

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Manages document uploads and downloads using GCS or local disk."""

    def __init__(self) -> None:
        self.use_mock = False
        self.client: storage.Client | None = None
        self.local_dir = Path(".storage")
        self.local_dir.mkdir(parents=True, exist_ok=True)

        if settings.gcp_project_id and settings.gcp_project_id != "local-dev-project":
            try:
                self.client = storage.Client(project=settings.gcp_project_id)
                self.bucket = self.client.bucket(settings.gcs_bucket_name)
                logger.info(
                    "Connected to Cloud Storage (bucket: %s)", settings.gcs_bucket_name
                )
            except Exception as e:
                logger.warning(
                    "Failed to connect to GCS (%s). Falling back to local storage.", e
                )
                self.use_mock = True
        else:
            self.use_mock = True

    def upload_bytes(
        self,
        data: bytes,
        destination_name: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload raw bytes and return the access URI."""
        if self.use_mock or not self.client:
            dest_path = self.local_dir / destination_name
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(data)
            return f"local://{dest_path.as_posix()}"

        blob = self.bucket.blob(destination_name)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{settings.gcs_bucket_name}/{destination_name}"

    def download_bytes(self, uri: str) -> bytes:
        """Download raw bytes from a URI (gs:// or local:// or file path)."""
        if uri.startswith("local://"):
            path = Path(uri.replace("local://", ""))
            return path.read_bytes()
        elif uri.startswith("gs://"):
            if self.use_mock or not self.client:
                # If in mock mode, attempt finding in local_dir
                blob_name = uri.split("/", 3)[-1]
                local_path = self.local_dir / blob_name
                if local_path.exists():
                    return local_path.read_bytes()
                raise FileNotFoundError(
                    f"Mock GCS file not found locally: {local_path}"
                )
            parts = uri.replace("gs://", "").split("/", 1)
            bucket_name = parts[0]
            blob_name = parts[1]
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.download_as_bytes()
        else:
            # Regular local filesystem path
            return Path(uri).read_bytes()


_storage_service_instance: StorageService | None = None


def get_storage_service() -> StorageService:
    global _storage_service_instance
    if _storage_service_instance is None:
        _storage_service_instance = StorageService()
    return _storage_service_instance
