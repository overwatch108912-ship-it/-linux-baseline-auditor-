"""CLI 종단 테스트.

임시 디렉터리를 ``--root`` 로 넘겨 실제 시스템을 건드리지 않는다.
참고: 임시 디렉터리의 파일은 현재 사용자 소유(uid != 0)라서 U-16/U-18 은
"소유자가 root 아님"으로 FAIL 이 된다. 그래서 전체 실행의 종료 코드는 1 이다.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from linux_baseline_auditor.cli import main

from .support import SSHD_ALLOW, make_root


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class ListChecksTests(unittest.TestCase):
    def test_lists_registered_checks(self):
        code, out, _ = run_cli(["--list-checks"])
        self.assertEqual(code, 0)
        self.assertIn("U-01", out)
        self.assertIn("U-25", out)
        self.assertIn("등록된 점검 항목 7개", out)


class AuditRunTests(unittest.TestCase):
    def test_full_run_writes_reports_and_returns_1_on_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp) / "target")
            json_path = Path(tmp) / "out" / "report.json"
            html_path = Path(tmp) / "out" / "report.html"
            code, out, _ = run_cli([
                "--root", str(base),
                "--json", str(json_path),
                "--html", str(html_path),
                "--no-color",
            ])
            self.assertEqual(code, 1)
            self.assertTrue(json_path.exists())
            self.assertTrue(html_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["results"]), 7)
            self.assertEqual(payload["target_root"], str(base))
            self.assertIn("종합: FAIL", out)

    def test_only_filters_to_one_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp) / "target")
            json_path = Path(tmp) / "report.json"
            code, out, _ = run_cli([
                "--root", str(base), "--only", "U-01",
                "--json", str(json_path), "--no-html", "--no-color",
            ])
            self.assertEqual(code, 0)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual([r["check_id"] for r in payload["results"]], ["U-01"])
            self.assertIn("PermitRootLogin", out)

    def test_exclude_removes_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp) / "target")
            json_path = Path(tmp) / "report.json"
            code, _, _ = run_cli([
                "--root", str(base), "--exclude", "U-16", "U-18",
                "--json", str(json_path), "--no-html", "--no-color",
            ])
            ids = [r["check_id"] for r in json.loads(json_path.read_text(encoding="utf-8"))["results"]]
            self.assertNotIn("U-16", ids)
            self.assertEqual(len(ids), 5)
            self.assertEqual(code, 0)

    def test_fail_detected_after_fixing_owner_checks_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp) / "target", sshd=SSHD_ALLOW)
            code, out, _ = run_cli([
                "--root", str(base), "--only", "U-01",
                "--no-json", "--no-html", "--no-color",
            ])
            self.assertEqual(code, 1)
            self.assertIn("[FAIL] U-01", out)

    def test_no_write_flags_skip_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp) / "target")
            before = set(Path.cwd().iterdir())
            code, out, _ = run_cli(["--root", str(base), "--no-json", "--no-html", "--no-color"])
            after = set(Path.cwd().iterdir())
            self.assertEqual(code, 1)
            self.assertEqual(before, after)
            self.assertNotIn("리포트 저장", out)

    def test_scan_path_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp) / "target")
            shared = base / "shared"
            shared.mkdir()
            (shared / "w.txt").write_text("x", encoding="utf-8")
            (shared / "w.txt").chmod(0o666)
            json_path = Path(tmp) / "report.json"
            run_cli([
                "--root", str(base), "--scan-path", str(shared), "--only", "U-25",
                "--json", str(json_path), "--no-html", "--no-color",
            ])
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["status"], "FAIL")
            self.assertEqual(payload["results"][0]["evidence"]["risky_count"], 1)


class ErrorHandlingTests(unittest.TestCase):
    def test_unknown_check_id_returns_2(self):
        code, _, err = run_cli(["--only", "U-99"])
        self.assertEqual(code, 2)
        self.assertIn("등록되지 않은 점검 ID", err)

    def test_missing_root_returns_2(self):
        code, _, err = run_cli(["--root", "/no/such/path", "--no-color"])
        self.assertEqual(code, 2)
        self.assertIn("경로가 없습니다", err)

    def test_missing_scan_path_returns_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_root(Path(tmp) / "target")
            code, _, err = run_cli(["--root", str(base), "--scan-path", "/no/such/dir"])
            self.assertEqual(code, 2)
            self.assertIn("--scan-path", err)


if __name__ == "__main__":
    unittest.main()
