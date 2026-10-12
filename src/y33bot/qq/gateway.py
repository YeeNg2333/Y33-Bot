"""QQ 接入层：网关协议与官方 SDK 适配（PLAN.md §2.3、§3.2；需求 R1、R2、R23，假设 A5/A12）。

- ``QQGateway`` 是唯一抽象：``start`` / ``send_group_message`` / ``close``（协议签名冻结）。
- ``BotpyGateway`` 用 ``qq-botpy``（腾讯官方 SDK）：``on_group_at_message_create`` 收事件，
  ``post_group_message`` 发消息；被动回复带 ``msg_id``（5 分钟窗口），主动消息不带 ``msg_id``
  且 ``msg_seq`` 全局递增（A12）。
- 网关只负责「收发 + 事件转换」，不看业务规则（触发/文案都在 ``bridge`` 里）。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from y33bot.config import AppConfig
from y33bot.models import MCGroupMessage, OutgoingGroupMessage


@runtime_checkable
class QQGateway(Protocol):
    """QQ 群消息通道（真实实现或离线替身）。"""

    async def start(self) -> None:
        """建立网关连接并开始派发事件；失败抛异常（由 ``service`` 决定是否致命）。"""
        ...

    async def send_group_message(self, message: OutgoingGroupMessage) -> None:
        """发一条群消息；失败只记日志、不重试（N7 / A12）。"""
        ...

    async def close(self) -> None:
        """关闭网关（幂等）。"""
        ...


class BotpyGateway:
    """基于 ``qq-botpy`` 的 ``QQGateway`` 实现。

    构造函数形参属**实现细节**：PLAN.md 只冻结 ``QQGateway`` 协议，
    T7 可按 ``service.Service`` 的装配需要调整（例如携带 event loop 或 logger）。
    """

    def __init__(
        self,
        config: AppConfig,
        on_group_message: Callable[[MCGroupMessage], Awaitable[None]],
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        """``on_group_message`` 由 ``service`` 注入（内部转交 ``Bridge.handle_group_message``）。"""
        raise NotImplementedError("T7：见 PLAN.md §2.3")

    async def start(self) -> None:
        """``client.start(appid, secret, ret_coro=True)`` 并登记 ``on_group_at_message_create``。"""
        raise NotImplementedError("T7：见 PLAN.md §2.3")

    async def send_group_message(self, message: OutgoingGroupMessage) -> None:
        """``api.post_group_message(...)``；被动回复带 ``msg_id``、主动消息带递增 ``msg_seq``。"""
        raise NotImplementedError("T7：见 PLAN.md §2.3 / A12")

    async def close(self) -> None:
        """``await client.close()``（幂等）。"""
        raise NotImplementedError("T7：见 PLAN.md §2.3")
