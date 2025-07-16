# Summarization API

The Summarization API provides endpoints for generating intelligent summaries from your videos.

## Process a video for summarization

-   **Endpoint**: `POST /v1/analysis/summarize/process`
-   **Description**: Processes a video, extracts data, and stores it in the vector store for summarization.
-   **Query Parameters**:
    -   `video_uri` (string, required): The GCS URI of the video to process.
-   **Response**:
    -   `status` (string): The status of the processing job.
    -   `video_id` (string): A unique identifier for the video.

## Generate a summary

-   **Endpoint**: `GET /v1/analysis/summarize/`
-   **Description**: Generates a text summary for a video specified by its video ID.
-   **Query Parameters**:
    -   `video_id` (string, required): The unique ID of the video.
    -   `q` (string, required): The user query for summarization.
-   **Response**: A `StreamingResponse` with Server-Sent Events (SSE) containing the summary.