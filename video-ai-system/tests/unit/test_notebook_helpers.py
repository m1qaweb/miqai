import pytest
import json
import subprocess
from unittest.mock import patch, MagicMock

from video_ai_system.notebook_helpers import (
    ProcessingConfig,
    estimate_storage_gb,
    calculate_md5,
    verify_video_properties,
    upload_to_s3_with_verification,
)

@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file with known content for testing."""
    p = tmp_path / "test_file.txt"
    content = b"hello world"
    p.write_bytes(content)
    return p, content

@pytest.fixture
def config():
    """Provides a default ProcessingConfig for tests."""
    return ProcessingConfig(
        s3_bucket_name="test-bucket",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret"
    )

def test_estimate_storage_gb():
    """Tests the storage estimation logic."""
    # 1 hour (3600 seconds) at 8 Mbps should be 3.515625 GB
    # (3600s * 8 Mb/s) / (8 bits/byte * 1024 MB/GB) = 3.515625 GB
    assert abs(estimate_storage_gb(3600, 8) - 3.515625) < 1e-9
    assert estimate_storage_gb(0, 8) == 0

def test_calculate_md5(temp_file):
    """Tests that the MD5 hash calculation is correct."""
    file_path, content = temp_file
    # MD5 hash of "hello world"
    expected_md5 = "5eb63bbbe01eeed093cb22bb8f5acdc3"
    assert calculate_md5(str(file_path)) == expected_md5

@patch('subprocess.run')
def test_verify_video_properties_valid(mock_run):
    """Tests ffprobe verification for a valid video."""
    ffprobe_output = {
        "streams": [{"width": 1920, "height": 1080}]
    }
    mock_run.return_value = MagicMock(
        stdout=json.dumps(ffprobe_output),
        stderr="",
        returncode=0
    )
    is_valid, msg = verify_video_properties("dummy.mp4", 256, 256)
    assert is_valid
    assert "Valid resolution: 1920x1080" in msg

@patch('subprocess.run')
def test_verify_video_properties_invalid_resolution(mock_run):
    """Tests ffprobe verification for a video with insufficient resolution."""
    ffprobe_output = {
        "streams": [{"width": 100, "height": 100}]
    }
    mock_run.return_value = MagicMock(
        stdout=json.dumps(ffprobe_output),
        stderr="",
        returncode=0
    )
    is_valid, msg = verify_video_properties("dummy.mp4", 256, 256)
    assert not is_valid
    assert "Invalid resolution: 100x100" in msg

@patch('subprocess.run')
def test_verify_video_properties_ffprobe_error(mock_run):
    """Tests handling of a subprocess error from ffprobe."""
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="ffprobe error")
    is_valid, msg = verify_video_properties("dummy.mp4", 256, 256)
    assert not is_valid
    assert "Failed to verify video properties" in msg

@patch('video_ai_system.notebook_helpers.calculate_md5')
def test_upload_to_s3_with_verification_success(mock_md5, config):
    """Tests a successful S3 upload and ETag verification."""
    mock_s3_client = MagicMock()
    mock_md5.return_value = "test_md5_hash"
    mock_s3_client.head_object.return_value = {'ETag': '"test_md5_hash"'}

    is_verified, msg = upload_to_s3_with_verification(
        mock_s3_client, "local/file.mp4", config.s3_bucket_name, "s3/key.mp4"
    )

    assert is_verified
    assert "S3 ETag verification successful" in msg
    mock_s3_client.upload_file.assert_called_once_with(
        "local/file.mp4", "test-bucket", "s3/key.mp4"
    )

@patch('video_ai_system.notebook_helpers.calculate_md5')
def test_upload_to_s3_with_verification_etag_mismatch(mock_md5, config):
    """Tests a failed S3 upload due to an ETag mismatch (multipart upload)."""
    mock_s3_client = MagicMock()
    mock_md5.return_value = "local_md5_hash"
    # S3 ETag for multipart uploads ends with -N
    mock_s3_client.head_object.return_value = {'ETag': '"some-other-hash-1"'}

    is_verified, msg = upload_to_s3_with_verification(
        mock_s3_client, "local/file.mp4", config.s3_bucket_name, "s3/key.mp4"
    )
    
    # The logic was updated to treat multipart ETags as a success with a warning
    assert is_verified
    assert "S3 ETag verification skipped for multipart upload" in msg

@patch('video_ai_system.notebook_helpers.calculate_md5')
def test_upload_to_s3_client_error(mock_md5, config):
    """Tests handling of a Boto3 ClientError during upload."""
    mock_s3_client = MagicMock()
    mock_md5.return_value = "local_md5_hash"
    from botocore.exceptions import ClientError
    mock_s3_client.upload_file.side_effect = ClientError({'Error': {'Code': 'AccessDenied'}}, 'UploadFile')

    is_verified, msg = upload_to_s3_with_verification(
        mock_s3_client, "local/file.mp4", config.s3_bucket_name, "s3/key.mp4"
    )

    assert not is_verified
    assert "S3 ClientError" in msg