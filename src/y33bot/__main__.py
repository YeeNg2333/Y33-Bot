"""``python -m y33bot`` 入口（PLAN.md §3.1）。"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":  # pragma: no cover - 进程入口
    sys.exit(main())
