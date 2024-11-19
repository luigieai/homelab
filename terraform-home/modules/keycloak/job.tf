resource "nomad_job" "app" {
  jobspec = templatefile("${path.module}/conf/keycloak.hcl", {
    NOMAD_ALLOC_DIR   = "/alloc"
    POSTGREE_ENDPOINT = var.postgree_endpoint
    POSTGREE_USER     = var.postgree_user
    POSTGREE_PASSWORD = var.postgree_password
    KC_USER           = var.KC_USER
    KC_PASSWORD       = var.KC_PASSWORD
  })
}
