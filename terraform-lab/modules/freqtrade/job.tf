resource "nomad_job" "app" {
  jobspec = templatefile("${path.module}/conf/freqtrade.hcl", {
    NOMAD_ALLOC_DIR = "./private",
    CONFIG_JSON     = templatefile("${path.module}/conf/config.json.tpl", {
      exchange_key    = var.exchange_key,
      exchange_secret = var.exchange_secret,
      exchange_password = var.exchange_password,
      telegram_token  = var.telegram_token,
      telegram_chat_id = var.telegram_chat_id
    })
    STRATEGY_NAME = file("${path.module}/conf/strategy.py")
  })

}

variable "exchange_key" {
  type = string
}

variable "exchange_secret" {
  type = string
}

variable "exchange_password" {
  type = string
}

variable "telegram_token" {
  type = string
}

variable "telegram_chat_id" {
  type = string
}

variable "jwt_secret_key" {
  type = string
}

variable "username" {
  type = string
}

variable "password" {
  type = string
}
