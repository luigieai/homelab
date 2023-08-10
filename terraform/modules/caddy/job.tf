resource "nomad_job" "app" {
  jobspec = templatefile("${path.module}/conf/caddy.hcl", {
    caddyfile = data.template_file.caddyfile.rendered
    NOMAD_ALLOC_DIR = "/alloc"
  })
}