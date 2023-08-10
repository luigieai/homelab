job "caddy" {
  datacenters = ["dc"]
  type        = "service"

  group "proxy" {
    count = 1

    network {

      port "http" {
        static = 80
        to     = 80
      }

      port "https" {
        static = 443
        to     = 443
      }
    }

    restart {
      attempts = 2
      interval = "2m"
      delay    = "30s"
      mode     = "fail"
    }

    task "internal" {
      driver = "docker"

      config {
        image = "mrkaran/caddy:latest"

        volumes = [
          "${NOMAD_ALLOC_DIR}/caddy/data:/data",
        ]

        # Bind the config file to container.
        mount {
          type   = "bind"
          source = "configs"
          target = "/etc/caddy" # Bind mount the template from `NOMAD_TASK_DIR`.
        }
        ports = ["http", "https"]
      }

      resources {
        cpu    = 100
        memory = 100
      }

      service {
            name = "caddy-http"
            port = "http"
            provider = "nomad"
        }
      
      service {
            name = "caddy-http"
            port = "https"
            provider = "nomad"
        }

      template {
        data = <<EOF
            ${caddyfile}
        EOF

        destination = "configs/Caddyfile" # Rendered template.

        # Caddy doesn't support reload via signals as of 
        change_mode = "restart"
      }
    }
  }
}