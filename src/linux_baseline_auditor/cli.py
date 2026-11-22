"""명령줄 인터페이스.

    python3 run.py                      # 현재 시스템 전체 점검
    python3 run.py --html report.html   # HTML 리포트까지 저장
    python3 run.py --only U-16 U-18     # 특정 항목만
    python3 run.py --root /mnt/disk     # 다른 파일 시스템 기준으로 점검

종료 코드: 0 = FAIL 없음, 1 = FAIL 있음, 2 = 사용법/실행 오류.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import checks as checks_module
from .checks.filesystem import load_allowlist
from .engine import run_audit
from .models import TOOL_NAME, TOOL_VERSION, AuditContext
from .reporters import render_console, write_html, write_json

EXIT_OK = 0
EXIT_FAIL_FOUND = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linux-baseline-auditor",
        description="리눅스 보안 기준선(KISA UNIX 항목) 읽기 전용 점검기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시:\n"
            "  python3 run.py\n"
            "  python3 run.py --only U-01 U-16 --html report.html\n"
            "  python3 run.py --list-checks\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    parser.add_argument(
        "--root",
        default="/",
        help="점검 대상 루트 디렉터리 (기본: /). 마운트 이미지나 테스트용 트리에 쓸 수 있습니다.",
    )
    parser.add_argument(
        "--scan-path",
        action="append",
        default=None,
        metavar="DIR",
        help="파일 탐색 점검(U-23, U-25)의 대상 디렉터리. 여러 번 지정 가능 (기본: --root 전체)",
    )
    parser.add_argument("--only", nargs="+", metavar="ID", help="지정한 항목만 점검 (예: U-01 U-16)")
    parser.add_argument("--exclude", nargs="+", metavar="ID", help="지정한 항목은 건너뜀")
    parser.add_argument("--list-checks", action="store_true", help="점검 항목 목록만 출력하고 종료")
    parser.add_argument("--json", default="report.json", metavar="PATH", help="JSON 리포트 경로 (기본: report.json)")
    parser.add_argument("--html", default="report.html", metavar="PATH", help="HTML 리포트 경로 (기본: report.html)")
    parser.add_argument("--no-json", action="store_true", help="JSON 리포트를 쓰지 않음")
    parser.add_argument("--no-html", action="store_true", help="HTML 리포트를 쓰지 않음")
    parser.add_argument(
        "--max-entries",
        type=int,
        default=200_000,
        metavar="N",
        help="파일 탐색 시 최대 항목 수 (기본: 200000). 넘으면 부분 점검으로 표시",
    )
    parser.add_argument(
        "--suid-allowlist",
        default=None,
        metavar="FILE",
        help="SUID/SGID 허용 목록 파일(한 줄에 경로 하나). 기본 내장 목록 대신 사용",
    )
    parser.add_argument("--no-color", action="store_true", help="콘솔 색상 사용 안 함")
    parser.add_argument("--quiet", action="store_true", help="콘솔 요약만 출력")
    return parser


def _print_checks() -> None:
    print(f"{TOOL_NAME} v{TOOL_VERSION} — 등록된 점검 항목 {len(checks_module.all_checks())}개\n")
    current = None
    for check in checks_module.all_checks():
        if check.category != current:
            current = check.category
            print(f"[{current}]")
        print(f"  {check.id}  {check.title}  (중요도 {check.severity})")
    print("\n주의: 여기 없는 항목은 아직 구현 전입니다. README 의 4주 로드맵을 참고하세요.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_checks:
        _print_checks()
        return EXIT_OK

    root = Path(args.root).expanduser()
    if not root.exists():
        print(f"오류: --root 경로가 없습니다: {root}", file=sys.stderr)
        return EXIT_ERROR

    try:
        selected = checks_module.select_checks(args.only, args.exclude)
    except KeyError as exc:
        print(f"오류: 등록되지 않은 점검 ID: {exc}", file=sys.stderr)
        print("--list-checks 로 사용 가능한 ID를 확인하세요.", file=sys.stderr)
        return EXIT_ERROR

    if not selected:
        print("오류: 실행할 점검이 없습니다(--only/--exclude 조합 확인)", file=sys.stderr)
        return EXIT_ERROR

    allowlist = AuditContext().suid_allowlist
    if args.suid_allowlist:
        allowlist_path = Path(args.suid_allowlist).expanduser()
        try:
            allowlist = load_allowlist(allowlist_path)
        except OSError as exc:
            print(f"오류: SUID 허용 목록을 읽을 수 없습니다: {exc}", file=sys.stderr)
            return EXIT_ERROR

    scan_paths: List[Path] = [Path(p).expanduser() for p in (args.scan_path or [])]
    missing = [str(p) for p in scan_paths if not p.exists()]
    if missing:
        print(f"오류: --scan-path 경로가 없습니다: {', '.join(missing)}", file=sys.stderr)
        return EXIT_ERROR

    ctx = AuditContext(
        root=root,
        scan_paths=tuple(scan_paths),
        max_entries=max(1, args.max_entries),
        suid_allowlist=frozenset(allowlist),
    )

    report = run_audit(ctx=ctx, selected=selected)
    color = not args.no_color and sys.stdout.isatty()
    print(render_console(report, color=color))

    written: List[str] = []
    try:
        if not args.no_json:
            written.append(str(write_json(report, Path(args.json))))
        if not args.no_html:
            written.append(str(write_html(report, Path(args.html))))
    except OSError as exc:
        print(f"오류: 리포트를 저장하지 못했습니다: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if written and not args.quiet:
        print("리포트 저장: " + ", ".join(written))

    return EXIT_FAIL_FOUND if report.has_fail else EXIT_OK
