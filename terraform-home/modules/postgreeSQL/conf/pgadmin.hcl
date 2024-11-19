job "pg_admin" {
  datacenters = ["dc"]
  type        = "service"

  group "pg_admin" {
    count = 1

    network {

      port "pgadmin_port" {
        static = 8090
        to     = 80
      }
    }

    restart {
      attempts = 2
      interval = "5m"
      delay    = "30s"
      mode     = "delay"
    }

    task "pg_admin" {
      driver = "docker"

      config {
        image = "dpage/pgadmin4:latest"
        #network_mode = "host"
        volumes = [
          "${NOMAD_ALLOC_DIR}/pgadmin:/var/lib/pgadmin"
        ]
        ports = ["pgadmin_port"]
      }

      
      env {
          PGADMIN_DEFAULT_EMAIL="${PGADMIN_USER}"
          PGADMIN_DEFAULT_PASSWORD="${PGADMIN_PASSWORD}"
         #PGADMIN_SERVER_JSON_FILE="/pgadmin4/serverslist/servers.json"
         # PGADMIN_DEFAULT_PASSWORD_FILE="/pgadmin4/serverslist/passwords"
      }

      service {
            name = "pgadmin"
            port = "pgadmin_port"
            provider = "nomad"
        }

      logs {
        max_files     = 5
        max_file_size = 15
      }
    }

  }
}