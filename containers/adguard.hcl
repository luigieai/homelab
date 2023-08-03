job "adguard" {
    
    datacenters = ["dc"]
    
    type = "service"
    
    group "adguard-g" {
        count = 1

        ephemeral_disk {
            size = 500 // MB
            sticky = true
        }

        task "adguard"{ 
            driver = "docker"

            config {
                image = "adguard/adguardhome"
                ports = ["ad-ui", "ad-dns", "ad-install"]
                network_mode = "host"
                volumes = [
                    "${NOMAD_ALLOC_DIR}/adguard-work:/opt/adguardhome/conf",
                    "${NOMAD_ALLOC_DIR}/adguard-conf:/opt/adguardhome/work"
                ]

            }
        }

        network {
            mode = "host"

            port "ad-ui" {
                static = 8080
                to = 80
            }
            port "ad-dns" {
                static = 53
                to = 53
            }
            port "ad-install" {
                static = 3000
                to = 3000
            }

        }

        service {
            name = "adguard"
            port = "ad-ui"
            provider = "nomad"
            check {
                type = "http"
                path = "/"
                interval = "20s"
                timeout = "60s"
            }
        }

    }
}