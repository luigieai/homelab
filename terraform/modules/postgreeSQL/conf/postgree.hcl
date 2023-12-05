job "postgres" {
  datacenters = ["dc"]
  type        = "service"

  group "postgres" {
    count = 1

    network {

      port "postgres_port" {
        static = 5432
        to     = 5432
      }
    }

    restart {
      attempts = 2
      interval = "5m"
      delay    = "30s"
      mode     = "delay"
    }

    task "postgres" {
      driver = "docker"

      config {
        image = "postgres:alpine"
        network_mode = "host"
        volumes = [
          "${NOMAD_ALLOC_DIR}/postgres/:/data/postgres",
        ]

        ports = ["postgres_port"]
      }
      env {
          POSTGRES_USER="${POSTGREE_USER}"
          POSTGRES_PASSWORD="${POSTGREE_PASSWORD}"
          PGDATA="/data/postgres"
      }

      resources {
        cpu    = 1000
        memory = 1024
      }

      service {
            name = "postgres"
            port = "postgres_port"
            provider = "nomad"
            check {
              name = "alive"
              type = "tcp"
              interval = "10s"
              timeout = "4s"
            }
        }

      logs {
        max_files     = 5
        max_file_size = 15
      }
    }

  }
}