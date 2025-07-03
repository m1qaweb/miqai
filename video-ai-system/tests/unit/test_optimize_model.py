import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import onnx
import onnx.helper as h
from onnx import TensorProto

# Add scripts directory to path to allow import
sys.path.append(str(Path(__file__).parent.parent.parent / "scripts"))

from optimize_model import main as optimize_main
from optimize_model import optimize_model


def create_dummy_onnx_model(path: Path):
    """Creates a simple dummy ONNX model for testing."""
    X = h.make_tensor_value_info("input", TensorProto.FLOAT, [None, 3, 224, 224])
    Y = h.make_tensor_value_info("output", TensorProto.FLOAT, [None, 1000])
    node_def = h.make_node("Identity", ["input"], ["output"])
    graph_def = h.make_graph([node_def], "dummy-model", [X], [Y])
    model_def = h.make_model(graph_def, producer_name="test")
    onnx.save(model_def, str(path))


class TestOptimizeModelScript(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(__file__).parent / "test_optimize_output"
        self.test_dir.mkdir(exist_ok=True)
        self.input_model_path = self.test_dir / "dummy_model.onnx"
        self.output_model_path = self.test_dir / "optimized_model.onnx"
        create_dummy_onnx_model(self.input_model_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)

    @patch("optimize_model.olive_run")
    def test_optimize_model_success(self, mock_olive_run):
        """
        Tests that the optimize_model function calls olive_run and
        renames the output file correctly on a simulated success.
        """
        # Simulate olive creating the output directory and file
        optimized_dir_name = f"{self.output_model_path.stem}_cpu-onnx_quantization"
        olive_output_dir = self.test_dir / optimized_dir_name
        olive_output_dir.mkdir()
        (olive_output_dir / "optimized.onnx").touch()

        optimize_model(self.input_model_path, self.output_model_path)

        mock_olive_run.assert_called_once()
        # Check that the final output file exists after renaming
        final_output_file = self.test_dir / "optimized_model.onnx"
        self.assertTrue(final_output_file.exists())

    def test_optimize_model_input_not_found(self):
        """Tests that a FileNotFoundError is raised for a missing input model."""
        with self.assertRaises(FileNotFoundError):
            optimize_model(Path("non_existent_model.onnx"), self.output_model_path)

    @patch("optimize_model.olive_run")
    @patch("optimize_model.logger")
    @patch("sys.exit")
    def test_optimize_model_olive_failure(self, mock_exit, mock_logger, mock_olive_run):
        """
        Tests that the script logs an error and exits if Olive fails to produce a model.
        """
        # We don't create the expected output directory, simulating an Olive failure
        optimize_model(self.input_model_path, self.output_model_path)
        
        mock_olive_run.assert_called_once()
        self.assertIn(
            call.error("Could not find the optimized model in %s. Olive run might have failed."),
            mock_logger.mock_calls
        )
        mock_exit.assert_called_with(1)

    @patch("sys.argv", ["optimize_model.py", "--input-model", "in.onnx", "--output-model", "out.onnx"])
    @patch("optimize_model.optimize_model")
    def test_main_function(self, mock_optimize_func):
        """Tests that the main function parses args and calls the optimizer."""
        optimize_main()
        mock_optimize_func.assert_called_once_with(Path("in.onnx"), Path("out.onnx"))

    @patch("sys.argv", ["optimize_model.py"])
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_function_no_args(self, mock_parse_args):
        """Tests that main function handles missing arguments gracefully."""
        # The argparse module will call sys.exit(2) on error.
        with self.assertRaises(SystemExit) as cm:
            optimize_main()
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()