module "caddy" {
  source               = "./modules/caddy"
  cloudflare_api_token = var.cloudflare_caddy_api_token
  endpoint             = "192.168.15.92"
  providers = {
    nomad = nomad
  }
}

module "postgree" {
  source            = "./modules/postgreeSQL"
  postgree_user     = var.postgree_user
  postgree_password = var.postgree_password
  pgadmin_user      = var.pgadmin_user
  pgadmin_password  = var.pgadmin_password
  providers = {
    nomad = nomad
  }
}

