"""RCON 传输层接口与异常（PLAN.md §3.2 / A13）。

只定义抽象：`AsyncRconClient`（真实连接）与 `FakeRconTransport`（离线替身）都实现 `RconTransport`，
日后若要换用第三方库，只需再写一个实现接在同一个协议下。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = [
    "RconError",
    "RconAuthError",
    "RconConnectError",
    "RconDisconnectedError",
    "RconTimeoutError",
    "RconTransport",
]


class RconError(Exception):
    """RCON 层错误基类。"""


class RconAuthError(RconError):
    """密码错误 / 鉴权被拒（响应 id 为 -1）。"""


class RconConnectError(RconError):
    """TCP 连接或鉴权握手失败。"""


class RconDisconnectedError(RconError):
    """连接在进行中中断（PLAN.md A14：不自动重发当前命令）。"""


class RconTimeoutError(RconError):
    """连接或命令超时。"""


@runtime_checkable
class RconTransport(Protocol):
    """一条 RCON 连接。"""

    async def connect(self) -> None:
        """建立连接并完成鉴权；失败抛 `RconError` 子类。"""
        ...

    async def command(self, cmd: str) -> str:
        """执行一条命令并返回完整响应；未连接时先自动重连。"""
        ...

    async def close(self) -> None:
        """关闭连接（幂等）。"""
        ...

    @property
    def connected(self) -> bool:
        """当前是否持有可用连接。"""
        ...
