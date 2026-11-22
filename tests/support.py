"""테스트용 가짜 /etc 트리 만들기.

실제 /etc 를 건드리지 않도록 임시 디렉터리에 최소한의 파일만 만든다.
"""

from __future__ import annotations

import os
from pathlib import Path

from linux_baseline_auditor.models import AuditContext

PASSWD_SAMPLE = """root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
audituser:x:1000:1000::/home/audituser:/bin/bash
"""

SHADOW_SAMPLE = """root:*:19000:0:99999:7:::
daemon:*:19000:0:99999:7:::
audituser:$6$fakehash$abcdefghijklmnop:19000:0:99999:7:::
"""

SSHD_DENY = """# 테스트용 sshd_config
PermitRootLogin no
PasswordAuthentication yes
"""

SSHD_ALLOW = """Port 22
PermitRootLogin yes
"""


def chmod(path: Path, mode: int) -> Path:
    os.chmod(path, mode)
    return path


def make_root(
    base: Path,
    *,
    passwd: str | None = PASSWD_SAMPLE,
    shadow: bool = True,
    passwd_mode: int = 0o644,
    shadow_mode: int = 0o400,
    sshd: str | None = SSHD_DENY,
    extra_dirs: tuple[str, ...] = (),
) -> Path:
    """임시 디렉터리에 etc/passwd, etc/shadow, etc/ssh/sshd_config 를 만든다.

    ``None`` 을 주면 해당 파일을 만들지 않는다(파일 없음 → SKIP 시나리오).
    ``shadow=False`` 는 shadow 파일 없음, ``sshd=None`` 은 sshd 설정 없음.
    """
    etc = base / "etc"
    etc.mkdir(parents=True, exist_ok=True)

    if passwd is not None:
        (etc / "passwd").write_text(passwd, encoding="utf-8")
        chmod(etc / "passwd", passwd_mode)

    if shadow:
        (etc / "shadow").write_text(SHADOW_SAMPLE, encoding="utf-8")
        chmod(etc / "shadow", shadow_mode)

    if sshd is not None:
        ssh = etc / "ssh"
        ssh.mkdir(parents=True, exist_ok=True)
        (ssh / "sshd_config").write_text(sshd, encoding="utf-8")

    for name in extra_dirs:
        (base / name).mkdir(parents=True, exist_ok=True)

    return base


def context(root: Path, **kwargs) -> AuditContext:
    """테스트용 AuditContext. 기본은 root 아래만 탐색."""
    options = {"root": root, "scan_paths": (root,), "max_entries": 5000}
    options.update(kwargs)
    return AuditContext(**options)
