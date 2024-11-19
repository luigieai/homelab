variable "postgree_user" {
  type        = string
  description = "Postgree username"
}

variable "postgree_password" {
  type        = string
  description = "Poastgree password"
}

variable "postgree_endpoint" {
  type        = string
  description = "Postgree endpoint"
}

variable "KC_USER" {
  type        = string
  description = "Keycloak default user"
}

variable "KC_PASSWORD" {
  type        = string
  description = "Keycloak default password"
}
