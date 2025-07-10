# This terraform block configures the GCS backend for storing the terraform state remotely.
# Using a remote backend is a best practice for teams to ensure that everyone is working
# with the same state and to prevent conflicts. State locking is enabled to prevent
# concurrent state operations, which can lead to corruption.
terraform {
  backend "gcs" {
    bucket = "your-tfstate-bucket-name" # This will be parameterized later
    prefix = "terraform/state"
  }
}

# Creates the GCS bucket that will be used to store the remote terraform state.
# Versioning is enabled as a security measure to protect against accidental deletions
# or overwrites of the state file. It allows for the recovery of previous state versions.
resource "google_storage_bucket" "tfstate" {
  name          = var.tfstate_bucket_name
  project       = var.project_id
  location      = var.location
  force_destroy = false # Set to true to allow deletion of non-empty buckets

  versioning {
    enabled = true
  }

  # Uniform bucket-level access is enabled to simplify access control.
  uniform_bucket_level_access = true
}

# Creates the GCS bucket for video uploads.
# Versioning is enabled to protect against accidental data loss.
# The lifecycle rule automatically deletes objects after 30 days to manage costs.
resource "google_storage_bucket" "video_uploads" {
  name          = var.video_upload_bucket_name
  project       = var.project_id
  location      = var.location
  force_destroy = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30 # days
    }
    action {
      type = "Delete"
    }
  }

  uniform_bucket_level_access = true
}

# This resource grants the specified service account the 'Storage Object Creator' role
# on the video upload bucket. This follows the principle of least privilege by only
# granting the necessary permissions for the service account to upload objects,
# without giving it broader permissions like deletion or ownership.
resource "google_storage_bucket_iam_member" "uploader" {
  bucket = google_storage_bucket.video_uploads.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${var.uploader_service_account_email}"
}