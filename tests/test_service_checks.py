import tempfile
import unittest
from pathlib import Path

from linux_baseline_auditor.checks.service import (
    RootRemoteLogin,
    evaluate_permit_root_login,
    parse_sshd_value,
)
from linux_baseline_auditor.models import Status

from .support import SSHD_ALLOW, SSHD_DENY, context, make_root


class ParseSshdValueTests(unittest.TestCase):
    def test_finds_value(self):
        value, count = parse_sshd_value(SSHD_DENY)
        self.assertEqual(value, "no")
        self.assertEqual(count, 1)

    def test_first_occurrence_wins_like_sshd(self):
        text = "PermitRootLogin no\nPermitRootLogin yes\n"
        value, count = parse_sshd_value(text)
        self.assertEqual(value, "no")
        self.assertEqual(count, 2)

    def test_case_insensitive_key_and_value(self):
        value, _ = parse_sshd_value("permitrootlogin PROHIBIT-PASSWORD\n")
        self.assertEqual(value, "prohibit-password")

    def test_equals_form(self):
        value, _ = parse_sshd_value("PermitRootLogin=yes\n")
        self.assertEqual(value, "yes")

    def test_ignores_comments(self):
        value, count = parse_sshd_value("#PermitRootLogin yes\n")
        self.assertIsNone(value)
        self.assertEqual(count, 0)

    def test_stops_at_match_block(self):
        text = "PasswordAuthentication yes\nMatch User backup\n    PermitRootLogin yes\n"
        value, _ = parse_sshd_value(text)
        self.assertIsNone(value)

    def test_missing_key(self):
        value, count = parse_sshd_value("Port 22\n")
        self.assertIsNone(value)
        self.assertEqual(count, 0)


class PermitRootLoginRuleTests(unittest.TestCase):
    def test_no_is_pass(self):
        self.assertIs(evaluate_permit_root_login("no")[0], Status.PASS)

    def test_yes_is_fail(self):
        self.assertIs(evaluate_permit_root_login("yes")[0], Status.FAIL)

    def test_prohibit_password_is_warn(self):
        self.assertIs(evaluate_permit_root_login("prohibit-password")[0], Status.WARN)

    def test_unset_is_warn(self):
        status, reason = evaluate_permit_root_login(None)
        self.assertIs(status, Status.WARN)
        self.assertIn("미설정", reason)

    def test_unknown_value_is_warn(self):
        self.assertIs(evaluate_permit_root_login("sometimes")[0], Status.WARN)


class RootRemoteLoginCheckTests(unittest.TestCase):
    def test_permit_root_login_no_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), sshd=SSHD_DENY)
            outcome = RootRemoteLogin().run(context(root))
            self.assertIs(outcome.status, Status.PASS)
            self.assertEqual(outcome.evidence["permit_root_login"], "no")

    def test_permit_root_login_yes_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), sshd=SSHD_ALLOW)
            outcome = RootRemoteLogin().run(context(root))
            self.assertIs(outcome.status, Status.FAIL)

    def test_config_without_key_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), sshd="Port 2222\n")
            self.assertIs(RootRemoteLogin().run(context(root)).status, Status.WARN)

    def test_missing_config_is_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), sshd=None)
            outcome = RootRemoteLogin().run(context(root))
            self.assertIs(outcome.status, Status.SKIP)
            self.assertEqual(len(outcome.evidence["searched"]), 3)

    def test_alternate_location_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp), sshd=None)
            (base / "etc" / "sshd_config").write_text("PermitRootLogin no\n", encoding="utf-8")
            outcome = RootRemoteLogin().run(context(base))
            self.assertIs(outcome.status, Status.PASS)
            self.assertTrue(outcome.evidence["path"].endswith("etc/sshd_config"))

    def test_include_directive_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), sshd="Include /etc/ssh/sshd_config.d/*.conf\nPermitRootLogin no\n")
            outcome = RootRemoteLogin().run(context(root))
            self.assertIn("include_directives", outcome.evidence)


if __name__ == "__main__":
    unittest.main()
