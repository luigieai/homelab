variable "cloudflare_caddy_api_token" {
  type        = string
  description = "API key to edit TLS in DNS zones in Cloudflare used by Caddy"
}

variable "postgree_user" {
  type        = string
  description = "Postgree username"
}

variable "postgree_password" {
  type        = string
  description = "Poastgree password"
}

variable "pgadmin_user" {
  type        = string
  description = "PgAdmin username"
}

variable "pgadmin_password" {
  type        = string
  description = "PgAdmin password"
}

variable "kc_user" {
  type        = string
  description = "Keycloak default user"
}

variable "kc_password" {
  type        = string
  description = "Keycloak default password"
}
