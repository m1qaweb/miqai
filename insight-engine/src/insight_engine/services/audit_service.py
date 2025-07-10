import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditLogEntry(BaseModel):
    """Represents a single, structured entry in the audit log."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str  # User or system component performing the action
    action: str  # e.g., "MODEL_ROLLOUT_APPROVED", "RETRAINING_TRIGGERED"
    details: Dict[str, Any]  # Action-specific details
    previous_hash: str
    entry_hash: str


class AuditService:
    """
    Handles the creation and storage of tamper-evident audit logs using hash-chaining.

    This service ensures that all governance-related actions are logged in a way
    that makes unauthorized modification or deletion detectable. Each log entry is
    hashed with the hash of the previous entry, forming a blockchain-like chain.
    """

    def __init__(self, log_file_path: str):
        """
        Initializes the AuditService.

        Args:
            log_file_path: The path to the file where audit logs will be stored.
        """
        self.log_file_path = Path(log_file_path)
        self._lock = asyncio.Lock()
        self._ensure_log_file_exists()

    def _ensure_log_file_exists(self):
        """Ensures the log file and its parent directories exist."""
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_file_path.exists():
            self.log_file_path.touch()
            logger.info(f"Created audit log file at {self.log_file_path}")

    def _calculate_hash(self, content: str) -> str:
        """Calculates the SHA-256 hash of the given content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def get_last_log_hash(self) -> str:
        """
        Retrieves the hash of the most recent entry in the audit log.

        Returns:
            The hash of the last log entry, or a default genesis hash if the log is empty.
        """
        async with self._lock:
            if self.log_file_path.stat().st_size == 0:
                return self._calculate_hash("GENESIS_BLOCK")

            # In a real-world scenario with large files, this would need optimization.
            # For this project, reading the last line is acceptable.
            last_line = None
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    last_line = line

            if last_line:
                try:
                    last_log_data = json.loads(last_line)
                    return last_log_data.get(
                        "entry_hash", self._calculate_hash("GENESIS_BLOCK")
                    )
                except json.JSONDecodeError:
                    logger.error(
                        "Could not parse last line of audit log. Returning genesis hash."
                    )
                    return self._calculate_hash("GENESIS_BLOCK")
            return self._calculate_hash("GENESIS_BLOCK")

    async def log(
        self, actor: str, action: str, details: Dict[str, Any]
    ) -> AuditLogEntry:
        """
        Creates and stores a new audit log entry.

        This method is asynchronous and thread-safe.

        Args:
            actor: The identifier of the user or system performing the action.
            action: A string identifier for the action being logged.
            details: A dictionary of relevant details about the action.

        Returns:
            The created AuditLogEntry.
        """
        previous_hash = await self.get_last_log_hash()

        # Create timestamp ONCE to ensure consistency for hashing and storage.
        now = datetime.now(timezone.utc)

        entry_data_for_hashing = {
            "timestamp": now.isoformat(),
            "actor": actor,
            "action": action,
            "details": details,
            "previous_hash": previous_hash,
        }
        # Use canonical JSON format for consistent hashing
        canonical_json = json.dumps(
            entry_data_for_hashing, sort_keys=True, separators=(",", ":")
        )
        entry_hash = self._calculate_hash(canonical_json)

        # Explicitly pass the created timestamp to the model to override the default factory.
        log_entry = AuditLogEntry(
            timestamp=now,
            actor=actor,
            action=action,
            details=details,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )

        async with self._lock:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(log_entry.model_dump_json() + "\n")

        logger.info(f"Audit log: Actor='{actor}', Action='{action}'")
        return log_entry

    async def get_all_logs(self) -> List[AuditLogEntry]:
        """Retrieves all entries from the audit log."""
        logs = []
        if not self.log_file_path.exists():
            return logs

        with open(self.log_file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    logs.append(AuditLogEntry(**data))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Failed to parse audit log entry: {line}. Error: {e}")
        return logs

    async def verify_log_integrity(self) -> bool:
        """
        Verifies the entire audit log chain to detect tampering.

        Returns:
            True if the chain is valid, False otherwise.
        """
        logs = await self.get_all_logs()
        if not logs:
            return True  # An empty log is considered valid.

        current_previous_hash = self._calculate_hash("GENESIS_BLOCK")

        for entry in logs:
            if entry.previous_hash != current_previous_hash:
                logger.warning(
                    f"Log integrity check FAILED. Entry {entry.entry_hash} has mismatched previous_hash."
                )
                return False

            # Re-calculate hash to ensure entry content wasn't altered
            entry_data_for_hashing = {
                "timestamp": entry.timestamp.isoformat(),
                "actor": entry.actor,
                "action": entry.action,
                "details": entry.details,
                "previous_hash": entry.previous_hash,
            }
            canonical_json = json.dumps(
                entry_data_for_hashing, sort_keys=True, separators=(",", ":")
            )
            recalculated_hash = self._calculate_hash(canonical_json)

            if entry.entry_hash != recalculated_hash:
                logger.warning(
                    f"Log integrity check FAILED. Entry content for hash {entry.entry_hash} may have been altered."
                )
                return False

            current_previous_hash = entry.entry_hash

        logger.info("Audit log integrity check PASSED.")
        return True
