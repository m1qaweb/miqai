variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "region" {
  description = "The GCP region for the API Gateway."
  type        = string
}

variable "api_id" {
  description = "The ID for the API Gateway API."
  type        = string
  default     = "insight-engine-api"
}

variable "gateway_id" {
  description = "The ID for the API Gateway."
  type        = string
  default     = "insight-engine-gateway"
}

variable "cloud_run_service_url" {
  description = "The URL of the backend Cloud Run service."
  type        = string
}

resource "google_api_gateway_api" "api" {
  project = var.project_id
  api_id  = var.api_id
}

resource "google_api_gateway_api_config" "api_config" {
  project      = var.project_id
  api          = google_api_gateway_api.api.api_id
  api_config_id_prefix = "insight-engine-config-"

  openapi_documents {
    document {
      path     = "api_gateway.yml"
      contents = base64encode(templatefile("${path.module}/../../api_gateway.yml", {
        SERVICE_URL = var.cloud_run_service_url
      }))
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_api_gateway_gateway" "gateway" {
  project   = var.project_id
  region    = var.region
  gateway_id = var.gateway_id
  api_config = google_api_gateway_api_config.api_config.id

  depends_on = [google_api_gateway_api_config.api_config]
}

output "gateway_url" {
  description = "The URL of the deployed API Gateway."
  value       = "https://${google_api_gateway_gateway.gateway.default_hostname}"
}