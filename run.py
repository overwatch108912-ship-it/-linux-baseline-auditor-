#!/usr/bin/env python3
"""설치 없이 바로 실행하는 진입점.

    python3 run.py --html report.html

``pip install -e .`` 을 하면 같은 기능을 ``linux-baseline-auditor`` 명령으로
쓸 수 있지만, 처음 받은 사람이 3줄 안에 실행할 수 있도록 이 파일을 둔다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from linux_baseline_auditor.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
