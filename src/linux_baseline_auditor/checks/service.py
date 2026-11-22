"""서비스 관리 점검 (KISA U-01).

sshd 설정 파일을 읽어 root 원격 로그인 허용 여부를 판정한다.
설정 파일이 없는 서버(sshd 미설치)는 SKIP 이 아니라 PASS 로 두지 않는다 —
"확인할 수 없음"이 곧 "안전"은 아니므로 SKIP 으로 남긴다.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..models import AuditContext, CheckOutcome, Status
from ..sysutil import FileUnavailable, read_text
from .base import Check, register

#: 배포판마다 위치가 다르므로 순서대로 찾는다.
SSHD_CONFIG_CANDIDATES: Tuple[Tuple[str, ...], ...] = (
    ("etc", "ssh", "sshd_config"),
    ("etc", "sshd_config"),
    ("usr", "local", "etc", "ssh", "sshd_config"),
)

#: root 로그인을 명시적으로 막는 값.
DENY_VALUES = frozenset({"no", "false"})
#: 키 인증만 허용하는 값. 정책에 따라 허용할 수 있어 WARN.
RESTRICTED_VALUES = frozenset(
    {"prohibit-password", "without-password", "forced-commands-only"}
)
ALLOW_VALUES = frozenset({"yes", "true"})


def parse_sshd_value(text: str, key: str = "permitrootlogin") -> Tuple[Optional[str], int]:
    """sshd_config 에서 키 값을 찾는다.

    sshd 는 **먼저 나온 값**을 쓰고, ``Match`` 블록 안의 값은 조건부이므로
    블록에 들어가기 전까지만 본다. 반환값은 (값, 발견 횟수).
    """
    key = key.lower()
    found: Optional[str] = None
    count = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        first = line.split()[0]
        token = first.split("=")[0].lower()
        if token == "match":
            break
        if token != key:
            continue
        if "=" in line:
            _, _, value = line.partition("=")
        else:
            parts = line.split(None, 1)
            value = parts[1] if len(parts) > 1 else ""
        value = value.strip().strip('"')
        count += 1
        if found is None:
            found = value.lower()
    return found, count


def evaluate_permit_root_login(value: Optional[str]) -> Tuple[Status, str]:
    """PermitRootLogin 값에 대한 판정."""
    if value is None:
        return (
            Status.WARN,
            "PermitRootLogin 미설정 — OpenSSH 기본값(prohibit-password)에 의존하므로 명시 설정 권장",
        )
    if value in DENY_VALUES:
        return Status.PASS, f"PermitRootLogin {value} — root 원격 로그인 차단"
    if value in RESTRICTED_VALUES:
        return Status.WARN, f"PermitRootLogin {value} — 키 인증 root 로그인은 여전히 허용"
    if value in ALLOW_VALUES:
        return Status.FAIL, f"PermitRootLogin {value} — root 원격 로그인이 허용됨"
    return Status.WARN, f"PermitRootLogin {value} — 알 수 없는 값, 수동 확인 필요"


@register
class RootRemoteLogin(Check):
    """U-01: root 계정 원격 접속 제한."""

    id = "U-01"
    title = "root 계정 원격 접속 제한"
    severity = "상"
    category = "서비스 관리"
    remediation = (
        "sshd_config 에 'PermitRootLogin no' 설정 후 sshd 재시작. "
        "root 작업은 일반 계정 로그인 → sudo 로 수행"
    )

    def run(self, ctx: AuditContext) -> CheckOutcome:
        tried: List[str] = []
        for rel in SSHD_CONFIG_CANDIDATES:
            path = ctx.path(*rel)
            tried.append(str(path))
            try:
                text = read_text(path)
            except FileUnavailable:
                continue
            value, count = parse_sshd_value(text)
            status, reason = evaluate_permit_root_login(value)
            evidence: Dict[str, Any] = {
                "path": str(path),
                "permit_root_login": value,
                "occurrences": count,
            }
            includes = [ln.strip() for ln in text.splitlines() if ln.strip().lower().startswith("include")]
            if includes:
                evidence["include_directives"] = includes[:5]
                evidence["note"] = "Include 로 불러온 파일의 설정은 이 점검에서 읽지 않았습니다"
            return CheckOutcome(status, reason, evidence)

        return CheckOutcome(
            Status.SKIP,
            "sshd 설정 파일을 찾지 못해 판정할 수 없음 (sshd 미설치이거나 접근 권한 없음)",
            {"searched": tried},
        )


def service_checks() -> Iterable[Check]:
    return (RootRemoteLogin(),)
