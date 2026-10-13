"""Pytest fixtures and test configuration."""

import os

# Set local testing environment variables
os.environ["APP_ENV"] = "test"
os.environ["GCP_PROJECT_ID"] = "local-dev-project"
os.environ["NOTION_API_KEY"] = "mock_secret_notion_key_12345"
os.environ["USE_VERTEX_AI"] = "false"
