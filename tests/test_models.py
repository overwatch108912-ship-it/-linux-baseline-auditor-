import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from linux_baseline_auditor.models import (
    AuditContext,
    CheckOutcome,
    CheckResult,
    Report,
    Status,
)


def result(check_id: str, status: Status, severity: str = "상") -> CheckResult:
    return CheckResult(
        check_id=check_id,
        title=f"항목 {check_id}",
        category="계정 관리",
        severity=severity,
        status=status,
        summary="요약",
    )


class StatusTests(unittest.TestCase):
    def test_korean_label(self):
        self.assertEqual(Status.PASS.label_ko, "양호")
        self.assertEqual(Status.SKIP.label_ko, "건너뜀")

    def test_status_is_string_for_json(self):
        # str Enum 이므로 json 직렬화가 그대로 된다
        self.assertEqual(json.dumps({"s": Status.FAIL}), '{"s": "FAIL"}')


class AuditContextTests(unittest.TestCase):
    def test_path_joins_under_root(self):
        ctx = AuditContext(root=Path("/tmp/target"))
        self.assertEqual(ctx.path("etc", "passwd"), Path("/tmp/target/etc/passwd"))

    def test_effective_scan_paths_defaults_to_root(self):
        ctx = AuditContext(root=Path("/tmp/target"))
        self.assertEqual(ctx.effective_scan_paths, (Path("/tmp/target"),))

    def test_effective_scan_paths_uses_explicit_paths(self):
        ctx = AuditContext(root=Path("/x"), scan_paths=(Path("/x/a"), Path("/x/b")))
        self.assertEqual(ctx.effective_scan_paths, (Path("/x/a"), Path("/x/b")))


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.report = Report(
            results=[
                result("U-01", Status.PASS),
                result("U-16", Status.FAIL),
                result("U-18", Status.WARN),
                result("U-23", Status.SKIP),
            ],
            target_root="/",
            generated_at=datetime(2026, 11, 22, 9, 0, tzinfo=timezone.utc),
            hostname="test-vm",
        )

    def test_counts(self):
        self.assertEqual(
            self.report.counts, {"PASS": 1, "FAIL": 1, "WARN": 1, "SKIP": 1}
        )

    def test_overall_prefers_fail(self):
        self.assertIs(self.report.overall, Status.FAIL)
        self.assertTrue(self.report.has_fail)

    def test_overall_without_fail_is_warn(self):
        self.report.results = [result("U-01", Status.PASS), result("U-18", Status.WARN)]
        self.assertIs(self.report.overall, Status.WARN)
        self.assertFalse(self.report.has_fail)

    def test_overall_all_pass(self):
        self.report.results = [result("U-01", Status.PASS), result("U-04", Status.PASS)]
        self.assertIs(self.report.overall, Status.PASS)

    def test_overall_all_skip(self):
        self.report.results = [result("U-01", Status.SKIP)]
        self.assertIs(self.report.overall, Status.SKIP)

    def test_to_dict_is_json_serializable(self):
        payload = self.report.to_dict()
        text = json.dumps(payload, ensure_ascii=False)
        restored = json.loads(text)
        self.assertEqual(restored["summary"]["overall"], "FAIL")
        self.assertEqual(len(restored["results"]), 4)
        self.assertEqual(restored["results"][1]["status_ko"], "취약")
        self.assertEqual(restored["tool"]["name"], "linux-baseline-auditor")
        self.assertEqual(restored["schema_version"], "1.0")


class CheckOutcomeTests(unittest.TestCase):
    def test_evidence_is_not_shared_between_instances(self):
        a = CheckOutcome(Status.PASS, "a")
        b = CheckOutcome(Status.PASS, "b")
        self.assertEqual(a.evidence, {})
        self.assertIsNot(a.evidence, b.evidence)


if __name__ == "__main__":
    unittest.main()
