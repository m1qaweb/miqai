variable "project_id" {
  description = "The GCP project ID to host the resources."
  type        = string
}

variable "location" {
  description = "The GCP region where the GCS buckets will be created."
  type        = string
  default     = "US-CENTRAL1"
}

variable "video_upload_bucket_name" {
  description = "The name of the GCS bucket for video uploads."
  type        = string
}

variable "tfstate_bucket_name" {
  description = "The name of the GCS bucket for storing Terraform state."
  type        = string
}

variable "uploader_service_account_email" {
  description = "The email address of the service account that will be granted permission to upload videos."
  type        = string
}