import argparse
import json
import logging
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
import psutil

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def preprocess_frame(frame, target_size=(224, 224)):
    """
    Preprocesses a single video frame for the model.
    This is a placeholder and should be adapted to the specific model's requirements.
    """
    # Resize frame
    resized_frame = cv2.resize(frame, target_size)
    # Convert BGR to RGB
    rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
    # Normalize to [0, 1]
    normalized_frame = rgb_frame.astype(np.float32) / 255.0
    # Add batch dimension and transpose to (B, C, H, W)
    input_tensor = np.expand_dims(normalized_frame, axis=0).transpose(0, 3, 1, 2)
    return input_tensor


def run_benchmark(model_path: Path, video_path: Path, num_frames: int = 30):
    """
    Runs inference benchmark on an ONNX model.

    Args:
        model_path: Path to the ONNX model.
        video_path: Path to the sample video for inference.
        num_frames: The number of frames to process from the video.
    """
    if not model_path.exists():
        logger.error(f"Model file not found: {model_path}")
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        raise FileNotFoundError(f"Video file not found: {video_path}")

    logger.info(f"Starting benchmark for model: {model_path}")
    logger.info(f"Using ONNX Runtime version: {ort.__version__}")
    logger.info(f"Processing {num_frames} frames from {video_path}")

    # 1. Load Model
    session = ort.InferenceSession(str(model_path))
    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape
    # Assuming HxW is dynamic, get target size from model input shape
    target_size = (input_shape[3], input_shape[2]) # (width, height)

    # 2. Prepare Data
    cap = cv2.VideoCapture(str(video_path))
    frames_to_process = []
    for _ in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            break
        frames_to_process.append(preprocess_frame(frame, target_size))
    cap.release()

    if not frames_to_process:
        logger.error("Could not read any frames from the video.")
        sys.exit(1)

    # 3. Run Inference and Collect Metrics
    latencies = []
    cpu_percents = []

    # Warm-up run
    _ = session.run(None, {input_name: frames_to_process[0]})

    for i, input_tensor in enumerate(frames_to_process):
        start_time = time.perf_counter()
        
        # Capture CPU usage during inference
        p = psutil.Process()
        p.cpu_percent(interval=None) # Start interval
        session.run(None, {input_name: input_tensor})
        cpu_percent = p.cpu_percent(interval=None)

        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        latencies.append(latency_ms)
        cpu_percents.append(cpu_percent)
        logger.debug(f"Frame {i+1}/{len(frames_to_process)} - Latency: {latency_ms:.2f} ms, CPU: {cpu_percent:.2f}%")

    # 4. Aggregate and Output Results
    avg_latency = np.mean(latencies)
    avg_cpu_percent = np.mean(cpu_percents)
    p95_latency = np.percentile(latencies, 95)
    
    results = {
        "model_path": str(model_path),
        "onnxruntime_version": ort.__version__,
        "system_info": {
            "platform": platform.system(),
            "architecture": platform.machine(),
            "cpu_cores": psutil.cpu_count(logical=False),
            "logical_processors": psutil.cpu_count(logical=True),
        },
        "benchmark_params": {
            "video_source": str(video_path),
            "frames_processed": len(frames_to_process),
        },
        "performance_metrics": {
            "average_latency_ms": round(avg_latency, 4),
            "p95_latency_ms": round(p95_latency, 4),
            "average_cpu_usage_percent": round(avg_cpu_percent, 4),
        },
    }

    print(json.dumps(results, indent=4))
    logger.info("Benchmark finished successfully.")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Benchmark an ONNX model.")
    parser.add_argument(
        "--model-path",
        type=Path,
        required=True,
        help="Path to the ONNX model to benchmark.",
    )
    parser.add_argument(
        "--video-path",
        type=Path,
        required=True,
        help="Path to the sample video for inference.",
    )
    parser.add_argument(
        "--num-frames",
        type=int,
        default=30,
        help="Number of frames to process for the benchmark.",
    )
    args = parser.parse_args()

    try:
        run_benchmark(args.model_path, args.video_path, args.num_frames)
    except Exception as e:
        logger.exception(f"An error occurred during benchmarking: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()