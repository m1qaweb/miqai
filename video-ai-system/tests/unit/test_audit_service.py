import asyncio
import json
from pathlib import Path

import pytest
from video_ai_system.services.audit_service import AuditService, AuditLogEntry


@pytest.fixture
def audit_log_file(tmp_path: Path) -> Path:
    """Provides a temporary file path for the audit log."""
    return tmp_path / "test_audit.log"


@pytest.fixture
def audit_service(audit_log_file: Path) -> AuditService:
    """Provides an instance of the AuditService."""
    return AuditService(log_file_path=audit_log_file)


@pytest.mark.asyncio
async def test_initialization_creates_log_file(audit_log_file: Path):
    """Test that the AuditService creates the log file if it doesn't exist."""
    assert not audit_log_file.exists()
    _ = AuditService(log_file_path=audit_log_file)
    assert audit_log_file.exists()


@pytest.mark.asyncio
async def test_get_last_log_hash_on_empty_log(audit_service: AuditService):
    """Test that the genesis hash is returned when the log is empty."""
    last_hash = await audit_service.get_last_log_hash()
    assert last_hash == audit_service._calculate_hash("GENESIS_BLOCK")


@pytest.mark.asyncio
async def test_log_creates_valid_entry(audit_service: AuditService):
    """Test that a single log entry is created correctly."""
    actor = "test_user"
    action = "TEST_ACTION"
    details = {"key": "value"}

    log_entry = await audit_service.log(actor, action, details)

    assert log_entry.actor == actor
    assert log_entry.action == action
    assert log_entry.details == details
    assert log_entry.previous_hash == audit_service._calculate_hash("GENESIS_BLOCK")

    # Verify the entry hash
    entry_data_for_hashing = {
        "timestamp": log_entry.timestamp.isoformat(),
        "actor": actor,
        "action": action,
        "details": details,
        "previous_hash": log_entry.previous_hash,
    }
    canonical_json = json.dumps(entry_data_for_hashing, sort_keys=True, separators=(",", ":"))
    expected_hash = audit_service._calculate_hash(canonical_json)
    assert log_entry.entry_hash == expected_hash


@pytest.mark.asyncio
async def test_log_chaining(audit_service: AuditService):
    """Test that subsequent log entries correctly chain their hashes."""
    entry1 = await audit_service.log("user1", "ACTION_1", {"data": 1})
    entry2 = await audit_service.log("user2", "ACTION_2", {"data": 2})

    assert entry2.previous_hash == entry1.entry_hash


@pytest.mark.asyncio
async def test_get_all_logs(audit_service: AuditService, audit_log_file: Path):
    """Test retrieving all logs from the log file."""
    await audit_service.log("user1", "ACTION_1", {})
    await audit_service.log("user2", "ACTION_2", {})

    logs = await audit_service.get_all_logs()
    assert len(logs) == 2
    assert isinstance(logs[0], AuditLogEntry)
    assert logs[0].action == "ACTION_1"
    assert logs[1].action == "ACTION_2"

    # Test with empty file
    audit_log_file.unlink()
    audit_log_file.touch()
    logs = await audit_service.get_all_logs()
    assert len(logs) == 0


@pytest.mark.asyncio
async def test_verify_log_integrity_valid_chain(audit_service: AuditService):
    """Test that the integrity check passes for a valid, unmodified log."""
    await audit_service.log("user1", "LOGIN", {})
    await audit_service.log("user2", "CREATE_RESOURCE", {"id": "res1"})
    await audit_service.log("user1", "DELETE_RESOURCE", {"id": "res1"})

    assert await audit_service.verify_log_integrity() is True


@pytest.mark.asyncio
async def test_verify_log_integrity_broken_previous_hash(audit_service: AuditService, audit_log_file: Path):
    """Test that integrity check fails if a previous_hash link is broken."""
    await audit_service.log("user1", "ACTION_1", {})
    entry2 = await audit_service.log("user2", "ACTION_2", {})

    # Manually tamper with the log file
    with open(audit_log_file, "r+") as f:
        lines = f.readlines()
        log2_data = json.loads(lines[1])
        log2_data["previous_hash"] = "tampered_hash"
        lines[1] = json.dumps(log2_data) + "\n"
        f.seek(0)
        f.writelines(lines)

    # Re-initialize service to clear any in-memory state if necessary
    fresh_audit_service = AuditService(audit_log_file)
    assert await fresh_audit_service.verify_log_integrity() is False


@pytest.mark.asyncio
async def test_verify_log_integrity_tampered_content(audit_service: AuditService, audit_log_file: Path):
    """Test that integrity check fails if an entry's content is altered."""
    await audit_service.log("user1", "ACTION_1", {"data": "original"})
    await audit_service.log("user2", "ACTION_2", {})

    # Manually tamper with the log file content
    with open(audit_log_file, "r+") as f:
        lines = f.readlines()
        log1_data = json.loads(lines[0])
        log1_data["details"]["data"] = "tampered"  # Change the content
        lines[0] = json.dumps(log1_data) + "\n"
        f.seek(0)
        f.writelines(lines)
        f.truncate()

    fresh_audit_service = AuditService(audit_log_file)
    assert await fresh_audit_service.verify_log_integrity() is False


@pytest.mark.asyncio
async def test_concurrent_logging(audit_service: AuditService):
    """Test that concurrent log writes do not corrupt the hash chain."""
    tasks = [
        audit_service.log(f"actor_{i}", f"ACTION_{i}", {"i": i})
        for i in range(10)
    ]
    await asyncio.gather(*tasks)

    # The ultimate test is whether the final chain is valid
    assert await audit_service.verify_log_integrity() is True
    logs = await audit_service.get_all_logs()
    assert len(logs) == 10