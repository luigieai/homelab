module "caddy" {
  source               = "./modules/caddy"
  cloudflare_api_token = var.cloudflare_caddy_api_token
  endpoint = "192.168.15.92"
  providers = {
    nomad = nomad
  }
}