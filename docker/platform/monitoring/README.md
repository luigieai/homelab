# Monitoring stack

Metrics, alerts, dashboards and logs for the homelab node `mirage`, its LXC/VM
guests and the Docker containers on `docker01`.

| Component | Role | Port (host) |
|---|---|---|
| Prometheus | metrics TSDB + alert rules (also scrapes coredns 10.0.0.4:9153, traefik 10.0.0.3:8082, registry 10.0.0.3:5001 — see "Metrics endpoints owned by other services" below) | `10.0.0.3:9090` |
| Alertmanager | routing to Telegram | `10.0.0.3:9093` |
| Grafana | dashboards | `127.0.0.1:3000`, UI at <https://grafana.lab.marioverde.com.br> |
| Loki | log store (7 days) | internal `loki:3100` |
| Alloy | tails container logs, pushes to Loki | internal |
| prometheus-pve-exporter | Proxmox API → node/CT/VM/storage metrics | internal `pve-exporter:9221` |
| cAdvisor | per-container metrics | `127.0.0.1:8080` (debug) |
| node-exporter | host OS metrics | `127.0.0.1:9100` (docker01), `10.0.0.1:9100` (mirage) |
| postgres-exporter | `pg_*` metrics from the lab Postgres (CT 103, `10.0.0.2`) | internal `postgres-exporter:9187` |

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

## SSO (Authentik)

Grafana logs users in through Authentik (OIDC, `auth.generic_oauth`). The provider is created in
Authentik and its credentials reach the container from the **Komodo stack environment**
(`GRAFANA_OIDC_CLIENT_ID`, `GRAFANA_OIDC_CLIENT_SECRET`) — never from this repo.

* Provider: OAuth2/OpenID, client type Confidential, redirect URI
  `https://grafana.lab.marioverde.com.br/login/generic_oauth`, scopes `openid profile email`
  (the `profile` mapping must emit `groups` — Grafana maps roles from it).
* Roles: `authentik Admins` -> `GrafanaAdmin`, any other authenticated user -> `Viewer`.
* Data sources carry fixed uids (`prometheus`, `loki`) because the provisioned dashboards reference them by
  uid — renaming a data source or dropping its `uid` breaks every panel.
* `GF_AUTH_GENERIC_OAUTH_AUTO_LOGIN` is `"true"`, so `/` sends anonymous visitors straight to Authentik; the local `admin` account is still available as an emergency login at `/login?disableAutoLogin=true`.
* If login fails, `docker logs monitoring-grafana-1 | grep -i oauth` shows the exchange error, and
  `docker exec monitoring-grafana-1 wget -qO- https://auth.lab.marioverde.com.br/application/o/userinfo/`
  proves the container's network path to Authentik.

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
- **Query logs**: Grafana → Explore → Loki datasource, e.g. `{compose_project="iam"}`
  (labels: `container`, `compose_project`, `service`). Traefik only emits JSON access
  lines when its `accesslog` is enabled, so `{container="traefik-traefik"}` is usually
  empty — pick a container that writes to stdout, e.g. `{container="komodo-core-1"}`.
- **Retention**: metrics via `PROM_RETENTION` / `PROM_RETENTION_SIZE` in the stack
  environment; logs via `limits_config.retention_period` in `loki/loki-config.yaml`.
- **Dashboards**: provisioned from the repo (`grafana/dashboards/*.json` through
  `grafana/provisioning/dashboards/dashboards.yml`) — Node Exporter Full, Cadvisor exporter, Proxmox via
  Prometheus, CoreDNS, Traefik, Docker Registry, PostgreSQL Database. Edit them in the UI if you must, but the next deploy overwrites UI edits: export the change
  back into `grafana/dashboards/` instead.

## Metrics endpoints owned by other services

These are enabled where the metrics are produced, not in this stack, and all bind to the infra network only:

| Service | Endpoint | Enabled by |
|---|---|---|
| CoreDNS (dns01, CT 104) | `10.0.0.4:9153` | `prometheus :9153` in `/etc/coredns/Corefile` **on dns01** — hand-managed, not in this repo |
| Traefik (docker01) | `10.0.0.3:8082` | `--entrypoints.metrics.address` + `--metrics.prometheus*` in `docker/platform/traefik/compose.yaml` |
| Registry (docker01) | `10.0.0.3:5001` | `REGISTRY_HTTP_DEBUG_*` env + a published `5001` in `docker/platform/registry/compose.yaml` |
| PostgreSQL (CT 103) | internal `postgres-exporter:9187` | `postgres-exporter` service in this stack, DSN from the Komodo stack environment |

Renaming or moving any of them means editing the scrape job in `prometheus/prometheus.yml` too.

## Troubleshooting

- No Telegram alerts: `docker compose logs alertmanager | tail -30`, verify the
  secret files exist and are readable, then run the `amtool` test above.
- Empty dashboards: Prometheus → Status → Targets — every job must be `UP`.
- Container metrics missing: `docker compose logs cadvisor | tail -30` and
  confirm the flags in `compose.yaml` match `docker run --rm ghcr.io/google/cadvisor:v0.60.6 --help`.
