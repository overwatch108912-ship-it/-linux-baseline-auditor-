"""계정 관리 점검 (KISA U-04, U-05, U-16, U-18).

모든 점검은 읽기 전용이다. /etc/passwd, /etc/shadow 를 **읽거나 stat** 할 뿐
어떤 파일도 수정하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from ..models import AuditContext, CheckOutcome, Status
from ..sysutil import FileUnavailable, read_text, stat_path
from .base import Check, register

PASSWD_PATH = ("etc", "passwd")
SHADOW_PATH = ("etc", "shadow")

#: 패스워드가 shadow 로 위임되었다는 표시. 이 값이 아니면 /etc/passwd 에
#: 해시나 빈 값이 남아 있다고 본다.
SHADOW_PLACEHOLDERS = frozenset({"x", "*", "!", "!!"})


@dataclass(frozen=True)
class PasswdEntry:
    """/etc/passwd 한 줄을 필드 단위로 나눈 것."""

    name: str
    password: str
    uid: int
    gid: int
    home: str
    shell: str


def parse_passwd(text: str) -> tuple[List[PasswdEntry], int]:
    """passwd 형식 텍스트를 파싱한다.

    반환값은 (정상 항목 목록, 형식이 깨진 줄 수). 주석(#)과 빈 줄은 세지 않는다.
    """
    entries: List[PasswdEntry] = []
    malformed = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(":")
        if len(fields) < 7:
            malformed += 1
            continue
        try:
            uid, gid = int(fields[2]), int(fields[3])
        except ValueError:
            malformed += 1
            continue
        entries.append(
            PasswdEntry(
                name=fields[0],
                password=fields[1],
                uid=uid,
                gid=gid,
                home=fields[5],
                shell=fields[6],
            )
        )
    return entries, malformed


def evaluate_passwd_permissions(mode: int, uid: int) -> tuple[Status, str]:
    """`/etc/passwd` 권한 판정 (KISA U-16: 소유자 root, 권한 644 이하)."""
    perm = mode & 0o777
    if uid != 0:
        return Status.FAIL, f"소유자가 root(0)가 아님 (uid={uid})"
    if perm & ~0o644:
        return Status.FAIL, f"권한 {perm:04o}: 644 이하가 아님 (그룹/기타 쓰기·실행 등)"
    if not perm & 0o400:
        return Status.FAIL, f"권한 {perm:04o}: 소유자 읽기 권한이 없어 비정상"
    if perm != 0o644:
        return Status.PASS, f"권한 {perm:04o}: 644 보다 엄격함(양호)"
    return Status.PASS, "권한 0644, 소유자 root(0) — 기준 충족"


def evaluate_shadow_permissions(mode: int, uid: int) -> tuple[Status, str]:
    """`/etc/shadow` 권한 판정 (KISA: 소유자 root, 권한 400 이하 권장)."""
    perm = mode & 0o777
    if uid != 0:
        return Status.FAIL, f"소유자가 root(0)가 아님 (uid={uid})"
    if perm & 0o007:
        return Status.FAIL, f"권한 {perm:04o}: 기타 사용자 접근 허용"
    if perm & 0o030:
        return Status.FAIL, f"권한 {perm:04o}: 그룹 쓰기/실행 허용"
    if perm & 0o040:
        return Status.WARN, f"권한 {perm:04o}: 그룹 읽기 허용 (0400 권장, root:shadow 구성이면 정책 확인)"
    if not perm & 0o400:
        return Status.WARN, f"권한 {perm:04o}: 소유자 읽기 권한 없음 — 비정상 설정"
    return Status.PASS, f"권한 {perm:04o}, 소유자 root(0) — 기준 충족"


def _missing(path: Any, exc: FileUnavailable) -> CheckOutcome:
    return CheckOutcome(
        Status.SKIP,
        f"{path} 확인 불가: {exc.reason}",
        {"path": str(path), "reason": exc.reason},
    )


@register
class PasswordFileProtected(Check):
    """U-04: 패스워드가 shadow 파일에만 저장되는지."""

    id = "U-04"
    title = "비밀번호 파일 보호 (shadow 사용)"
    severity = "상"
    category = "계정 관리"
    remediation = (
        "/etc/passwd 두 번째 필드를 x 로 두고 실제 해시는 /etc/shadow 에만 저장 "
        "(pwconv 로 동기화). 빈 패스워드 계정은 잠금(passwd -l) 처리"
    )

    def run(self, ctx: AuditContext) -> CheckOutcome:
        passwd_path = ctx.path(*PASSWD_PATH)
        try:
            entries, malformed = parse_passwd(read_text(passwd_path))
        except FileUnavailable as exc:
            return _missing(passwd_path, exc)

        if not entries:
            return CheckOutcome(
                Status.SKIP,
                "계정 항목을 찾지 못해 판정할 수 없음",
                {"path": str(passwd_path), "malformed_lines": malformed},
            )

        exposed = [e.name for e in entries if e.password not in SHADOW_PLACEHOLDERS]
        shadow_exists = ctx.path(*SHADOW_PATH).exists()
        evidence: Dict[str, Any] = {
            "path": str(passwd_path),
            "accounts": len(entries),
            "malformed_lines": malformed,
            "exposed_accounts": exposed[:10],
            "shadow_exists": shadow_exists,
        }

        if exposed:
            shown = ", ".join(exposed[:5])
            more = f" 외 {len(exposed) - 5}개" if len(exposed) > 5 else ""
            return CheckOutcome(
                Status.FAIL,
                f"{len(exposed)}개 계정의 패스워드 필드가 shadow 로 위임되지 않음: {shown}{more}",
                evidence,
            )
        if not shadow_exists:
            return CheckOutcome(
                Status.WARN,
                "/etc/passwd 는 x 표기지만 /etc/shadow 파일이 없음",
                evidence,
            )
        return CheckOutcome(
            Status.PASS,
            f"전체 {len(entries)}개 계정이 shadow 로 위임됨",
            evidence,
        )


@register
class RootUidOnly(Check):
    """U-05: UID 0 계정이 root 하나뿐인지."""

    id = "U-05"
    title = "root 이외의 UID가 '0' 금지"
    severity = "중"
    category = "계정 관리"
    remediation = "UID 0 을 가진 비-root 계정의 UID 를 일반 범위로 변경하거나 계정 삭제"

    def run(self, ctx: AuditContext) -> CheckOutcome:
        passwd_path = ctx.path(*PASSWD_PATH)
        try:
            entries, _ = parse_passwd(read_text(passwd_path))
        except FileUnavailable as exc:
            return _missing(passwd_path, exc)

        if not entries:
            return CheckOutcome(
                Status.SKIP, "계정 항목을 찾지 못해 판정할 수 없음",
                {"path": str(passwd_path)},
            )

        uid_zero = [e.name for e in entries if e.uid == 0]
        extra = [n for n in uid_zero if n != "root"]
        evidence = {
            "path": str(passwd_path),
            "accounts": len(entries),
            "uid0_accounts": uid_zero,
        }
        if extra:
            return CheckOutcome(
                Status.FAIL,
                f"root 외 UID 0 계정 {len(extra)}개: {', '.join(extra)}",
                evidence,
            )
        return CheckOutcome(
            Status.PASS,
            "UID 0 계정은 root 하나뿐" if uid_zero else "UID 0 계정이 없어 위반 아님",
            evidence,
        )


@register
class PasswdPermissions(Check):
    """U-16: /etc/passwd 소유자 및 권한."""

    id = "U-16"
    title = "/etc/passwd 파일 소유자 및 권한 설정"
    severity = "상"
    category = "계정 관리"
    remediation = "chown root:root /etc/passwd && chmod 644 /etc/passwd"

    def run(self, ctx: AuditContext) -> CheckOutcome:
        target = ctx.path(*PASSWD_PATH)
        try:
            st = stat_path(target)
        except FileUnavailable as exc:
            return _missing(target, exc)
        status, reason = evaluate_passwd_permissions(st.mode, st.uid)
        return CheckOutcome(
            status, reason,
            {"path": st.path, "mode": st.mode_octal, "uid": st.uid, "gid": st.gid},
        )


@register
class ShadowPermissions(Check):
    """U-18: /etc/shadow 소유자 및 권한."""

    id = "U-18"
    title = "/etc/shadow 파일 소유자 및 권한 설정"
    severity = "상"
    category = "계정 관리"
    remediation = "chown root:root /etc/shadow && chmod 400 /etc/shadow (정책에 따라 640 허용)"

    def run(self, ctx: AuditContext) -> CheckOutcome:
        target = ctx.path(*SHADOW_PATH)
        try:
            st = stat_path(target)
        except FileUnavailable as exc:
            return _missing(target, exc)
        status, reason = evaluate_shadow_permissions(st.mode, st.uid)
        return CheckOutcome(
            status, reason,
            {"path": st.path, "mode": st.mode_octal, "uid": st.uid, "gid": st.gid},
        )


def account_checks() -> Iterable[Check]:
    """이 모듈이 등록한 점검 목록(테스트·문서용)."""
    return (
        PasswordFileProtected(),
        RootUidOnly(),
        PasswdPermissions(),
        ShadowPermissions(),
    )
