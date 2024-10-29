variable "url" {
  type        = string
  description = "Caddy url for potiz"
}

variable "postgree_endpoint" {
  type        = string
  description = "Postgree host for potiz"
}

variable "postgree_user" {
  type        = string
  description = "Postgree username for potiz"
}

variable "postgree_password" {
  type        = string
  description = "Postgree password for potiz"
}

variable "postgree_database" {
  type        = string
  description = "Postgree database for potiz"
}

variable "redis_endpoint" {
  type        = string
  description = "Redis host for potiz"
}

variable "jwt_secret" {
  type        = string
  description = "JWT token for potiz"
}