job "twitchminer" {
  datacenters = ["dc"]
  type        = "service"

  group "twitchminer" {
    count = 1

    network {

      port "twitchminer_port" {
        static = 5001
        to     = 5000
      }
    }

    restart {
      attempts = 2
      interval = "5m"
      delay    = "30s"
      mode     = "delay"
    }



    task "twitchminer" {
      driver = "docker"

      config {
        image = "rdavidoff/twitch-channel-points-miner-v2:1.9.5"
        image_pull_timeout = "20m"
        #network_mode = "host"
        volumes = [
          "${NOMAD_ALLOC_DIR}/twitchminer/analytics:/usr/src/app/analytics",
          "${NOMAD_ALLOC_DIR}/twitchminer/cookies:/usr/src/app/cookies",
          "${NOMAD_ALLOC_DIR}/twitchminer/logs:/usr/src/app/logs",
          "local/run.py:/usr/src/app/run.py",
        ]
        ports = ["twitchminer_port"]
      }

      
      env {
        TERM="xterm-256color"
      }

      service {
            name = "twitchminer"
            port = "twitchminer_port"
            provider = "nomad"
        }

      template {
        data = <<EOF
            ${RUN_FILE}
        EOF

        destination = "local/run.py" # Rendered template.

        # Caddy doesn't support reload via signals as of 
        change_mode = "restart"
      }

    }

  }
}