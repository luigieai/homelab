resource "nomad_job" "app_twitchminer" {
  jobspec = templatefile("${path.module}/conf/twitchminer.hcl", {
    NOMAD_ALLOC_DIR = "/alloc"
    RUN_FILE        = data.template_file.runpy.rendered
  })
}