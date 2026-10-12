"""Valve RCON 二进制协议客户端（仅标准库 asyncio；PLAN.md §2.4，假设 A13/A14）。

包格式：``<i 长度> <ii 请求id/类型> <body UTF-8> \\x00\\x00``，类型 3=LOGIN、2=COMMAND、0=RESPONSE。

必须实现的能力（T4 逐条落实，并由 ``tests/test_rcon_client.py`` 的内存假 RCON 服覆盖）：

1. **多包响应**：读完首个 ``RESPONSE(0)`` 后在 ``drain_timeout`` 内继续读后续包并拼接
   （Vanilla 长输出会拆成多个 4KB 包）——这是否决 ``aio-mc-rcon`` 的原因（§2.8）。
2. **并发串行化**：``asyncio.Lock`` 保证同一条连接上「一问一答」配对，多任务并发调用不串包。
3. **命令体上限**：``cmd`` 编码后 > ``MAX_PAYLOAD_BYTES``(1446) 直接拒绝。
4. **自动重连**：断连后**下一次调用时**重连，不重发当前命令（A14）。
5. **鉴权**：LOGIN 响应 id 为 -1 → ``RconAuthError``；超时抛 ``RconTimeoutError``。
"""

from __future__ import annotations


class AsyncRconClient:
    """一条 TCP 连接上的 RCON 客户端（实现 ``rcon.protocol.RconTransport``）。"""

    MAX_PAYLOAD_BYTES = 1446

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        *,
        connect_timeout: float = 5.0,
        command_timeout: float = 5.0,
        drain_timeout: float = 0.1,
    ) -> None:
        """``drain_timeout`` 是「首包之后再等多久收尾包」的时间窗（默认 0.1s）。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4 / A13")

    async def connect(self) -> None:
        """建立 TCP 连接并完成 LOGIN 鉴权。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4")

    async def command(self, cmd: str) -> str:
        """执行一条命令，返回拼接后的完整响应文本。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4")

    async def close(self) -> None:
        """关闭连接（幂等，不抛异常）。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4")

    @property
    def connected(self) -> bool:
        """是否已连接且鉴权通过。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4")
