module "freqtrade" {
  source = "./modules/freqtrade"
  providers = {
    nomad = nomad
  }
  exchange_key       = var.exchange_key
  exchange_secret    = var.exchange_secret
  exchange_password  = var.exchange_password
  telegram_token     = var.telegram_token
  telegram_chat_id   = var.telegram_chat_id
  jwt_secret_key     = var.jwt_secret_key
  username           = var.username
  password           = var.password
}
