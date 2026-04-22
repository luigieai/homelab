
terraform {
  required_providers {
    nomad = {
      source  = "hashicorp/nomad"
      version = "2.0.0-rc.1"
    }
  }
  required_version = ">= 0.14"
}

# Configure the Nomad provider.
provider "nomad" {
  address = "http://192.168.15.92:4646"
}
