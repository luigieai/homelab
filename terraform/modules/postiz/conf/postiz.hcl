job "postizz" {
  datacenters = ["dc"]
  type        = "service"

  group "postizz" {
    count = 1

    update {
      healthy_deadline  = "15m"
      progress_deadline = "20m" 
    }


    network {
      port "postizz" {
        static = 5000
        to     = 5000
      }
    }
    
    restart {
      attempts = 2
      interval = "5m"
      delay    = "30s"
      mode     = "delay"
    }

    task "postizz" {
      driver = "docker"
      
      config {
        image = "ghcr.io/gitroomhq/postiz-app:amd64-1729871118"
        ports = ["postizz"]
        volumes = [
          "${NOMAD_ALLOC_DIR}/postiz-config:/config/",
          "${NOMAD_ALLOC_DIR}/postiz-uploads:/uploads/"
        ]
      }

      resources {
        memory_max = 3024
      }

      env {
        MAIN_URL                  = "https://${URL}"
        FRONTEND_URL              = "https://${URL}"
        NEXT_PUBLIC_BACKEND_URL   = "https://${URL}/api"
        JWT_SECRET                = "${JWT_SECRET}"
        DATABASE_URL              = "postgresql://${POSTGREE_USER}:${POSTGREE_PASSWORD}@${POSTGREE_ENDPOINT}:5432/${POSTGREE_DATABASE}"
        REDIS_URL                 = "redis://${REDIS_ENPOINT}"
        BACKEND_INTERNAL_URL      = "http://localhost:3000"
        IS_GENERAL                = "true"
        STORAGE_PROVIDER          = "local"
        UPLOAD_DIRECTORY          = "/uploads"
        NEXT_PUBLIC_UPLOAD_DIRECTORY = "/uploads"
      }
      service {
        name     = "postizz"
        port     = "postizz"
        provider = "nomad"

        check {
          name     = "postiz-check"
          type     = "tcp"
          port     = "postizz"
          interval = "10s"
          timeout  = "3s"
        }
      }

      logs {
        max_files     = 5
        max_file_size = 15
      }
    }
  }
}