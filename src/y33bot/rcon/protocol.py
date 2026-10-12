"""RCON 传输层抽象与异常（PLAN.md §2.4、§3.2）。

``RconTransport`` 是 RCON 能力的唯一抽象（``connect`` / ``command`` / ``close`` / ``connected``）：

- 真实实现：``rcon.client.AsyncRconClient``（Valve 协议，多包响应、并发锁、自动重连）；
- 测试替身：``rcon.fakes.FakeRconTransport``（dry-run / 单测，不发任何网络包）。

异常分层让上层能区分「鉴权失败（配置问题，需人工）」与「暂时连不上（只告警继续跑）」。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class RconError(Exception):
    """RCON 层所有异常的基类。"""


class RconAuthError(RconError):
    """密码错误（LOGIN 响应 id 为 -1）：配置问题，调用方应告警而非重试。"""


class RconConnectError(RconError):
    """建立连接失败（拒绝连接 / DNS / 超时）。"""


class RconDisconnectedError(RconError):
    """连接已被对端关闭；下一次调用会尝试重连（A14：不自动重发当前命令）。"""


class RconTimeoutError(RconError):
    """等待响应超时（``command_timeout`` / ``connect_timeout``）。"""


@runtime_checkable
class RconTransport(Protocol):
    """单台 MC 服上的一条 RCON 通道。"""

    async def connect(self) -> None:
        """建立连接并完成 LOGIN 鉴权；失败抛 ``RconConnectError`` / ``RconAuthError``。"""
        ...

    async def command(self, cmd: str) -> str:
        """执行一条命令并返回完整响应文本（多包响应需拼接；命令体上限 1446 字节）。"""
        ...

    async def close(self) -> None:
        """关闭连接（幂等）。"""
        ...

    @property
    def connected(self) -> bool:
        """当前是否处于已鉴权可用的连接状态。"""
        ...
