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
crash-loop, or missed event wiping public DNS. Only hostnames observed
actively exposed at least once are ever candidates; they and their
first-absent timestamps are tracked in a small state file so the grace
period survives a dns-sync restart too.

An optional HTTP trigger (POST/GET /reconcile, GET /healthz; see CLAUDE.md,
"Manual trigger (HTTP webhook)") runs one reconcile pass on demand. It only
starts when WEBHOOK_TOKEN is set. `force` mode, which deletes absent hostnames
ahead of the grace period, is reachable only through it, never periodically.
"""

import argparse
import hmac
import json
import logging
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import docker
import requests

__version__ = "0.3.1"

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
RECONCILE_LOCK = threading.Lock()  # serialises every reconcile pass (state file is read/modify/write)
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "").strip()  # empty -> HTTP listener disabled
HTTP_BIND = os.environ.get("HTTP_BIND", "0.0.0.0")
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8080"))
HTTP_MAX_BODY_BYTES = 64 * 1024
HTTP_ROUTES = {"/reconcile": ("GET", "POST"), "/healthz": ("GET",)}

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


def load_state() -> tuple[dict[str, float], set[str]]:
    """Returns (absent_since, managed). A legacy flat {host: ts} file loads as
    absent_since with managed = its keys; the next save_state() upgrades it."""
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}, set()
    if not isinstance(data, dict):
        return {}, set()
    if "absent_since" in data or "managed" in data:
        return dict(data.get("absent_since", {})), set(data.get("managed", []))
    return data, set(data)


def save_state(absent_since: dict[str, float], managed: set[str]) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp_path = f"{STATE_FILE}.tmp"
    with open(tmp_path, "w") as f:
        json.dump({"absent_since": absent_since, "managed": sorted(managed)}, f)
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
    absent_since, managed = load_state()
    active = active_hostnames(client)
    managed |= active
    absent_since = {h: ts for h, ts in absent_since.items() if h in managed}
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

    for hostname in sorted(managed - active):
        remaining = DELETE_GRACE_SECONDS - (now - absent_since.setdefault(hostname, now))
        if force or remaining <= 0:
            if force and remaining > 0:
                log.warning(
                    "force: deleting %s with %ds of grace remaining", hostname, int(remaining)
                )
            if cf_delete_record(hostname) == "deleted":
                summary["deleted"].append(hostname)
            del absent_since[hostname]
            managed.discard(hostname)
        else:
            log.info("hostname %s absent, %ds until deletion", hostname, int(remaining))
            summary["pending"].append(
                {"hostname": hostname, "seconds_remaining": int(remaining)}
            )

    if not DRY_RUN:
        save_state(absent_since, managed)
    log.info(
        "reconciliation pass complete, %d active, %d pending deletion",
        len(active), len(absent_since),
    )
    return summary


def locked_reconcile(
    client: docker.DockerClient, force: bool = False, blocking: bool = True
) -> dict | None:
    """reconcile() under RECONCILE_LOCK. Returns None if blocking=False and the lock is held."""
    if not RECONCILE_LOCK.acquire(blocking=blocking):
        return None
    try:
        return reconcile(client, force=force)
    finally:
        RECONCILE_LOCK.release()


def periodic_reconcile(client: docker.DockerClient) -> None:
    # Never forced; never waits for an in-flight pass.
    if locked_reconcile(client, blocking=False) is None:
        log.info("skipped, reconcile already running")


def handle_event(event: dict, client: docker.DockerClient) -> None:
    labels = event.get("Actor", {}).get("Attributes", {})
    if labels.get(LABEL) != LABEL_TRUE:
        return

    hostnames = wan_hostnames_from_labels(labels)
    if not hostnames:
        return

    status = event.get("status")
    if status == "start":
        with RECONCILE_LOCK:  # same state file as reconcile(); never interleave
            absent_since, managed = load_state()
            changed = False
            for hostname in hostnames:
                cf_upsert_record(hostname)
                if absent_since.pop(hostname, None) is not None:
                    changed = True
                if hostname not in managed:
                    managed.add(hostname)
                    changed = True
            if changed:
                save_state(absent_since, managed)
    # Deliberately no action on die/stop/destroy here — deletion only happens
    # via reconcile() after the hostname has been continuously absent for
    # DELETE_GRACE_SECONDS, to avoid wiping DNS on a transient restart.


def make_handler(token: str, reconcile_fn):
    """Request handler class. reconcile_fn(force=bool) must return the summary dict."""
    token_bytes = token.encode()

    class Handler(BaseHTTPRequestHandler):
        server_version = "dns-sync"

        def log_message(self, fmt, *args):
            log.info("http %s - %s", self.address_string(), fmt % args)

        def _send(self, status, payload, headers=None):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status, message, headers=None):
            self._send(status, {"status": "error", "error": message}, headers)

        def _authorized(self):
            scheme, _, supplied = self.headers.get("Authorization", "").partition(" ")
            return scheme == "Bearer" and hmac.compare_digest(supplied.encode(), token_bytes)

        def _read_force(self, query):
            force = False
            raw = query.get("force", [None])[0]
            if raw is not None:
                if raw.lower() in ("1", "true"):
                    force = True
                elif raw.lower() not in ("0", "false", ""):
                    raise ValueError("query param force must be 1, true, 0 or false")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ValueError("invalid Content-Length")
            if length < 0 or length > HTTP_MAX_BODY_BYTES:
                raise ValueError("invalid body size")
            if length:
                try:
                    body = json.loads(self.rfile.read(length))
                except ValueError:
                    raise ValueError("malformed JSON body")
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                value = body.get("force", False)
                if not isinstance(value, bool):
                    raise ValueError('"force" must be a boolean')
                force = force or value
            return force

        def _dispatch(self):
            url = urlsplit(self.path)
            allowed = HTTP_ROUTES.get(url.path)
            if allowed is None:
                return self._error(404, "not found")
            if self.command not in allowed:
                return self._error(405, "method not allowed", {"Allow": ", ".join(allowed)})
            if url.path == "/healthz":
                return self._send(200, {"status": "ok"})
            if not self._authorized():
                return self._error(401, "unauthorized", {"WWW-Authenticate": "Bearer"})
            try:
                force = self._read_force(parse_qs(url.query, keep_blank_values=True))
            except ValueError as exc:
                return self._error(400, str(exc))
            if force:
                log.warning("force reconcile requested via HTTP from %s", self.address_string())
            try:
                summary = reconcile_fn(force=force)
            except requests.HTTPError as exc:
                log.error("Cloudflare API error during HTTP-triggered reconcile: %s", exc)
                return self._error(502, "Cloudflare API error")
            except Exception:
                log.exception("HTTP-triggered reconcile failed")
                return self._error(500, "internal error")
            log.info("HTTP-triggered reconcile finished (force=%s)", force)
            self._send(200, summary)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _dispatch

    return Handler


def build_server(bind: str, port: int, token: str, reconcile_fn) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((bind, port), make_handler(token, reconcile_fn))


def start_http_server(client: docker.DockerClient) -> ThreadingHTTPServer | None:
    """Starts the trigger endpoint in a daemon thread. Fails closed without WEBHOOK_TOKEN."""
    if not WEBHOOK_TOKEN:
        log.error("WEBHOOK_TOKEN is not set, HTTP trigger endpoint disabled")
        return None
    try:
        server = build_server(
            HTTP_BIND, HTTP_PORT, WEBHOOK_TOKEN,
            lambda force: locked_reconcile(client, force=force),
        )
    except OSError as exc:
        log.error("cannot start HTTP trigger endpoint on %s:%d: %s", HTTP_BIND, HTTP_PORT, exc)
        return None
    threading.Thread(target=server.serve_forever, name="http-trigger", daemon=True).start()
    log.info("HTTP trigger endpoint listening on %s:%d", HTTP_BIND, HTTP_PORT)
    return server


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

    start_http_server(client)
    last_reconcile = time.monotonic()
    for event in client.events(decode=True, filters={"type": "container"}):
        try:
            handle_event(event, client)
        except requests.HTTPError as exc:
            log.error("Cloudflare API error: %s", exc)

        if time.monotonic() - last_reconcile > RECONCILE_INTERVAL_SECONDS:
            try:
                periodic_reconcile(client)
            except requests.HTTPError as exc:
                log.error("Cloudflare API error during reconciliation: %s", exc)
            last_reconcile = time.monotonic()


if __name__ == "__main__":
    try:
        main(dry_run=parse_args().dry_run)
    except KeyboardInterrupt:
        sys.exit(0)
