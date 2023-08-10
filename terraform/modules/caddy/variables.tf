variable "cloudflare_api_token" {
  type        = string
  description = "Cloudflare API token to edit DNS Zones and Records."
}

variable "endpoint" {
  type = string
  description = "Nomad's server endpoint, the machine IP Address so we can reverse proxy our services."
}