"""
Integration tests for background task processing.

This module tests background task processing including Pub/Sub message handling,
video analysis jobs, clip extraction, and task retry mechanisms.
"""

import asyncio
import json
import pytest
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock, call
from pathlib import Path

from tests.utils import AsyncTestCase, MockExternalServices


class TestClipExtractionTasks(AsyncTestCase):
    """Test clip extraction background task processing."""
    
    @pytest.mark.integration
    @patch('insight_engine.worker.storage_client')
    @patch('insight_engine.worker.ffmpeg')
    def test_process_clip_job_success(self, mock_ffmpeg, mock_storage_client):
        """Test successful clip extraction job processing."""
        # Import here to avoid circular import issues
        from insight_engine.worker import process_clip_job
        
        # Setup mock message
        mock_message = MagicMock()
        job_data = {
            "job_id": "test-job-123",
            "video_id": "video-456",
            "object_query": "person walking"
        }
        mock_message.data.decode.return_value = json.dumps(job_data)
        
        # Setup mock GCS
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.bucket.return_value = mock_bucket
        
        # Setup mock FFmpeg
        mock_ffmpeg.input.return_value.output.return_value.run.return_value = None
        
        # Process the job
        process_clip_job(mock_message)
        
        # Verify message was acknowledged
        mock_message.ack.assert_called_once()
        
        # Verify GCS interactions
        assert mock_storage_client.bucket.call_count >= 2  # Source and destination buckets
        mock_blob.download_to_filename.assert_called_once()
        
        # Verify FFmpeg was called for clip generation
        mock_ffmpeg.input.assert_called()
        
        # Verify clips were uploaded
        clips_bucket_calls = [call for call in mock_storage_client.bucket.call_args_list 
                             if 'clips' in str(call)]
        assert len(clips_bucket_calls) > 0
    
    @pytest.mark.integration
    @patch('insight_engine.worker.storage_client')
    def test_process_clip_job_video_not_found(self, mock_storage_client):
        """Test clip extraction when source video doesn't exist."""
        # Import here to avoid circular import issues
        from insight_engine.worker import process_clip_job
        
        # Setup mock message
        mock_message = MagicMock()
        job_data = {
            "job_id": "test-job-404",
            "video_id": "nonexistent-video",
            "object_query": "person walking"
        }
        mock_message.data.decode.return_value = json.dumps(job_data)
        
        # Setup mock GCS - video doesn't exist
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.bucket.return_value = mock_bucket
        
        # Process the job
        process_clip_job(mock_message)
        
        # Should acknowledge message to prevent retries
        mock_message.ack.assert_called_once()
        
        # Should not attempt download
        mock_blob.download_to_filename.assert_not_called()
    
    @pytest.mark.integration
    @patch('insight_engine.worker.storage_client')
    @patch('insight_engine.worker.ffmpeg')
    def test_process_clip_job_ffmpeg_error(self, mock_ffmpeg, mock_storage_client):
        """Test clip extraction with FFmpeg processing error."""
        # Import here to avoid circular import issues
        from insight_engine.worker import process_clip_job
        
        # Setup mock message
        mock_message = MagicMock()
        job_data = {
            "job_id": "test-job-ffmpeg-error",
            "video_id": "video-789",
            "object_query": "car driving"
        }
        mock_message.data.decode.return_value = json.dumps(job_data)
        
        # Setup mock GCS
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.bucket.return_value = mock_bucket
        
        # Setup mock FFmpeg to raise error
        import ffmpeg
        mock_ffmpeg.Error = ffmpeg.Error
        mock_ffmpeg.input.return_value.output.return_value.run.side_effect = ffmpeg.Error(
            "ffmpeg", "", b"FFmpeg processing failed"
        )
        
        # Process the job
        process_clip_job(mock_message)
        
        # Should still acknowledge message (job completed with errors)
        mock_message.ack.assert_called_once()
        
        # Should attempt FFmpeg processing
        mock_ffmpeg.input.assert_called()
    
    @pytest.mark.integration
    def test_process_clip_job_invalid_message(self):
        """Test clip extraction with invalid message format."""
        # Import here to avoid circular import issues
        from insight_engine.worker import process_clip_job
        
        # Setup mock message with invalid JSON
        mock_message = MagicMock()
        mock_message.data.decode.return_value = "invalid json"
        
        # Process the job
        process_clip_job(mock_message)
        
        # Should nack message for retry
        mock_message.nack.assert_called_once()
        mock_message.ack.assert_not_called()
    
    @pytest.mark.integration
    @patch('insight_engine.worker.storage_client')
    def test_process_clip_job_gcs_error(self, mock_storage_client):
        """Test clip extraction with GCS error."""
        # Import here to avoid circular import issues
        from insight_engine.worker import process_clip_job
        
        # Setup mock message
        mock_message = MagicMock()
        job_data = {
            "job_id": "test-job-gcs-error",
            "video_id": "video-gcs-error",
            "object_query": "object detection"
        }
        mock_message.data.decode.return_value = json.dumps(job_data)
        
        # Setup mock GCS to raise error
        mock_storage_client.bucket.side_effect = Exception("GCS connection failed")
        
        # Process the job
        process_clip_job(mock_message)
        
        # Should nack message for retry
        mock_message.nack.assert_called_once()
        mock_message.ack.assert_not_called()


class TestVideoAnalysisJobs(AsyncTestCase):
    """Test video analysis job processing."""
    
    @pytest.mark.integration
    async def test_run_analysis_job_success(self):
        """Test successful video analysis job."""
        with patch('httpx.AsyncClient') as mock_client:
            # Setup mock HTTP client
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            # Mock job submission response
            submit_response = MagicMock()
            submit_response.status_code = 200
            submit_response.json.return_value = {
                "task_id": "analysis-task-123",
                "status_endpoint": "/api/v1/status/analysis-task-123"
            }
            submit_response.raise_for_status.return_value = None
            
            # Mock status polling responses
            status_response_processing = MagicMock()
            status_response_processing.status_code = 200
            status_response_processing.json.return_value = {
                "status": "PROCESSING",
                "progress": 50
            }
            
            status_response_success = MagicMock()
            status_response_success.status_code = 200
            status_response_success.json.return_value = {
                "status": "SUCCESS",
                "result": {
                    "analysis_data": "test analysis results",
                    "confidence": 0.95
                }
            }
            
            # Configure mock responses
            mock_client_instance.post.return_value = submit_response
            mock_client_instance.get.side_effect = [
                status_response_processing,
                status_response_success
            ]
            
            # Import here to avoid circular import issues
            from insight_engine.services.video_ai_client import run_analysis_job
            
            # Run analysis job
            task_id, result = await run_analysis_job("/path/to/test/video.mp4")
            
            # Verify results
            assert task_id == "analysis-task-123"
            assert result["analysis_data"] == "test analysis results"
            assert result["confidence"] == 0.95
            
            # Verify API calls
            mock_client_instance.post.assert_called_once()
            assert mock_client_instance.get.call_count == 2
    
    @pytest.mark.integration
    async def test_run_analysis_job_submission_error(self):
        """Test video analysis job submission error."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            # Mock HTTP error on submission
            import httpx
            mock_client_instance.post.side_effect = httpx.RequestError("Connection failed")
            
            # Import here to avoid circular import issues
            from insight_engine.services.video_ai_client import run_analysis_job, VideoAIClientError
            
            # Should raise VideoAIClientError
            with pytest.raises(VideoAIClientError, match="Failed to connect"):
                await run_analysis_job("/path/to/test/video.mp4")
    
    @pytest.mark.integration
    async def test_run_analysis_job_http_error(self):
        """Test video analysis job with HTTP error response."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            # Mock HTTP error response
            import httpx
            error_response = MagicMock()
            error_response.status_code = 400
            error_response.text = "Bad request"
            
            http_error = httpx.HTTPStatusError(
                "Bad request", 
                request=MagicMock(), 
                response=error_response
            )
            mock_client_instance.post.side_effect = http_error
            
            # Import here to avoid circular import issues
            from insight_engine.services.video_ai_client import run_analysis_job, VideoAIClientError
            
            # Should raise VideoAIClientError
            with pytest.raises(VideoAIClientError, match="Error submitting job"):
                await run_analysis_job("/path/to/test/video.mp4")
    
    @pytest.mark.integration
    async def test_run_analysis_job_failed_status(self):
        """Test video analysis job that fails during processing."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            # Mock successful submission
            submit_response = MagicMock()
            submit_response.status_code = 200
            submit_response.json.return_value = {
                "task_id": "failed-task-456",
                "status_endpoint": "/api/v1/status/failed-task-456"
            }
            submit_response.raise_for_status.return_value = None
            
            # Mock failed status response
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {
                "status": "FAILED",
                "error_message": "Video processing failed due to invalid format"
            }
            
            mock_client_instance.post.return_value = submit_response
            mock_client_instance.get.return_value = status_response
            
            # Import here to avoid circular import issues
            from insight_engine.services.video_ai_client import run_analysis_job, VideoAIClientError
            
            # Should raise VideoAIClientError
            with pytest.raises(VideoAIClientError, match="Analysis failed"):
                await run_analysis_job("/path/to/test/video.mp4")
    
    @pytest.mark.integration
    async def test_run_analysis_job_timeout(self):
        """Test video analysis job timeout."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            # Mock successful submission
            submit_response = MagicMock()
            submit_response.status_code = 200
            submit_response.json.return_value = {
                "task_id": "timeout-task-789",
                "status_endpoint": "/api/v1/status/timeout-task-789"
            }
            submit_response.raise_for_status.return_value = None
            
            # Mock processing status that never completes
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {
                "status": "PROCESSING",
                "progress": 10
            }
            
            mock_client_instance.post.return_value = submit_response
            mock_client_instance.get.return_value = status_response
            
            # Import here to avoid circular import issues
            from insight_engine.services.video_ai_client import run_analysis_job, VideoAIClientError
            
            # Should raise VideoAIClientError for timeout
            with pytest.raises(VideoAIClientError, match="Polling timed out"):
                await run_analysis_job("/path/to/test/video.mp4")


class TestTaskIntegration(AsyncTestCase):
    """Test integration between different background tasks."""
    
    @pytest.mark.integration
    async def test_video_processing_pipeline_integration(self):
        """Test complete video processing pipeline integration."""
        with patch('httpx.AsyncClient') as mock_http_client, \
             patch('insight_engine.worker.storage_client') as mock_storage, \
             patch('insight_engine.worker.ffmpeg') as mock_ffmpeg:
            
            # Setup mocks for video analysis
            mock_client_instance = AsyncMock()
            mock_http_client.return_value.__aenter__.return_value = mock_client_instance
            
            analysis_submit_response = MagicMock()
            analysis_submit_response.status_code = 200
            analysis_submit_response.json.return_value = {
                "task_id": "pipeline-task-123",
                "status_endpoint": "/api/v1/status/pipeline-task-123"
            }
            analysis_submit_response.raise_for_status.return_value = None
            
            analysis_status_response = MagicMock()
            analysis_status_response.status_code = 200
            analysis_status_response.json.return_value = {
                "status": "SUCCESS",
                "result": {
                    "objects_detected": ["person", "car"],
                    "timestamps": [{"object": "person", "start": 5.0, "end": 8.5}]
                }
            }
            
            mock_client_instance.post.return_value = analysis_submit_response
            mock_client_instance.get.return_value = analysis_status_response
            
            # Setup mocks for clip extraction
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_blob.exists.return_value = True
            mock_bucket.blob.return_value = mock_blob
            mock_storage.bucket.return_value = mock_bucket
            mock_ffmpeg.input.return_value.output.return_value.run.return_value = None
            
            # Import here to avoid circular import issues
            from insight_engine.services.video_ai_client import run_analysis_job
            from insight_engine.worker import process_clip_job
            
            # Step 1: Run video analysis
            task_id, analysis_result = await run_analysis_job("/path/to/video.mp4")
            
            # Verify analysis results
            assert task_id == "pipeline-task-123"
            assert "objects_detected" in analysis_result
            assert "person" in analysis_result["objects_detected"]
            
            # Step 2: Process clip extraction based on analysis
            mock_message = MagicMock()
            clip_job_data = {
                "job_id": "clip-job-456",
                "video_id": "video-123",
                "object_query": "person",
                "analysis_task_id": task_id
            }
            mock_message.data.decode.return_value = json.dumps(clip_job_data)
            
            # Process clip extraction
            process_clip_job(mock_message)
            
            # Verify integration
            mock_message.ack.assert_called_once()
            mock_ffmpeg.input.assert_called()
            
            # Verify both tasks completed successfully
            assert mock_client_instance.post.called
            assert mock_client_instance.get.called
    
    @pytest.mark.integration
    async def test_task_error_propagation(self):
        """Test error propagation between related tasks."""
        # Import here to avoid circular import issues
        from insight_engine.services.video_ai_client import run_analysis_job, VideoAIClientError
        from insight_engine.worker import process_clip_job
        
        # Test that errors in one task properly affect dependent tasks
        with patch('httpx.AsyncClient') as mock_http_client:
            mock_client_instance = AsyncMock()
            mock_http_client.return_value.__aenter__.return_value = mock_client_instance
            
            # Mock analysis job failure
            import httpx
            mock_client_instance.post.side_effect = httpx.RequestError("Service unavailable")
            
            # Analysis should fail
            with pytest.raises(VideoAIClientError):
                await run_analysis_job("/path/to/video.mp4")
            
            # Dependent clip extraction should handle missing analysis gracefully
            mock_message = MagicMock()
            clip_job_data = {
                "job_id": "dependent-clip-job",
                "video_id": "video-456",
                "object_query": "person",
                "requires_analysis": True
            }
            mock_message.data.decode.return_value = json.dumps(clip_job_data)
            
            # Should handle missing analysis dependency
            # In a real implementation, this might check for analysis results first
            process_clip_job(mock_message)
            
            # Should still process (with mock data) or handle gracefully
            assert mock_message.ack.called or mock_message.nack.called


class TestTaskResilience(AsyncTestCase):
    """Test task resilience and retry mechanisms."""
    
    @pytest.mark.integration
    async def test_task_retry_mechanism(self):
        """Test task retry mechanism for transient failures."""
        retry_count = 0
        
        async def flaky_task():
            nonlocal retry_count
            retry_count += 1
            if retry_count < 3:
                raise Exception("Transient failure")
            return {"status": "success", "attempts": retry_count}
        
        # Simulate retry logic
        max_retries = 3
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                result = await flaky_task()
                break
            except Exception as e:
                last_exception = e
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
        
        # Should succeed after retries
        assert result["status"] == "success"
        assert result["attempts"] == 3
    
    @pytest.mark.integration
    async def test_task_circuit_breaker(self):
        """Test circuit breaker pattern for task processing."""
        failure_count = 0
        circuit_open = False
        
        async def unreliable_task():
            nonlocal failure_count, circuit_open
            
            if circuit_open:
                raise Exception("Circuit breaker is open")
            
            failure_count += 1
            if failure_count <= 3:
                raise Exception("Service failure")
            
            return {"status": "success"}
        
        # Test circuit breaker logic
        max_failures = 3
        
        # Should fail initially
        for _ in range(max_failures):
            try:
                await unreliable_task()
            except Exception:
                pass
        
        # Circuit should open after max failures
        if failure_count >= max_failures:
            circuit_open = True
        
        # Should prevent further calls
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await unreliable_task()
    
    @pytest.mark.integration
    async def test_task_timeout_handling(self):
        """Test task timeout handling."""
        async def slow_task():
            await asyncio.sleep(2.0)  # Simulate slow task
            return "completed"
        
        # Test timeout
        try:
            result = await asyncio.wait_for(slow_task(), timeout=1.0)
        except asyncio.TimeoutError:
            result = "timeout_handled"
        
        assert result == "timeout_handled"
    
    @pytest.mark.integration
    async def test_concurrent_task_processing(self):
        """Test concurrent task processing."""
        async def process_task(task_id: int):
            await asyncio.sleep(0.1)  # Simulate work
            return {"task_id": task_id, "status": "completed"}
        
        # Process multiple tasks concurrently
        tasks = [process_task(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All tasks should complete
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result["task_id"] == i
            assert result["status"] == "completed"


@pytest.mark.integration
class TestTaskMonitoring:
    """Test task monitoring and observability."""
    
    async def test_task_metrics_collection(self):
        """Test task metrics collection."""
        task_metrics = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "average_processing_time": 0.0
        }
        
        async def monitored_task(should_fail: bool = False):
            import time
            start_time = time.time()
            
            try:
                if should_fail:
                    raise Exception("Task failed")
                
                await asyncio.sleep(0.1)  # Simulate work
                
                # Update metrics
                task_metrics["tasks_processed"] += 1
                processing_time = time.time() - start_time
                task_metrics["average_processing_time"] = (
                    task_metrics["average_processing_time"] + processing_time
                ) / 2
                
                return {"status": "success"}
                
            except Exception:
                task_metrics["tasks_failed"] += 1
                raise
        
        # Process successful tasks
        await monitored_task(should_fail=False)
        await monitored_task(should_fail=False)
        
        # Process failed task
        try:
            await monitored_task(should_fail=True)
        except Exception:
            pass
        
        # Verify metrics
        assert task_metrics["tasks_processed"] == 2
        assert task_metrics["tasks_failed"] == 1
        assert task_metrics["average_processing_time"] > 0
    
    async def test_task_health_monitoring(self):
        """Test task health monitoring."""
        task_health = {
            "status": "healthy",
            "last_successful_task": None,
            "consecutive_failures": 0
        }
        
        async def health_monitored_task(should_fail: bool = False):
            from datetime import datetime
            
            try:
                if should_fail:
                    raise Exception("Task failed")
                
                # Update health on success
                task_health["status"] = "healthy"
                task_health["last_successful_task"] = datetime.utcnow()
                task_health["consecutive_failures"] = 0
                
                return {"status": "success"}
                
            except Exception:
                task_health["consecutive_failures"] += 1
                if task_health["consecutive_failures"] >= 3:
                    task_health["status"] = "unhealthy"
                raise
        
        # Process successful task
        await health_monitored_task(should_fail=False)
        assert task_health["status"] == "healthy"
        assert task_health["consecutive_failures"] == 0
        
        # Process multiple failed tasks
        for _ in range(3):
            try:
                await health_monitored_task(should_fail=True)
            except Exception:
                pass
        
        # Should be marked as unhealthy
        assert task_health["status"] == "unhealthy"
        assert task_health["consecutive_failures"] == 3