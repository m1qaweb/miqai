# Uploads API

The Uploads API provides endpoints for uploading videos and managing your media library.

## Request a presigned URL for video upload

-   **Endpoint**: `POST /v1/uploads/request-url`
-   **Description**: Provides a client with a presigned URL to upload a video file to GCS.
-   **Request Body**:
    -   `file_name` (string, required): The name of the video file to be uploaded.
    -   `content_type` (string, required): The MIME type of the video file.
-   **Response**:
    -   `video_id` (string): A unique identifier for the video.
    -   `upload_url` (string): The presigned URL for the client to upload the video to.