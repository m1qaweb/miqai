resource "google_cloud_run_v2_service" "service" {
  name     = var.service_name
  location = var.project_id

  template {
    containers {
      image = var.container_image
    }
  }
}