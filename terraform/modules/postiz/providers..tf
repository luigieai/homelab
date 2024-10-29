terraform {
  required_providers {
    nomad = {
      source  = "hashicorp/nomad"
      version = "2.0.0-rc.1"
    }
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "1.24.0"
    }
  }
  required_version = ">= 0.14"
}

provider "postgresql" {
  host            = var.postgree_endpoint
  port            = 5432
  username        = var.postgree_user
  password        = var.postgree_password
  sslmode         = "disable"
  connect_timeout = 15
}