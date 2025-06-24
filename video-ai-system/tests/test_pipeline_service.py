import json
import pytest
from unittest.mock import patch, mock_open
from video_ai_system.services.pipeline_service import PipelineService
from video_ai_system.modules.data_collection_module import DataCollectionModule

def test_load_from_config_success():
    config_data = {
        "pipeline": [{"module_name": "data_collection_module", "module_params": {"video_source_path": "dummy.mp4"}}]
    }
    with patch("pathlib.Path.is_file", return_value=True):
        with patch("pathlib.Path.open", mock_open(read_data=json.dumps(config_data))):
            service = PipelineService()
            service.load_from_config("dummy_path")
            assert len(service.pipeline) == 1
            assert isinstance(service.pipeline[0], DataCollectionModule)

def test_execute_pipeline():
    # This test now checks the corrected generator handling
    class MockGeneratorModule:
        def process(self, data):
            for i in range(3):
                yield i
    
    class MockProcessorModule:
        def process(self, data):
            return data * 2

    service = PipelineService()
    service.pipeline = [MockGeneratorModule(), MockProcessorModule()]
    
    results = service.execute(None)
    assert results == [0, 2, 4]