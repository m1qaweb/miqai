import pytest
from video_ai_system.modules.sampling_policy import FixedRateSamplingPolicy, HeuristicSamplingPolicy

def test_fixed_rate_sampling_policy_initialization():
    """Tests that the FixedRateSamplingPolicy initializes correctly."""
    policy = FixedRateSamplingPolicy(rate_fps=1)
    assert policy.interval_seconds == 1.0
    policy = FixedRateSamplingPolicy(rate_fps=10)
    assert policy.interval_seconds == 0.1

def test_fixed_rate_sampling_policy_invalid_rate():
    """Tests that the policy raises an error for invalid rates."""
    with pytest.raises(ValueError):
        FixedRateSamplingPolicy(rate_fps=0)
    with pytest.raises(ValueError):
        FixedRateSamplingPolicy(rate_fps=-1)

def test_fixed_rate_sampling_policy_decision_logic():
    """Tests the core decision logic of the FixedRateSamplingPolicy."""
    policy = FixedRateSamplingPolicy(rate_fps=1)
    # First frame should always be processed
    assert policy.should_process({"timestamp": 1000.0}) is True
    # Second frame, too soon, should be skipped
    assert policy.should_process({"timestamp": 1000.5}) is False
    # Third frame, after interval, should be processed
    assert policy.should_process({"timestamp": 1001.0}) is True
    # Fourth frame, exactly at interval, should be processed
    assert policy.should_process({"timestamp": 1002.0}) is True

def test_heuristic_sampling_policy_initialization():
    """Tests that the HeuristicSamplingPolicy initializes correctly."""
    policy = HeuristicSamplingPolicy(motion_threshold=0.5)
    assert policy.motion_threshold == 0.5

def test_heuristic_sampling_policy_invalid_threshold():
    """Tests that the policy raises an error for invalid thresholds."""
    with pytest.raises(ValueError):
        HeuristicSamplingPolicy(motion_threshold=0)
    with pytest.raises(ValueError):
        HeuristicSamplingPolicy(motion_threshold=-0.1)

def test_heuristic_sampling_policy_decision_logic():
    """Tests the core decision logic of the HeuristicSamplingPolicy."""
    policy = HeuristicSamplingPolicy(motion_threshold=0.2)
    # Motion below threshold, should be skipped
    assert policy.should_process({"motion_magnitude": 0.1}) is False
    # Motion above threshold, should be processed
    assert policy.should_process({"motion_magnitude": 0.3}) is True
    # Motion equal to threshold, should be skipped
    assert policy.should_process({"motion_magnitude": 0.2}) is False
    # No motion feature, should be skipped
    assert policy.should_process({}) is False