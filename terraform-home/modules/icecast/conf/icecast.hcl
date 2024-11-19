job "icecast" {
  datacenters = ["dc"]
  type        = "service"

  group "icecast" {
    count = 1

    network {

      port "icecast" {
        static = 8000
        to     = 8000
      }
    }

    restart {
      attempts = 2
      interval = "5m"
      delay    = "30s"
      mode     = "delay"
    }

    task "icecast" {
      driver = "docker"
      
      config {
        image = "moul/icecast"
        ports = ["icecast"]
      }
      env {
        //TODO :)
          #ICECAST_SOURCE_PASSWORD=""
          #ICECAST_ADMIN_PASSWORD=bbbb
          #ICECAST_PASSWORD=cccc
          #ICECAST_RELAY_PASSWORD=dddd
      }

      service {
            name = "icecast"
            port = "icecast"
            provider = "nomad"
        }
    }

  }
}