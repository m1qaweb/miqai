# Prerequisites:
# 1. Google Cloud SDK installed and authenticated.
#    Run `gcloud auth application-default login` to authenticate.
import asyncio
from typing import List

from google.cloud import speech
from google.cloud import videointelligence
from pydantic import BaseModel


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

    async def extract_data(self, video_uri: str) -> ExtractedData:
        """
        Main entry point to extract data from a video concurrently.

        Args:
            video_uri: The URI of the video file.

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

        return ExtractedData(
            transcript=transcript,
            visual_labels=visual_labels
        )

    async def _extract_transcript(self, video_uri: str) -> str:
        """
        Extracts transcript from the video's audio track using Google Cloud Speech-to-Text.
        """
        client = speech.SpeechAsyncClient()

        config = speech.RecognitionConfig(
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="video"
        )
        audio = speech.RecognitionAudio(uri=video_uri)

        operation = await client.long_running_recognize(config=config, audio=audio)
        response = await asyncio.to_thread(operation.result, timeout=300)

        transcript = "".join(
            result.alternatives[0].transcript for result in response.results
        )
        return transcript

    async def _extract_visual_labels(self, video_uri: str) -> list[str]:
        """
        Extracts visual labels from the video frames using Google Cloud Vision API.
        """
        client = videointelligence.VideoIntelligenceServiceClient()

        features = [videointelligence.Feature.LABEL_DETECTION]
        
        def sync_annotate_video():
            operation = client.annotate_video(
                request={"input_uri": video_uri, "features": features}
            )
            return operation.result(timeout=300)

        result = await asyncio.to_thread(sync_annotate_video)

        shot_labels = [
            label.entity.description
            for annotation in result.annotation_results
            for label in annotation.shot_label_annotations
        ]
        return list(set(shot_labels))