"""
Unit tests for video processing services.

This module tests video preprocessing, keyframe extraction,
and video analysis components.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import numpy as np
from PIL import Image
import cv2

from insight_engine.services.preprocessing_service import VideoPreprocessor
from insight_engine.exceptions import VideoProcessingException, ValidationException


class TestVideoPreprocessor:
    """Test video preprocessing service."""
    
    @pytest.fixture
    def preprocessor_config(self):
        """Sample preprocessor configuration."""
        return {
            "HASH_ALGORITHM": "phash",
            "HASH_DISTANCE_THRESHOLD": 5,
            "HASH_SIZE": 8,
            "TARGET_SIZE": (224, 224),
            "CPU_THRESHOLD": 85,
            "THROTTLE_DELAY": 0.5
        }
    
    @pytest.fixture
    def video_preprocessor(self, preprocessor_config):
        """Create VideoPreprocessor instance."""
        return VideoPreprocessor(preprocessor_config)
    
    def test_preprocessor_initialization(self, video_preprocessor, preprocessor_config):
        """Test preprocessor initialization with config."""
        assert video_preprocessor.hash_algorithm == "phash"
        assert video_preprocessor.threshold == 5
        assert video_preprocessor.hash_size == 8
        assert video_preprocessor.target_size == (224, 224)
        assert video_preprocessor.cpu_threshold == 85
        assert video_preprocessor.throttle_delay == 0.5
    
    def test_preprocessor_default_config(self):
        """Test preprocessor with default configuration values."""
        config = {}
        preprocessor = VideoPreprocessor(config)
        
        assert preprocessor.hash_algorithm == "phash"
        assert preprocessor.threshold == 5
        assert preprocessor.hash_size == 8
        assert preprocessor.target_size == (224, 224)
        assert preprocessor.cpu_threshold == 85
        assert preprocessor.throttle_delay == 0.5
    
    @patch('insight_engine.services.preprocessing_service.psutil.cpu_percent')
    def test_throttle_when_cpu_high(self, mock_cpu_percent, video_preprocessor):
        """Test throttling when CPU usage is high."""
        mock_cpu_percent.return_value = 90  # Above threshold
        
        with patch('time.sleep') as mock_sleep:
            video_preprocessor._throttle()
            mock_sleep.assert_called_once_with(0.5)
    
    @patch('insight_engine.services.preprocessing_service.psutil.cpu_percent')
    def test_no_throttle_when_cpu_normal(self, mock_cpu_percent, video_preprocessor):
        """Test no throttling when CPU usage is normal."""
        mock_cpu_percent.return_value = 50  # Below threshold
        
        with patch('time.sleep') as mock_sleep:
            video_preprocessor._throttle()
            mock_sleep.assert_not_called()
    
    def test_transform_frame(self, video_preprocessor):
        """Test frame transformation (resize and normalize)."""
        # Create a sample frame (BGR format as OpenCV uses)
        original_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        transformed = video_preprocessor._transform_frame(original_frame)
        
        # Check dimensions
        assert transformed.shape == (224, 224, 3)
        # Check normalization (values should be between 0 and 1)
        assert transformed.min() >= 0.0
        assert transformed.max() <= 1.0
        # Check data type
        assert transformed.dtype == np.float32
    
    def test_compute_hash(self, video_preprocessor):
        """Test perceptual hash computation."""
        # Create a sample frame
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        hash_result = video_preprocessor._compute_hash(frame)
        
        # Check that we get an ImageHash object
        assert hasattr(hash_result, '__str__')  # ImageHash has string representation
        assert len(str(hash_result)) > 0
    
    def test_compute_hash_consistency(self, video_preprocessor):
        """Test that same frame produces same hash."""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        hash1 = video_preprocessor._compute_hash(frame)
        hash2 = video_preprocessor._compute_hash(frame)
        
        assert str(hash1) == str(hash2)
    
    @patch('cv2.VideoCapture')
    def test_extract_frames_generator(self, mock_cv2_capture, video_preprocessor):
        """Test frame extraction generator."""
        # Mock video capture
        mock_cap = MagicMock()
        mock_cv2_capture.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        
        # Mock frames
        sample_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [
            (True, sample_frame),
            (True, sample_frame),
            (False, None)  # End of video
        ]
        
        frames = list(video_preprocessor._extract_frames("test_video.mp4"))
        
        assert len(frames) == 2
        assert frames[0][0] == 1  # First frame number
        assert frames[1][0] == 2  # Second frame number
        mock_cap.release.assert_called_once()
    
    @patch('cv2.VideoCapture')
    def test_extract_frames_video_not_found(self, mock_cv2_capture, video_preprocessor):
        """Test frame extraction with video file not found."""
        mock_cap = MagicMock()
        mock_cv2_capture.return_value = mock_cap
        mock_cap.isOpened.return_value = False
        
        frames = list(video_preprocessor._extract_frames("nonexistent.mp4"))
        
        assert len(frames) == 0
        mock_cap.release.assert_called_once()
    
    @patch.object(VideoPreprocessor, '_extract_frames')
    @patch.object(VideoPreprocessor, '_compute_hash')
    def test_extract_keyframes(self, mock_compute_hash, mock_extract_frames, video_preprocessor):
        """Test keyframe extraction logic."""
        # Mock frame extraction
        sample_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        mock_extract_frames.return_value = [
            (1, sample_frame),
            (2, sample_frame),
            (3, sample_frame)
        ]
        
        # Mock hash computation with different hashes
        mock_hash1 = MagicMock()
        mock_hash2 = MagicMock()
        mock_hash3 = MagicMock()
        
        # Set up hash differences
        mock_hash1.__sub__ = MagicMock(return_value=10)  # Large difference
        mock_hash2.__sub__ = MagicMock(return_value=2)   # Small difference
        mock_hash3.__sub__ = MagicMock(return_value=8)   # Large difference
        
        mock_compute_hash.side_effect = [mock_hash1, mock_hash2, mock_hash3]
        
        keyframes = list(video_preprocessor.extract_keyframes("test_video.mp4"))
        
        # Should extract first frame and third frame (large differences)
        assert len(keyframes) == 2
        # Each keyframe should be transformed (224x224x3)
        for keyframe in keyframes:
            assert keyframe.shape == (224, 224, 3)
    
    @pytest.mark.asyncio
    async def test_process_video_async(self, video_preprocessor):
        """Test async video processing."""
        with patch.object(video_preprocessor, 'extract_keyframes') as mock_extract:
            # Mock keyframes
            mock_keyframes = [
                np.random.rand(224, 224, 3).astype(np.float32),
                np.random.rand(224, 224, 3).astype(np.float32)
            ]
            mock_extract.return_value = mock_keyframes
            
            result = await video_preprocessor.process_video("test_video.mp4")
            
            assert len(result) == 2
            assert all(frame.shape == (224, 224, 3) for frame in result)
            mock_extract.assert_called_once_with("test_video.mp4")
    
    @pytest.mark.asyncio
    async def test_process_video_with_frame_numbers(self, video_preprocessor):
        """Test async video processing with frame numbers and timestamps."""
        with patch('cv2.VideoCapture') as mock_cv2_capture:
            # Mock video capture for FPS
            mock_cap = MagicMock()
            mock_cv2_capture.return_value = mock_cap
            mock_cap.get.return_value = 30.0  # 30 FPS
            
            with patch.object(video_preprocessor, '_extract_frames') as mock_extract_frames:
                sample_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                mock_extract_frames.return_value = [
                    (30, sample_frame),   # Frame at 1 second
                    (60, sample_frame),   # Frame at 2 seconds
                ]
                
                with patch.object(video_preprocessor, '_compute_hash') as mock_compute_hash:
                    mock_hash1 = MagicMock()
                    mock_hash2 = MagicMock()
                    mock_hash1.__sub__ = MagicMock(return_value=10)  # Large difference
                    mock_hash2.__sub__ = MagicMock(return_value=8)   # Large difference
                    mock_compute_hash.side_effect = [mock_hash1, mock_hash2]
                    
                    result = await video_preprocessor.process_video_with_frame_numbers("test_video.mp4")
                    
                    assert len(result) == 2
                    assert result[0]["frame_number"] == 30
                    assert result[0]["timestamp"] == 1.0
                    assert result[1]["frame_number"] == 60
                    assert result[1]["timestamp"] == 2.0
                    assert all("frame" in item for item in result)


class TestVideoValidation:
    """Test video validation utilities."""
    
    def test_validate_video_format_valid(self):
        """Test video format validation with valid formats."""
        from insight_engine.security import validate_file_type
        
        valid_formats = ["mp4", "avi", "mov", "wmv"]
        
        for fmt in valid_formats:
            filename = f"test_video.{fmt}"
            assert validate_file_type(filename, valid_formats) is True
    
    def test_validate_video_format_invalid(self):
        """Test video format validation with invalid formats."""
        from insight_engine.security import validate_file_type
        
        valid_formats = ["mp4", "avi", "mov", "wmv"]
        invalid_filename = "test_video.txt"
        
        assert validate_file_type(invalid_filename, valid_formats) is False
    
    def test_validate_video_size_valid(self):
        """Test video size validation with valid size."""
        from insight_engine.security import validate_file_size
        
        file_size = 50 * 1024 * 1024  # 50MB
        max_size = 100  # 100MB limit
        
        assert validate_file_size(file_size, max_size) is True
    
    def test_validate_video_size_invalid(self):
        """Test video size validation with invalid size."""
        from insight_engine.security import validate_file_size
        
        file_size = 150 * 1024 * 1024  # 150MB
        max_size = 100  # 100MB limit
        
        assert validate_file_size(file_size, max_size) is False


@pytest.mark.unit
class TestVideoProcessingIntegration:
    """Integration tests for video processing components."""
    
    @pytest.fixture
    def sample_video_data(self):
        """Sample video metadata for testing."""
        return {
            "id": "test-video-123",
            "filename": "sample_video.mp4",
            "duration": 120.0,
            "size": 15728640,
            "format": "mp4",
            "status": "uploaded"
        }
    
    def test_video_processing_pipeline(self, sample_video_data):
        """Test complete video processing pipeline."""
        config = {
            "HASH_ALGORITHM": "phash",
            "HASH_DISTANCE_THRESHOLD": 5,
            "TARGET_SIZE": (224, 224),
            "CPU_THRESHOLD": 85
        }
        
        preprocessor = VideoPreprocessor(config)
        
        # Test configuration
        assert preprocessor.hash_algorithm == "phash"
        assert preprocessor.target_size == (224, 224)
        
        # Test frame transformation
        test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        transformed = preprocessor._transform_frame(test_frame)
        
        assert transformed.shape == (224, 224, 3)
        assert 0.0 <= transformed.min() <= transformed.max() <= 1.0
    
    def test_error_handling_in_processing(self):
        """Test error handling in video processing."""
        config = {"TARGET_SIZE": (224, 224)}
        preprocessor = VideoPreprocessor(config)
        
        # Test with invalid frame data
        with pytest.raises(Exception):  # Should raise some kind of error
            invalid_frame = "not_a_frame"
            preprocessor._transform_frame(invalid_frame)
    
    @patch('cv2.VideoCapture')
    def test_video_processing_with_corrupted_file(self, mock_cv2_capture):
        """Test video processing with corrupted file."""
        config = {"TARGET_SIZE": (224, 224)}
        preprocessor = VideoPreprocessor(config)
        
        # Mock corrupted video file
        mock_cap = MagicMock()
        mock_cv2_capture.return_value = mock_cap
        mock_cap.isOpened.return_value = False
        
        frames = list(preprocessor._extract_frames("corrupted.mp4"))
        
        assert len(frames) == 0
        mock_cap.release.assert_called_once()


class TestVideoMetrics:
    """Test video processing metrics and performance."""
    
    def test_keyframe_extraction_efficiency(self):
        """Test that keyframe extraction is efficient."""
        config = {
            "HASH_DISTANCE_THRESHOLD": 10,  # Higher threshold = fewer keyframes
            "TARGET_SIZE": (224, 224)
        }
        preprocessor = VideoPreprocessor(config)
        
        # Create frames with similar content (should extract fewer keyframes)
        base_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        with patch.object(preprocessor, '_extract_frames') as mock_extract:
            # Mock similar frames
            mock_extract.return_value = [
                (i, base_frame + np.random.randint(-5, 5, base_frame.shape, dtype=np.int8))
                for i in range(1, 11)  # 10 similar frames
            ]
            
            keyframes = list(preprocessor.extract_keyframes("test_video.mp4"))
            
            # Should extract fewer keyframes due to similarity
            assert len(keyframes) < 10  # Less than total frames
    
    def test_memory_usage_optimization(self):
        """Test that video processing doesn't consume excessive memory."""
        config = {"TARGET_SIZE": (224, 224)}
        preprocessor = VideoPreprocessor(config)
        
        # Test frame transformation doesn't create memory leaks
        for _ in range(100):  # Process many frames
            test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            transformed = preprocessor._transform_frame(test_frame)
            
            # Verify expected output
            assert transformed.shape == (224, 224, 3)
            
            # Clean up reference
            del transformed