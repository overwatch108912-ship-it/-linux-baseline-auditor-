"""점검 항목의 공통 뼈대와 등록소(registry).

새 점검을 추가하는 방법::

    @register
    class MyCheck(Check):
        id = "U-99"
        title = "새 점검 항목"
        severity = "중"
        category = "계정 관리"
        remediation = "조치 방법"
        def run(self, ctx):
            return CheckOutcome(Status.PASS, "이유", {...})

``checks/__init__.py`` 가 모듈을 import 하는 순간 등록되므로, 추가 작업은 없다.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Type

from ..models import AuditContext, CheckOutcome


class Check:
    """점검 항목 하나. 하위 클래스가 메타데이터와 ``run`` 을 채운다."""

    id: str = ""
    title: str = ""
    severity: str = "중"
    category: str = "기타"
    remediation: str = ""

    def run(self, ctx: AuditContext) -> CheckOutcome:  # pragma: no cover - 추상
        raise NotImplementedError

    def __repr__(self) -> str:  # 디버깅용
        return f"<{type(self).__name__} {self.id}>"


_REGISTRY: Dict[str, Check] = {}


def register(cls: Type[Check]) -> Type[Check]:
    """점검 클래스를 등록한다. 같은 ID 를 두 번 등록하면 오류로 알린다."""
    instance = cls()
    if not instance.id:
        raise ValueError(f"{cls.__name__}: 점검 ID가 비어 있습니다")
    if instance.id in _REGISTRY:
        raise ValueError(f"점검 ID 중복: {instance.id}")
    _REGISTRY[instance.id] = instance
    return cls


def all_checks() -> List[Check]:
    """등록 순서(계정 → 파일 → 서비스)대로 점검 목록을 돌려준다."""
    return list(_REGISTRY.values())


def select_checks(
    only: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> List[Check]:
    """``--only`` / ``--exclude`` 로 점검을 골라 낸다(ID는 대소문자 무시)."""
    checks = all_checks()
    if only:
        wanted = {i.strip().upper() for i in only if i.strip()}
        unknown = wanted - {c.id.upper() for c in checks}
        if unknown:
            raise KeyError(", ".join(sorted(unknown)))
        checks = [c for c in checks if c.id.upper() in wanted]
    if exclude:
        banned = {i.strip().upper() for i in exclude if i.strip()}
        checks = [c for c in checks if c.id.upper() not in banned]
    return checks
