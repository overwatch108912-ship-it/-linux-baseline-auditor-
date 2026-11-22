"""점검 실행 엔진.

점검 함수 하나가 예외로 죽더라도 전체 점검은 계속되어야 한다.
그래서 예외는 SKIP 판정으로 바꾸고 근거(evidence)에 예외 내용을 남긴다.
"""

from __future__ import annotations

import platform
import socket
import time
import traceback
from datetime import datetime
from typing import Iterable, List, Optional

from . import checks as checks_module
from .models import AuditContext, CheckResult, Report, Status


def _safe_hostname() -> str:
    try:
        return socket.gethostname() or platform.node() or "unknown"
    except OSError:  # pragma: no cover - 극단적 환경
        return "unknown"


def run_check(check, ctx: AuditContext) -> CheckResult:
    """점검 하나를 실행하고 결과를 CheckResult 로 감싼다."""
    started = time.perf_counter()
    try:
        outcome = check.run(ctx)
    except Exception as exc:  # noqa: BLE001 - 어떤 예외도 리포트에 남기고 계속한다
        outcome_status = Status.SKIP
        outcome_summary = f"점검 실행 중 오류: {type(exc).__name__}: {exc}"
        outcome_evidence = {"error": traceback.format_exc(limit=3)}
    else:
        outcome_status = outcome.status
        outcome_summary = outcome.summary
        outcome_evidence = dict(outcome.evidence)
    elapsed_ms = (time.perf_counter() - started) * 1000

    return CheckResult(
        check_id=check.id,
        title=check.title,
        category=check.category,
        severity=check.severity,
        status=outcome_status,
        summary=outcome_summary,
        remediation=check.remediation,
        evidence=outcome_evidence,
        duration_ms=elapsed_ms,
    )


def run_audit(
    ctx: Optional[AuditContext] = None,
    selected: Optional[Iterable] = None,
    generated_at: Optional[datetime] = None,
) -> Report:
    """점검 전체를 실행해 Report 를 만든다."""
    ctx = ctx or AuditContext()
    targets: List = list(selected) if selected is not None else checks_module.all_checks()
    results = [run_check(check, ctx) for check in targets]
    return Report(
        results=results,
        target_root=str(ctx.root),
        generated_at=generated_at or datetime.now().astimezone(),
        hostname=_safe_hostname(),
    )
