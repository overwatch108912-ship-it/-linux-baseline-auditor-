"""테스트 패키지.

점검 코드는 ``src/`` 아래에 있으므로, 테스트가 설치 없이 import 할 수 있도록
여기서 한 번만 ``sys.path`` 를 조정한다. (``python3 -m unittest discover`` 와
``pytest`` 모두 이 파일을 거쳐 간다.)
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
