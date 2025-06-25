import json
import pytest
from jsonschema import ValidationError
from video_ai_system.services.optimization_service import OptimizationService
import torch
import torch.nn as nn
import os


@pytest.fixture
def valid_config_file(tmp_path):
    config = {
        "enabled": True,
        "quantization": {"method": "int8", "calibration_dataset_size": 1000},
        "conversion_format": "onnx",
    }
    config_file = tmp_path / "valid_config.json"
    config_file.write_text(json.dumps(config))
    return str(config_file)


@pytest.fixture
def invalid_config_file(tmp_path):
    config = {
        "enabled": "yes",  # Invalid type
        "quantization": {
            "method": "int8"
            # Missing required property "calibration_dataset_size"
        },
        "conversion_format": "onnx",
    }
    config_file = tmp_path / "invalid_config.json"
    config_file.write_text(json.dumps(config))
    return str(config_file)


@pytest.fixture
def schema_file(tmp_path):
    schema = {
        "type": "object",
        "properties": {
            "optimization_service": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "quantization": {
                        "type": "object",
                        "properties": {
                            "method": {"type": "string"},
                            "calibration_dataset_size": {"type": "integer"},
                        },
                        "required": ["method", "calibration_dataset_size"],
                    },
                    "conversion_format": {"type": "string"},
                },
                "required": ["enabled", "quantization", "conversion_format"],
            }
        },
    }
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps(schema))
    return str(schema_file)


def test_load_from_valid_config(valid_config_file, schema_file):
    """
    Tests that the OptimizationService can be successfully initialized
    from a valid configuration file.
    """
    service = OptimizationService.load_from_config(valid_config_file, schema_file)
    assert isinstance(service, OptimizationService)
    assert service.config["enabled"] is True
    assert service.config["conversion_format"] == "onnx"


def test_load_from_invalid_config(invalid_config_file, schema_file):
    """
    Tests that the OptimizationService raises a ValidationError when
    provided with an invalid configuration file.
    """
    with pytest.raises(ValidationError):
        OptimizationService.load_from_config(invalid_config_file, schema_file)


class SimpleModel(nn.Module):
    def __init__(self):
        super(SimpleModel, self).__init__()
        self.linear = nn.Linear(10, 1)

    def forward(self, x):
        return self.linear(x)


@pytest.fixture
def dummy_pytorch_model(tmp_path):
    model = SimpleModel()
    model_path = tmp_path / "model.pth"
    torch.save(model, model_path)
    return str(model_path)


def test_export_to_onnx_success(dummy_pytorch_model, tmp_path):
    """
    Tests that the _export_to_onnx method successfully creates an ONNX model file.
    """
    config = {
        "enabled": True,
        "quantization": {"method": "int8", "calibration_dataset_size": 1000},
        "conversion_format": "onnx",
    }
    service = OptimizationService(config)
    output_onnx_path = tmp_path / "model.onnx"

    # Since the test model is different from the one expected by the service's
    # _export_to_onnx, we'll create a model that matches the expected input dimensions.
    model = nn.Sequential(
        nn.Flatten(), nn.Linear(3 * 224 * 224, 10)
    )
    torch.save(model, dummy_pytorch_model)

    service._export_to_onnx(dummy_pytorch_model, str(output_onnx_path))

    assert os.path.exists(output_onnx_path)


def test_quantize_model_success(dummy_pytorch_model, tmp_path):
    """
    Tests that the _quantize_model method successfully creates a quantized ONNX model.
    """
    config = {
        "enabled": True,
        "quantization": {"method": "int8", "calibration_dataset_size": 100},
        "conversion_format": "onnx",
    }
    service = OptimizationService(config)
    onnx_model_path = tmp_path / "model.onnx"
    quantized_model_path = tmp_path / "quantized_model.onnx"

    # First, export a model to ONNX
    model = nn.Sequential(
        nn.Flatten(), nn.Linear(3 * 224 * 224, 10)
    )
    torch.save(model, dummy_pytorch_model)
    service._export_to_onnx(dummy_pytorch_model, str(onnx_model_path))

    # Now, quantize the ONNX model
    service._quantize_model(str(onnx_model_path), str(quantized_model_path))

    assert os.path.exists(quantized_model_path)


def test_benchmark_model_success(dummy_pytorch_model, tmp_path):
    """
    Tests that the _benchmark_model method returns valid performance metrics.
    """
    config = {
        "enabled": True,
        "quantization": {"method": "int8", "calibration_dataset_size": 100},
        "conversion_format": "onnx",
    }
    service = OptimizationService(config)
    onnx_model_path = tmp_path / "model.onnx"

    # Export a model to ONNX to be benchmarked
    model = nn.Sequential(
        nn.Flatten(), nn.Linear(3 * 224 * 224, 10)
    )
    # Adjust the input size to match the dummy input in _export_to_onnx
    dummy_input = torch.randn(1, 3, 224, 224)
    # Since the model is created here, we need to adjust the linear layer input features
    # based on the output of the flatten layer.
    # For a 3x224x224 input to a Conv2d(3,3,3) with no padding, the output is 3x222x222.
    # Flattened, this is 3 * 222 * 222 = 147852.
    # Let's use a simpler model for the test to avoid complex calculations.
    model = nn.Sequential(nn.Flatten(), nn.Linear(3 * 224 * 224, 10))
    torch.save(model, dummy_pytorch_model)
    service._export_to_onnx(dummy_pytorch_model, str(onnx_model_path))

    # Benchmark the ONNX model
    metrics = service._benchmark_model(str(onnx_model_path), iterations=10)

    # Assert that the metrics are valid
    assert "average_latency_ms" in metrics
    assert "p95_latency_ms" in metrics
    assert metrics["average_latency_ms"] > 0
    assert metrics["p95_latency_ms"] > 0


def test_run_pipeline_success(dummy_pytorch_model, tmp_path):
    """
    Tests that the full optimization pipeline runs successfully and returns
    a correctly structured results dictionary.
    """
    config = {
        "enabled": True,
        "quantization": {"method": "int8", "calibration_dataset_size": 100},
        "conversion_format": "onnx",
    }
    service = OptimizationService(config)
    output_dir = tmp_path / "optimized_models"
    output_dir.mkdir()

    # Use a model that matches the expected input dimensions for the pipeline
    model = nn.Sequential(nn.Flatten(), nn.Linear(3 * 224 * 224, 10))
    torch.save(model, dummy_pytorch_model)

    # Run the full pipeline
    results = service.run(dummy_pytorch_model, str(output_dir))

    # Assert that the results dictionary is correct
    assert "onnx_model_path" in results
    assert "quantized_model_path" in results
    assert "base_model_metrics" in results
    assert "quantized_model_metrics" in results

    # Assert that the model files were created
    assert os.path.exists(results["onnx_model_path"])
    assert os.path.exists(results["quantized_model_path"])

    # Assert that the metrics are valid
    assert results["base_model_metrics"]["average_latency_ms"] > 0
    assert results["quantized_model_metrics"]["average_latency_ms"] > 0
