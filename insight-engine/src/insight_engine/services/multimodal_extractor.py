# Prerequisites:
# 1. Google Cloud SDK installed and authenticated.
#    Run `gcloud auth application-default login` to authenticate.
import asyncio
import logging
from typing import List

from google.cloud import speech, videointelligence, dlp_v2
from pydantic import BaseModel
from insight_engine.resilience import gcp_resilient
from insight_engine.resilience.fallbacks import FallbackManager

logger = logging.getLogger(__name__)


class ExtractedData(BaseModel):
    """
    Data model for storing extracted multimodal information.
    """
    transcript: str
    visual_labels: List[str]


class MultimodalExtractor:
    """
    Service to extract multimodal data (transcript, visual labels) from a video.
    """

    def __init__(self, dlp_client: dlp_v2.DlpServiceClient):
        """
        Initializes the MultimodalExtractor.

        Args:
            dlp_client: An instance of the DlpServiceClient.
        """
        self.dlp_client = dlp_client

    async def extract_data(self, video_uri: str, project_id: str) -> ExtractedData:
        """
        Main entry point to extract data from a video concurrently.

        Args:
            video_uri: The URI of the video file.
            project_id: The GCP project ID.

        Returns:
            An ExtractedData object containing the transcript and visual labels.
        """
        transcript_task = self._extract_transcript(video_uri)
        visual_labels_task = self._extract_visual_labels(video_uri)

        # Run extraction tasks concurrently
        results = await asyncio.gather(
            transcript_task,
            visual_labels_task,
            return_exceptions=True
        )
        
        transcript_result = results[0]
        visual_labels_result = results[1]

        transcript = transcript_result if isinstance(transcript_result, str) else ""
        visual_labels = visual_labels_result if isinstance(visual_labels_result, list) else []

        redacted_transcript = await self._redact_text(transcript, project_id)

        return ExtractedData(
            transcript=redacted_transcript,
            visual_labels=visual_labels
        )

    @gcp_resilient("speech_to_text", fallback=FallbackManager.speech_to_text_fallback)
    async def _extract_transcript(self, video_uri: str) -> str:
        """
        Extracts transcript from the video's audio track using Google Cloud Speech-to-Text.
        """
        logger.info(f"Extracting transcript from video: {video_uri}")
        client = speech.SpeechAsyncClient()

        config = speech.RecognitionConfig(
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="video"
        )
        audio = speech.RecognitionAudio(uri=video_uri)

        operation = await client.long_running_recognize(config=config, audio=audio)
        response = await asyncio.to_thread(operation.result, timeout=300)

        if response and hasattr(response, 'results'):
            transcript = "".join(
                result.alternatives[0].transcript for result in response.results
            )
            logger.info(f"Successfully extracted transcript ({len(transcript)} characters)")
            return transcript
        
        logger.warning("No transcript results returned from Speech-to-Text API")
        return ""

    @gcp_resilient("video_intelligence", fallback=FallbackManager.video_intelligence_fallback)
    async def _extract_visual_labels(self, video_uri: str) -> list[str]:
        """
        Extracts visual labels from the video frames using Google Cloud Video Intelligence API.
        """
        logger.info(f"Extracting visual labels from video: {video_uri}")
        client = videointelligence.VideoIntelligenceServiceClient()

        features = [videointelligence.Feature.LABEL_DETECTION]
        
        def sync_annotate_video():
            operation = client.annotate_video(
                request={"input_uri": video_uri, "features": features}
            )
            return operation.result(timeout=300)

        result = await asyncio.to_thread(sync_annotate_video)

        if result and result.annotation_results:
            shot_labels = [
                label.entity.description
                for annotation in result.annotation_results
                for label in annotation.shot_label_annotations
            ]
            unique_labels = list(set(shot_labels))
            logger.info(f"Successfully extracted {len(unique_labels)} unique visual labels")
            return unique_labels
        
        logger.warning("No visual labels returned from Video Intelligence API")
        return []

    @gcp_resilient("dlp", fallback=FallbackManager.dlp_fallback)
    async def _redact_text(self, text: str, project_id: str) -> str:
        """
        Redacts sensitive information from the given text using the DLP API.
        """
        if not text.strip():
            return text
            
        logger.info(f"Redacting sensitive information from text ({len(text)} characters)")
        
        parent = f"projects/{project_id}"
        item = {"value": text}
        inspect_config = {
            "info_types": [{"name": "PERSON_NAME"}, {"name": "EMAIL_ADDRESS"}]
        }
        deidentify_config = {
            "info_type_transformations": {
                "transformations": [
                    {"primitive_transformation": {"replace_with_info_type_config": {}}}
                ]
            }
        }

        response = self.dlp_client.deidentify_content(
            request={
                "parent": parent,
                "deidentify_config": deidentify_config,
                "inspect_config": inspect_config,
                "item": item,
            }
        )
        
        redacted_text = response.item.value
        logger.info("Successfully redacted sensitive information")
        return redacted_text