import argparse
import logging
import sys
from pathlib import Path

from olive.workflows import run as olive_run

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def optimize_model(input_model_path: Path, output_model_path: Path):
    """
    Optimizes an ONNX model using Microsoft Olive, applying INT8 quantization.

    Args:
        input_model_path: Path to the input ONNX model.
        output_model_path: Path where the optimized ONNX model will be saved.
    """
    if not input_model_path.exists():
        logger.error(f"Input model not found at: {input_model_path}")
        raise FileNotFoundError(f"Input model not found at: {input_model_path}")

    output_model_path.parent.mkdir(parents=True, exist_ok=True)

    # This is a basic configuration for INT8 quantization.
    # In a real-world scenario, this might be loaded from a YAML/JSON file
    # and could be much more complex, specifying data loaders for calibration.
    olive_config = {
        "input_model": {
            "type": "ONNXModel",
            "config": {"model_path": str(input_model_path)},
        },
        "systems": {
            "local_system": {
                "type": "LocalSystem",
                "config": {"accelerators": ["cpu"]},
            }
        },
        "evaluators": {
            "common_evaluator": {
                "metrics": [
                    {
                        "name": "latency",
                        "sub_types": [{"name": "avg", "priority": 1}],
                        "user_config": {"data_dir": "data", "batch_size": 1},
                    }
                ]
            }
        },
        "passes": {
            "quantization": {
                "type": "OnnxQuantization",
                "config": {
                    "quant_mode": "integer",
                    "activation_type": "int8",
                    "weight_type": "int8",
                    "static": False,  # Using dynamic quantization for simplicity
                },
            }
        },
        "engine": {
            "evaluator": "common_evaluator",
            "host": "local_system",
            "target": "local_system",
            "cache_dir": "cache",
            "output_dir": str(output_model_path.parent),
            "output_name": output_model_path.stem,
        },
    }

    logger.info(f"Starting model optimization for {input_model_path}...")
    logger.info(f"Olive config: {olive_config}")

    # Forcing output name to be exactly what we want.
    # Olive's output structure can be complex.
    olive_run(olive_config)

    # The output from olive_run is complex. We'll find the quantized model
    # in the output directory and rename it to the desired output path.
    # A typical path is: {output_dir}/{output_name}_cpu-onnx_quantized/
    optimized_dir = output_model_path.parent / f"{output_model_path.stem}_cpu-onnx_quantization"
    
    # Find the model file in the output directory
    try:
        optimized_model_file = next(optimized_dir.glob("*.onnx"))
        final_output_path = output_model_path.parent / f"{output_model_path.stem}.onnx"
        optimized_model_file.rename(final_output_path)
        logger.info(f"Optimization complete. Model saved to {final_output_path}")
    except StopIteration:
        logger.error(f"Could not find the optimized model in {optimized_dir}. Olive run might have failed.")
        sys.exit(1)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Optimize an ONNX model using INT8 quantization."
    )
    parser.add_argument(
        "--input-model",
        type=Path,
        required=True,
        help="Path to the input ONNX model.",
    )
    parser.add_argument(
        "--output-model",
        type=Path,
        required=True,
        help="Path to save the optimized ONNX model.",
    )
    args = parser.parse_args()

    try:
        optimize_model(args.input_model, args.output_model)
        logger.info("Script finished successfully.")
    except Exception as e:
        logger.exception(f"An error occurred during optimization: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()