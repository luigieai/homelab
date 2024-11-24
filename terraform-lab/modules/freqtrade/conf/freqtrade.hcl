job "freqtrade" {
  datacenters = ["marioverde"]
  type        = "service"

  group "freqtrade" {
    count = 1

    network {
      port "api" {
        static = 9696
        to     = 8080
      }
    }

    restart {
      attempts = 3
      interval = "2m"
      delay    = "30s"
      mode     = "delay"
    }

    ephemeral_disk {
      migrate = true
      sticky  = true
      size    = 500
    }

    task "freqtrade" {
      driver = "podman"

      config {
        image = "docker.io/freqtradeorg/freqtrade:stable"
        ports = ["api"]

        volumes = [
          "${NOMAD_ALLOC_DIR}:/freqtrade/user_data/"
        ]

        args = [
          "trade",
          "--logfile", "/freqtrade/user_data/logs/freqtrade.log",
          "--db-url", "sqlite:////freqtrade/user_data/tradesv3.sqlite",
          "--config", "/freqtrade/user_data/config.json",
          "--strategy", "MyStrategy"
        ]
      }

      template {
        data = <<EOF
${CONFIG_JSON}
EOF
        destination = "${NOMAD_ALLOC_DIR}/config.json"
        change_mode = "restart"
      }

      template {
        data = <<EOF
${STRATEGY_NAME}
EOF
        destination = "${NOMAD_ALLOC_DIR}/strategies/strategy.py"
        change_mode = "restart"
      }

      resources {
        cpu    = 1000
        memory = 2024
      }

      service {
        name     = "freqtrade"
        port     = "api"
        provider = "nomad"
        
        check {
          type     = "http"
          path     = "/api/v1/ping"
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