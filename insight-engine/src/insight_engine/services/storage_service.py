"""
Service for handling file uploads to a simulated cloud storage bucket.
"""
import os
import shutil
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class StorageService:
    """
    A service to manage file transfers to a simulated cloud storage bucket.
    In a real production environment, this would be replaced with a client
    for a cloud storage provider like Google Cloud Storage or AWS S3.
    """

    def __init__(self, bucket_path: str = "cloud_storage_bucket"):
        """
        Initializes the StorageService.

        Args:
            bucket_path: The local directory to use as the simulated bucket.
        """
        self.bucket_path = Path(bucket_path)
        self.bucket_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"StorageService initialized with bucket at: {self.bucket_path.resolve()}")

    def upload_file(self, source_path: str) -> str:
        """
        "Uploads" a file by copying it to the local bucket directory.

        Args:
            source_path: The path to the local file to upload.

        Returns:
            The path to the file in the "bucket".
        """
        source_file = Path(source_path)
        if not source_file.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        destination_path = self.bucket_path / source_file.name
        
        try:
            shutil.copy(source_file, destination_path)
            logger.info(f"Successfully 'uploaded' {source_path} to {destination_path}")
            return str(destination_path)
        except Exception as e:
            logger.error(f"Failed to 'upload' file {source_path}: {e}")
            raise
