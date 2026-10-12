"""RCON 离线替身：``FakeRconTransport``（PLAN.md §3.4；CLI ``--dry-run`` 与 CI 专用）。

行为契约：不做任何网络 IO，``command()`` 只把命令按固定前缀打印出来::

    [RCON main] tellraw @a {"text":"[QQ] Steve: 你好"}

这样 ``simulate --dry-run`` 的 stdout 与真实分支**逐行同构**（只少一次真实注入），
CI 与单测因此可以完全离线断言 S2–S4 的输出（PLAN.md §3.4、§5）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class FakeRconTransport:
    """实现 ``rcon.protocol.RconTransport`` 的替身；记录并打印收到的命令。"""

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        *,
        server_name: str = "",
        printer: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        """``server_name`` 只用于打印前缀；``**kwargs`` 吸收与客户端相同的超时参数。"""

        raise NotImplementedError("T4：见 PLAN.md §3.4")

    async def connect(self) -> None:
        """总是立即成功（替身不需要真连接）。"""
        raise NotImplementedError("T4")

    async def command(self, cmd: str) -> str:
        """记录 ``cmd`` 并按 ``[RCON <server>] <cmd>`` 打印，返回空字符串。"""
        raise NotImplementedError("T4")

    async def close(self) -> None:
        """空实现（幂等）。"""
        raise NotImplementedError("T4")

    @property
    def connected(self) -> bool:
        """替身始终视为已连接。"""
        raise NotImplementedError("T4")

    @property
    def commands(self) -> list[str]:
        """已收到的命令列表（便于断言）。"""
        raise NotImplementedError("T4")
