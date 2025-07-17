"""Tests for resilience patterns (circuit breaker, retry, timeout)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
import time
from typing import Any

from insight_engine.resilience import (
    CircuitBreaker,
    CircuitBreakerState,
    RetryConfig,
    RetryManager,
    TimeoutConfig,
    TimeoutManager,
    http_resilient,
    gcp_resilient,
    CircuitBreakerOpenError,
    RetryExhaustedError,
    TimeoutError as ResilienceTimeoutError,
)
from insight_engine.resilience.config import resilience_config_manager
from insight_engine.resilience.decorators import get_circuit_breaker_stats, reset_circuit_breaker


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for testing."""
        return CircuitBreaker("test_service")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self, circuit_breaker):
        """Test circuit breaker in closed state allows calls."""
        async def success_func():
            return "success"
        
        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_tracking(self, circuit_breaker):
        """Test circuit breaker tracks failures correctly."""
        async def failing_func():
            raise Exception("Test failure")
        
        # First few failures should not open circuit
        for i in range(4):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_func)
            assert circuit_breaker.state == CircuitBreakerState.CLOSED
            assert circuit_breaker.failure_count == i + 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self, circuit_breaker):
        """Test circuit breaker opens after failure threshold."""
        async def failing_func():
            raise Exception("Test failure")
        
        # Trigger enough failures to open circuit
        for i in range(5):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Next call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await circuit_breaker.call(failing_func)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_transition(self, circuit_breaker):
        """Test circuit breaker transitions to half-open after timeout."""
        # Set short recovery timeout for testing
        circuit_breaker.config.recovery_timeout = 0.1
        
        async def failing_func():
            raise Exception("Test failure")
        
        # Open the circuit
        for i in range(5):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Next call should transition to half-open
        async def success_func():
            return "success"
        
        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_after_success_threshold(self, circuit_breaker):
        """Test circuit breaker closes after success threshold in half-open."""
        # Set short recovery timeout for testing
        circuit_breaker.config.recovery_timeout = 0.1
        circuit_breaker.config.success_threshold = 2
        
        async def failing_func():
            raise Exception("Test failure")
        
        async def success_func():
            return "success"
        
        # Open the circuit
        for i in range(5):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_func)
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Make successful calls to close circuit
        for i in range(2):
            result = await circuit_breaker.call(success_func)
            assert result == "success"
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0


class TestRetryManager:
    """Test retry logic functionality."""
    
    @pytest.fixture
    def retry_manager(self):
        """Create a retry manager for testing."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)  # Fast retries for testing
        return RetryManager("test_service", config)
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self, retry_manager):
        """Test successful call on first attempt."""
        async def success_func():
            return "success"
        
        result = await retry_manager.execute(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self, retry_manager):
        """Test successful call after some failures."""
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = await retry_manager.execute(flaky_func)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhausted(self, retry_manager):
        """Test retry exhaustion after max attempts."""
        async def failing_func():
            raise ConnectionError("Persistent failure")
        
        with pytest.raises(RetryExhaustedError) as exc_info:
            await retry_manager.execute(failing_func)
        
        assert exc_info.value.attempts == 3
        assert "Persistent failure" in str(exc_info.value.last_exception)
    
    @pytest.mark.asyncio
    async def test_retry_non_retryable_exception(self, retry_manager):
        """Test non-retryable exceptions are not retried."""
        async def failing_func():
            raise ValueError("Non-retryable error")
        
        with pytest.raises(ValueError):
            await retry_manager.execute(failing_func)
    
    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self, retry_manager):
        """Test exponential backoff timing."""
        call_times = []
        
        async def failing_func():
            call_times.append(time.time())
            raise ConnectionError("Test failure")
        
        with pytest.raises(RetryExhaustedError):
            await retry_manager.execute(failing_func)
        
        # Check that delays increase exponentially
        assert len(call_times) == 3
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        assert delay2 > delay1  # Second delay should be longer


class TestTimeoutManager:
    """Test timeout functionality."""
    
    @pytest.fixture
    def timeout_manager(self):
        """Create a timeout manager for testing."""
        config = TimeoutConfig(total_timeout=0.1)  # Short timeout for testing
        return TimeoutManager("test_service", config)
    
    @pytest.mark.asyncio
    async def test_timeout_success(self, timeout_manager):
        """Test successful call within timeout."""
        async def fast_func():
            await asyncio.sleep(0.01)
            return "success"
        
        result = await timeout_manager.execute(fast_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_timeout_exceeded(self, timeout_manager):
        """Test timeout exceeded."""
        async def slow_func():
            await asyncio.sleep(0.2)
            return "too slow"
        
        with pytest.raises(ResilienceTimeoutError) as exc_info:
            await timeout_manager.execute(slow_func)
        
        assert exc_info.value.timeout_seconds == 0.1


class TestResilienceDecorators:
    """Test resilience decorators."""
    
    @pytest.mark.asyncio
    async def test_http_resilient_decorator(self):
        """Test HTTP resilient decorator."""
        call_count = 0
        
        @http_resilient("test_http_service")
        async def flaky_http_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Network error")
            return "success"
        
        result = await flaky_http_call()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_gcp_resilient_decorator(self):
        """Test GCP resilient decorator."""
        call_count = 0
        
        @gcp_resilient("test_gcp_service")
        async def flaky_gcp_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                # Simulate GCP transient error
                error = Mock()
                error.code = "UNAVAILABLE"
                raise error
            return "success"
        
        result = await flaky_gcp_call()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_fallback_mechanism(self):
        """Test fallback mechanism."""
        async def fallback_func(*args, **kwargs):
            return "fallback_result"
        
        @http_resilient("test_fallback_service", fallback=fallback_func)
        async def always_failing():
            raise ConnectionError("Always fails")
        
        result = await always_failing()
        assert result == "fallback_result"


class TestResilienceConfig:
    """Test resilience configuration."""
    
    def test_default_configs(self):
        """Test default configurations are available."""
        http_config = resilience_config_manager.get_config("http_api")
        assert http_config.circuit_breaker.failure_threshold == 5
        assert http_config.retry.max_attempts == 3
        assert http_config.timeout.total_timeout == 45.0
        
        gcp_config = resilience_config_manager.get_config("gcp")
        assert gcp_config.circuit_breaker.failure_threshold == 3
        assert gcp_config.retry.max_attempts == 5
        assert gcp_config.timeout.total_timeout == 600.0
    
    def test_custom_config(self):
        """Test setting custom configuration."""
        from insight_engine.resilience.config import ResilienceConfig
        from insight_engine.resilience.circuit_breaker import CircuitBreakerConfig
        from insight_engine.resilience.retry import RetryConfig
        from insight_engine.resilience.timeout import TimeoutConfig
        
        custom_config = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(failure_threshold=10),
            retry=RetryConfig(max_attempts=10),
            timeout=TimeoutConfig(total_timeout=120.0)
        )
        
        resilience_config_manager.set_config("custom_service", custom_config)
        retrieved_config = resilience_config_manager.get_config("custom_service")
        
        assert retrieved_config.circuit_breaker.failure_threshold == 10
        assert retrieved_config.retry.max_attempts == 10
        assert retrieved_config.timeout.total_timeout == 120.0


class TestCircuitBreakerStats:
    """Test circuit breaker statistics and monitoring."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_stats(self):
        """Test getting circuit breaker statistics."""
        @http_resilient("stats_test_service")
        async def test_func():
            return "success"
        
        # Make a successful call to create circuit breaker
        await test_func()
        
        stats = get_circuit_breaker_stats()
        assert "stats_test_service" in stats
        
        service_stats = stats["stats_test_service"]
        assert service_stats["state"] == "closed"
        assert service_stats["failure_count"] == 0
    
    @pytest.mark.asyncio
    async def test_reset_circuit_breaker(self):
        """Test manually resetting circuit breaker."""
        @http_resilient("reset_test_service")
        async def failing_func():
            raise ConnectionError("Test failure")
        
        # Trigger failures to open circuit
        for _ in range(5):
            try:
                await failing_func()
            except:
                pass
        
        stats = get_circuit_breaker_stats()
        assert stats["reset_test_service"]["state"] == "open"
        
        # Reset circuit breaker
        success = reset_circuit_breaker("reset_test_service")
        assert success is True
        
        # Check it's closed now
        stats = get_circuit_breaker_stats()
        assert stats["reset_test_service"]["state"] == "closed"
        assert stats["reset_test_service"]["failure_count"] == 0


@pytest.mark.asyncio
async def test_integration_all_patterns():
    """Integration test combining all resilience patterns."""
    call_count = 0
    
    @http_resilient("integration_test_service")
    async def complex_service_call():
        nonlocal call_count
        call_count += 1
        
        # Simulate various failure scenarios
        if call_count == 1:
            raise ConnectionError("Network timeout")
        elif call_count == 2:
            await asyncio.sleep(0.01)  # Small delay
            raise ConnectionError("Connection refused")
        else:
            return {"status": "success", "data": "test_data"}
    
    result = await complex_service_call()
    assert result["status"] == "success"
    assert call_count == 3
    
    # Verify circuit breaker is still closed after successful recovery
    stats = get_circuit_breaker_stats()
    assert stats["integration_test_service"]["state"] == "closed"