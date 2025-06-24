import json
import importlib
from pathlib import Path
from typing import List, Any, Generator
from video_ai_system.modules.module_interface import VideoModule

class PipelineService:
    """
    Encapsulates the logic for loading and executing a processing pipeline.
    """
    def __init__(self):
        self.pipeline: List[VideoModule] = []

    def load_from_config(self, config_path_str: str):
        """Loads and initializes a pipeline of modules from a config file."""
        config_path = Path(config_path_str)
        if not config_path.is_file():
            raise RuntimeError(f"Configuration file not found at {config_path}")

        with config_path.open() as f:
            config = json.load(f)
        
        pipeline_config = config.get("pipeline", [])
        
        for module_config in pipeline_config:
            module_name = module_config.get("module_name")
            if not module_name:
                raise RuntimeError(f"Module config missing 'module_name': {module_config}")
            
            try:
                module_path = f"video_ai_system.modules.{module_name}"
                imported_module = importlib.import_module(module_path)
                class_name = "".join(word.capitalize() for word in module_name.split('_'))
                module_class = getattr(imported_module, class_name)
                
                instance = module_class()
                instance.initialize(module_config.get("module_params", {}))
                self.pipeline.append(instance)
            except (ModuleNotFoundError, AttributeError) as e:
                raise RuntimeError(f"Failed to load module '{module_name}': {e}")
        
        loaded_modules = [p.__class__.__name__ for p in self.pipeline]
        print(f"PipelineService loaded pipeline: {' -> '.join(loaded_modules)}")

    def execute(self, initial_data: Any) -> List[Any]:
        """
        Executes the loaded pipeline. Correctly handles generator modules.
        """
        if not self.pipeline:
            return []

        final_results = []
        
        # The first module might be a generator (e.g., DataCollectionModule)
        first_module = self.pipeline[0]
        data_stream = first_module.process(initial_data)
        
        # The rest of the pipeline processes each item from the stream
        processing_pipeline = self.pipeline[1:]

        if isinstance(data_stream, Generator):
            for item in data_stream:
                processed_item = item
                for module in processing_pipeline:
                    processed_item = module.process(processed_item)
                final_results.append(processed_item)
        else:
            # If the first module is not a generator, process its single output
            processed_item = data_stream
            for module in processing_pipeline:
                processed_item = module.process(processed_item)
            final_results.append(processed_item)
            
        return final_results