import os
from functools import lru_cache
from google.cloud import secretmanager
from google.cloud import storage

@lru_cache(maxsize=1)
def get_secret_manager_client() -> secretmanager.SecretManagerServiceClient:
    """
    Returns a cached instance of the Google Cloud Secret Manager client.
    Caching is used to avoid creating a new client for each request, which is inefficient.
    """
    return secretmanager.SecretManagerServiceClient()

def get_secret(secret_id: str, version_id: str = "latest") -> str:
    """
    Retrieves a secret's value from Google Cloud Secret Manager.

    Args:
        secret_id: The ID of the secret to retrieve.
        version_id: The version of the secret (defaults to 'latest').

    Returns:
        The secret value as a string.
    """
    client = get_secret_manager_client()
    settings = get_settings()
    project_id = settings.GCP_PROJECT_ID

    # If project_id is not in settings, try getting it from environment variables
    if not project_id:
        project_id = os.environ.get("GCP_PROJECT_ID")

    if not project_id:
        raise ValueError("GCP_PROJECT_ID not set in settings or environment variables.")

    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

@lru_cache(maxsize=1)
def get_gcs_client() -> storage.Client:
    """
    Returns a cached instance of the Google Cloud Storage client.
    """
    return storage.Client()


def load_secrets():
    """
    Loads secrets from Google Secret Manager and sets them as environment variables.
    This function should be called once at application startup.
    """
    try:
        secret_key = get_secret("JWT_SECRET_KEY")
        os.environ["SECRET_KEY"] = secret_key
    except Exception as e:
        # Handle cases where the secret cannot be fetched, e.g., in local development
        # or when Secret Manager is not available.
        # You might want to log this error or handle it based on your application's needs.
        print(f"Could not load secrets from Secret Manager: {e}")
        # In a production environment, you might want to raise the exception
        # to prevent the application from starting without the necessary secrets.
        # raise


# Call load_secrets at the module level to ensure secrets are loaded when the app starts.
load_secrets()

from .config import settings


@lru_cache(maxsize=1)
def get_settings():
    """
    Returns a cached instance of the application settings.
    """
    return settings