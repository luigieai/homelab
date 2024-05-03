variable "endpoint" {
  default = "192.168.15.92"
}
module "caddy" {
  source               = "./modules/caddy"
  cloudflare_api_token = var.cloudflare_caddy_api_token
  endpoint             = var.endpoint
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

module "keycloak" {
  source            = "./modules/keycloak"
  postgree_user     = var.postgree_user
  postgree_password = var.postgree_password
  postgree_endpoint = var.endpoint
  KC_USER           = var.kc_user
  KC_PASSWORD       = var.kc_password
  providers = {
    nomad = nomad
  }
}

module "icecast" {
  source = "./modules/icecast"

  providers = {
    nomad = nomad
  }
}

module "twitchminer" {
  source = "./modules/twitchminer"
  discord_webhook = var.discord_webhook
  twitch_username = var.twitch_username
  twitch_password = var.twitch_password
  providers = {
    nomad = nomad
  }
}