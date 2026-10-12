"""QQ 离线替身：``FakeQQGateway``（PLAN.md §3.4；CLI ``simulate`` 与 CI 专用）。

契约：**绝不连 QQ**。发送内容按 ``[群消息] <文本>`` 打印并存入 ``sent`` 列表，
供 ``simulate`` 的 stdout 与单测断言使用（PLAN.md §3.4）。
"""

from __future__ import annotations

from collections.abc import Callable

from y33bot.models import OutgoingGroupMessage


class FakeQQGateway:
    """实现 ``qq.gateway.QQGateway`` 的替身。"""

    def __init__(self, *, printer: Callable[[str], None] | None = None) -> None:
        """``printer`` 缺省用 ``print``；测试可注入收集器。"""
        raise NotImplementedError("T7：见 PLAN.md §3.4")

    @property
    def sent(self) -> list[OutgoingGroupMessage]:
        """已“发送”的消息（按发生顺序）。"""
        raise NotImplementedError("T7")

    async def start(self) -> None:
        """空实现（替身不需要连接）。"""
        raise NotImplementedError("T7")

    async def send_group_message(self, message: OutgoingGroupMessage) -> None:
        """打印 ``[群消息] <text>`` 并记录到 ``sent``。"""
        raise NotImplementedError("T7")

    async def close(self) -> None:
        """空实现（幂等）。"""
        raise NotImplementedError("T7")
