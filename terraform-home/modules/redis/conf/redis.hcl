job "redis" {
  datacenters = ["dc"]
  type        = "service"

  group "redis" {
    count = 1

    network {
      port "redis" {
        static = 6379
        to     = 6379
      }
    }

    restart {
      attempts = 2
      interval = "5m"
      delay    = "30s"
      mode     = "delay"
    }

    task "redis" {
      driver = "docker"

      config {
        image = "redis:7.2"
        ports = ["redis"]
        volumes = [
          "${NOMAD_ALLOC_DIR}/postiz-redis-data:/data"
        ]
      }

      resources {
        cpu    = 500
        memory = 512
      }

      service {
        name     = "redis"
        port     = "redis"
        provider = "nomad"
        check {
          name     = "redis-check"
          type     = "tcp"
          port     = "redis"
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
