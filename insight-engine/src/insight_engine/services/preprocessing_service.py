# -*- coding: utf-8 -*-
"""
This service handles the preprocessing of video files, including
keyframe extraction, frame transformation, and resource-aware throttling.

This service was redesigned to use a strategy-driven perceptual hashing
approach for more robust and configurable keyframe extraction.
"""
import asyncio
import time
from typing import Generator, List, Callable, Dict
from PIL import Image
import imagehash

import cv2
import numpy as np
import psutil
from loguru import logger


class VideoPreprocessor:
    """
    Handles keyframe extraction using a configurable perceptual hashing strategy,
    plus frame transformation and resource-aware processing.
    """

    def __init__(self, config: dict):
        """
        Initializes the preprocessor with configuration.

        Args:
            config (dict): A dictionary containing keys like 'HASH_ALGORITHM',
                           'HASH_DISTANCE_THRESHOLD', 'HASH_SIZE', 'TARGET_SIZE',
                           'CPU_THRESHOLD', 'THROTTLE_DELAY'.
        """
        self.config = config
        # Dynamically select the hashing function based on config
        self.hash_algorithm: str = self.config.get("HASH_ALGORITHM", "phash")
        self.hash_func: Callable = getattr(imagehash, self.hash_algorithm)
        self.threshold: int = self.config.get("HASH_DISTANCE_THRESHOLD", 5)
        self.hash_size: int = self.config.get("HASH_SIZE", 8)
        self.target_size: tuple = self.config.get("TARGET_SIZE", (224, 224))
        self.cpu_threshold: int = self.config.get("CPU_THRESHOLD", 85)
        self.throttle_delay: float = self.config.get("THROTTLE_DELAY", 0.5)
        logger.info(
            f"VideoPreprocessor initialized with strategy: {self.hash_algorithm}"
        )

    def _throttle(self):
        """
        Pauses execution if CPU usage exceeds the configured threshold.
        """
        cpu_percent = psutil.cpu_percent()
        if cpu_percent > self.cpu_threshold:
            logger.warning(
                f"CPU usage {cpu_percent}% exceeded threshold of {self.cpu_threshold}%. Throttling for {self.throttle_delay}s."
            )
            time.sleep(self.throttle_delay)

    def _transform_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Resizes and normalizes a single frame.
        """
        # Resize
        resized_frame = cv2.resize(frame, self.target_size)
        # BGR to RGB
        rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
        # Normalize to [0, 1]
        normalized_frame = rgb_frame.astype(np.float32) / 255.0
        return normalized_frame

    def _compute_hash(self, frame: np.ndarray) -> imagehash.ImageHash:
        """
        Computes the perceptual hash of a single frame.
        """
        # Convert frame from OpenCV BGR to PIL RGB for hashing
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return self.hash_func(image, hash_size=self.hash_size)

    def _extract_frames(self, video_path: str) -> Generator[tuple[int, np.ndarray], None, None]:
        """
        A generator that extracts frames and their numbers from a video file.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Error opening video file: {video_path}")
            return

        frame_count = 0
        try:
            while cap.isOpened():
                self._throttle()
                ret, frame = cap.read()
                if not ret:
                    break
                frame_count += 1
                yield frame_count, frame
        finally:
            cap.release()
            logger.info(
                f"Finished processing {video_path}. Analyzed {frame_count} frames."
            )

    def extract_keyframes(self, video_path: str) -> Generator[np.ndarray, None, None]:
        """
        Extracts keyframes from a video file using the configured hashing strategy.
        """
        last_keyframe_hash = None
        for frame_count, frame in self._extract_frames(video_path):
            current_hash = self._compute_hash(frame)
            if (
                last_keyframe_hash is None
                or (current_hash - last_keyframe_hash) > self.threshold
            ):
                logger.debug(
                    f"Extracted keyframe at frame {frame_count} (hash diff > {self.threshold})"
                )
                last_keyframe_hash = current_hash
                yield self._transform_frame(frame)

    async def process_video(self, video_path: str) -> List[np.ndarray]:
        """
        Public method to orchestrate the video processing.
        """
        loop = asyncio.get_running_loop()

        def sync_process():
            return list(self.extract_keyframes(video_path))

        keyframes = await loop.run_in_executor(None, sync_process)
        logger.info(
            f"Extracted a total of {len(keyframes)} keyframes from {video_path}"
        )
        return keyframes

    async def process_video_with_frame_numbers(self, video_path: str) -> List[Dict]:
        """
        Public method that provides keyframes with their frame number and timestamp.
        """
        loop = asyncio.get_running_loop()

        def sync_process_with_info():
            keyframes_with_info = []
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return []
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()

            last_keyframe_hash = None
            for frame_count, frame in self._extract_frames(video_path):
                current_hash = self._compute_hash(frame)
                if (
                    last_keyframe_hash is None
                    or (current_hash - last_keyframe_hash) > self.threshold
                ):
                    last_keyframe_hash = current_hash
                    timestamp = frame_count / fps if fps > 0 else 0
                    transformed_frame = self._transform_frame(frame)
                    keyframes_with_info.append(
                        {
                            "frame": transformed_frame,
                            "frame_number": frame_count,
                            "timestamp": timestamp,
                        }
                    )
            return keyframes_with_info

        keyframes_with_info = await loop.run_in_executor(None, sync_process_with_info)
        logger.info(
            f"Extracted a total of {len(keyframes_with_info)} keyframes with info from {video_path}"
        )
        return keyframes_with_info
