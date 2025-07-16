variable "service_name" {
  description = "The name of the Cloud Run service."
  type        = string
}

variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "container_image" {
  description = "The container image to deploy."
  type        = string
}