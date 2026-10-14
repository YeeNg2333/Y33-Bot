"""QQ 离线替身（PLAN.md §3.2 / §3.4）。

`simulate` 与单元测试用它替代 `BotpyGateway`：绝不连 QQ，只把消息记在内存里，
并按 CLI 契约打印 `[群消息] ` 行。
"""

from __future__ import annotations

import asyncio
import logging

from ..models import OutgoingGroupMessage

__all__ = ["FakeQQGateway"]


class FakeQQGateway:
    """与 `QQGateway` 同签名的假实现。"""

    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        self.sent: list[OutgoingGroupMessage] = []
        self.started = False
        self._closed = asyncio.Event()
        self._logger = logger or logging.getLogger("y33bot.qq.fakes")

    async def start(self) -> None:
        self.started = True
        self._closed.clear()

    async def send_group_message(self, message: OutgoingGroupMessage) -> None:
        self.sent.append(message)
        self._logger.info("[群消息] %s", message.text)

    async def close(self) -> None:
        self.started = False
        self._closed.set()

    async def wait_closed(self) -> None:
        """假网关不会自己断线：等到 `close()` 为止（`Service.run()` 用它监视网关）。"""

        await self._closed.wait()

    # ------------------------------------------------------------ 测试辅助
    def messages(self) -> list[str]:
        return [item.text for item in self.sent]

    def last(self) -> OutgoingGroupMessage | None:
        return self.sent[-1] if self.sent else None

    def clear(self) -> None:
        self.sent.clear()
