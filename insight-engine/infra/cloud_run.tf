resource "google_cloud_run_v2_service" "default" {
  name     = "insight-engine"
  location = "us-central1"

  template {
    containers {
      image = "gcr.io/${var.gcp_project_id}/insight-engine"
      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.gcp_project_id
      }
      env {
        name  = "REDIS_HOST"
        value = var.redis_host
      }

      startup_health_check {
        timeout {
          seconds = 240
        }
        period_seconds  = 30
        failure_threshold = 3
        tcp_socket {
          port = 8080
        }
      }

      liveness_health_check {
        period_seconds = 30
        http_get {
          path = "/health"
          port = 8080
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
  }

  traffic {
    percent         = 100
    type            = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Allow unauthenticated access to the service
resource "google_cloud_run_v2_service_iam_member" "noauth" {
  project  = google_cloud_run_v2_service.default.project
  location = google_cloud_run_v2_service.default.location
  name     = google_cloud_run_v2_service.default.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}