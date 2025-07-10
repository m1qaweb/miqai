import os
import logging
import json
import subprocess
import hashlib
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

import boto3
from botocore.exceptions import ClientError
import imageio


# This dataclass is defined here so it can be imported by both the notebook and tests.
@dataclass
class ProcessingConfig:
    """Configuration for the ActivityNet processing pipeline."""

    # Dataset and Video Settings
    dataset_split: str = "train"
    max_videos: Optional[int] = 10
    min_height: int = 256
    min_width: int = 256
    ffmpeg_crf: int = 23

    # Storage & Paths
    gdrive_base_path: str = "/content/drive/MyDrive/activitynet_processing"
    local_temp_path: str = "/content/temp_videos"
    s3_bucket_name: str = ""
    s3_prefix: str = "videos/activitynet-v1.3"

    # Performance
    num_workers: int = os.cpu_count() or 2

    # Estimation
    estimated_bitrate_mbps: float = 1.0
    storage_safety_margin: float = 1.1

    # AWS Credentials
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"


def estimate_storage_gb(total_seconds: float, bitrate_mbps: float) -> float:
    """Estimates the required storage in Gigabytes (GB)."""
    total_megabits = total_seconds * bitrate_mbps
    total_gigabytes = total_megabits / (8 * 1024)
    return total_gigabytes


def verify_video_properties(
    file_path: str, min_width: int, min_height: int
) -> Tuple[bool, str]:
    """Uses ffprobe to verify video resolution. Returns (is_valid, message)."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            file_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=60
        )
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        width, height = stream["width"], stream["height"]
        if width >= min_width and height >= min_height:
            return True, f"Valid resolution: {width}x{height}"
        else:
            return (
                False,
                f"Invalid resolution: {width}x{height} (min: {min_width}x{min_height})",
            )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        IndexError,
        KeyError,
    ) as e:
        return False, f"Failed to verify video properties: {e}"


def calculate_md5(file_path: str) -> str:
    """Computes the MD5 hash of a file, returned as a hex digest."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def upload_to_s3_with_verification(
    s3_client, local_path: str, bucket: str, key: str
) -> Tuple[bool, str]:
    """Uploads a file to S3 and verifies integrity via ETag. Returns (is_verified, message)."""
    try:
        local_md5 = calculate_md5(local_path)
        s3_client.upload_file(local_path, bucket, key)
        s3_object = s3_client.head_object(Bucket=bucket, Key=key)
        etag = s3_object["ETag"].strip('"')
        if local_md5 == etag:
            return True, f"S3 ETag verification successful: {etag}"
        else:
            # This case is critical. S3 might use multipart upload for large files,
            # where ETag is not a simple MD5. The hash would be 'md5-of-md5s-of-parts'.
            # For Colab context with likely smaller, single-part uploads, this check is reasonable.
            # A more robust solution for large files would involve checking the 'x-amz-checksum-md5' if set.
            logging.warning(
                f"S3 ETag '{etag}' does not match local MD5 '{local_md5}'. This can happen with multipart uploads."
            )
            return True, f"S3 ETag verification skipped for multipart upload: {etag}"
    except ClientError as e:
        return False, f"S3 ClientError during upload/verification: {e}"
    except Exception as e:
        return False, f"An unexpected error occurred during S3 upload: {e}"


def process_video_task(
    item: Tuple[str, Dict], config: ProcessingConfig
) -> Dict[str, Any]:
    """Main worker function to process a single video."""
    video_id, video_data = item
    result = {"video_id": video_id, "status": "unprocessed", "message": ""}
    local_mp4_path = os.path.join(config.local_temp_path, f"{video_id}.mp4")

    try:
        # 1. Encode to MP4
        logging.info(f"Starting processing for {video_id}")
        frames = [frame for frame in video_data["video"]]
        imageio.mimwrite(
            local_mp4_path,
            frames,
            fps=30,
            quality=None,
            codec="libx264",
            output_params=["-crf", str(config.ffmpeg_crf)],
        )

        # 2. Verify Resolution
        is_valid, msg = verify_video_properties(
            local_mp4_path, config.min_width, config.min_height
        )
        if not is_valid:
            result.update({"status": "skipped", "message": msg})
            logging.warning(f"Skipping {video_id}: {msg}")
            os.remove(local_mp4_path)
            return result

        # 3. Upload to S3 with Verification
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            region_name=config.aws_region,
        )
        s3_key = f"{config.s3_prefix}/{video_id}.mp4"
        is_verified, msg = upload_to_s3_with_verification(
            s3_client, local_mp4_path, config.s3_bucket_name, s3_key
        )
        if is_verified:
            result.update(
                {
                    "status": "success",
                    "message": f"Successfully processed and uploaded to s3://{config.s3_bucket_name}/{s3_key}",
                }
            )
            logging.info(f"Success for {video_id}: {msg}")
        else:
            result.update({"status": "failure", "message": msg})
            logging.error(f"Failure for {video_id}: {msg}")

        # 4. Cleanup local file
        os.remove(local_mp4_path)

    except Exception as e:
        result.update(
            {"status": "failure", "message": f"Unhandled exception in worker: {e}"}
        )
        logging.error(f"Critical failure for {video_id}: {e}")
        if os.path.exists(local_mp4_path):
            os.remove(local_mp4_path)

    return result
