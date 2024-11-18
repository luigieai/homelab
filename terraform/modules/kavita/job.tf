resource "nomad_job" "kavita" {
  jobspec = templatefile("${path.module}/conf/kavita.hcl", {
    NOMAD_ALLOC_DIR = "/alloc"
  })
}