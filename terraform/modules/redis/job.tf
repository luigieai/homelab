resource "nomad_job" "app" {
  jobspec = templatefile("${path.module}/conf/redis.hcl", {
    NOMAD_ALLOC_DIR   = "/alloc"
  })
}
