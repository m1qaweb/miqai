provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

terraform {
  backend "gcs" {
    bucket = "the-insight-engine-tfstate"
    prefix = "prod"
  }
}

module "storage" {
  source      = "./modules/gcs"
  project_id  = var.gcp_project_id
  location    = var.gcp_region
  bucket_name = "insight-engine-ingestion"
}

module "pubsub" {
  source     = "./modules/pubsub"
  project_id = var.gcp_project_id
  topic_name = "clip-extraction-jobs"
}

module "api_service" {
  source          = "./modules/cloud_run"
  project_id      = var.gcp_project_id
  service_name    = "api-orchestrator"
  container_image = "gcr.io/${var.gcp_project_id}/api-orchestrator:latest"
}