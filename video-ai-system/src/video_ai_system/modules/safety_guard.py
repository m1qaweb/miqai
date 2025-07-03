import time
import logging
from collections import deque
from typing import Any, Dict, Optional

from .sampling_policy import SamplingPolicy

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitors the latency of policy decisions."""
    def __init__(self, latency_threshold_ms: float, window_size: int = 100):
        self.latency_threshold_s = latency_threshold_ms / 1000.0
        self.latencies = deque(maxlen=window_size)
        self._start_time = -1.0

    def start(self):
        """Starts the latency timer."""
        self._start_time = time.perf_counter()

    def stop(self):
        """Stops the timer and records the latency."""
        if self._start_time > 0:
            latency = time.perf_counter() - self._start_time
            self.latencies.append(latency)
            self._start_time = -1.0

    def is_breached(self) -> bool:
        """Checks if the average latency exceeds the threshold."""
        # Require the window to be at least half full to make a decision
        if len(self.latencies) < self.latencies.maxlen / 2:
            return False
        avg_latency = sum(self.latencies) / len(self.latencies)
        if avg_latency > self.latency_threshold_s:
            logger.warning(
                f"Performance breach! Average latency "
                f"({avg_latency*1000:.2f}ms) > threshold "
                f"({self.latency_threshold_s*1000:.2f}ms)."
            )
            return True
        return False


class AccuracyMonitor:
    """
    Monitors a proxy for downstream task accuracy.

    Assumption: A3.2 - A proxy metric (like rate of high-confidence detections)
    is a reliable indicator of overall task accuracy.
    """
    def __init__(self, accuracy_drop_threshold: float, window_size: int = 100):
        self.threshold = accuracy_drop_threshold
        # We need separate windows for the baseline (heuristic) and the candidate (learned)
        self.baseline_metrics = deque(maxlen=window_size)
        self.candidate_metrics = deque(maxlen=window_size)
        self.baseline_avg = -1.0

    def record_metric(self, value: float, is_baseline: bool):
        """Records a new data point for either the baseline or candidate policy."""
        if is_baseline:
            self.baseline_metrics.append(value)
        else:
            self.candidate_metrics.append(value)
        # Always update baseline average if there are metrics
        if self.baseline_metrics:
            self.baseline_avg = sum(self.baseline_metrics) / len(self.baseline_metrics)

    def is_breached(self) -> bool:
        """
        Checks if the candidate policy's accuracy has dropped significantly
        compared to the established baseline.
        """
        # Cannot determine a breach without an established baseline and enough candidate data
        if self.baseline_avg < 0 or len(self.candidate_metrics) < self.candidate_metrics.maxlen / 2:
            return False

        candidate_avg = sum(self.candidate_metrics) / len(self.candidate_metrics)
        
        # Check for a relative drop in performance
        if candidate_avg < self.baseline_avg * (1 - self.threshold):
            logger.warning(
                f"Accuracy breach! Candidate policy average ({candidate_avg:.2f}) "
                f"is significantly lower than baseline ({self.baseline_avg:.2f})."
            )
            return True
        return False


class SafetyGuard(SamplingPolicy):
    """
    A wrapper policy that enforces safety guarantees (performance, accuracy)
    and falls back to a safe heuristic if the primary policy fails.
    """
    def __init__(
        self,
        primary_policy: SamplingPolicy,
        fallback_policy: SamplingPolicy,
        latency_threshold_ms: float,
        accuracy_drop_threshold: float,
        cooldown_period_minutes: int,
    ):
        self.primary_policy = primary_policy
        self.fallback_policy = fallback_policy
        self.perf_monitor = PerformanceMonitor(latency_threshold_ms)
        # The accuracy monitor needs to be shared or accessed from the pipeline service
        self.accuracy_monitor: Optional[AccuracyMonitor] = None

        self.cooldown_seconds = cooldown_period_minutes * 60
        self.is_fallback_active = False
        self.fallback_activation_time = -1.0

        logger.info(f"SafetyGuard initialized for policy {type(primary_policy).__name__}.")
        logger.info(f"Fallback policy is {type(fallback_policy).__name__}.")
        logger.info(f"Cooldown period is {cooldown_period_minutes} minutes.")

    def set_accuracy_monitor(self, monitor: AccuracyMonitor):
        """Injects the shared accuracy monitor."""
        self.accuracy_monitor = monitor

    def _check_for_breach(self) -> bool:
        """Checks all monitors for a breach condition."""
        if self.perf_monitor.is_breached():
            return True
        if self.accuracy_monitor and self.accuracy_monitor.is_breached():
            return True
        return False

    def _activate_fallback(self):
        """Activates the fallback mode and starts the cooldown timer."""
        if not self.is_fallback_active:
            logger.critical(
                f"Activating fallback policy ({type(self.fallback_policy).__name__}) "
                f"due to performance/accuracy breach."
            )
            self.is_fallback_active = True
            self.fallback_activation_time = time.time()

    def _try_recover(self):
        """Checks if the cooldown period has passed, allowing a return to the primary policy."""
        if time.time() - self.fallback_activation_time >= self.cooldown_seconds:
            logger.info("Cooldown period ended. Attempting to recover to primary policy.")
            self.is_fallback_active = False
            self.fallback_activation_time = -1.0
            # Reset monitors to give the primary policy a clean slate
            self.perf_monitor.latencies.clear()
            if self.accuracy_monitor:
                self.accuracy_monitor.candidate_metrics.clear()

    def should_process(self, features: Dict[str, Any]) -> bool:
        """
        Decides whether to process a frame, wrapping the primary policy with safety checks.
        """
        if self.is_fallback_active:
            recovered_this_call = self.fallback_activation_time > 0 and \
                                  (time.time() - self.fallback_activation_time) >= self.cooldown_seconds
            if recovered_this_call:
                self._try_recover()

            # If we are still in fallback mode (recovery failed) OR we just recovered,
            # use the safe fallback policy for this frame. This prevents immediate re-breach.
            if self.is_fallback_active or recovered_this_call:
                return self.fallback_policy.should_process(features)

        # --- Now using the primary policy ---
        self.perf_monitor.start()
        try:
            decision = self.primary_policy.should_process(features)
        finally:
            self.perf_monitor.stop()

        if self._check_for_breach():
            self._activate_fallback()
            # On the frame that triggers the breach, use the fallback decision
            return self.fallback_policy.should_process(features)

        return decision