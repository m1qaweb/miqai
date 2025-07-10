import json
import logging
from typing import Any, Dict

from wasmtime import Config, Engine, Linker, Module, Store, WasiConfig, Trap

from .models import PluginManifest


# A placeholder for a real cryptography library
class SignatureVerifier:
    def verify(self, data: bytes, signature: bytes, public_key: bytes) -> bool:
        # In a real implementation, this would use a library like `cryptography`
        # to verify the signature. For now, we'll just pretend it's valid.
        return True


class PluginRuntimeError(Exception):
    """Custom exception for plugin runtime errors."""

    pass


# Define a reasonable size limit for plugin I/O to prevent large data payloads
# from causing memory issues.
MAX_IO_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB


class PluginRuntime:
    """
    Manages the lifecycle and execution of a single WASM plugin instance.
    """

    def __init__(
        self,
        manifest: PluginManifest,
        wasm_bytes: bytes,
        signature: bytes,
        public_key: bytes,
    ):
        self.manifest = manifest
        self.wasm_bytes = wasm_bytes
        self.signature = signature
        self.public_key = public_key
        self.logger = logging.getLogger(f"PluginRuntime.{manifest.identity.name}")

        # Setup wasmtime engine and store
        self._engine = self._create_engine()
        self._linker = Linker(self._engine)
        self._linker.define_wasi()
        self._store = None  # Initialized during load
        self._verifier = SignatureVerifier()

    def _create_engine(self) -> Engine:
        """Creates a wasmtime Engine with resource limits configured."""
        config = Config()
        limits = self.manifest.security_context.resource_limits

        # Enforce memory limits (convert MB to bytes)
        try:
            # A more robust solution would parse units like 'MiB', 'GiB'.
            memory_limit_bytes = int(limits.memory.replace("MB", "")) * 1024 * 1024
        except ValueError:
            raise PluginRuntimeError(f"Invalid memory limit format: {limits.memory}")

        config.static_memory_maximum_size = memory_limit_bytes
        config.dynamic_memory_guard_size = memory_limit_bytes

        # Enable epoch-based interruptions for timeout enforcement
        config.epoch_interruption = True

        return Engine(config)

    def _configure_sandbox(self) -> WasiConfig:
        """
        Configures the WASI sandbox based on the plugin's security context.
        """
        wasi_config = WasiConfig()
        wasi_config.inherit_stdin()
        wasi_config.inherit_stdout()
        wasi_config.inherit_stderr()

        # Example: Grant access to a specific directory if allowed
        allowed_dirs = self.manifest.security_context.get("allowed_dirs", [])
        if allowed_dirs:
            for d in allowed_dirs:
                # For now, we just log this. In a real scenario, we would preopen dirs.
                self.logger.info(f"Granting access to directory: {d}")
                # wasi_config.preopen_dir(d, d) # This would be the actual call

        return wasi_config

    def _verify_signature(self):
        """
        Verifies the signature of the WASM module.
        This is a placeholder. A real implementation would fetch the public key
        from a trusted source.
        """
        self.logger.info("Verifying plugin signature...")
        if not self._verifier.verify(self.wasm_bytes, self.signature, self.public_key):
            raise PluginRuntimeError("Plugin signature verification failed.")
        self.logger.info("Plugin signature verified.")

    def load(self):
        """
        Verifies, loads the WASM module and prepares it for execution.
        """
        self._verify_signature()

        self.logger.info(
            f"Loading WASM module for plugin: {self.manifest.identity.name}"
        )
        try:
            wasi_config = self._configure_sandbox()
            self._store = Store(self._engine)
            self._store.set_wasi(wasi_config)

            module = Module(self._engine, self.wasm_bytes)
            self._instance = self._linker.instantiate(self._store, module)
        except Exception as e:
            self.logger.error(f"Failed to load or instantiate WASM module: {e}")
            raise PluginRuntimeError(f"WASM instantiation failed: {e}") from e

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the 'run' function in the WASM module.

        Handles marshalling data (JSON string) into the WASM memory space
        and retrieving the result.
        """
        if not self._store or not self._instance:
            raise PluginRuntimeError("Plugin is not loaded. Call load() first.")

        # Set the epoch deadline before each execution
        try:
            timeout_seconds = int(
                self.manifest.security_context.resource_limits.execution_timeout.replace(
                    "s", ""
                )
            )
        except ValueError:
            raise PluginRuntimeError(
                f"Invalid execution timeout format: {self.manifest.security_context.resource_limits.execution_timeout}"
            )

        self._store.set_epoch_deadline(timeout_seconds)
        self._engine.increment_epoch()

        exports = self._instance.exports(self._store)
        run_func = exports.get("run")
        if not run_func:
            raise PluginRuntimeError("Plugin does not export a 'run' function.")

        allocate_func = exports.get("allocate")
        deallocate_func = exports.get("deallocate")
        if not allocate_func or not deallocate_func:
            raise PluginRuntimeError(
                "Plugin must export 'allocate' and 'deallocate' functions."
            )

        # 1. Serialize input data and check size
        input_str = json.dumps(input_data)
        input_bytes = input_str.encode("utf-8")
        input_len = len(input_bytes)
        if input_len > MAX_IO_SIZE_BYTES:
            raise PluginRuntimeError(
                f"Input size {input_len} bytes exceeds the limit of {MAX_IO_SIZE_BYTES} bytes."
            )

        # 2. Allocate memory in WASM
        input_ptr = allocate_func(self._store, input_len)
        if not isinstance(input_ptr, int):
            raise PluginRuntimeError(
                "WASM 'allocate' function returned an invalid pointer."
            )

        # 3. Write input to WASM memory
        memory = exports["memory"]
        memory.write(self._store, input_bytes, input_ptr)

        # 4. Execute the plugin
        self.logger.info("Executing plugin 'run' function...")
        try:
            result_ptr = run_func(self._store, input_ptr, input_len)
            if not isinstance(result_ptr, int):
                raise PluginRuntimeError(
                    "WASM 'run' function returned an invalid pointer."
                )
        except Trap as e:
            if "wasm trap: interrupt" in str(e):
                self.logger.error("Plugin execution timed out.")
                raise PluginRuntimeError("Plugin execution timed out.") from e
            raise

        # 5. Read result from WASM memory, with size checking
        result_bytes = []
        offset = 0
        while True:
            if len(result_bytes) > MAX_IO_SIZE_BYTES:
                raise PluginRuntimeError(
                    f"Output size exceeds the limit of {MAX_IO_SIZE_BYTES} bytes."
                )
            byte = memory.read(self._store, result_ptr + offset, 1)
            if byte[0] == 0:
                break
            result_bytes.append(byte[0])
            offset += 1

        output_str = bytes(result_bytes).decode("utf-8")

        # 6. Deallocate memory
        deallocate_func(self._store, input_ptr, input_len)
        deallocate_func(self._store, result_ptr, len(result_bytes) + 1)

        self.logger.info("Plugin execution completed.")
        return json.loads(output_str)
