"""运行状态读写：``data/state.json``（PLAN.md §4.3、§4.5；需求 R24、R26）。

持久化内容（一份文件装三类状态）：

- 每服日志**字节偏移** ``log_offset``（R24）+ 诊断用的 ``log_size`` / ``log_inode``（A10）；
- 健康状态 ``health_online`` / ``health_changed_at``：用于“变化时提示一次”（R19）；
- QQ 主动消息的全局递增 ``msg_seq``（A12）。

实现要点：

- ``version != 1`` → 备份为 ``state.json.bak`` 后重置，不静默丢数据（§4.5-4）；
- 写入用「临时文件 + ``os.replace()``」原子替换（§3.6）；
- 每次事件推进后与优雅退出时各写一次（§2.6）。

类名与方法名来自 PLAN.md §3.2；``RuntimeState`` / ``ServerState`` 定义在 ``y33bot.models``。
"""

from __future__ import annotations

from pathlib import Path

from y33bot.models import RuntimeState


class StateError(Exception):
    """状态文件读写失败。"""


class StateStore:
    """``data/state.json`` 的读写门面。

    实现约定：实例属性 ``state: RuntimeState`` 保存当前内存状态，
    ``LogWatcher``（偏移）与 ``Bridge``（健康、``msg_seq``）都通过它读写；
    未实现的辅助方法由 T3 补充（A12 需要“取下一个 msg_seq 并持久化”的能力）。
    """

    def __init__(self, path: Path) -> None:
        """``path`` 为 ``state.json`` 路径；构造时**不**读盘（显式调用 ``load()``）。"""
        raise NotImplementedError("T3：见 PLAN.md §4.3")

    def load(self) -> RuntimeState:
        """读盘并返回内存状态；文件不存在返回默认值，版本不符则备份后重置。"""
        raise NotImplementedError("T3：见 PLAN.md §4.5-4")

    def save(self) -> None:
        """原子写回 ``state.json``（临时文件 + ``os.replace()``）。"""
        raise NotImplementedError("T3：见 PLAN.md §3.6")
