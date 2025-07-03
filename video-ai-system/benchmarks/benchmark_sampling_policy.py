import time
import json
import argparse
import numpy as np
import os
import sys
import platform

# Add src to path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.video_ai_system.modules.sampling_policy import LearnedSamplingPolicy

def create_dummy_onnx_model(path: str):
    """Creates a placeholder file. The actual model content is not relevant
    for the latency benchmark, but the file must exist for the class to load."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # A real ONNX model would be needed for full accuracy benchmarking.
    # For latency, the file just needs to be loadable by the runtime.
    # A minimal valid ONNX model is a bit complex to generate on the fly,
    # so we will rely on the user providing a real (even if simple) model.
    # For CI/CD, we can create a tiny valid ONNX file.
    if not os.path.exists(path):
        print(f"Creating dummy model file at: {path}. For real benchmarks, replace this with a valid ONNX model.")
        with open(path, "w") as f:
            f.write("dummy onnx model")

def run_benchmark(iterations: int, policy_model: str, feature_model: str):
    """
    Measures the performance of the LearnedSamplingPolicy.
    """
    print("--- Setting up benchmark for LearnedSamplingPolicy ---")
    
    # Create dummy models if they don't exist
    create_dummy_onnx_model(policy_model)
    create_dummy_onnx_model(feature_model)

    try:
        policy = LearnedSamplingPolicy(
            policy_model_path=policy_model,
            feature_extractor_model_path=feature_model,
        )
    except Exception as e:
        print(f"Failed to initialize LearnedSamplingPolicy. Ensure valid ONNX models are present.")
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Running benchmark for {iterations} iterations...")

    # Prepare dummy input features
    features = {
        "timestamp": 0.0,
        "motion_magnitude": 0.05, # Low motion to force semantic check
        "frame_data": np.random.rand(1, 3, 224, 224).astype(np.float32)
    }

    latencies = []
    
    # Run the benchmark loop
    for i in range(iterations):
        features["timestamp"] = time.time()
        start_time = time.perf_counter()
        # We are benchmarking the core decision logic
        policy.should_process(features)
        end_time = time.perf_counter()
        latencies.append((end_time - start_time) * 1000) # convert to ms

    # --- Analysis ---
    p99 = np.percentile(latencies, 99)
    p95 = np.percentile(latencies, 95)
    avg = np.mean(latencies)
    max_latency = np.max(latencies)
    min_latency = np.min(latencies)

    target_latency = 5.0 # ms
    passed = p99 < target_latency

    results = {
        "benchmark_id": "T3.4_sampling_policy_latency",
        "assumptions_validated": ["A3.1"],
        "hardware": {
            "system": platform.system(),
            "release": platform.release(),
            "processor": platform.processor(),
        },
        "parameters": {
            "iterations": iterations,
            "policy_model": policy_model,
            "feature_model": feature_model,
        },
        "metrics": {
            "p99_latency_ms": p99,
            "p95_latency_ms": p95,
            "avg_latency_ms": avg,
            "max_latency_ms": max_latency,
            "min_latency_ms": min_latency,
        },
        "success_criteria": {
            "target_p99_latency_ms": target_latency,
        },
        "result": "PASSED" if passed else "FAILED"
    }

    print("\n--- Benchmark Results ---")
    print(json.dumps(results, indent=2))
    print("-------------------------")

    if not passed:
        print(f"Escalation required: p99 latency ({p99:.2f}ms) exceeded target ({target_latency:.2f}ms).")
        print("Potential escalation to: Debug Mode or Architect Mode.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark for LearnedSamplingPolicy.")
    parser.add_argument("--iterations", type=int, default=1000, help="Number of iterations to run.")
    parser.add_argument("--policy-model", type=str, default="models/sampling_policy.onnx", help="Path to the policy ONNX model.")
    parser.add_argument("--feature-model", type=str, default="models/feature_extractor.onnx", help="Path to the feature extractor ONNX model.")
    args = parser.parse_args()

    run_benchmark(args.iterations, args.policy_model, args.feature_model)