import time
import pytest
from unittest.mock import MagicMock, Mock

from video_ai_system.modules.safety_guard import SafetyGuard, PerformanceMonitor, AccuracyMonitor
from video_ai_system.modules.sampling_policy import SamplingPolicy

class MockPolicy(SamplingPolicy):
    def __init__(self, decision: bool, process_delay: float = 0):
        self._decision = decision
        self._process_delay = process_delay

    def should_process(self, features):
        time.sleep(self._process_delay)
        return self._decision

@pytest.fixture
def fast_primary_policy():
    return MockPolicy(decision=True, process_delay=0)

@pytest.fixture
def slow_primary_policy():
    return MockPolicy(decision=True, process_delay=0.01)

@pytest.fixture
def fallback_policy():
    return MockPolicy(decision=False)

def test_performance_monitor_breach():
    monitor = PerformanceMonitor(latency_threshold_ms=5, window_size=10)
    for _ in range(10):
        monitor.start()
        time.sleep(0.006)
        monitor.stop()
    assert monitor.is_breached()

def test_performance_monitor_no_breach():
    monitor = PerformanceMonitor(latency_threshold_ms=10, window_size=10)
    for _ in range(10):
        monitor.start()
        time.sleep(0.005)
        monitor.stop()
    assert not monitor.is_breached()

def test_accuracy_monitor_breach():
    monitor = AccuracyMonitor(accuracy_drop_threshold=0.1, window_size=10)
    for _ in range(10):
        monitor.record_metric(1.0, is_baseline=True)
    for _ in range(10):
        monitor.record_metric(0.8, is_baseline=False)
    assert monitor.is_breached()

def test_accuracy_monitor_no_breach():
    monitor = AccuracyMonitor(accuracy_drop_threshold=0.1, window_size=10)
    for _ in range(10):
        monitor.record_metric(1.0, is_baseline=True)
    for _ in range(10):
        monitor.record_metric(0.95, is_baseline=False)
    assert not monitor.is_breached()

def test_safety_guard_uses_primary_policy_when_healthy(fast_primary_policy, fallback_policy):
    guard = SafetyGuard(fast_primary_policy, fallback_policy, 10, 0.1, 1)
    assert guard.should_process({}) is True
    assert not guard.is_fallback_active

def test_safety_guard_activates_fallback_on_latency_breach(slow_primary_policy, fallback_policy):
    guard = SafetyGuard(slow_primary_policy, fallback_policy, 5, 0.1, 1)
    # Fill the performance monitor window
    for _ in range(50):
        guard.should_process({})
    # Next call should trigger fallback
    assert guard.should_process({}) is False
    assert guard.is_fallback_active

def test_safety_guard_activates_fallback_on_accuracy_breach(fast_primary_policy, fallback_policy):
    guard = SafetyGuard(fast_primary_policy, fallback_policy, 10, 0.1, 1)
    accuracy_monitor = AccuracyMonitor(accuracy_drop_threshold=0.1, window_size=10)
    guard.set_accuracy_monitor(accuracy_monitor)

    for _ in range(10):
        accuracy_monitor.record_metric(1.0, is_baseline=True)
    for _ in range(10):
        accuracy_monitor.record_metric(0.8, is_baseline=False)

    # This call should detect the breach and use the fallback policy
    assert guard.should_process({}) is False
    assert guard.is_fallback_active

def test_safety_guard_cooldown_and_recovery(slow_primary_policy, fallback_policy):
    guard = SafetyGuard(slow_primary_policy, fallback_policy, 5, 0.1, 0.01) # 0.01 min cooldown
    # Trigger fallback
    for _ in range(50):
        guard.should_process({})
    assert guard.is_fallback_active

    # Wait for cooldown
    time.sleep(0.01 * 60)

    # The guard should now attempt to use the primary policy again.
    # Since the primary is still slow, it will re-trigger.
    # We check that it *tries* by seeing if it returns the primary's decision (True)
    # before re-activating fallback on the *next* call.
    # This is a subtle point. The recovery happens, then the breach is detected again.
    guard.should_process({}) # This call recovers
    assert not guard.is_fallback_active