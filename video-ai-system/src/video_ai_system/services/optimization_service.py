import json
from jsonschema import validate
import torch
import onnx
import numpy as np
import onnxruntime
import time
from neural_compressor.quantization import fit
from neural_compressor.config import PostTrainingQuantConfig


class OptimizationService:
    """
    A service to handle model optimization tasks, including conversion
    and quantization, based on a provided configuration.
    """

    def __init__(self, config: dict):
        """
        Initializes the OptimizationService with a validated configuration.

        Args:
            config (dict): A dictionary containing the service's configuration.
        """
        self.config = config

    @classmethod
    def load_from_config(cls, config_path: str, schema_path: str):
        """
        Loads, validates, and creates an instance of the OptimizationService
        from a JSON configuration file.

        Args:
            config_path (str): The path to the JSON configuration file.
            schema_path (str): The path to the JSON schema for validation.

        Returns:
            OptimizationService: An instance of the service.

        Raises:
            ValidationError: If the configuration is invalid.
            FileNotFoundError: If the config or schema file is not found.
        """
        with open(config_path, "r") as f:
            config = json.load(f)

        with open(schema_path, "r") as f:
            schema = json.load(f)

        # Assuming the optimization service config is a part of the main config
        optimization_schema = schema["properties"]["optimization_service"]
        validate(instance=config, schema=optimization_schema)

        return cls(config)

    def _export_to_onnx(self, source_model_path: str, output_onnx_path: str):
        """
        Loads a PyTorch model and exports it to ONNX format.

        Args:
            source_model_path (str): The path to the source PyTorch model.
            output_onnx_path (str): The path to save the exported ONNX model.
        """
        # Load the PyTorch model
        # In a real scenario, this would load a more complex model.
        # For this task, the model is defined and saved in the test.
        model = torch.load(source_model_path, weights_only=False)
        model.eval()

        # Create a dummy input tensor with a dynamic batch size
        dummy_input = torch.randn(1, 3, 224, 224, requires_grad=True)

        # Export the model
        torch.onnx.export(
            model,
            dummy_input,
            output_onnx_path,
            export_params=True,
            opset_version=11,
            do_constant_folding=True,
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
        )

        # Verify the ONNX model
        onnx_model = onnx.load(output_onnx_path)
        onnx.checker.check_model(onnx_model)

    def _benchmark_model(self, onnx_model_path: str, iterations: int = 100) -> dict:
        """
        Benchmarks an ONNX model to measure its inference latency.

        Args:
            onnx_model_path (str): The path to the ONNX model file.
            iterations (int): The number of inference runs to perform.

        Returns:
            dict: A dictionary containing performance metrics like
                  'average_latency_ms' and 'p95_latency_ms'.
        """
        # Create an inference session
        session = onnxruntime.InferenceSession(onnx_model_path)
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape

        # Adjust for dynamic batch size if needed (e.g., 'batch_size')
        # For this benchmark, we'll use a fixed batch size of 1.
        if isinstance(input_shape[0], str):
            input_shape[0] = 1

        # Generate dummy input data
        dummy_input = np.random.randn(*input_shape).astype(np.float32)

        latencies = []
        # Warm-up run
        session.run(None, {input_name: dummy_input})

        for _ in range(iterations):
            start_time = time.perf_counter()
            session.run(None, {input_name: dummy_input})
            end_time = time.perf_counter()
            latencies.append((end_time - start_time) * 1000)  # Convert to ms

        # Calculate metrics
        avg_latency = np.mean(latencies)
        p95_latency = np.percentile(latencies, 95)

        return {
            "average_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
        }

    def _quantize_model(self, input_model_path: str, output_model_path: str):
        """
        Quantizes an ONNX model using Intel Neural Compressor.

        Args:
            input_model_path (str): Path to the input ONNX model.
            output_model_path (str): Path to save the quantized model.
        """

        # Dummy dataloader for calibration
        class DummyDataloader:
            def __init__(self, batch_size=1):
                self.batch_size = batch_size

            def __iter__(self):
                for _ in range(10):  # Yield 10 batches of random data
                    dummy_input = np.random.rand(self.batch_size, 3, 224, 224).astype(
                        np.float32
                    )
                    yield dummy_input, None  # (input, label=None)

        # Define the quantization configuration
        config = PostTrainingQuantConfig(approach="static", backend="onnxrt_dnnl_ep")

        # Create a dataloader instance
        dataloader = DummyDataloader()

        # Run quantization
        q_model = fit(model=input_model_path, conf=config, calib_dataloader=dataloader)

        # Save the quantized model
        q_model.save(output_model_path)

    def run(self, source_model_path: str, output_dir: str) -> dict:
        """
        Runs the full optimization pipeline: export, benchmark, quantize, and re-benchmark.

        Args:
            source_model_path (str): The path to the source PyTorch model.
            output_dir (str): The directory to save the output models.

        Returns:
            dict: A dictionary containing the paths to the generated models and
                  their performance metrics.
        """
        # Define output paths
        base_onnx_path = f"{output_dir}/model.onnx"
        quantized_onnx_path = f"{output_dir}/model.quant.onnx"

        # 1. Export to ONNX
        self._export_to_onnx(source_model_path, base_onnx_path)

        # 2. Benchmark the base ONNX model
        base_metrics = self._benchmark_model(base_onnx_path)

        # 3. Quantize the model
        self._quantize_model(base_onnx_path, quantized_onnx_path)

        # 4. Benchmark the quantized model
        quantized_metrics = self._benchmark_model(quantized_onnx_path)

        # 5. Compile and return results
        results = {
            "onnx_model_path": base_onnx_path,
            "quantized_model_path": quantized_onnx_path,
            "base_model_metrics": base_metrics,
            "quantized_model_metrics": quantized_metrics,
        }

        return results
