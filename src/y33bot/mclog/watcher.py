"""日志增量轮询：字节偏移、轮转重置、残行缓冲（PLAN.md §2.5、§3.2；需求 R24–R26，假设 A10/A20）。

行为契约：

1. **增量读取**：从 ``StateStore`` 里该服的 ``log_offset`` 起 ``seek`` 并读新增字节（R24）；
2. **轮转**：``当前大小 < 持久化偏移`` → 打印
   ``[警告] 日志文件缩小（size=... < offset=...），偏移重置为 0``
   并把偏移重置为 0 重读（R25 / A10）；同时把 ``st_ino`` / ``st_size`` 写进状态便于人工排查；
3. **重启**：``load()`` 拿到持久化偏移，文件比偏移短则从 0 开始（R26）；
4. **残行缓冲**：未以换行结尾的半行留在缓冲区，等下次轮询凑齐再解析（A20）；
5. **编码兜底**：按 ``patterns.encoding`` 读取、``errors="replace"``，坏字节不打断轮询（A20）；
6. **文件缺失**：只 ``[警告]``，下一轮继续尝试（文件出现后从 0 开始，PLAN.md §3.6）。

同步实现，由 ``service`` 用 ``asyncio.to_thread()`` 调用（PLAN.md §2.5）。
"""

from __future__ import annotations

from y33bot.config import LogPatterns, MCServerConfig
from y33bot.models import MCLogEvent
from y33bot.state import StateStore


class LogWatcher:
    """单台 MC 服 ``latest.log`` 的增量轮询器（每服恰好一个实例，§4.5-6）。"""

    def __init__(self, server: MCServerConfig, patterns: LogPatterns, store: StateStore) -> None:
        """``server.log_path`` 为日志文件；偏移与诊断字段读写 ``store.state.servers[name]``。"""
        raise NotImplementedError("T5：见 PLAN.md §2.5")

    def poll_new_events(self) -> list[MCLogEvent]:
        """读取自上次偏移以来的新增完整行，返回解析出的事件列表（同步、无事件循环依赖）。"""
        raise NotImplementedError("T5：见 PLAN.md §2.5 / R24–R26")
