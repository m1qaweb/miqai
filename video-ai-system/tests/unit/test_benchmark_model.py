import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

import cv2
import numpy as np
import onnx
import onnx.helper as h
from onnx import TensorProto

# Add scripts directory to path to allow import
sys.path.append(str(Path(__file__).parent.parent.parent / "scripts"))

from benchmark_model import main as benchmark_main
from benchmark_model import run_benchmark


def create_dummy_onnx_model(path: Path):
    """Creates a simple dummy ONNX model for testing."""
    X = h.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 224, 224])
    Y = h.make_tensor_value_info("output", TensorProto.FLOAT, [1, 1000])
    node_def = h.make_node("Identity", ["input"], ["output"])
    graph_def = h.make_graph([node_def], "dummy-benchmark-model", [X], [Y])
    model_def = h.make_model(graph_def, producer_name="benchmark_test")
    onnx.save(model_def, str(path))


def create_dummy_video_file(path: Path, frames=5, width=640, height=480):
    """Creates a small, dummy MP4 video file."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(path), fourcc, 20.0, (width, height))
    for _ in range(frames):
        frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        out.write(frame)
    out.release()


class TestBenchmarkModelScript(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(__file__).parent / "test_benchmark_output"
        self.test_dir.mkdir(exist_ok=True)
        self.model_path = self.test_dir / "dummy_benchmark_model.onnx"
        self.video_path = self.test_dir / "dummy_video.mp4"
        create_dummy_onnx_model(self.model_path)
        create_dummy_video_file(self.video_path, frames=5)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)

    @patch("sys.stdout.write")
    def test_run_benchmark_output(self, mock_stdout_write):
        """Tests that the benchmark script produces valid JSON output."""
        run_benchmark(self.model_path, self.video_path, num_frames=5)
        
        # Check that something was written to stdout
        self.assertTrue(mock_stdout_write.called)
        
        # Get the string passed to the last call of stdout.write
        output_json_str = mock_stdout_write.call_args[0][0]
        
        # Validate the output is valid JSON
        try:
            data = json.loads(output_json_str)
        except json.JSONDecodeError:
            self.fail("Output was not valid JSON.")

        # Check for key fields in the output
        self.assertIn("model_path", data)
        self.assertIn("performance_metrics", data)
        self.assertIn("average_latency_ms", data["performance_metrics"])
        self.assertIn("p95_latency_ms", data["performance_metrics"])
        self.assertEqual(data["benchmark_params"]["frames_processed"], 5)

    def test_benchmark_model_input_not_found(self):
        """Tests that a FileNotFoundError is raised for a missing model."""
        with self.assertRaises(FileNotFoundError):
            run_benchmark(Path("non_existent_model.onnx"), self.video_path)

    def test_benchmark_video_not_found(self):
        """Tests that a FileNotFoundError is raised for a missing video."""
        with self.assertRaises(FileNotFoundError):
            run_benchmark(self.model_path, Path("non_existent_video.mp4"))

    @patch("sys.argv", ["benchmark_model.py", "--model-path", "m.onnx", "--video-path", "v.mp4"])
    @patch("benchmark_model.run_benchmark")
    def test_main_function(self, mock_run_benchmark):
        """Tests that the main function parses args and calls the benchmark runner."""
        benchmark_main()
        mock_run_benchmark.assert_called_once_with(Path("m.onnx"), Path("v.mp4"), 30)

    @patch("sys.argv", ["benchmark_model.py"])
    def test_main_function_no_args(self):
        """Tests that main function handles missing arguments gracefully."""
        with self.assertRaises(SystemExit) as cm:
            benchmark_main()
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()