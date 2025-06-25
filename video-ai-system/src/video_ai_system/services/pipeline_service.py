import json
import importlib
from pathlib import Path
from typing import List, Any, Generator, Dict
from video_ai_system.modules.module_interface import VideoModule
from video_ai_system.services.model_registry_service import ModelRegistryService


class PipelineService:
    """
    Encapsulates the logic for loading and executing processing pipelines.
    """

    def __init__(self, model_registry_service: ModelRegistryService):
        self.pipelines: Dict[str, List[VideoModule]] = {}
        self.model_registry_service = model_registry_service

    def load_from_config(self, config_path_str: str):
        """Loads and initializes pipelines from a config file."""
        config_path = Path(config_path_str)
        if not config_path.is_file():
            raise RuntimeError(f"Configuration file not found at {config_path}")

        with config_path.open() as f:
            config = json.load(f)

        self.load_from_config_dict(config)

    def load_from_config_dict(self, config: dict):
        """Loads and initializes pipelines from a configuration dictionary."""
        pipelines_config = config.get("pipelines", {})

        for pipeline_name, pipeline_modules in pipelines_config.items():
            pipeline = []
            for module_config in pipeline_modules:
                module_name = module_config.get("module_name")
                if not module_name:
                    raise RuntimeError(
                        f"Module config in pipeline '{pipeline_name}' missing 'module_name': {module_config}"
                    )

                try:
                    module_path = f"video_ai_system.modules.{module_name}"
                    imported_module = importlib.import_module(module_path)
                    class_name = "".join(
                        word.capitalize() for word in module_name.split("_")
                    )
                    module_class = getattr(imported_module, class_name)

                    instance = module_class(
                        module_config=module_config,
                        model_registry_service=self.model_registry_service,
                    )
                    instance.initialize(module_config.get("module_params", {}))
                    pipeline.append(instance)
                except (ModuleNotFoundError, AttributeError) as e:
                    raise RuntimeError(
                        f"Failed to load module '{module_name}' in pipeline '{pipeline_name}': {e}"
                    )

            self.pipelines[pipeline_name] = pipeline
            loaded_modules = [p.__class__.__name__ for p in pipeline]
            print(
                f"PipelineService loaded '{pipeline_name}' pipeline: {' -> '.join(loaded_modules)}"
            )

    def execute_pipeline(self, pipeline_name: str, initial_data: Any) -> List[Any]:
        """
        Executes a specific named pipeline. Correctly handles generator modules.
        """
        pipeline = self.pipelines.get(pipeline_name)
        if not pipeline:
            raise ValueError(f"Pipeline '{pipeline_name}' not found.")

        final_results = []

        # The first module might be a generator (e.g., DataCollectionModule)
        first_module = pipeline[0]
        data_stream = first_module.process(initial_data)

        # The rest of the pipeline processes each item from the stream
        processing_pipeline = pipeline[1:]

        if isinstance(data_stream, Generator):
            for item in data_stream:
                processed_item = item
                for module in processing_pipeline:
                    processed_item = module.process(processed_item)
                final_results.append(processed_item)
        elif not processing_pipeline:
            # If there's only one module and it's not a generator, its output is the final result
            final_results.append(data_stream)
        else:
            # If the first module is not a generator, process its single output
            processed_item = data_stream
            for module in processing_pipeline:
                processed_item = module.process(processed_item)
            final_results.append(processed_item)

        return final_results

    def get_pipeline(self, name: str) -> List[VideoModule]:
        """Returns the specified pipeline."""
        return self.pipelines.get(name, [])
