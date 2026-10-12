# Monitoring stack

Metrics, alerts, dashboards and logs for the homelab node `mirage`, its LXC/VM
guests and the Docker containers on `docker01`.

| Component | Role | Port (host) |
|---|---|---|
| Prometheus | metrics TSDB + alert rules | `10.0.0.3:9090` |
| Alertmanager | routing to Telegram | `10.0.0.3:9093` |
| Grafana | dashboards | `127.0.0.1:3000`, UI at <https://grafana.lab.marioverde.com.br> |
| Loki | log store (7 days) | internal `loki:3100` |
| Alloy | tails container logs, pushes to Loki | internal |
| prometheus-pve-exporter | Proxmox API → node/CT/VM/storage metrics | internal `pve-exporter:9221` |
| cAdvisor | per-container metrics | `127.0.0.1:8080` (debug) |
| node-exporter | host OS metrics | `127.0.0.1:9100` (docker01), `10.0.0.1:9100` (mirage) |

## Secrets

- `.env` (git-ignored, written by Komodo from the stack Environment settings):
  `PVE_TOKEN_VALUE`, `GRAFANA_ADMIN_PASSWORD`, retention knobs.
- `TELEGRAM_BOT_TOKEN` / chat id are **not** in `.env`: this repo is public, so
  Alertmanager reads them from files on the docker01 host:

  ```sh
  install -d -m 750 -o root -g 65534 /etc/komodo/secrets
  printf '%s' '<token>'    > /etc/komodo/secrets/telegram_bot_token
  printf '%s' '<chat id>'  > /etc/komodo/secrets/telegram_chat_id
  chmod 640 /etc/komodo/secrets/telegram_*
  ```

  No trailing newline (Alertmanager parses the chat id as an integer). After
  changing a file, `docker compose up -d --force-recreate alertmanager`.

  The `alertmanager` container runs as `nobody` (uid/gid 65534), so the files must be
  readable by gid 65534 — `0600 root:root` makes every notification fail with
  `permission denied` on `/etc/alertmanager-secrets/telegram_bot_token`, even though the
  files look correct on the host. They are bind-mounted read-only at
  `/etc/alertmanager-secrets/` (deliberately outside the read-only `./alertmanager` config
  bind, which cannot host a nested mountpoint).

## Proxmox token

Read-only token on `mirage` (PVEAuditor has only `*.Audit` privileges):

```sh
pveum user add monitoring@pve --comment "Monitoring stack (read-only)"
pveum acl modify / --users monitoring@pve --roles PVEAuditor
pveum user token add monitoring@pve pve-exporter --privsep 0   # prints the secret once
```

Put the printed secret in the Komodo stack environment as `PVE_TOKEN_VALUE`
(or in `.env` for a manual `docker compose up`).

## Common tasks

- **Add a scrape target**: edit `prometheus/prometheus.yml`, then
  `docker compose exec prometheus kill -HUP 1` (or `curl -X POST 10.0.0.3:9090/-/reload`).
- **Add an alert**: edit `prometheus/alerts.yml` and reload the same way; check
  state in Prometheus → Alerts, or `curl -s 10.0.0.3:9090/api/v1/rules`.
- **Test that alerts reach Telegram**:
  `docker compose exec alertmanager amtool alert add alertname=Test severity=info --alertmanager.url=http://localhost:9093`
  — you should get a Telegram message within ~30s, then it resolves in ~5 min.
- **Query logs**: Grafana → Explore → Loki datasource, `{container="traefik-traefik"}`
  (labels: `container`, `compose_project`, `service`).
- **Retention**: metrics via `PROM_RETENTION` / `PROM_RETENTION_SIZE` in the stack
  environment; logs via `limits_config.retention_period` in `loki/loki-config.yaml`.
- **Dashboards to import** (Grafana → Dashboards → New → Import by ID):
  `1860` (Node Exporter Full), `14282` (cAdvisor), `10347` (Proxmox via
  Prometheus). If an ID is retired, search the same name in the import dialog and
  take the top result; wire the datasource to `Prometheus` / `Loki`.
  The `Prometheus` and `Loki` data sources are provisioned from the repo
  (`grafana/provisioning/datasources/datasources.yml`), so a fresh deploy needs no
  manual data source setup.

## Troubleshooting

- No Telegram alerts: `docker compose logs alertmanager | tail -30`, verify the
  secret files exist and are readable, then run the `amtool` test above.
- Empty dashboards: Prometheus → Status → Targets — every job must be `UP`.
- Container metrics missing: `docker compose logs cadvisor | tail -30` and
  confirm the flags in `compose.yaml` match `docker run --rm ghcr.io/google/cadvisor:v0.60.6 --help`.
