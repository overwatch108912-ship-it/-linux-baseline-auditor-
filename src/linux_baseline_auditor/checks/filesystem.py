"""파일 및 디렉터리 점검 (KISA U-23, U-25).

두 점검 모두 파일 시스템을 **걷기만** 한다(읽기 전용). 목록을 얻기 위해
``os.scandir`` 을 쓰고, 심볼릭 링크는 따라가지 않아 순환을 피한다.
기본 대상은 ``--root`` 아래 전체이며 ``--scan-path`` 로 좁힐 수 있다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence

from ..models import AuditContext, CheckOutcome, Status
from .base import Check, register

#: root 가 "/" 일 때 걷지 않는 가상 파일 시스템. 여기서 나오는 파일은
#: 디스크 상의 실제 설정 파일이 아니므로 오탐의 원인이 된다.
PSEUDO_FS = ("proc", "sys", "dev", "run")

#: 배포판 공통으로 존재하는 정당한 SUID/SGID 실행 파일(예시 목록).
#: 환경마다 다르므로 ``--suid-allowlist`` 로 자기 시스템 기준 목록을 넘기는 것이 정확하다.
DEFAULT_SUID_ALLOWLIST = frozenset(
    {
        "/usr/bin/passwd",
        "/usr/bin/sudo",
        "/usr/bin/su",
        "/bin/su",
        "/usr/bin/chsh",
        "/usr/bin/chfn",
        "/usr/bin/gpasswd",
        "/usr/bin/newgrp",
        "/usr/bin/mount",
        "/usr/bin/umount",
        "/usr/bin/pkexec",
        "/usr/bin/fusermount",
        "/usr/bin/fusermount3",
        "/usr/bin/at",
        "/usr/bin/wall",
        "/usr/bin/write",
        "/usr/bin/crontab",
        "/usr/sbin/unix_chkpwd",
        "/usr/lib/openssh/ssh-keysign",
        "/usr/lib/dbus-1.0/dbus-daemon-launch-helper",
        "/usr/lib/policykit-1/polkit-agent-helper-1",
        "/usr/libexec/polkit-agent-helper-1",
    }
)


@dataclass
class ScanOutcome:
    """파일 시스템 걷기 결과."""

    entries: List[tuple[str, int, bool]] = field(default_factory=list)  # (경로, 모드, 디렉터리 여부)
    visited: int = 0
    unreadable_dirs: List[str] = field(default_factory=list)
    truncated: bool = False


def scan_modes(
    paths: Sequence[Path],
    want: Callable[[int, bool], bool],
    max_entries: int,
    skip: Sequence[str] = (),
) -> ScanOutcome:
    """``paths`` 아래를 걸으며 ``want(mode, is_dir)`` 가 참인 항목을 모은다."""
    outcome = ScanOutcome()
    skip_prefixes = tuple(os.path.normpath(s) for s in skip)
    stack = [Path(p) for p in paths]

    while stack:
        current = stack.pop()
        if _is_skipped(current, skip_prefixes):
            continue
        try:
            with os.scandir(current) as it:
                for entry in it:
                    outcome.visited += 1
                    if outcome.visited > max_entries:
                        outcome.truncated = True
                        return outcome
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    is_dir = entry.is_dir(follow_symlinks=False)
                    mode = st.st_mode & 0o7777
                    if want(mode, is_dir):
                        outcome.entries.append((os.path.normpath(entry.path), mode, is_dir))
                    if is_dir and not entry.is_symlink():
                        stack.append(Path(entry.path))
        except (PermissionError, OSError):
            outcome.unreadable_dirs.append(os.path.normpath(str(current)))
    return outcome


def _is_skipped(path: Path, prefixes: Sequence[str]) -> bool:
    normalized = os.path.normpath(str(path))
    return any(normalized == p or normalized.startswith(p + os.sep) for p in prefixes)


def _skip_list(root: Path) -> List[str]:
    """가상 파일 시스템 경로 목록(대상 root 기준)."""
    if os.path.normpath(str(root)) == os.path.normpath(os.sep):
        return [os.path.join(os.sep, name) for name in PSEUDO_FS]
    return []


def _scan_note(outcome: ScanOutcome) -> Dict[str, Any]:
    note: Dict[str, Any] = {"entries_visited": outcome.visited}
    if outcome.truncated:
        note["truncated"] = True
    if outcome.unreadable_dirs:
        note["unreadable_dirs"] = outcome.unreadable_dirs[:5]
        note["unreadable_dir_count"] = len(outcome.unreadable_dirs)
    return note


@register
class SuidSgidFiles(Check):
    """U-23: SUID/SGID/Sticky bit 이 설정된 파일 점검."""

    id = "U-23"
    title = "SUID, SGID, Sticky bit 설정 파일 점검"
    severity = "상"
    category = "파일 및 디렉터리 관리"
    remediation = (
        "허용 목록에 없는 SUID/SGID 파일은 출처를 확인한 뒤 "
        "chmod u-s,g-s 로 비트 제거(운영체제 기본 파일은 건드리지 말 것)"
    )

    def run(self, ctx: AuditContext) -> CheckOutcome:
        skip = _skip_list(ctx.root)
        outcome = scan_modes(
            ctx.effective_scan_paths,
            want=lambda mode, is_dir: bool(mode & 0o6000),
            max_entries=ctx.max_entries,
            skip=skip,
        )
        allowlist = {os.path.normpath(p) for p in ctx.suid_allowlist} or {
            os.path.normpath(p) for p in DEFAULT_SUID_ALLOWLIST
        }
        unknown = [(p, m) for p, m, _ in outcome.entries if p not in allowlist]
        evidence = {
            "total_found": len(outcome.entries),
            "unexpected_count": len(unknown),
            "unexpected": [{"path": p, "mode": f"{m:04o}"} for p, m in unknown[:10]],
            "allowlist_size": len(allowlist),
            **_scan_note(outcome),
        }

        if not outcome.entries:
            if outcome.truncated or outcome.unreadable_dirs:
                return CheckOutcome(
                    Status.WARN,
                    "일부 경로를 읽지 못해 SUID/SGID 파일을 확정할 수 없음",
                    evidence,
                )
            return CheckOutcome(Status.PASS, "SUID/SGID 설정 파일이 발견되지 않음", evidence)

        if unknown:
            shown = ", ".join(p for p, _ in unknown[:3])
            more = f" 외 {len(unknown) - 3}건" if len(unknown) > 3 else ""
            return CheckOutcome(
                Status.WARN,
                f"허용 목록 밖 SUID/SGID 파일 {len(unknown)}건: {shown}{more}",
                evidence,
            )
        return CheckOutcome(
            Status.PASS,
            f"SUID/SGID 파일 {len(outcome.entries)}건 모두 허용 목록 내",
            evidence,
        )


@register
class WorldWritable(Check):
    """U-25: world writable 파일 점검."""

    id = "U-25"
    title = "world writable 파일 점검"
    severity = "상"
    category = "파일 및 디렉터리 관리"
    remediation = (
        "용도가 불명한 world writable 파일·디렉터리는 chmod o-w 로 제거. "
        "공용 디렉터리는 sticky bit(chmod +t)를 함께 설정"
    )

    def run(self, ctx: AuditContext) -> CheckOutcome:
        skip = _skip_list(ctx.root)
        outcome = scan_modes(
            ctx.effective_scan_paths,
            want=lambda mode, is_dir: bool(mode & 0o002),
            max_entries=ctx.max_entries,
            skip=skip,
        )
        risky: List[tuple[str, int, bool]] = []
        sticky_dirs = 0
        for path, mode, is_dir in outcome.entries:
            if is_dir and mode & 0o1000:  # sticky bit → /tmp 처럼 정상적인 공용 디렉터리
                sticky_dirs += 1
                continue
            risky.append((path, mode, is_dir))

        evidence = {
            "world_writable_total": len(outcome.entries),
            "risky_count": len(risky),
            "risky": [
                {"path": p, "mode": f"{m:04o}", "type": "dir" if d else "file"}
                for p, m, d in risky[:10]
            ],
            "sticky_dirs_ignored": sticky_dirs,
            **_scan_note(outcome),
        }

        if risky:
            shown = ", ".join(p for p, _, _ in risky[:3])
            more = f" 외 {len(risky) - 3}건" if len(risky) > 3 else ""
            return CheckOutcome(
                Status.FAIL,
                f"sticky bit 없는 world writable 항목 {len(risky)}건: {shown}{more}",
                evidence,
            )
        if outcome.truncated or outcome.unreadable_dirs:
            return CheckOutcome(
                Status.WARN,
                "일부 경로를 읽지 못해 world writable 파일을 확정할 수 없음",
                evidence,
            )
        return CheckOutcome(
            Status.PASS,
            f"위험한 world writable 항목 없음 (sticky 공용 디렉터리 {sticky_dirs}건은 정상)",
            evidence,
        )


def load_allowlist(path: Path) -> frozenset[str]:
    """허용 목록 파일(한 줄에 경로 하나, # 주석)을 읽는다."""
    items: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            items.append(line)
    return frozenset(items)


def filesystem_checks() -> Iterable[Check]:
    return (SuidSgidFiles(), WorldWritable())
