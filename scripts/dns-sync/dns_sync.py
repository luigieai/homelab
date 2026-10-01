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

import argparse
import json
import logging
import os
import re
import sys
import time

import docker
import requests

__version__ = "0.2.0"

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
DRY_RUN = False  # set by main(); when True, no Cloudflare API call or state write is made

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


def cf_upsert_record(hostname: str) -> str:
    """Returns what was done: created | updated | unchanged | would-upsert (dry run)."""
    if DRY_RUN:
        log.info(
            "[dry-run] would upsert DNS record %s -> %s (%s, proxied=%s)",
            hostname, RECORD_TARGET, RECORD_TYPE, RECORD_PROXIED,
        )
        return "would-upsert"
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
            return "unchanged"
        resp = cf_session.put(
            f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records/{existing['id']}", json=payload
        )
        resp.raise_for_status()
        log.info("updated DNS record %s -> %s", hostname, RECORD_TARGET)
        return "updated"
    resp = cf_session.post(f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records", json=payload)
    resp.raise_for_status()
    log.info("created DNS record %s -> %s", hostname, RECORD_TARGET)
    return "created"


def cf_delete_record(hostname: str) -> str:
    """Returns what was done: deleted | absent (no such record) | would-delete (dry run)."""
    if DRY_RUN:
        log.info(
            "[dry-run] would delete DNS record %s (absent >= %ds)",
            hostname, DELETE_GRACE_SECONDS,
        )
        return "would-delete"
    existing = cf_find_record(hostname)
    if not existing:
        return "absent"
    resp = cf_session.delete(f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records/{existing['id']}")
    resp.raise_for_status()
    log.info("deleted DNS record %s (absent >= %ds)", hostname, DELETE_GRACE_SECONDS)
    return "deleted"


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


def reconcile(client: docker.DockerClient, force: bool = False) -> dict:
    """One reconcile pass. Returns a summary dict (see the HTTP trigger docs).

    force=True deletes every currently-absent hostname immediately, ignoring the
    remaining grace period. It must only be set by the token-gated HTTP trigger,
    never by the periodic pass.
    """
    now = time.time()
    absent_since = load_absent_since()
    active = active_hostnames(client)
    summary = {
        "status": "ok",
        "mode": "force" if force else "normal",
        "dry_run": DRY_RUN,
        "active": sorted(active),
        "created": [],
        "updated": [],
        "unchanged": [],
        "deleted": [],
        "pending": [],
    }

    for hostname in sorted(active):
        action = cf_upsert_record(hostname)
        if action in ("created", "updated", "unchanged"):
            summary[action].append(hostname)
        absent_since.pop(hostname, None)

    for hostname in sorted(absent_since):
        remaining = DELETE_GRACE_SECONDS - (now - absent_since[hostname])
        if force or remaining <= 0:
            if force and remaining > 0:
                log.warning(
                    "force: deleting %s with %ds of grace remaining", hostname, int(remaining)
                )
            if cf_delete_record(hostname) == "deleted":
                summary["deleted"].append(hostname)
            del absent_since[hostname]
        else:
            log.info("hostname %s absent, %ds until deletion", hostname, int(remaining))
            summary["pending"].append(
                {"hostname": hostname, "seconds_remaining": int(remaining)}
            )

    if not DRY_RUN:
        save_absent_since(absent_since)
    log.info(
        "reconciliation pass complete, %d active, %d pending deletion",
        len(active), len(absent_since),
    )
    return summary


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--version", action="version", version=f"dns-sync {__version__}")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="log the record changes one reconcile pass would make, then exit "
             "without calling the Cloudflare API or writing the state file",
    )
    return parser.parse_args(argv)


def main(dry_run: bool = False) -> None:
    global DRY_RUN
    DRY_RUN = dry_run

    client = docker.from_env()
    reconcile(client)
    if DRY_RUN:
        log.info("[dry-run] done, exiting without watching events")
        return

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
        main(dry_run=parse_args().dry_run)
    except KeyboardInterrupt:
        sys.exit(0)
