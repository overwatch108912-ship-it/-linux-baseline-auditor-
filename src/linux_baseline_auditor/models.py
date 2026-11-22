"""점검 결과 데이터 모델.

이 모듈은 다른 모듈에 의존하지 않는다. 점검(check) 모듈, 실행 엔진(engine),
리포트 출력기(reporters)가 모두 여기의 자료형만 주고받는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

TOOL_NAME = "linux-baseline-auditor"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"


class Status(str, Enum):
    """점검 항목 하나의 판정 결과."""

    PASS = "PASS"   # 양호: 기준을 만족
    FAIL = "FAIL"   # 취약: 기준 위반
    WARN = "WARN"   # 확인 필요: 위반은 아니지만 정책 확인이 필요
    SKIP = "SKIP"   # 건너뜀: 파일이 없거나 권한이 없어 판정 불가

    @property
    def label_ko(self) -> str:
        """리포트에 함께 표시할 한국어 라벨."""
        return {
            "PASS": "양호",
            "FAIL": "취약",
            "WARN": "확인 필요",
            "SKIP": "건너뜀",
        }[self.value]


#: KISA 가이드의 항목 중요도. 낮을수록 위험도가 높다.
SEVERITY_RANK = {"상": 0, "중": 1, "하": 2}


@dataclass(frozen=True)
class AuditContext:
    """점검 실행 환경.

    ``root`` 를 바꾸면 실제 운영체제 대신 임시 디렉터리나 마운트된 이미지를
    대상으로 점검할 수 있다. 이 덕분에 단위 테스트가 시스템을 건드리지 않는다.
    """

    root: Path = Path("/")
    scan_paths: Sequence[Path] = ()
    max_entries: int = 200_000
    suid_allowlist: frozenset[str] = frozenset()

    def path(self, *parts: str) -> Path:
        """``root`` 기준 상대 경로를 절대 경로로 만든다."""
        return self.root.joinpath(*parts)

    @property
    def effective_scan_paths(self) -> Sequence[Path]:
        """스캔 대상 디렉터리. 지정하지 않으면 ``root`` 전체를 본다."""
        return tuple(self.scan_paths) or (self.root,)


@dataclass(frozen=True)
class CheckOutcome:
    """점검 함수 하나가 돌려주는 판정과 근거."""

    status: Status
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    """점검 항목 메타데이터 + 실행 결과. 리포트의 한 행이다."""

    check_id: str
    title: str
    category: str
    severity: str
    status: Status
    summary: str
    remediation: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "category": self.category,
            "severity": self.severity,
            "status": self.status.value,
            "status_ko": self.status.label_ko,
            "summary": self.summary,
            "remediation": self.remediation,
            "evidence": self.evidence,
            "duration_ms": round(self.duration_ms, 3),
        }


@dataclass
class Report:
    """한 번의 점검 실행 전체 결과."""

    results: list[CheckResult]
    target_root: str
    generated_at: datetime
    hostname: str
    tool_version: str = TOOL_VERSION

    def count(self, status: Status) -> int:
        return sum(1 for r in self.results if r.status is status)

    @property
    def counts(self) -> dict[str, int]:
        return {s.value: self.count(s) for s in Status}

    @property
    def overall(self) -> Status:
        """종합 판정: FAIL > WARN > SKIP > PASS 순으로 나쁜 쪽을 따른다."""
        if self.count(Status.FAIL):
            return Status.FAIL
        if self.count(Status.WARN):
            return Status.WARN
        if self.count(Status.PASS):
            return Status.PASS
        return Status.SKIP

    @property
    def has_fail(self) -> bool:
        return self.count(Status.FAIL) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "tool": {"name": TOOL_NAME, "version": self.tool_version},
            "generated_at": self.generated_at.isoformat(timespec="seconds"),
            "hostname": self.hostname,
            "target_root": self.target_root,
            "summary": {**self.counts, "overall": self.overall.value},
            "results": [r.to_dict() for r in self.results],
        }
