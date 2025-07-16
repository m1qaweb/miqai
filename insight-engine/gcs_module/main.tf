# ------------------------------------------------------------------------------
# GCS BUCKET FOR VIDEO INGESTION
# ------------------------------------------------------------------------------
resource "google_storage_bucket" "ingestion_bucket" {
  # Naming the bucket using the variable defined in variables.tf.
  # Bucket names must be globally unique.
  name          = var.ingestion_bucket_name
  project       = var.project_id
  location      = var.location
  storage_class = "STANDARD"

  # Enable versioning to protect against accidental overwrites or deletions.
  # This keeps a history of objects, allowing for recovery.
  versioning {
    enabled = true
  }

  # A lifecycle rule to manage object versions and control costs.
  # This rule will automatically delete objects after 30 days.
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 30 # Days
    }
  }

  # Enforce uniform bucket-level access to simplify permissions management.
  # This disables object-level ACLs and ensures that only bucket-level IAM
  # policies grant access to objects.
  uniform_bucket_level_access = true
}

# ------------------------------------------------------------------------------
# GCS BUCKET FOR TERRAFORM REMOTE STATE
# ------------------------------------------------------------------------------
resource "google_storage_bucket" "tfstate" {
  # Naming the bucket for Terraform state storage.
  name          = var.tfstate_bucket_name
  project       = var.project_id
  location      = var.location
  storage_class = "STANDARD"

  # Enable versioning to keep a history of the infrastructure's state files.
  # This is critical for auditing changes and recovering previous states.
  versioning {
    enabled = true
  }

  # A lifecycle rule to clean up old, noncurrent state file versions.
  # This helps manage storage costs by deleting historical versions after 30 days.
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      num_newer_versions = 10 # Keep at least 10 newer versions
      with_state         = "ANY"
    }
  }

  # Prevent accidental deletion of the Terraform state bucket.
  # This is a critical safeguard to avoid losing the infrastructure state,
  # which would orphan all managed resources.
  lifecycle {
    prevent_destroy = true
  }

  # Enforce uniform bucket-level access for consistent and secure IAM.
  uniform_bucket_level_access = true
}