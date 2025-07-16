# ------------------------------------------------------------------------------
# PROJECT CONFIGURATION
# ------------------------------------------------------------------------------

variable "project_id" {
  description = "The GCP project ID where resources will be deployed."
  type        = string
}

variable "location" {
  description = "The GCP region where the GCS buckets will be created (e.g., 'US-CENTRAL1')."
  type        = string
}

# ------------------------------------------------------------------------------
# BUCKET-SPECIFIC CONFIGURATION
# ------------------------------------------------------------------------------

variable "ingestion_bucket_name" {
  description = "A globally unique name for the video ingestion GCS bucket."
  type        = string
}

variable "tfstate_bucket_name" {
  description = "A globally unique name for the GCS bucket to store Terraform state."
  type        = string
}