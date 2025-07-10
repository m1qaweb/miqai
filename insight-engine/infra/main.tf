# Terraform configuration for the serverless video processing trigger.

# Define variables for reusable values
variable "project_id" {
  description = "The Google Cloud project ID."
  type        = string
}

variable "location" {
  description = "The Google Cloud region for the resources."
  type        = string
}

variable "bucket_name" {
  description = "The name of the GCS bucket for video uploads."
  type        = string
}

# Create a dedicated service account for the Cloud Function
resource "google_service_account" "video_processor_sa" {
  project      = var.project_id
  account_id   = "video-processor-sa"
  display_name = "Video Processor Service Account"
}

# Grant the service account the necessary IAM roles
resource "google_project_iam_member" "eventarc_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.video_processor_sa.email}"
}

resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.video_processor_sa.email}"
}

resource "google_project_iam_member" "logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.video_processor_sa.email}"
}

resource "google_project_iam_member" "run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.video_processor_sa.email}"
}

# Define the Google Cloud Function
resource "google_cloudfunctions2_function" "video_processor_function" {
  project  = var.project_id
  name     = "video-processor-function"
  location = var.location

  build_config {
    runtime     = "python311"
    entry_point = "process_video_gcs"
    # The source code will be uploaded separately.
    # For now, we can point to an empty placeholder or a bucket source.
    # This example assumes the source is handled outside this TF script.
    source {
      storage_source {
        bucket = var.bucket_name # This could be a dedicated bucket for function sources
        object = "source.zip"    # Placeholder source archive
      }
    }
  }

  service_config {
    max_instance_count = 5
    min_instance_count = 0
    available_memory   = "512Mi"
    timeout_seconds    = 540
    service_account_email = google_service_account.video_processor_sa.email
  }
}

# Define the Eventarc trigger
resource "google_eventarc_trigger" "video_upload_trigger" {
  project  = var.project_id
  name     = "video-upload-trigger"
  location = var.location

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  matching_criteria {
    attribute = "bucket"
    value     = var.bucket_name
  }

  destination {
    cloud_function = google_cloudfunctions2_function.video_processor_function.id
  }

  service_account = google_service_account.video_processor_sa.email
}