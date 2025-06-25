import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from filelock import FileLock, Timeout

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelRegistryService:
    """
    Manages model registration and lifecycle using a single JSON file.

    This service provides a "Zero-Budget" implementation of a model registry,
    adhering to the design specified in docs/model_registry_design.md. It uses
    a file lock to ensure safe concurrent writes to the registry file.
    """

    def __init__(self, registry_path: str = "models/registry.json"):
        """
        Initializes the ModelRegistryService.

        Args:
            registry_path: The path to the JSON file serving as the model registry.
        """
        self.registry_path = Path(registry_path)
        self.lock_path = self.registry_path.with_suffix(".lock")
        self._ensure_registry_exists()

    def _ensure_registry_exists(self):
        """Creates the registry file with an empty structure if it doesn't exist."""
        if not self.registry_path.exists():
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_path, "w") as f:
                json.dump({"models": []}, f, indent=4)
            logger.info(f"Created empty model registry at: {self.registry_path}")

    def _read_registry(self) -> Dict:
        """Reads the entire content of the registry file."""
        with open(self.registry_path, "r") as f:
            return json.load(f)

    def _write_registry(self, data: Dict):
        """
        Writes data to the registry file, using a file lock for safety.
        """
        try:
            with FileLock(self.lock_path, timeout=5):
                with open(self.registry_path, "w") as f:
                    json.dump(data, f, indent=4)
        except Timeout:
            logger.error(f"Could not acquire lock on {self.registry_path}. Operation failed.")
            raise

    def _get_next_version(self, models: List[Dict], model_name: str) -> int:
        """Determines the next version number for a given model."""
        versions = [
            m["version"] for m in models if m.get("model_name") == model_name
        ]
        return max(versions) + 1 if versions else 1

    def register_model(
        self, model_name: str, path: str, metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Registers a new model version. The new version is created with 'staging' status.

        Args:
            model_name: The name of the model.
            path: The file path to the model artifact.
            metadata: Optional dictionary with additional model metadata (e.g., metrics).

        Returns:
            The full dictionary of the newly registered model entry.
        """
        registry = self._read_registry()
        models = registry.get("models", [])

        next_version = self._get_next_version(models, model_name)

        new_model_entry = {
            "model_name": model_name,
            "version": next_version,
            "path": path,
            "status": "staging",
            "creation_timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        models.append(new_model_entry)
        registry["models"] = models
        self._write_registry(registry)

        logger.info(f"Registered model '{model_name}' version {next_version}.")
        return new_model_entry

    def list_models(self, model_name: Optional[str] = None) -> List[Dict]:
        """
        Lists all registered models, optionally filtering by model name.

        Args:
            model_name: If provided, only versions of this model will be returned.

        Returns:
            A list of model entries.
        """
        registry = self._read_registry()
        models = registry.get("models", [])

        if model_name:
            return [m for m in models if m.get("model_name") == model_name]
        
        return models

    def activate_model_version(self, model_name: str, version: int) -> Optional[Dict]:
        """
        Promotes a specific model version to 'production'.

        This action will also demote any existing 'production' version of the
        same model to 'staging' to ensure only one version is active at a time.

        Args:
            model_name: The name of the model to activate.
            version: The version number to promote.

        Returns:
            The updated model entry if successful, otherwise None.
        """
        registry = self._read_registry()
        models = registry.get("models", [])
        
        target_model = None
        
        for model in models:
            if model.get("model_name") == model_name:
                # Demote current production model if it exists
                if model.get("status") == "production":
                    model["status"] = "staging"
                # Find the target model to activate
                if model.get("version") == version:
                    target_model = model

        if not target_model:
            logger.warning(f"Model '{model_name}' version {version} not found.")
            return None

        target_model["status"] = "production"
        registry["models"] = models
        self._write_registry(registry)

        logger.info(f"Activated model '{model_name}' version {version} as production.")
        return target_model

    def get_production_model(self, model_name: str) -> Optional[Dict]:
        """
        Retrieves the metadata for the model currently marked as 'production'.

        Args:
            model_name: The name of the model to look for.

        Returns:
            The production model's entry dictionary, or None if not found.
        """
        models = self.list_models(model_name=model_name)
        for model in models:
            if model.get("status") == "production":
                return model
        
        logger.warning(f"No production model found for '{model_name}'.")
        return None
