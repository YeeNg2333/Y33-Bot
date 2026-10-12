"""``python -m y33bot`` 入口：转交 ``y33bot.cli.main``（PLAN.md §2.7）。"""

from __future__ import annotations

import sys

from y33bot.cli import main

if __name__ == "__main__":
    sys.exit(main())
