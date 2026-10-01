import os
import unittest
from unittest import mock

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


if __name__ == "__main__":
    unittest.main()
