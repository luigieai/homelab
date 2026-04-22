resource "nomad_job" "app" {
  jobspec = templatefile("${path.module}/conf/deluge.hcl", {})

}