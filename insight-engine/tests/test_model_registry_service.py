import pytest
import json
from pathlib import Path
from insight_engine.services.model_registry_service import ModelRegistryService


@pytest.fixture
def registry_path(tmp_path: Path) -> str:
    """Provides a path to a temporary JSON file for the registry."""
    return str(tmp_path / "test_registry.json")


@pytest.fixture
def service(registry_path: str) -> ModelRegistryService:
    """Fixture to create a ModelRegistryService instance with a temporary path."""
    return ModelRegistryService(registry_path=registry_path)


def test_initialization_creates_registry_file(registry_path: str):
    """Test that the registry file is created if it doesn't exist."""
    path = Path(registry_path)
    assert not path.exists()
    ModelRegistryService(registry_path=registry_path)
    assert path.exists()
    with open(path, "r") as f:
        data = json.load(f)
    assert data == {"models": []}


def test_register_first_model_version(service: ModelRegistryService):
    """Test registering a model for the first time."""
    model_name = "test-model-1"
    model_path = "models/test-model-1/v1/model.onnx"
    metadata = {"description": "A test model"}

    result = service.register_model(model_name, model_path, metadata)

    assert result["model_name"] == model_name
    assert result["version"] == 1
    assert result["path"] == model_path
    assert result["status"] == "staging"
    assert result["metadata"]["description"] == "A test model"
    assert "creation_timestamp" in result

    # Verify the content of the registry file
    registry_data = service._read_registry()
    assert len(registry_data["models"]) == 1
    assert registry_data["models"][0] == result


def test_register_subsequent_model_version(service: ModelRegistryService):
    """Test registering a second version of an existing model."""
    model_name = "test-model-1"
    service.register_model(model_name, "path/v1", {})

    result_v2 = service.register_model(model_name, "path/v2", {"info": "v2"})

    assert result_v2["version"] == 2
    assert result_v2["metadata"]["info"] == "v2"

    registry_data = service._read_registry()
    assert len(registry_data["models"]) == 2


def test_list_models_all(service: ModelRegistryService):
    """Test listing all registered models."""
    service.register_model("model-a", "path/a1", {})
    service.register_model("model-a", "path/a2", {})
    service.register_model("model-b", "path/b1", {})

    models = service.list_models()
    assert len(models) == 3


def test_list_models_filtered_by_name(service: ModelRegistryService):
    """Test filtering the list of models by name."""
    service.register_model("model-a", "path/a1", {})
    service.register_model("model-a", "path/a2", {})
    service.register_model("model-b", "path/b1", {})

    models_a = service.list_models(model_name="model-a")
    assert len(models_a) == 2
    assert all(m["model_name"] == "model-a" for m in models_a)

    models_b = service.list_models(model_name="model-b")
    assert len(models_b) == 1
    assert models_b[0]["model_name"] == "model-b"


def test_get_production_model_none_found(service: ModelRegistryService):
    """Test getting a production model when none are active."""
    service.register_model("test-model", "path/v1", {})
    assert service.get_production_model("test-model") is None


def test_activate_model_version(service: ModelRegistryService):
    """Test activating a model version and ensuring it becomes production."""
    service.register_model("test-model", "path/v1", {})

    activated_model = service.activate_model_version("test-model", 1)
    assert activated_model is not None
    assert activated_model["status"] == "production"

    production_model = service.get_production_model("test-model")
    assert production_model is not None
    assert production_model["version"] == 1


def test_activate_demotes_old_production_model(service: ModelRegistryService):
    """Test that activating a new version demotes the old production one."""
    service.register_model("test-model", "path/v1", {})
    service.register_model("test-model", "path/v2", {})

    # Activate v1
    service.activate_model_version("test-model", 1)
    prod_v1 = service.get_production_model("test-model")
    assert prod_v1["version"] == 1

    # Activate v2
    service.activate_model_version("test-model", 2)
    prod_v2 = service.get_production_model("test-model")
    assert prod_v2["version"] == 2

    # Verify that v1 is now 'staging'
    all_models = service.list_models("test-model")
    model_v1 = next(m for m in all_models if m["version"] == 1)
    assert model_v1["status"] == "staging"


def test_activate_non_existent_model(service: ModelRegistryService):
    """Test that activating a non-existent model version returns None."""
    service.register_model("test-model", "path/v1", {})
    result = service.activate_model_version("test-model", 99)
    assert result is None


def test_get_production_model_multiple_models(service: ModelRegistryService):
    """Test getting the correct production model when multiple models exist."""
    service.register_model("model-x", "path/x1", {})
    service.register_model("model-y", "path/y1", {})
    service.register_model("model-y", "path/y2", {})

    service.activate_model_version("model-y", 2)

    assert service.get_production_model("model-x") is None

    prod_y = service.get_production_model("model-y")
    assert prod_y is not None
    assert prod_y["version"] == 2
    assert prod_y["status"] == "production"
