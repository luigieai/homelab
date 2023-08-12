job "wg-easy" {
    
    datacenters = ["dc"]
    
    type = "service"
    
    group "wg-easy" {
        count = 1

        task "wg-easy" { 
            driver = "docker"

            config {
                image = "weejewel/wg-easy"
                ports = ["vpn", "webui"]
                network_mode = "host"
                volumes = [
                    "${NOMAD_ALLOC_DIR}/wg-easy:/etc/wireguard",
                ]

            }
        }

        network {
            mode = "host"

            port "vpn" {
                static = 51820
                to = 51820
            }
            port "webui" {
                static = 51821
                to = 51821
            }

        }

        service {
            name = "wgeasy"
            port = "webui"
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