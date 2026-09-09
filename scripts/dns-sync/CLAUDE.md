# dns-sync

Custom watcher that keeps Cloudflare DNS records in sync with Docker container
lifecycle, so a service opts into having its DNS managed purely via a label —
no manual Cloudflare dashboard edits, and no leftover DNS record after the
container is removed. It publishes one record per Traefik `Host()` router the
container declares under `*.app.marioverde.com.br` and/or
`*.lab.marioverde.com.br` — a container with both a `-lab` and `-app` router
gets both DNS records created.

This directory is **source + build only**. The running deployment lives at
[docker/platform/dns-sync/](../../docker/platform/dns-sync/), which pulls a
pre-built image from the private registry rather than building from source —
see "Build and deploy a new version" below.

## How it works

`dns_sync.py` connects to the Docker socket and:

1. On startup, reconciles: lists all running containers with label
   `homelab.wan-expose=true` and upserts a Cloudflare DNS record for every
   `.app.`/`.lab.` `Host()` router hostname each one declares.
2. Streams Docker container events. A `start` event upserts the matching
   record immediately. `die`/`stop`/`destroy` events do **not** delete
   anything — deletion only ever happens via reconciliation (see below).
3. Re-reconciles periodically (`RECONCILE_INTERVAL_SECONDS`, default 300s).
   Reconciliation is also what performs deletion: a hostname that is
   currently absent (no running labeled container serving it) is tracked
   with a "first seen absent" timestamp in a small state file
   (`STATE_FILE`, default `/state/absent-since.json`, on a persisted
   volume). Only once a hostname has been **continuously absent for
   `DELETE_GRACE_SECONDS`** (default 24h) is its Cloudflare record actually
   deleted. If the container comes back before the grace period elapses,
   the pending deletion is cancelled and the timer resets.

This grace period is deliberate: deleting a public DNS record immediately on
`stop`/`die` would wipe WAN access on a container restart, brief
crash-loop, or transient Docker event — expensive to get wrong on a
public-facing record. Don't shortcut this back to immediate deletion on
lifecycle events without a good reason.

The label alone doesn't say *which* hostname(s) to publish — those are read
from the container's own Traefik router labels: every
`traefik.http.routers.<name>.rule=Host(\`...\`)` label that resolves to a
`*.app.marioverde.com.br` or `*.lab.marioverde.com.br` hostname gets its own
record. This means a service must have **both** the label and at least one
matching router:

```yaml
labels:
  - "traefik.http.routers.myapp-lab.rule=Host(`myapp.lab.marioverde.com.br`)"
  - "traefik.http.routers.myapp-app.rule=Host(`myapp.app.marioverde.com.br`)"
  - "homelab.wan-expose=true"
```

— which creates both `myapp.lab.marioverde.com.br` and
`myapp.app.marioverde.com.br` Cloudflare records, each pointed at the same
`DNS_RECORD_TARGET`. The label without any matching router is a no-op
(logged as a warning) — `dns-sync` only creates DNS records, it never
creates Traefik routers, so WAN traffic still needs the `-app` router (and
LAN clients the `-lab` router, if internal DNS doesn't already resolve it)
to actually reach the service.

## Label contract

| Label | Meaning |
|---|---|
| `homelab.wan-expose=true` | Opt this container into dynamic WAN DNS. Any other value or absence is ignored. |

## Cloudflare record semantics

- Record type, proxied status, and target are **not** derived per-service —
  they're fixed via env vars (`DNS_RECORD_TYPE`, `DNS_RECORD_TARGET`,
  `DNS_RECORD_PROXIED`) so every dns-sync-managed record points the same way
  the static entries in [docker/platform/ddns](../../docker/platform/ddns/)
  do. Don't try to track the WAN IP independently here — `ddns` already owns
  that; `dns-sync` only owns record *existence*, not IP freshness.
- Matching on delete/upsert is by `(type, name)` — see `cf_find_record` in
  `dns_sync.py`. If a record with that hostname already exists but wasn't
  created by dns-sync (e.g. hand-added in the Cloudflare dashboard), it will
  be adopted/overwritten. Don't reuse a `*.app.`/`*.lab.` hostname that's
  manually managed elsewhere.
- `.lab.` hostnames are published to Cloudflare too (not just internal DNS)
  when a labeled container has a `-lab` router — same `DNS_RECORD_TARGET` as
  `.app.` records. This repo's `.lab` domains aren't only resolved by
  internal DNS; if that assumption changes, revisit whether `.lab.` records
  should stay in scope here.

## Required environment (see [docker/platform/dns-sync/.env.example](../../docker/platform/dns-sync/.env.example))

- `CLOUDFLARE_API_TOKEN` — Zone:DNS:Edit scope, same permission level as the
  tokens already used by `docker/platform/traefik` and `docker/platform/ddns`.
- `CLOUDFLARE_ZONE_ID` — zone ID for `marioverde.com.br`.
- `DNS_RECORD_TARGET` — what the created records point at (CNAME target or A
  record IP), matching whatever `docker/platform/ddns` keeps updated.
- `DNS_RECORD_TYPE` (default `CNAME`), `DNS_RECORD_PROXIED` (default `false`),
  `RECONCILE_INTERVAL_SECONDS` (default `300`), `DELETE_GRACE_SECONDS`
  (default `86400`, i.e. 24h), `STATE_FILE` (default `/state/absent-since.json`)
  — optional overrides.

## State file

`/state/absent-since.json` (mounted from the `dns_sync_state` volume in
`docker/platform/dns-sync/compose.yaml`) maps hostname → unix timestamp of
when it was first observed absent. It must persist across dns-sync
container restarts, otherwise the grace period silently resets to zero
every deploy and the safety guarantee is lost. If you ever need to force an
immediate deletion, editing/clearing this file (or waiting out the grace
period) is the supported way — don't add a "force delete" code path without
thinking through why the grace period exists first.

## Build and deploy a new version

No CI is set up for this repo — building and pushing is a manual step:

```bash
cd scripts/dns-sync/
docker build -t registry.lab.marioverde.com.br/dns-sync:<tag> .
docker push registry.lab.marioverde.com.br/dns-sync:<tag>

cd ../../docker/platform/dns-sync/
# bump the tag in compose.yaml (or .env if parameterized) to <tag>
docker compose pull
docker compose up -d
```

Registry is unauthenticated (internal `.lab` only, see
[docker/platform/registry](../../docker/platform/registry/)) — no login step
needed on the home network.

## Local testing

`docker/from_env()` requires the Docker socket mounted read-write enough for
event streaming (read-only is fine — no writes are made to Docker itself).
Run against a real Cloudflare zone carefully: this script creates and
deletes real public DNS records. Prefer testing against a throwaway
subdomain/hostname before pointing it at a real service like Authentik.
