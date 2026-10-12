"""日志层：模板编译与增量轮询（PLAN.md §2.5、§3.2；需求 R24–R27，假设 A9/A10/A20）。

``patterns`` 负责「模板 → 正则 → 事件」，``watcher`` 负责「字节偏移 → 新行 → 事件」。
watcher 是**同步**实现（``Path.open`` + ``seek`` + 正则），由 ``service`` 用
``asyncio.to_thread()`` 调度：单测无需事件循环即可覆盖偏移/轮转/半行（PLAN.md §2.5）。
"""

from __future__ import annotations
