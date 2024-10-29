resource "postgresql_database" "postiz_database" {
   name                   = var.postgree_database
  owner                  = var.postgree_user
  lc_collate             = "C"
  connection_limit       = -1
  allow_connections      = true
  alter_object_ownership = true
}

resource "nomad_job" "app" {
  jobspec = templatefile("${path.module}/conf/postiz.hcl", {
    NOMAD_ALLOC_DIR   = "/alloc"
    URL               = var.url
    POSTGREE_ENDPOINT = var.postgree_endpoint
    POSTGREE_USER     = var.postgree_user
    POSTGREE_PASSWORD = var.postgree_password
    POSTGREE_DATABASE = var.postgree_database
    REDIS_ENPOINT     = var.redis_endpoint
    JWT_SECRET        = var.jwt_secret

    depends_on = postgresql_database.postiz_database
  })
}


