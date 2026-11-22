"""점검 모듈 묶음.

여기서 하위 모듈을 import 하는 것이 곧 점검 항목 등록이다.
새 모듈을 추가하면 이 파일에도 한 줄 추가한다.
"""

from __future__ import annotations

from .base import Check, all_checks, register, select_checks  # noqa: F401
from . import account  # noqa: F401  (등록 부수효과)
from . import filesystem  # noqa: F401
from . import service  # noqa: F401

__all__ = ["Check", "all_checks", "register", "select_checks"]
