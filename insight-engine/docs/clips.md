# Clip Extraction API

The Clip Extraction API provides endpoints for extracting clips from your videos based on object detection.

## Extract clips from a video

-   **Endpoint**: `POST /v1/analysis/extract-clips/`
-   **Description**: Enqueues tasks to extract relevant clips from a video by publishing messages to a GCP Pub/Sub topic.
-   **Request Body**:
    -   `video_uri` (string, required): The GCS URI of the video.
    -   `clips` (array of objects, required): A list of clips to extract. Each object should have the following properties:
        -   `start_time` (float, required): The start time of the clip in seconds.
        -   `end_time` (float, required): The end time of the clip in seconds.
-   **Response**:
    -   `status` (string): The status of the clip extraction job.