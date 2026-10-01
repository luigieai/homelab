import contextlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

import requests

os.environ.setdefault("CLOUDFLARE_API_TOKEN", "test-token")
os.environ.setdefault("CLOUDFLARE_ZONE_ID", "test-zone")
os.environ.setdefault("DNS_RECORD_TARGET", "target.example.com")

import dns_sync  # noqa: E402

HOST_NEW = "new.lab.marioverde.com.br"
HOST_OLD = "old.lab.marioverde.com.br"


class ParseArgsTest(unittest.TestCase):
    def test_default_is_not_dry_run(self):
        self.assertFalse(dns_sync.parse_args([]).dry_run)

    def test_flag_enables_dry_run(self):
        self.assertTrue(dns_sync.parse_args(["--dry-run"]).dry_run)


class VersionFlagTest(unittest.TestCase):
    def test_version_prints_and_exits_zero(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            dns_sync.parse_args(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertEqual(out.getvalue(), "dns-sync 0.3.0\n")

    def test_version_does_not_touch_cloudflare(self):
        with mock.patch.object(dns_sync, "cf_session") as session, \
                contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit):
            dns_sync.parse_args(["--version"])
        self.assertEqual(session.method_calls, [])


class DryRunRecordTest(unittest.TestCase):
    def test_upsert_logs_and_skips_api(self):
        with mock.patch.object(dns_sync, "DRY_RUN", True), \
                mock.patch.object(dns_sync, "cf_session") as session, \
                self.assertLogs("dns-sync", "INFO") as logs:
            dns_sync.cf_upsert_record(HOST_NEW)
        self.assertEqual(session.method_calls, [])
        self.assertIn("[dry-run] would upsert DNS record " + HOST_NEW, logs.output[0])

    def test_delete_logs_and_skips_api(self):
        with mock.patch.object(dns_sync, "DRY_RUN", True), \
                mock.patch.object(dns_sync, "cf_session") as session, \
                self.assertLogs("dns-sync", "INFO") as logs:
            dns_sync.cf_delete_record(HOST_OLD)
        self.assertEqual(session.method_calls, [])
        self.assertIn("[dry-run] would delete DNS record " + HOST_OLD, logs.output[0])

    def test_normal_mode_still_calls_api(self):
        with mock.patch.object(dns_sync, "DRY_RUN", False), \
                mock.patch.object(dns_sync, "cf_session") as session:
            session.get.return_value.json.return_value = {"result": []}
            dns_sync.cf_upsert_record(HOST_NEW)
        session.get.assert_called_once()
        session.post.assert_called_once()


class DryRunReconcileTest(unittest.TestCase):
    def test_reconcile_logs_changes_and_does_not_save_state(self):
        state = {HOST_OLD: 0.0}  # absent since epoch, far past the grace period
        with mock.patch.object(dns_sync, "DRY_RUN", True), \
                mock.patch.object(dns_sync, "cf_session") as session, \
                mock.patch.object(dns_sync, "active_hostnames", return_value={HOST_NEW}), \
                mock.patch.object(dns_sync, "load_absent_since", side_effect=lambda: dict(state)), \
                mock.patch.object(dns_sync, "save_absent_since") as save, \
                self.assertLogs("dns-sync", "INFO") as logs:
            dns_sync.reconcile(mock.Mock())
        output = "\n".join(logs.output)
        self.assertIn("would upsert DNS record " + HOST_NEW, output)
        self.assertIn("would delete DNS record " + HOST_OLD, output)
        self.assertEqual(session.method_calls, [])
        save.assert_not_called()


class DryRunMainTest(unittest.TestCase):
    def tearDown(self):
        dns_sync.DRY_RUN = False

    def test_main_dry_run_reconciles_once_and_skips_event_loop(self):
        with mock.patch.object(dns_sync.docker, "from_env") as from_env, \
                mock.patch.object(dns_sync, "reconcile") as reconcile:
            dns_sync.main(dry_run=True)
        reconcile.assert_called_once_with(from_env.return_value)
        from_env.return_value.events.assert_not_called()


class RecordActionTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch.object(dns_sync, "DRY_RUN", False))
        self.session = self.enterContext(mock.patch.object(dns_sync, "cf_session"))

    def _existing(self, **overrides):
        record = {
            "id": "rec1",
            "content": dns_sync.RECORD_TARGET,
            "proxied": dns_sync.RECORD_PROXIED,
        }
        record.update(overrides)
        self.session.get.return_value.json.return_value = {"result": [record]}

    def test_upsert_reports_created(self):
        self.session.get.return_value.json.return_value = {"result": []}
        self.assertEqual(dns_sync.cf_upsert_record(HOST_NEW), "created")

    def test_upsert_reports_updated(self):
        self._existing(content="other.example.com")
        self.assertEqual(dns_sync.cf_upsert_record(HOST_NEW), "updated")
        self.session.put.assert_called_once()

    def test_upsert_reports_unchanged(self):
        self._existing()
        self.assertEqual(dns_sync.cf_upsert_record(HOST_NEW), "unchanged")
        self.session.put.assert_not_called()
        self.session.post.assert_not_called()

    def test_upsert_dry_run_reports_would_upsert(self):
        with mock.patch.object(dns_sync, "DRY_RUN", True):
            self.assertEqual(dns_sync.cf_upsert_record(HOST_NEW), "would-upsert")

    def test_delete_reports_deleted(self):
        self._existing()
        self.assertEqual(dns_sync.cf_delete_record(HOST_OLD), "deleted")
        self.session.delete.assert_called_once()

    def test_delete_reports_absent_when_no_record(self):
        self.session.get.return_value.json.return_value = {"result": []}
        self.assertEqual(dns_sync.cf_delete_record(HOST_OLD), "absent")
        self.session.delete.assert_not_called()

    def test_delete_dry_run_reports_would_delete(self):
        with mock.patch.object(dns_sync, "DRY_RUN", True):
            self.assertEqual(dns_sync.cf_delete_record(HOST_OLD), "would-delete")
        self.session.delete.assert_not_called()


class ReconcileSummaryTest(unittest.TestCase):
    GRACE = 1000

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.state_path = os.path.join(tmp.name, "absent-since.json")
        with open(self.state_path, "w") as f:
            json.dump({HOST_OLD: time.time() - 100}, f)  # ~900s of grace left
        self.enterContext(mock.patch.object(dns_sync, "DRY_RUN", False))
        self.enterContext(mock.patch.object(dns_sync, "STATE_FILE", self.state_path))
        self.enterContext(mock.patch.object(dns_sync, "DELETE_GRACE_SECONDS", self.GRACE))
        self.enterContext(
            mock.patch.object(dns_sync, "active_hostnames", return_value={HOST_NEW})
        )
        self.upsert = self.enterContext(
            mock.patch.object(dns_sync, "cf_upsert_record", return_value="created")
        )
        self.delete = self.enterContext(
            mock.patch.object(dns_sync, "cf_delete_record", return_value="deleted")
        )

    def _state(self):
        with open(self.state_path) as f:
            return json.load(f)

    def test_normal_mode_keeps_absent_hostname_in_grace_and_reports_pending(self):
        summary = dns_sync.reconcile(mock.Mock())
        self.delete.assert_not_called()
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["mode"], "normal")
        self.assertFalse(summary["dry_run"])
        self.assertEqual(summary["active"], [HOST_NEW])
        self.assertEqual(summary["created"], [HOST_NEW])
        self.assertEqual(summary["deleted"], [])
        self.assertEqual(len(summary["pending"]), 1)
        pending = summary["pending"][0]
        self.assertEqual(pending["hostname"], HOST_OLD)
        self.assertTrue(895 <= pending["seconds_remaining"] <= 900)
        self.assertIn(HOST_OLD, self._state())

    def test_force_mode_deletes_absent_hostname_and_drops_it_from_state(self):
        summary = dns_sync.reconcile(mock.Mock(), force=True)
        self.delete.assert_called_once_with(HOST_OLD)
        self.assertEqual(summary["mode"], "force")
        self.assertEqual(summary["deleted"], [HOST_OLD])
        self.assertEqual(summary["pending"], [])
        self.assertNotIn(HOST_OLD, self._state())


class LockedReconcileTest(unittest.TestCase):
    def setUp(self):
        self.lock = threading.Lock()
        self.enterContext(mock.patch.object(dns_sync, "RECONCILE_LOCK", self.lock))
        self.reconcile = self.enterContext(
            mock.patch.object(dns_sync, "reconcile", return_value={"status": "ok"})
        )

    def test_runs_reconcile_without_force_by_default_and_releases_lock(self):
        client = mock.Mock()
        self.assertEqual(dns_sync.locked_reconcile(client), {"status": "ok"})
        self.reconcile.assert_called_once_with(client, force=False)
        self.assertFalse(self.lock.locked())

    def test_non_blocking_returns_none_when_lock_held(self):
        self.lock.acquire()
        self.assertIsNone(dns_sync.locked_reconcile(mock.Mock(), blocking=False))
        self.reconcile.assert_not_called()

    def test_periodic_runs_without_force_when_free(self):
        client = mock.Mock()
        dns_sync.periodic_reconcile(client)
        self.reconcile.assert_called_once_with(client, force=False)

    def test_periodic_logs_skip_when_lock_held(self):
        self.lock.acquire()
        with self.assertLogs("dns-sync", "INFO") as logs:
            dns_sync.periodic_reconcile(mock.Mock())
        self.assertIn("skipped, reconcile already running", logs.output[0])
        self.reconcile.assert_not_called()


TOKEN = "s3cret-token"
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_call(port, method, path, token=TOKEN, body=None, raw=None):
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=headers
    )
    try:
        with _opener.open(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        with exc:
            return exc.code, json.loads(exc.read())


class HttpEndpointTest(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def fake_reconcile(force=False):
            self.calls.append(force)
            return {"status": "ok", "mode": "force" if force else "normal"}

        self.port = self.serve(fake_reconcile)

    def serve(self, reconcile_fn):
        server = dns_sync.build_server("127.0.0.1", 0, TOKEN, reconcile_fn)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_address[1]

    def test_post_without_token_is_401(self):
        status, body = http_call(self.port, "POST", "/reconcile", token=None)
        self.assertEqual(status, 401)
        self.assertEqual(body["status"], "error")
        self.assertEqual(self.calls, [])

    def test_post_with_wrong_token_is_401(self):
        status, body = http_call(self.port, "POST", "/reconcile", token="nope")
        self.assertEqual(status, 401)
        self.assertEqual(body["status"], "error")
        self.assertEqual(self.calls, [])

    def test_post_with_correct_token_returns_summary(self):
        status, body = http_call(self.port, "POST", "/reconcile")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok", "mode": "normal"})
        self.assertEqual(self.calls, [False])

    def test_body_force_true_is_forwarded(self):
        status, body = http_call(self.port, "POST", "/reconcile", body={"force": True})
        self.assertEqual(status, 200)
        self.assertEqual(body["mode"], "force")
        self.assertEqual(self.calls, [True])

    def test_query_force_is_forwarded(self):
        status, _ = http_call(self.port, "POST", "/reconcile?force=1")
        self.assertEqual(status, 200)
        self.assertEqual(self.calls, [True])

    def test_get_reconcile_requires_auth(self):
        status, body = http_call(self.port, "GET", "/reconcile", token=None)
        self.assertEqual(status, 401)
        self.assertEqual(body["status"], "error")
        self.assertEqual(self.calls, [])

    def test_get_reconcile_runs_a_normal_pass(self):
        status, body = http_call(self.port, "GET", "/reconcile")
        self.assertEqual(status, 200)
        self.assertEqual(body["mode"], "normal")
        self.assertEqual(self.calls, [False])

    def test_healthz_needs_no_auth(self):
        status, body = http_call(self.port, "GET", "/healthz", token=None)
        self.assertEqual((status, body), (200, {"status": "ok"}))
        self.assertEqual(self.calls, [])

    def test_unknown_path_is_404(self):
        status, body = http_call(self.port, "GET", "/nope")
        self.assertEqual(status, 404)
        self.assertEqual(body["status"], "error")

    def test_delete_on_reconcile_is_405(self):
        status, body = http_call(self.port, "DELETE", "/reconcile")
        self.assertEqual(status, 405)
        self.assertEqual(body["status"], "error")
        self.assertEqual(self.calls, [])

    def test_malformed_json_body_is_400(self):
        status, body = http_call(self.port, "POST", "/reconcile", raw=b"{not json")
        self.assertEqual(status, 400)
        self.assertEqual(body["status"], "error")
        self.assertEqual(self.calls, [])

    def test_non_boolean_force_is_400(self):
        status, body = http_call(self.port, "POST", "/reconcile", body={"force": "yes"})
        self.assertEqual(status, 400)
        self.assertEqual(body["status"], "error")
        self.assertEqual(self.calls, [])

    def test_cloudflare_error_is_502_json(self):
        def boom(force=False):
            raise requests.HTTPError("cf down")

        port = self.serve(boom)
        with self.assertLogs("dns-sync", "ERROR"):
            status, body = http_call(port, "POST", "/reconcile")
        self.assertEqual(status, 502)
        self.assertEqual(body["status"], "error")


class StartHttpServerTest(unittest.TestCase):
    def test_not_started_and_one_error_logged_when_token_empty(self):
        with mock.patch.object(dns_sync, "WEBHOOK_TOKEN", ""), \
                mock.patch.object(dns_sync, "build_server") as build, \
                self.assertLogs("dns-sync", "ERROR") as logs:
            result = dns_sync.start_http_server(mock.Mock())
        self.assertIsNone(result)
        build.assert_not_called()
        self.assertEqual(len(logs.output), 1)

    def test_started_in_background_thread_when_token_set(self):
        with mock.patch.object(dns_sync, "WEBHOOK_TOKEN", TOKEN), \
                mock.patch.object(dns_sync, "build_server") as build, \
                mock.patch.object(dns_sync.threading, "Thread") as thread:
            result = dns_sync.start_http_server(mock.Mock())
        self.assertIs(result, build.return_value)
        build.assert_called_once()
        thread.return_value.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
