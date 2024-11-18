job "kavita" {
  datacenters = ["dc"]
  type        = "service"

  group "kavita" {
    count = 1

    network {
      port "kavita" {
        static = 5002
        to     = 5000
      }
    }

    restart {
      attempts = 2
      interval = "5m"
      delay    = "30s"
      mode     = "delay"
    }

    task "kavita" {
      driver = "docker"

      config {
        image = "jvmilazz0/kavita:latest"
        ports = ["kavita"]
        volumes = [
          "${NOMAD_ALLOC_DIR}/kavita/manga:/manga",
          "${NOMAD_ALLOC_DIR}/kavita/comics:/comics", 
          "${NOMAD_ALLOC_DIR}/kavita/books:/books",
          "${NOMAD_ALLOC_DIR}/kavita/config:/kavita/config"
        ]
      }

      env {
        TZ = "America/Sao_Paulo"
      }

      resources {
        cpu    = 500
        memory = 512
      }

      service {
        name     = "kavita"
        port     = "kavita"
        provider = "nomad"
        check {
          type     = "http"
          path     = "/"
          interval = "10s"
          timeout  = "2s"
        }
      }

      logs {
        max_files     = 5
        max_file_size = 15
      }
    }
  }
}