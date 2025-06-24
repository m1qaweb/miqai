from fastapi.testclient import TestClient
import numpy as np
from video_ai_system.main import app, get_pipeline_service
from video_ai_system.services.pipeline_service import PipelineService

def test_health_check():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

def test_process_frame_endpoint():
    class MockPipelineService(PipelineService):
        def execute(self, initial_data):
            return [np.array([1, 2, 3])]

    def override_get_pipeline_service():
        return MockPipelineService()

    app.dependency_overrides[get_pipeline_service] = override_get_pipeline_service

    with TestClient(app) as client:
        response = client.post("/process_frame", json={"data": {}})
        assert response.status_code == 200
        assert response.json() == {"status": "success", "result": [[1, 2, 3]]}

    app.dependency_overrides.clear()