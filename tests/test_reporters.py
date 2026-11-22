import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from linux_baseline_auditor.models import CheckResult, Report, Status
from linux_baseline_auditor.reporters import render_console, render_html, write_html, write_json


def build_report() -> Report:
    results = [
        CheckResult("U-01", "root 계정 원격 접속 제한", "서비스 관리", "상", Status.PASS, "PermitRootLogin no"),
        CheckResult("U-16", "/etc/passwd 권한", "계정 관리", "상", Status.FAIL, "권한 0666"),
        CheckResult("U-23", "SUID/SGID 점검", "파일 및 디렉터리 관리", "상", Status.WARN, "허용 목록 밖 1건"),
        CheckResult("U-18", "/etc/shadow 권한", "계정 관리", "상", Status.SKIP, "파일 없음"),
    ]
    return Report(
        results=results,
        target_root="/",
        generated_at=datetime(2026, 11, 22, 9, 30, tzinfo=timezone.utc),
        hostname="audit-vm",
    )


class JsonReportTests(unittest.TestCase):
    def test_writes_utf8_json(self):
        report = build_report()
        with tempfile.TemporaryDirectory() as tmp:
            path = write_json(report, Path(tmp) / "out" / "report.json")
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text(encoding="utf-8"))
            text = path.read_text(encoding="utf-8")
        self.assertEqual(payload["hostname"], "audit-vm")
        self.assertEqual(payload["summary"]["PASS"], 1)
        self.assertEqual(payload["summary"]["overall"], "FAIL")
        self.assertEqual(len(payload["results"]), 4)
        self.assertIn("root 계정 원격 접속 제한", text)


class HtmlReportTests(unittest.TestCase):
    def test_contains_all_results_and_counts(self):
        html_text = render_html(build_report())
        for check_id in ("U-01", "U-16", "U-23", "U-18"):
            self.assertIn(check_id, html_text)
        self.assertIn('class="badge PASS"', html_text)
        self.assertIn("종합 FAIL", html_text)
        self.assertIn("<html lang=\"ko\">", html_text)

    def test_escapes_untrusted_text(self):
        report = build_report()
        report.results[0].summary = '<script>alert("x")</script>'
        html_text = render_html(report)
        self.assertNotIn("<script>alert", html_text)
        self.assertIn("&lt;script&gt;", html_text)

    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_html(build_report(), Path(tmp) / "report.html")
            self.assertTrue(path.exists())
            self.assertIn("리눅스 보안 기준선 점검 리포트", path.read_text(encoding="utf-8"))


class ConsoleReportTests(unittest.TestCase):
    def test_plain_text_has_no_ansi(self):
        text = render_console(build_report(), color=False)
        self.assertNotIn("\033[", text)
        self.assertIn("[PASS] U-01", text)
        self.assertIn("[FAIL] U-16", text)
        self.assertIn("종합: FAIL", text)

    def test_color_adds_ansi(self):
        self.assertIn("\033[", render_console(build_report(), color=True))


if __name__ == "__main__":
    unittest.main()
