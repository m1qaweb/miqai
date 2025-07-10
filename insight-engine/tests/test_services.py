import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from insight_engine.services.clip_generator import ClipGenerator
from insight_engine.services.multimodal_extractor import MultimodalExtractor, ExtractedData
from insight_engine.tools.vector_store import VectorStore


@pytest.mark.asyncio
async def test_multimodal_extractor(mocker):
    """Tests the MultimodalExtractor service, mocking Google Cloud clients."""
    # Mock the Speech-to-Text client
    mock_speech_client = mocker.patch("google.cloud.speech.SpeechAsyncClient").return_value
    mock_speech_operation = AsyncMock()
    mock_speech_result = MagicMock()
    mock_speech_result.results = [MagicMock(alternatives=[MagicMock(transcript="This is a test transcript.")])]
    mock_speech_operation.result.return_value = mock_speech_result
    mock_speech_client.long_running_recognize.return_value = mock_speech_operation

    # Mock the Video Intelligence client
    mock_videointelligence = mocker.patch("insight_engine.services.multimodal_extractor.videointelligence")
    mock_video_client = mock_videointelligence.VideoIntelligenceServiceClient.return_value
    mock_video_operation = MagicMock()
    mock_video_result = MagicMock()
    label_annotation = mock_video_result.annotation_results.add()
    label = label_annotation.shot_label_annotations.add()
    label.entity.description = "test label"
    mock_video_operation.result.return_value = mock_video_result
    mock_video_client.annotate_video.return_value = mock_video_operation

    # Instantiate the extractor and call the method
    extractor = MultimodalExtractor()
    result = await extractor.extract_data("gs://fake-bucket/fake-video.mp4")

    # Assertions
    assert isinstance(result, ExtractedData)
    assert result.transcript == "This is a test transcript."
    assert result.visual_labels == ["test label"]
    mock_speech_client.long_running_recognize.assert_called_once()
    mock_video_client.annotate_video.assert_called_once()


@pytest.mark.asyncio
async def test_vector_store(mocker):
    """Tests the VectorStore service, mocking Vertex AI."""
    # Mock Vertex AI
    mocker.patch("vertexai.init")
    mock_embedding_model = mocker.patch("vertexai.language_models.TextEmbeddingModel").return_value
    mock_embedding = MagicMock()
    mock_embedding.values = [0.1] * 768
    mock_embedding_model.get_embeddings.return_value = [mock_embedding]

    # Instantiate the vector store
    vector_store = VectorStore(project_id="fake-project", location="fake-location")

    # Upsert a document
    doc_text = "This is a test document."
    await vector_store.upsert_document(doc_text, {"source": "test"})

    # Query for the document
    query_text = "A document for testing."
    results = await vector_store.query(query_text)

    # Assertions
    assert len(results) == 1
    assert results[0] == doc_text
    mock_embedding_model.get_embeddings.assert_called()


@pytest.mark.asyncio
async def test_clip_generator(mocker):
    """Tests the ClipGenerator service, mocking ffmpeg."""
    # Mock ffmpeg.run_async
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"stdout", b"stderr")
    mock_process.returncode = 0
    mocker.patch("asyncio.create_subprocess_exec", return_value=mock_process)

    # Instantiate the clip generator
    clip_generator = ClipGenerator()

    # Generate a clip
    await clip_generator.generate_clip(
        video_uri="fake.mp4", start_time=10, end_time=20, output_path="clip.mp4"
    )

    # Assertion
    asyncio.create_subprocess_exec.assert_called_once()
