# -*- coding: utf-8 -*-
"""
Benchmark script for the VideoPreprocessor service.

This script runs the keyframe extraction process with various hashing
algorithms and parameters to measure performance and effectiveness.
The results are used to validate the design and inform the optimal
default configuration.

Example Usage:
    python benchmarks/benchmark_keyframe_extraction.py \
        --data-path ./data/sample_videos \
        --log-level INFO
"""
import argparse
import json
import platform
import time
from pathlib import Path
import psutil
import numpy as np
from loguru import logger

# Add the project root to the Python path to allow importing from src
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.video_ai_system.services.preprocessing_service import VideoPreprocessor

def run_benchmark(video_path: Path, config: dict) -> dict:
    """
    Runs a single benchmark instance for a given video and configuration.

    Args:
        video_path (Path): Path to the video file.
        config (dict): Configuration for the VideoPreprocessor.

    Returns:
        dict: A dictionary containing the benchmark results.
    """
    logger.info(f"Running benchmark for {video_path.name} with config: {config}")
    preprocessor = VideoPreprocessor(config)

    psutil.cpu_percent(interval=None)  # Start measuring CPU
    start_time = time.perf_counter()

    # This is a synchronous call for benchmarking purposes
    keyframes = []
    for frame in preprocessor.extract_keyframes(str(video_path)):
        keyframes.append(frame)

    end_time = time.perf_counter()
    cpu_usage = psutil.cpu_percent(interval=None)

    processing_time = end_time - start_time
    num_keyframes = len(keyframes)
    
    logger.info(f"Finished benchmark for {video_path.name}. Time: {processing_time:.2f}s, Keyframes: {num_keyframes}, CPU: {cpu_usage:.2f}%")

    return {
        "video_name": video_path.name,
        "config": config,
        "processing_time_seconds": round(processing_time, 4),
        "cpu_utilization_percent": round(cpu_usage, 2),
        "num_keyframes_extracted": num_keyframes,
    }

def main():
    """Main function to run the benchmark suite."""
    parser = argparse.ArgumentParser(description="Benchmark Keyframe Extraction Service")
    parser.add_argument(
        "--data-path",
        type=str,
        required=True,
        help="Path to the directory containing sample video files.",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default="benchmark_results.json",
        help="Path to save the JSON results file.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set the logging level.",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level=args.log_level)

    video_dir = Path(args.data_path)
    if not video_dir.is_dir():
        logger.error(f"Data path '{args.data_path}' is not a valid directory.")
        sys.exit(1)

    sample_videos = list(video_dir.glob("*.mp4"))
    if not sample_videos:
        logger.error(f"No .mp4 videos found in '{args.data_path}'.")
        sys.exit(1)

    # Define the matrix of configurations to test
    test_matrix = [
        {"HASH_ALGORITHM": "phash", "HASH_DISTANCE_THRESHOLD": 5, "HASH_SIZE": 8},
        {"HASH_ALGORITHM": "phash", "HASH_DISTANCE_THRESHOLD": 10, "HASH_SIZE": 8},
        {"HASH_ALGORITHM": "dhash", "HASH_DISTANCE_THRESHOLD": 5, "HASH_SIZE": 8},
        {"HASH_ALGORITHM": "dhash", "HASH_DISTANCE_THRESHOLD": 10, "HASH_SIZE": 8},
        {"HASH_ALGORITHM": "ahash", "HASH_DISTANCE_THRESHOLD": 5, "HASH_SIZE": 8},
        {"HASH_ALGORITHM": "whash", "HASH_DISTANCE_THRESHOLD": 10, "HASH_SIZE": 16}, # Wavelet hash can be more sensitive
    ]

    all_results = []
    
    # System Info
    system_info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "cpu_cores": psutil.cpu_count(logical=True),
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
    }
    logger.info(f"System Info: {system_info}")


    for video_path in sample_videos:
        for config_params in test_matrix:
            # Base config can be extended if needed
            base_config = {
                "TARGET_SIZE": (224, 224),
                "CPU_THRESHOLD": 95,  # Set high to not interfere with benchmark
                "THROTTLE_DELAY": 0.1,
            }
            current_config = {**base_config, **config_params}
            
            try:
                result = run_benchmark(video_path, current_config)
                all_results.append(result)
            except Exception as e:
                logger.error(f"Benchmark failed for {video_path.name} with config {current_config}. Error: {e}")

    # Prepare final output
    output_data = {
        "system_info": system_info,
        "benchmark_results": all_results,
        "summary": {
            "total_runs": len(all_results),
            "total_videos": len(sample_videos),
        }
    }

    # Save results to JSON file
    output_file = Path(args.output_path)
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=4)

    logger.info(f"Benchmark complete. Results saved to '{output_file.resolve()}'")
    print(f"\nBenchmark results saved to: {output_file.resolve()}")


if __name__ == "__main__":
    main()