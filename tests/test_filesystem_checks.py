import os
import tempfile
import unittest
from pathlib import Path

from linux_baseline_auditor.checks.filesystem import (
    SuidSgidFiles,
    WorldWritable,
    load_allowlist,
    scan_modes,
)
from linux_baseline_auditor.models import Status

from .support import chmod, context, make_root


def touch(path: Path, mode: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    chmod(path, mode)
    return path


class ScanTests(unittest.TestCase):
    def test_collects_only_matching_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            touch(base / "a.txt", 0o644)
            touch(base / "b.txt", 0o666)
            outcome = scan_modes(
                [base], want=lambda mode, is_dir: bool(mode & 0o002), max_entries=1000
            )
            self.assertEqual([Path(p).name for p, _, _ in outcome.entries], ["b.txt"])

    def test_truncates_at_max_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for i in range(20):
                touch(base / f"f{i}.txt", 0o644)
            outcome = scan_modes([base], want=lambda mode, is_dir: True, max_entries=5)
            self.assertTrue(outcome.truncated)
            self.assertLessEqual(outcome.visited, 6)


class WorldWritableTests(unittest.TestCase):
    def test_clean_tree_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp))
            outcome = WorldWritable().run(context(base))
            self.assertIs(outcome.status, Status.PASS)

    def test_world_writable_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp))
            touch(base / "srv" / "public.conf", 0o666)
            outcome = WorldWritable().run(context(base))
            self.assertIs(outcome.status, Status.FAIL)
            self.assertIn("public.conf", " ".join(e["path"] for e in outcome.evidence["risky"]))

    def test_world_writable_dir_without_sticky_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp))
            shared = base / "shared"
            shared.mkdir()
            chmod(shared, 0o777)
            outcome = WorldWritable().run(context(base))
            self.assertIs(outcome.status, Status.FAIL)

    def test_sticky_dir_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp))
            tmpdir = base / "tmp"
            tmpdir.mkdir()
            chmod(tmpdir, 0o1777)
            outcome = WorldWritable().run(context(base))
            self.assertIs(outcome.status, Status.PASS)
            self.assertEqual(outcome.evidence["sticky_dirs_ignored"], 1)

    def test_truncated_scan_warns_instead_of_passing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp))
            touch(base / "one.txt", 0o644)
            outcome = WorldWritable().run(context(base, max_entries=1))
            self.assertIs(outcome.status, Status.WARN)


class SuidSgidTests(unittest.TestCase):
    def test_no_suid_files_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp))
            self.assertIs(SuidSgidFiles().run(context(base)).status, Status.PASS)

    def test_unexpected_suid_file_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp))
            touch(base / "usr" / "bin" / "odd", 0o4755)
            outcome = SuidSgidFiles().run(context(base))
            self.assertIs(outcome.status, Status.WARN)
            self.assertEqual(outcome.evidence["unexpected_count"], 1)

    def test_allowlisted_suid_file_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp))
            target = touch(base / "usr" / "bin" / "passwd", 0o4755)
            ctx = context(base, suid_allowlist=frozenset({str(target)}))
            outcome = SuidSgidFiles().run(ctx)
            self.assertIs(outcome.status, Status.PASS)
            self.assertEqual(outcome.evidence["unexpected_count"], 0)

    def test_sgid_dir_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp))
            mail = base / "var" / "mail"
            mail.mkdir(parents=True)
            chmod(mail, 0o2775)
            outcome = SuidSgidFiles().run(context(base))
            self.assertIs(outcome.status, Status.WARN)


class AllowlistTests(unittest.TestCase):
    def test_reads_paths_and_skips_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.txt"
            path.write_text("# 주석\n/usr/bin/sudo\n\n/usr/bin/passwd\n", encoding="utf-8")
            allow = load_allowlist(path)
            self.assertEqual(allow, frozenset({"/usr/bin/sudo", "/usr/bin/passwd"}))


if __name__ == "__main__":
    unittest.main()
