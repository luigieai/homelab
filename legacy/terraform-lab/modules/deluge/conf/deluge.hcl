job "deluge" {
  datacenters = ["marioverde"]
  type        = "service"

  group "deluge" {
    count = 1

    network {
      port "http" { static = 8112 }
      port "tcp1" { static = 58846 }
      port "tcp2" { static = 58946 }
    }

    service {
        port = "http"
        name = "deluge"
        provider = "nomad"
        tags = [
          "traefik.enable=true",
          "traefik.http.routers.deluge_http.entrypoints=web,websecure",
          "traefik.http.routers.deluge_http.rule=Host(`deluge.marioverde.com.br`)",
        ]
        check {
          type     = "http"
          path     = "/"
          interval = "10s"
          timeout  = "2s"
        }
      }

    task "deluge" {
      driver = "podman"

      config {
        image        = "docker.io/linuxserver/deluge:2.1.1"
        network_mode = "host"
        ports        = ["http", "tcp1", "tcp2"]
        privileged   = "true"
        volumes = [
          "/etc/deluge:/config",
          "/opt/media/deluge:/downloads",
        ]
      }

      env {
        PUID      = "0"
        PGID      = "0"
      }

      resources {
        cpu    = 2000
        memory = 2048
      }
    }
  }
}