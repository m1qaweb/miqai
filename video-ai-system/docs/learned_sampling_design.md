# Design: Learned Sampling with Safety Guards

**Document Status:** Draft
**Phase:** 3 (Component 2)
**Author:** Architect Mode
**Date:** 2025-06-30

## 1. Overview & Goal

This document outlines the design for a "Learned Sampling" module. The primary goal is to replace the current static, heuristic-based frame sampling (e.g., "process 1 frame every N frames") with an intelligent, adaptive policy. This policy will decide whether to process or skip a frame based on its content, aiming to reduce redundant processing while capturing all significant events.

A critical, non-negotiable requirement is the inclusion of **Safety Guards**. The system must prioritize stability, performance, and accuracy. It will automatically disable the learned policy and revert to a safe, deterministic heuristic if performance overhead exceeds a predefined budget or if downstream task accuracy degrades.

### Success Metrics:

- **Performance:** The overhead of the policy network's inference must be less than 5ms per frame on the target CPU.
- **Efficiency:** Reduce the total number of processed frames by at least 20% compared to the 1 FPS baseline on representative validation datasets, without a significant drop in event detection accuracy.
- **Accuracy:** Downstream task accuracy (e.g., object detection mAP) must not decrease by more than 2% relative to the baseline heuristic.
- **Reliability:** The safety guard fallback mechanism must trigger within 1 minute of a sustained breach of performance or accuracy thresholds.

## 2. Architecture

The learned sampling logic will be encapsulated within a new `SamplingPolicy` class, which will be integrated into the `PipelineService`. This ensures modularity and allows for easy switching between different policies (learned or heuristic).

### 2.1. Architectural Diagram

```mermaid
graph TD
    A[Input Video Stream] --> B{PipelineService};
    B --> C[Frame Decoder];
    C --> D{SamplingPolicy};
    D -->|Decision: SKIP| C;
    D -->|Decision: PROCESS| E[Preprocessing & Inference];
    E --> F[Downstream Tasks];

    subgraph "Safety Guard & Monitoring"
        G[Performance Monitor] --> H{Fallback Trigger};
        F --> I[Accuracy Monitor];
        I --> H;
        H -->|Revert to Heuristic| D;
    end

    subgraph "Policy Network"
        J[Lightweight Policy Model (ONNX)]
    end

    D -- Uses --> J;
    C -- Provides Features (e.g., motion vectors, prev_embedding_diff) --> D;
```

### 2.2. Data Flow & Integration

1.  **Input to Policy:** The `SamplingPolicy` will operate on lightweight features extracted directly from the video stream or early in the pipeline to minimize overhead. The primary input feature will be the **temporal difference** between the embedding of the last processed frame and the embedding of the current candidate frame. To avoid running the full, expensive model for this, we will use a much smaller, distilled "feature extractor" model.
2.  **Integration Point:** The policy will be called within the main frame processing loop of the `PipelineService`, immediately after a frame is decoded.
3.  **Decision:** The policy network will output a binary decision: `PROCESS` or `SKIP`.
4.  **State Management:** The `SamplingPolicy` will maintain state, including the embedding of the last processed frame.

## 3. Policy Network

The policy network must be extremely lightweight to meet the strict <5ms inference budget.

### 3.1. Policy Input: Feature Engineering Trade-Offs

The choice of input features is a trade-off between signal quality and performance overhead.

- **Alternative 1: Motion Vectors:** Using low-level motion information (e.g., optical flow) is extremely fast but blind to semantic changes that occur without movement.
- **Alternative 2: Embedding Difference:** Using a distilled feature extractor to compare frame embeddings provides a rich semantic signal but incurs latency on every frame, threatening the strict performance budget.
- **Selected Approach (Hybrid):** We will adopt a **tiered feature analysis** to balance these needs.
  1.  **Tier 1 (Cheap):** Calculate motion vectors for the current frame. If motion exceeds a threshold, the frame is processed.
  2.  **Tier 2 (Expensive, Conditional):** If motion is low but a significant amount of time has passed since the last processed frame, we then compute the more expensive embedding difference to check for subtle semantic changes.

This hybrid approach reserves the expensive computation for only the most ambiguous frames, providing a good balance of performance and accuracy.

### 3.2. Model Architecture

- **Type:** A simple Multi-Layer Perceptron (MLP).
- **Input:** A concatenated vector of features from our tiered analysis (e.g., motion magnitude, embedding difference, time delta).
- **Structure:** 2 hidden layers with ReLU activation (e.g., `[Input_Dim -> 32 -> 16 -> 1]`).
- **Output:** A single logit passed through a sigmoid function to produce a probability of processing the frame.
- **Format:** The model will be converted to **ONNX** and executed with `onnxruntime` for maximum performance and portability.

### 3.3. Training Strategy: Imitation vs. Reinforcement Learning

- **Selected Approach: Imitation Learning (IL).** For Phase 3, we will use IL (Behavioral Cloning). This is the most stable and predictable method.

  - **Oracle:** We will generate a training dataset by running a high-accuracy, but slow, "oracle" policy on a large set of videos. The oracle will be a heuristic that processes a frame if the IoU of detected objects changes by more than a threshold (e.g., 15%) from the last processed frame.
  - **Training Data:** The training data will consist of `(input_features, oracle_decision)` pairs.
  - **Rationale:** This approach prioritizes safety and reliability. The policy learns from a known-good baseline, preventing erratic behavior.

- **Deferred Alternative: Reinforcement Learning (RL).** While RL could potentially discover a more optimal policy, it is significantly more complex and less stable to train. Defining a robust reward function is a major research challenge in itself. RL will be considered for a future research-focused phase (Phase 5), but is deemed too high-risk for the current production-focused phase.

## 4. Safety Guards & Fallbacks

This is the most critical component of the design. The system must not fail or degrade due to a faulty or slow policy.

### 4.1. The `SafetyGuard` Module

A `SafetyGuard` class will wrap the `SamplingPolicy` execution.

```python
# Pseudocode for SafetyGuard
class SafetyGuard:
    def __init__(self, policy, fallback_policy, config):
        self.policy = policy
        self.fallback_policy = fallback_policy
        self.is_fallback_active = False
        self.perf_monitor = PerformanceMonitor(config.latency_threshold)
        self.accuracy_monitor = AccuracyMonitor(config.accuracy_threshold)

    def should_process(self, frame_features):
        if self.is_fallback_active:
            return self.fallback_policy.should_process(frame_features)

        # Monitor performance of the policy execution
        with self.perf_monitor.time_block():
            decision = self.policy.should_process(frame_features)

        # Check for breaches
        if self.perf_monitor.is_breached() or self.accuracy_monitor.is_breached():
            self.activate_fallback()
            return self.fallback_policy.should_process(frame_features)

        return decision

    def activate_fallback(self):
        # Log event, send alert
        self.is_fallback_active = True
        # ...
```

### 4.2. Fallback Triggers

1.  **Latency Trigger:**

    - **Metric:** Moving average of the `SamplingPolicy` inference latency over a 60-second window.
    - **Threshold:** If the average latency exceeds **5ms**.
    - **Monitoring:** The `SafetyGuard` will use a simple timer to measure the execution time of the policy's `should_process` method.

2.  **Accuracy Trigger:**
    - **Metric:** A proxy for downstream task accuracy. We will use a "canary" or "sentinel" metric: the rate of high-confidence detections.
    - **Logic:** If the learned policy is active and the rate of high-confidence detections drops by more than a configured threshold (e.g., 10%) compared to a baseline established by the heuristic policy, it suggests important frames are being missed.
    - **Monitoring:** The `AccuracyMonitor` will subscribe to final inference results and maintain a moving average of this metric.

### 4.3. Fallback Policy

- **Policy:** A simple, deterministic `FixedRateSamplingPolicy` (e.g., process 1 frame per second). This is predictable, stable, and its performance characteristics are well-understood.
- **Re-evaluation:** Once the system enters a fallback state, it will remain there for a configurable "cooldown" period (e.g., 10 minutes) before attempting to re-enable the learned policy.

## 5. Integration with `PipelineService`

### 5.1. Configuration Changes

The main application configuration (`config.yml` or similar) will be extended to include a `sampling` section.

```yaml
# In config/config.schema.json or Pydantic model
sampling:
  policy: "learned" # or "heuristic"
  learned_policy:
    model_path: "/models/sampling_policy_v1.onnx"
    feature_extractor_model_path: "/models/feature_extractor_v1.onnx"
  heuristic_policy:
    rate_fps: 1
  safety_guards:
    enabled: true
    latency_threshold_ms: 5.0
    accuracy_drop_threshold: 0.10 # 10%
    monitoring_window_seconds: 60
    cooldown_period_minutes: 10
```

### 5.2. `PipelineService` Modifications

The `PipelineService`'s main processing loop will be modified to incorporate the policy.

```python
# In video_ai_system/services/pipeline_service.py

class PipelineService:
    def __init__(self, config):
        # ...
        self.sampling_policy = self._create_sampling_policy(config)

    def _create_sampling_policy(self, config):
        heuristic_policy = FixedRateSamplingPolicy(config.sampling.heuristic_policy)
        if config.sampling.policy == "learned":
            learned_policy = LearnedSamplingPolicy(config.sampling.learned_policy)
            if config.sampling.safety_guards.enabled:
                return SafetyGuard(learned_policy, heuristic_policy, config.sampling.safety_guards)
            return learned_policy
        return heuristic_policy

    def process_video(self, video_path):
        # ...
        for frame in video_stream:
            features = self.feature_extractor.extract(frame)
            if self.sampling_policy.should_process(features):
                # Full processing logic
                self.inference_service.run(frame)
            else:
                # Skip frame
                continue
```

## 6. Validation Plan

### 6.1. Unit Tests

- `test_fixed_rate_policy`: Ensure it samples at the correct, deterministic rate.
- `test_learned_policy_loading`: Verify the ONNX model can be loaded correctly.
- `test_safety_guard_latency_trigger`: Mock the performance monitor to exceed the threshold and verify the guard activates the fallback policy.
- `test_safety_guard_accuracy_trigger`: Mock the accuracy monitor to report a drop and verify the fallback is activated.
- `test_safety_guard_cooldown`: Verify the guard does not re-enable the learned policy until the cooldown period has passed.

### 6.2. Integration Tests

- `test_pipeline_with_learned_sampling`: Run a short video through the pipeline with the learned policy enabled and assert that the number of processed frames is non-zero and less than the total number of frames.
- `test_pipeline_fallback_e2e`: Create a scenario (e.g., by using a deliberately slow policy model) that forces the safety guard to trigger, and verify the system completes processing using the fallback heuristic.

### 6.3. Benchmark Scripts

- `benchmarks/benchmark_sampling_policy.py`:
  - **Objective:** Measure the inference latency of the `LearnedSamplingPolicy`'s `should_process` method.
  - **Procedure:** Run the method 1000 times with random input data.
  - **Pass Criteria:** P99 latency must be < 5ms.
- `benchmarks/benchmark_end_to_end_efficiency.py`:
  - **Objective:** Compare the end-to-end performance and efficiency of the learned vs. heuristic policies.
  - **Procedure:** Process a validation set of 5 representative videos with both policies.
  - **Metrics to Capture:**
    - Total frames processed.
    - Total processing time.
    - Downstream task accuracy (mAP).
  - **Pass Criteria:** The learned policy must meet the success metrics defined in Section 1.

## 7. Assumptions

- **A3.1:** A lightweight feature extractor model can be trained to produce embeddings suitable for temporal difference calculation with minimal overhead. (Confidence: Medium)
- **A3.2:** The rate of high-confidence detections is a reliable proxy for overall downstream task accuracy and can be used as a sentinel metric for the accuracy safety guard. (Confidence: Medium)
- **A3.3:** The imitation learning approach with an IoU-based oracle will produce a policy that is significantly more efficient than the fixed-rate heuristic. (Confidence: High)

## 8. Next Tasks for Code Mode

- **T3.1:** Implement the `FixedRateSamplingPolicy` class.
- **T3.2:** Implement the `LearnedSamplingPolicy` class, including ONNX model loading and inference logic.
- **T3.3:** Implement the `SafetyGuard` wrapper class with performance and accuracy monitoring hooks.
- **T3.4:** Implement the `PerformanceMonitor` and `AccuracyMonitor` utility classes.
- **T3.5:** Integrate the sampling policy mechanism into the `PipelineService` as described.
- **T3.6:** Update the configuration schema and parsing logic to support the new `sampling` section.
- **T3.7:** Create the unit and integration tests outlined in the validation plan.
- **T3.8:** Create the benchmark scripts for latency and end-to-end efficiency.
