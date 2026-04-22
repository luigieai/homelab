terraform {
  required_providers {
    nomad = {
      source  = "hashicorp/nomad"
      version = "2.0.0-rc.1"
    }
  }
  required_version = ">= 0.14"
}