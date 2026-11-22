"""파일을 안전하게 읽고 정보를 얻는 도우미.

점검기는 **읽기 전용**이다. 이 모듈에는 쓰기·삭제·권한 변경 함수를 두지 않는다.
파일이 없거나 권한이 없으면 예외 대신 ``FileUnavailable`` 로 알려 주고,
각 점검이 그것을 SKIP 판정으로 바꾼다.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

#: 한 번에 읽는 최대 크기(1 MiB). 로그·설정 파일 점검에 충분하고,
#: 실수로 거대한 파일을 통째로 메모리에 올리지 않는다.
MAX_READ_BYTES = 1024 * 1024


class FileUnavailable(Exception):
    """파일이 없거나 읽을 수 없을 때. ``reason`` 에 사람이 읽을 사유를 담는다."""

    def __init__(self, path: os.PathLike[str] | str, reason: str) -> None:
        self.path = str(path)
        self.reason = reason
        super().__init__(f"{self.path}: {reason}")


def read_text(path: Path, limit: int = MAX_READ_BYTES) -> str:
    """텍스트 파일을 읽는다. 실패하면 ``FileUnavailable`` 을 던진다."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(limit + 1)
    except FileNotFoundError:
        raise FileUnavailable(path, "파일 없음") from None
    except IsADirectoryError:
        raise FileUnavailable(path, "디렉터리임") from None
    except PermissionError:
        raise FileUnavailable(path, "읽기 권한 없음") from None
    except OSError as exc:
        raise FileUnavailable(path, f"읽기 실패({exc.strerror or exc})") from None
    return raw[:limit].decode("utf-8", errors="replace")


@dataclass(frozen=True)
class FileStat:
    """점검에 필요한 최소한의 파일 정보."""

    path: str
    mode: int   # 권한 비트만 (예: 0o644)
    uid: int
    gid: int
    size: int

    @property
    def mode_octal(self) -> str:
        return f"{self.mode:04o}"


def stat_path(path: Path) -> FileStat:
    """파일 정보를 얻는다(내용은 읽지 않는다). 실패하면 ``FileUnavailable``."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        raise FileUnavailable(path, "파일 없음") from None
    except PermissionError:
        raise FileUnavailable(path, "접근 권한 없음") from None
    except OSError as exc:
        raise FileUnavailable(path, f"stat 실패({exc.strerror or exc})") from None
    return FileStat(
        path=str(path),
        mode=stat.S_IMODE(st.st_mode),
        uid=st.st_uid,
        gid=st.st_gid,
        size=st.st_size,
    )


def is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except OSError:
        return False
