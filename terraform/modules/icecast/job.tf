resource "nomad_job" "app" {
  jobspec = templatefile("${path.module}/conf/icecast.hcl", {
    NOMAD_ALLOC_DIR   = "/alloc"

  })
}
