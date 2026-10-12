"""RCON 离线替身（PLAN.md §3.2 / §3.4）。

`--dry-run` 与单元测试用它替代 `AsyncRconClient`：只返回内存里的假响应，不做任何网络 IO。
命令回显由 `RconPool.query()` 统一打印（`[RCON <server>] <命令>`），因此这里不重复打印。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from ..models import PlayerList
from .client import AsyncRconClient
from .protocol import RconConnectError, RconError

__all__ = ["FakeRconTransport", "DEFAULT_LIST_RESPONSE"]

DEFAULT_LIST_RESPONSE = "There are 0 of a max of 20 players online:"


class FakeRconTransport:
    """与 `RconTransport` 同签名的假实现；`online=False` 模拟服务器离线。"""

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        *,
        connect_timeout: float = 5.0,
        command_timeout: float = 5.0,
        online: bool = True,
        responses: Mapping[str, str] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.connect_timeout = connect_timeout
        self.command_timeout = command_timeout
        self.online = online
        self.responses: dict[str, str] = dict(responses or {})
        self.commands: list[str] = []
        self._logger = logger or logging.getLogger("y33bot.rcon.fakes")
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        if not self.online:
            raise RconConnectError(f"假 RCON 服务器离线: {self.host}:{self.port}")
        self._connected = True

    async def command(self, cmd: str) -> str:
        if not self._connected:
            await self.connect()
        payload_len = len((cmd or "").encode("utf-8"))
        if payload_len > AsyncRconClient.MAX_PAYLOAD_BYTES:
            raise RconError(f"命令超过 {AsyncRconClient.MAX_PAYLOAD_BYTES} 字节上限（实际 {payload_len} 字节）")
        self.commands.append(cmd)
        if cmd in self.responses:
            return self.responses[cmd]
        if cmd.strip().lstrip("/").lower() == "list":
            return DEFAULT_LIST_RESPONSE
        return ""

    async def close(self) -> None:
        self._connected = False

    # ------------------------------------------------------------ 测试辅助
    def set_players(self, players: list[str], max_players: int = 20) -> PlayerList:
        """把 `/list` 响应设为给定玩家列表，返回期望的解析结果。"""

        listing = "There are {} of a max of {} players online: {}".format(
            len(players),
            max_players,
            ", ".join(players),
        )
        self.responses["/list"] = listing
        return PlayerList(
            online=len(players),
            max_players=max_players,
            players=list(players),
            raw=listing,
        )
