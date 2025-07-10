import logging
import httpx
import re
import yaml
from typing import Dict, List
from pydantic import ValidationError
from .models import PluginManifest
from .runtime import PluginRuntime

logger = logging.getLogger(__name__)

# A regex to validate that plugin names are safe, simple strings.
# This helps prevent path traversal or other injection attacks.
# Allows lowercase letters, numbers, and hyphens.
PLUGIN_NAME_REGEX = re.compile(r"^[a-z0-9-]+$")


class PluginManager:
    """
    Loads, validates, and manages the lifecycle of all plugins from a trusted repository.
    """

    def __init__(self, repository_url: str, public_key: bytes):
        """
        Initializes the PluginManager.

        Args:
            repository_url: The base URL of the trusted plugin artifact repository.
            public_key: The public key used to verify plugin signatures.
        """
        self.repository_url = repository_url
        self.public_key = public_key
        self.plugins: Dict[str, PluginRuntime] = {}
        self._client = httpx.Client()

    def load_plugin(self, plugin_name: str, version: str):
        """
        Fetches a specific plugin version from the repository, verifies it,
        and loads it into the runtime.
        """
        logger.info(
            f"Attempting to load plugin '{plugin_name}' v{version} from {self.repository_url}"
        )

        try:
            # Pre-flight check: Validate the plugin name format before making any network requests.
            if not PLUGIN_NAME_REGEX.match(plugin_name):
                logger.error(
                    f"Invalid plugin name format: '{plugin_name}'. Name must match regex: {PLUGIN_NAME_REGEX.pattern}"
                )
                return

            # 1. Fetch manifest
            manifest_url = (
                f"{self.repository_url}/plugins/{plugin_name}/{version}/plugin.yaml"
            )
            manifest_response = self._client.get(manifest_url)
            manifest_response.raise_for_status()
            manifest_data = yaml.safe_load(manifest_response.content)
            manifest = PluginManifest.model_validate(manifest_data)

            # Security Check: Ensure the name in the manifest matches the requested name.
            if manifest.identity.name != plugin_name:
                logger.error(
                    f"Manifest name '{manifest.identity.name}' does not match requested name '{plugin_name}'."
                )
                return

            # 2. Fetch WASM binary
            wasm_url = f"{self.repository_url}/plugins/{plugin_name}/{version}/{manifest.build.entrypoint}"
            wasm_response = self._client.get(wasm_url)
            wasm_response.raise_for_status()
            wasm_bytes = wasm_response.content

            # 3. Fetch signature
            sig_url = f"{self.repository_url}/plugins/{plugin_name}/{version}/{manifest.build.entrypoint}.sig"
            sig_response = self._client.get(sig_url)
            sig_response.raise_for_status()
            signature = sig_response.content

            # 4. Create and load runtime (verification happens inside)
            logger.info(f"WASM BYTES: {wasm_bytes}")
            logger.info(f"SIGNATURE: {signature}")
            runtime = PluginRuntime(
                manifest=manifest,
                wasm_bytes=wasm_bytes,
                signature=signature,
                public_key=self.public_key,
            )
            runtime.load()

            self.plugins[manifest.identity.name] = runtime
            logger.info(
                f"Successfully loaded plugin: {manifest.identity.name} v{manifest.identity.version}"
            )

        except (httpx.HTTPStatusError, ValidationError) as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}", exc_info=True)
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while loading plugin '{plugin_name}': {e}",
                exc_info=True,
            )

    def get_all_runtimes(self) -> List[PluginRuntime]:
        """Returns a list of all loaded plugin runtimes."""
        return list(self.plugins.values())

    def get_manifest(self, plugin_name: str) -> PluginManifest | None:
        """
        Retrieves the manifest for a specific plugin.

        Args:
            plugin_name: The name of the plugin.

        Returns:
            The plugin manifest, or None if not found.
        """
        return self.plugins.get(plugin_name)
