import tempfile
import unittest
from pathlib import Path

from linux_baseline_auditor.checks.account import (
    PasswdPermissions,
    PasswordFileProtected,
    RootUidOnly,
    ShadowPermissions,
    evaluate_passwd_permissions,
    evaluate_shadow_permissions,
    parse_passwd,
)
from linux_baseline_auditor.models import Status

from .support import context, make_root


class ParsePasswdTests(unittest.TestCase):
    def test_parses_fields(self):
        entries, malformed = parse_passwd(
            "root:x:0:0:root:/root:/bin/bash\n"
            "# 주석\n"
            "\n"
            "app:x:1001:1001::/home/app:/usr/sbin/nologin\n"
        )
        self.assertEqual(malformed, 0)
        self.assertEqual([e.name for e in entries], ["root", "app"])
        self.assertEqual(entries[1].uid, 1001)
        self.assertEqual(entries[1].shell, "/usr/sbin/nologin")

    def test_counts_malformed_lines(self):
        entries, malformed = parse_passwd("broken line\nroot:x:0:0:root:/root:/bin/bash\n")
        self.assertEqual(malformed, 1)
        self.assertEqual(len(entries), 1)

    def test_non_numeric_uid_is_malformed(self):
        _, malformed = parse_passwd("bad:x:abc:0::/home/bad:/bin/sh\n")
        self.assertEqual(malformed, 1)


class PasswdPermissionRuleTests(unittest.TestCase):
    def test_standard_644_root_is_pass(self):
        status, _ = evaluate_passwd_permissions(0o644, 0)
        self.assertIs(status, Status.PASS)

    def test_group_write_is_fail(self):
        status, reason = evaluate_passwd_permissions(0o664, 0)
        self.assertIs(status, Status.FAIL)
        self.assertIn("664", reason)

    def test_world_write_is_fail(self):
        status, _ = evaluate_passwd_permissions(0o646, 0)
        self.assertIs(status, Status.FAIL)

    def test_executable_bit_is_fail(self):
        status, _ = evaluate_passwd_permissions(0o755, 0)
        self.assertIs(status, Status.FAIL)

    def test_stricter_600_is_pass(self):
        status, _ = evaluate_passwd_permissions(0o600, 0)
        self.assertIs(status, Status.PASS)

    def test_non_root_owner_is_fail(self):
        status, reason = evaluate_passwd_permissions(0o644, 1000)
        self.assertIs(status, Status.FAIL)
        self.assertIn("1000", reason)


class ShadowPermissionRuleTests(unittest.TestCase):
    def test_400_is_pass(self):
        self.assertIs(evaluate_shadow_permissions(0o400, 0)[0], Status.PASS)

    def test_600_is_pass(self):
        self.assertIs(evaluate_shadow_permissions(0o600, 0)[0], Status.PASS)

    def test_640_is_warn(self):
        status, reason = evaluate_shadow_permissions(0o640, 0)
        self.assertIs(status, Status.WARN)
        self.assertIn("그룹 읽기", reason)

    def test_world_readable_is_fail(self):
        self.assertIs(evaluate_shadow_permissions(0o644, 0)[0], Status.FAIL)

    def test_group_write_is_fail(self):
        self.assertIs(evaluate_shadow_permissions(0o660, 0)[0], Status.FAIL)

    def test_non_root_owner_is_fail(self):
        self.assertIs(evaluate_shadow_permissions(0o400, 1001)[0], Status.FAIL)


class PasswordFileProtectedTests(unittest.TestCase):
    def test_shadow_placeholders_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            outcome = PasswordFileProtected().run(context(root))
            self.assertIs(outcome.status, Status.PASS)
            self.assertEqual(outcome.evidence["accounts"], 3)

    def test_plaintext_hash_is_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            passwd = "root:x:0:0:root:/root:/bin/bash\nold:$1$abc$def:1000:1000::/home/old:/bin/sh\n"
            root = make_root(Path(tmp), passwd=passwd)
            outcome = PasswordFileProtected().run(context(root))
            self.assertIs(outcome.status, Status.FAIL)
            self.assertIn("old", outcome.evidence["exposed_accounts"])

    def test_empty_password_field_is_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            passwd = "root::0:0:root:/root:/bin/bash\n"
            root = make_root(Path(tmp), passwd=passwd)
            self.assertIs(PasswordFileProtected().run(context(root)).status, Status.FAIL)

    def test_missing_passwd_is_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), passwd=None)
            outcome = PasswordFileProtected().run(context(root))
            self.assertIs(outcome.status, Status.SKIP)
            self.assertIn("파일 없음", outcome.summary)

    def test_missing_shadow_is_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), shadow=False)
            outcome = PasswordFileProtected().run(context(root))
            self.assertIs(outcome.status, Status.WARN)

    def test_empty_file_is_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), passwd="\n\n")
            self.assertIs(PasswordFileProtected().run(context(root)).status, Status.SKIP)


class RootUidOnlyTests(unittest.TestCase):
    def test_only_root_has_uid_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            outcome = RootUidOnly().run(context(root))
            self.assertIs(outcome.status, Status.PASS)
            self.assertEqual(outcome.evidence["uid0_accounts"], ["root"])

    def test_second_uid_zero_account_is_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            passwd = (
                "root:x:0:0:root:/root:/bin/bash\n"
                "backdoor:x:0:0::/home/backdoor:/bin/bash\n"
            )
            root = make_root(Path(tmp), passwd=passwd)
            outcome = RootUidOnly().run(context(root))
            self.assertIs(outcome.status, Status.FAIL)
            self.assertIn("backdoor", outcome.summary)

    def test_missing_file_is_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), passwd=None)
            self.assertIs(RootUidOnly().run(context(root)).status, Status.SKIP)


class StatBasedChecksTests(unittest.TestCase):
    """U-16/U-18 은 실제 파일의 권한을 stat 해서 판정한다.

    임시 디렉터리의 파일은 현재 사용자 소유(uid != 0)이므로 소유자 검사에서
    취약으로 나오는 것이 정상이다. 그래서 여기서는 stat 실패(SKIP)와
    권한 비트 반영만 확인한다.
    """

    def test_missing_passwd_is_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), passwd=None)
            outcome = PasswdPermissions().run(context(root))
            self.assertIs(outcome.status, Status.SKIP)

    def test_missing_shadow_is_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), shadow=False)
            outcome = ShadowPermissions().run(context(root))
            self.assertIs(outcome.status, Status.SKIP)

    def test_world_writable_shadow_is_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), shadow_mode=0o666)
            outcome = ShadowPermissions().run(context(root))
            self.assertIs(outcome.status, Status.FAIL)
            self.assertEqual(outcome.evidence["mode"], "0666")

    def test_evidence_contains_mode_and_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), passwd_mode=0o644)
            outcome = PasswdPermissions().run(context(root))
            self.assertEqual(outcome.evidence["mode"], "0644")
            self.assertIn("uid", outcome.evidence)


if __name__ == "__main__":
    unittest.main()
