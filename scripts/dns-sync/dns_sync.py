"""
Watches the Docker socket for containers labeled `homelab.wan-expose=true` and
keeps matching Cloudflare DNS records in sync with their lifecycle.

For each labeled container, the hostname(s) to publish are read from its
Traefik router label(s): `traefik.http.routers.<name>.rule=Host(`<hostname>`)`.
Every router rule resolving to a `*.lab.marioverde.com.br` host is published —
a container with multiple matching routers gets a record for each. On
container start (or at boot, via a reconciliation pass) each matching
Cloudflare record is created/updated immediately.

Deletion is deliberately NOT immediate: a hostname is only deleted once it has
been continuously absent (no running labeled container serving it) for
DELETE_GRACE_SECONDS (default 24h). This guards against a transient restart,
crash-loop, or missed event wiping public DNS. Absence is tracked in a small
state file so the grace period survives a dns-sync restart too.
"""

import json
import logging
import os
import re
import sys
import time

import docker
import requests

LABEL = "homelab.wan-expose"
LABEL_TRUE = "true"
HOST_RULE_RE = re.compile(r"Host\(`([^`]+)`\)")
MANAGED_DOMAIN_SUFFIX = ".lab.marioverde.com.br"

CF_API_BASE = "https://api.cloudflare.com/client/v4"
CF_API_TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]
CF_ZONE_ID = os.environ["CLOUDFLARE_ZONE_ID"]
RECORD_TYPE = os.environ.get("DNS_RECORD_TYPE", "CNAME")
RECORD_TARGET = os.environ["DNS_RECORD_TARGET"]
RECORD_PROXIED = os.environ.get("DNS_RECORD_PROXIED", "false").lower() == "true"
RECONCILE_INTERVAL_SECONDS = int(os.environ.get("RECONCILE_INTERVAL_SECONDS", "300"))
DELETE_GRACE_SECONDS = int(os.environ.get("DELETE_GRACE_SECONDS", str(24 * 60 * 60)))
STATE_FILE = os.environ.get("STATE_FILE", "/state/absent-since.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("dns-sync")

cf_session = requests.Session()
cf_session.headers.update(
    {"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"}
)


def wan_hostnames_from_labels(labels: dict) -> set[str]:
    hostnames = set()
    for key, value in labels.items():
        if not key.startswith("traefik.http.routers.") or not key.endswith(".rule"):
            continue
        match = HOST_RULE_RE.search(value)
        if match and match.group(1).endswith(MANAGED_DOMAIN_SUFFIX):
            hostnames.add(match.group(1))
    return hostnames


def load_absent_since() -> dict[str, float]:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_absent_since(absent_since: dict[str, float]) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp_path = f"{STATE_FILE}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(absent_since, f)
    os.replace(tmp_path, STATE_FILE)


def cf_find_record(hostname: str) -> dict | None:
    resp = cf_session.get(
        f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records",
        params={"type": RECORD_TYPE, "name": hostname},
    )
    resp.raise_for_status()
    records = resp.json()["result"]
    return records[0] if records else None


def cf_upsert_record(hostname: str) -> None:
    existing = cf_find_record(hostname)
    payload = {
        "type": RECORD_TYPE,
        "name": hostname,
        "content": RECORD_TARGET,
        "proxied": RECORD_PROXIED,
        "ttl": 1,
    }
    if existing:
        if existing["content"] == RECORD_TARGET and existing["proxied"] == RECORD_PROXIED:
            return
        resp = cf_session.put(
            f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records/{existing['id']}", json=payload
        )
        resp.raise_for_status()
        log.info("updated DNS record %s -> %s", hostname, RECORD_TARGET)
    else:
        resp = cf_session.post(f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records", json=payload)
        resp.raise_for_status()
        log.info("created DNS record %s -> %s", hostname, RECORD_TARGET)


def cf_delete_record(hostname: str) -> None:
    existing = cf_find_record(hostname)
    if not existing:
        return
    resp = cf_session.delete(f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records/{existing['id']}")
    resp.raise_for_status()
    log.info("deleted DNS record %s (absent >= %ds)", hostname, DELETE_GRACE_SECONDS)


def active_hostnames(client: docker.DockerClient) -> set[str]:
    hostnames = set()
    for container in client.containers.list(filters={"label": f"{LABEL}={LABEL_TRUE}"}):
        container_hostnames = wan_hostnames_from_labels(container.labels)
        if not container_hostnames:
            log.warning(
                "container %s has %s=%s but no *.lab.marioverde.com.br Host() router label",
                container.name, LABEL, LABEL_TRUE,
            )
            continue
        hostnames.update(container_hostnames)
    return hostnames


def reconcile(client: docker.DockerClient) -> None:
    now = time.time()
    absent_since = load_absent_since()
    active = active_hostnames(client)

    for hostname in active:
        cf_upsert_record(hostname)
        absent_since.pop(hostname, None)

    for hostname in list(absent_since):
        if hostname in active:
            continue
        first_absent = absent_since[hostname]
        if now - first_absent >= DELETE_GRACE_SECONDS:
            cf_delete_record(hostname)
            del absent_since[hostname]
        else:
            remaining = DELETE_GRACE_SECONDS - (now - first_absent)
            log.info("hostname %s absent, %ds until deletion", hostname, int(remaining))

    # Any previously-tracked hostname that just went missing starts its grace period now.
    known_hostnames = load_absent_since().keys() | active
    for hostname in known_hostnames - active:
        absent_since.setdefault(hostname, now)

    save_absent_since(absent_since)
    log.info(
        "reconciliation pass complete, %d active, %d pending deletion",
        len(active), len(absent_since),
    )


def handle_event(event: dict, client: docker.DockerClient) -> None:
    labels = event.get("Actor", {}).get("Attributes", {})
    if labels.get(LABEL) != LABEL_TRUE:
        return

    hostnames = wan_hostnames_from_labels(labels)
    if not hostnames:
        return

    status = event.get("status")
    if status == "start":
        absent_since = load_absent_since()
        changed = False
        for hostname in hostnames:
            cf_upsert_record(hostname)
            if absent_since.pop(hostname, None) is not None:
                changed = True
        if changed:
            save_absent_since(absent_since)
    # Deliberately no action on die/stop/destroy here — deletion only happens
    # via reconcile() after the hostname has been continuously absent for
    # DELETE_GRACE_SECONDS, to avoid wiping DNS on a transient restart.


def main() -> None:
    client = docker.from_env()
    reconcile(client)

    last_reconcile = time.monotonic()
    for event in client.events(decode=True, filters={"type": "container"}):
        try:
            handle_event(event, client)
        except requests.HTTPError as exc:
            log.error("Cloudflare API error: %s", exc)

        if time.monotonic() - last_reconcile > RECONCILE_INTERVAL_SECONDS:
            try:
                reconcile(client)
            except requests.HTTPError as exc:
                log.error("Cloudflare API error during reconciliation: %s", exc)
            last_reconcile = time.monotonic()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
