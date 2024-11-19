data "template_file" "runpy" {
  template = file("${path.module}/conf/run.py")
  vars = {
    discord_webhook = var.discord_webhook
    twitch_username = var.twitch_username
    twitch_password = var.twitch_password
  }
}