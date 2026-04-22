job "keycloak" {
  datacenters = ["dc"]
  type        = "service"

  group "keycloak" {
    count = 1

    network {

      port "keycloak_1" {
        static = 7080
        to     = 8080
      }
    }

    restart {
      attempts = 2
      interval = "5m"
      delay    = "30s"
      mode     = "delay"
    }

    task "keycloak" {
      driver = "docker"
      
      config {
        image = "quay.io/keycloak/keycloak:25.0"
        volumes = [
        ]
        args = ["start"]
        ports = ["keycloak_1"]
      }
      env {
          KC_DB="postgres"
          KC_DB_URL="jdbc:postgresql://${POSTGREE_ENDPOINT}:5432/"
          KC_DB_URL_HOST="${POSTGREE_ENDPOINT}:5432"
          KC_DB_USERNAME="${POSTGREE_USER}"
          KC_DB_PASSWORD="${POSTGREE_PASSWORD}"
          KC_HOSTNAME_STRICT="false"
          KC_HOSTNAME_STRICT_BACKCHANNEL="false"
          KEYCLOAK_ADMIN="${KC_USER}"
          KEYCLOAK_ADMIN_PASSWORD="${KC_PASSWORD}"
          KC_PROXY="edge"
      }

      resources {
        cpu    = 1000
        memory = 1024
      }
      service {
            name = "keycloak"
            port = "keycloak_1"
            provider = "nomad"
        }

      logs {
        max_files     = 5
        max_file_size = 15
      }
    }

  }
}