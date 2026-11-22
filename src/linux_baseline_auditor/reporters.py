"""리포트 출력기: 콘솔, JSON, HTML.

HTML 은 외부 CSS/JS 없이 한 파일로 열리도록 만들고, 모든 외부 문자열은
``html.escape`` 로 이스케이프한다(점검 요약에 파일명 등이 섞여 들어오므로).
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, List

from .models import Report, Status

# ── 콘솔 ────────────────────────────────────────────────────────────────

_ANSI = {
    Status.PASS: "\033[32m",   # 초록
    Status.FAIL: "\033[31m",   # 빨강
    Status.WARN: "\033[33m",   # 노랑
    Status.SKIP: "\033[90m",   # 회색
}
_RESET = "\033[0m"
_BOLD = "\033[1m"


def render_console(report: Report, color: bool = True) -> str:
    """터미널에 바로 찍을 요약 텍스트."""
    def paint(text: str, status: Status | None = None, bold: bool = False) -> str:
        if not color:
            return text
        prefix = ("" if status is None else _ANSI[status]) + (_BOLD if bold else "")
        return f"{prefix}{text}{_RESET}" if prefix else text

    lines: List[str] = []
    lines.append(paint(f"🛡️  {report.to_dict()['tool']['name']} v{report.tool_version}", bold=True))
    stamp = report.generated_at.strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    lines.append(f"대상: {report.target_root}   호스트: {report.hostname}   시각: {stamp}")
    lines.append("")

    for result in report.results:
        head = paint(f"[{result.status.value:<4}]", result.status)
        lines.append(f"{head} {result.check_id} {result.title} ({result.severity})")
        lines.append(f"       {result.summary}")
    lines.append("")

    counts = report.counts
    summary = " · ".join(f"{k} {v}" for k, v in counts.items() if v)
    overall = report.overall
    lines.append("─" * 60)
    lines.append(
        f"{summary}   →  종합: {paint(overall.value + ' (' + overall.label_ko + ')', overall, bold=True)}"
    )
    return "\n".join(lines)


# ── JSON ───────────────────────────────────────────────────────────────

def write_json(report: Report, path: Path) -> Path:
    """리포트를 JSON 으로 저장한다(한글 그대로, 들여쓰기 2칸)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


# ── HTML ───────────────────────────────────────────────────────────────

_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; padding: 32px 24px 64px; background: #f6f7f9; color: #1b1f24;
       font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo",
                    "Noto Sans KR", "Malgun Gothic", sans-serif; line-height: 1.55; }
main { max-width: 1040px; margin: 0 auto; }
header h1 { font-size: 22px; margin: 0 0 6px; }
header .meta { color: #5b6570; font-size: 13px; }
.cards { display: flex; gap: 12px; flex-wrap: wrap; margin: 22px 0 26px; }
.card { flex: 1 1 140px; background: #fff; border-radius: 10px; padding: 14px 16px;
        border: 1px solid #e3e6ea; }
.card .label { font-size: 12px; color: #5b6570; letter-spacing: .02em; }
.card .value { font-size: 26px; font-weight: 700; margin-top: 2px; }
.card.pass .value { color: #1a7f37; }
.card.fail .value { color: #c02424; }
.card.warn .value { color: #9a6700; }
.card.skip .value { color: #6b7280; }
.overall { display: inline-block; padding: 4px 10px; border-radius: 999px;
           font-size: 12px; font-weight: 600; }
.overall.PASS { background: #e6f4ea; color: #1a7f37; }
.overall.FAIL { background: #fde8e8; color: #c02424; }
.overall.WARN { background: #fdf3d7; color: #9a6700; }
.overall.SKIP { background: #eceef1; color: #4b5563; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px;
        overflow: hidden; border: 1px solid #e3e6ea; }
th, td { padding: 10px 12px; text-align: left; font-size: 13px; vertical-align: top;
         border-bottom: 1px solid #eef0f3; }
th { background: #fafbfc; font-size: 12px; color: #5b6570; font-weight: 600; }
tr:last-child td { border-bottom: none; }
td.id { font-variant-numeric: tabular-nums; white-space: nowrap; font-weight: 600; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px;
         font-weight: 700; white-space: nowrap; }
.badge.PASS { background: #e6f4ea; color: #1a7f37; }
.badge.FAIL { background: #fde8e8; color: #c02424; }
.badge.WARN { background: #fdf3d7; color: #9a6700; }
.badge.SKIP { background: #eceef1; color: #4b5563; }
.muted { color: #5b6570; }
details { margin-top: 6px; }
summary { cursor: pointer; font-size: 12px; color: #3b6ea5; }
pre { background: #f6f7f9; border: 1px solid #e3e6ea; border-radius: 8px; padding: 10px;
      font-size: 12px; overflow-x: auto; white-space: pre-wrap; word-break: break-all; }
footer { margin-top: 28px; font-size: 12px; color: #5b6570; }
footer p { margin: 4px 0; }
"""


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def render_html(report: Report) -> str:
    """자체 완결형 HTML 리포트 문자열."""
    counts = report.counts
    overall = report.overall
    rows: List[str] = []
    for r in report.results:
        evidence = html.escape(json.dumps(r.evidence, ensure_ascii=False, indent=2))
        remediation = (
            f'<div class="muted">조치: {_esc(r.remediation)}</div>' if r.remediation else ""
        )
        rows.append(
            f"""<tr>
  <td class="id">{_esc(r.check_id)}</td>
  <td>{_esc(r.title)}<div class="muted">{_esc(r.category)} · 중요도 {_esc(r.severity)}</div></td>
  <td><span class="badge {r.status.value}">{r.status.value}</span>
      <div class="muted">{_esc(r.status.label_ko)}</div></td>
  <td>{_esc(r.summary)}{remediation}
      <details><summary>근거 보기</summary><pre>{evidence}</pre></details></td>
</tr>"""
        )

    stamp = report.generated_at.strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    cards = "".join(
        f'<div class="card {name.lower()}"><div class="label">{name}</div>'
        f'<div class="value">{counts[name]}</div></div>'
        for name in ("PASS", "FAIL", "WARN", "SKIP")
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>리눅스 보안 기준선 점검 리포트 — {_esc(report.hostname)}</title>
<style>{_CSS}</style>
</head>
<body>
<main>
  <header>
    <h1>🛡️ 리눅스 보안 기준선 점검 리포트</h1>
    <div class="meta">
      호스트 {_esc(report.hostname)} · 대상 {_esc(report.target_root)} · {_esc(stamp)} ·
      점검 항목 {len(report.results)}개 ·
      <span class="overall {overall.value}">종합 {overall.value} ({overall.label_ko})</span>
    </div>
  </header>

  <section class="cards">{cards}</section>

  <table>
    <thead>
      <tr><th>코드</th><th>점검 항목</th><th>판정</th><th>결과 요약</th></tr>
    </thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
  </table>

  <footer>
    <p>이 리포트는 읽기 전용 점검 결과입니다. 항목 코드·기준은 KISA 「주요정보통신기반시설 기술적 취약점 분석·평가 방법 상세가이드」의 UNIX 항목을 참고했습니다.</p>
    <p>허가받은 시스템에서만 실행하세요. FAIL 은 곧 침해를 뜻하지 않으며, 최종 판단은 운영 정책과 함께 사람이 합니다.</p>
    <p>linux-baseline-auditor v{_esc(report.tool_version)} · 생성 {_esc(stamp)}</p>
  </footer>
</main>
</body>
</html>
"""


def write_html(report: Report, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(report), encoding="utf-8")
    return path


def summarize_counts(report: Report) -> Dict[str, int]:
    """요약 숫자만 필요할 때(테스트·CLI 메시지)."""
    return report.counts
