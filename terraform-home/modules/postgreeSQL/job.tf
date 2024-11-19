resource "nomad_job" "app_postgree" {
  jobspec = templatefile("${path.module}/conf/postgree.hcl", {
    NOMAD_ALLOC_DIR   = "/alloc"
    POSTGREE_USER     = var.postgree_user
    POSTGREE_PASSWORD = var.postgree_password
  })
}
resource "nomad_job" "app_pgadmin" {
  jobspec = templatefile("${path.module}/conf/pgadmin.hcl", {
    NOMAD_ALLOC_DIR  = "/alloc"
    PGADMIN_USER     = var.pgadmin_user
    PGADMIN_PASSWORD = var.pgadmin_password
  })
}