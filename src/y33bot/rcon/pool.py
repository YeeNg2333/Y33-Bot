"""多服 RCON 编排：广播、聚合状态、`/list` 解析（PLAN.md §3.2 / §2.4 / R15 / R29）。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable, Mapping, Sequence

from ..models import CommandResult, PlayerList, ServerStatusReport
from .client import AsyncRconClient
from .protocol import RconError, RconTransport

__all__ = ["RconPool", "parse_list_response", "LIST_COMMAND"]

#: `/status` 依赖的 Vanilla 命令（A15：不含 TPS）
LIST_COMMAND = "/list"

_LIST_RE = re.compile(
    r"There are (?P<online>\d+) of a max of (?P<max>\d+) players online:?(?P<players>.*)",
    re.IGNORECASE,
)


def parse_list_response(raw: str) -> PlayerList:
    """解析 Vanilla `/list` 文本，如 `There are 3 of a max of 20 players online: Steve, Alex`。"""

    text = (raw or "").strip()
    match = _LIST_RE.search(text)
    if match is None:
        raise ValueError(f"无法解析 /list 响应: {raw!r}")
    players = [name.strip() for name in match.group("players").split(",") if name.strip()]
    return PlayerList(
        online=int(match.group("online")),
        max_players=int(match.group("max")),
        players=players,
        raw=text,
    )


class RconPool:
    """一组 MC 服的 RCON 客户端；QQ→MC 方向在这里做全局广播（R29）。"""

    def __init__(
        self,
        servers: Sequence[object],
        passwords: Mapping[str, str],
        *,
        factory: Callable[..., RconTransport] = AsyncRconClient,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger("y33bot.rcon.pool")
        self._order: list[str] = []
        self._servers: dict[str, object] = {}
        self._clients: dict[str, RconTransport] = {}
        for server in servers:
            name = server.name
            if name in self._servers:
                raise ValueError(f"MC 服名称重复: {name}")
            if name not in passwords:
                raise ValueError(f"缺少 MC 服 {name} 的 RCON 密码")
            self._order.append(name)
            self._servers[name] = server
            self._clients[name] = factory(
                host=server.host,
                port=server.port,
                password=passwords[name],
                connect_timeout=server.connect_timeout,
                command_timeout=server.command_timeout,
            )

    # ------------------------------------------------------------------ 生命周期
    def server_names(self) -> list[str]:
        return list(self._order)

    async def start(self) -> None:
        """并发连接全部服；单服连不上只告警，不阻塞启动（PLAN.md §3.6）。"""

        await asyncio.gather(*(self._connect(name) for name in self._order))

    async def _connect(self, name: str) -> None:
        client = self._clients[name]
        try:
            await client.connect()
        except RconError as exc:
            self._logger.warning("[警告] RCON %s 连接失败（服务继续，下次调用自动重连）: %s", name, exc)
        else:
            self._logger.debug("[RCON %s] 已连接", name)

    async def close(self) -> None:
        await asyncio.gather(*(self._safe_close(name) for name in self._order))

    async def _safe_close(self, name: str) -> None:
        try:
            await self._clients[name].close()
        except (RconError, OSError) as exc:  # pragma: no cover - 纯防御
            self._logger.warning("[警告] RCON %s 关闭异常: %s", name, exc)

    # ------------------------------------------------------------------ 命令
    async def query(self, server: str, cmd: str) -> CommandResult:
        """对单条连接执行命令；任何失败都收敛为 `CommandResult(ok=False)`（不抛异常）。"""

        client = self._clients.get(server)
        if client is None:
            return CommandResult(server=server, ok=False, response="", error=f"未知服务器: {server}")
        self._logger.info("[RCON %s] %s", server, cmd)
        try:
            response = await client.command(cmd)
        except RconError as exc:
            self._logger.warning("[警告] RCON %s 命令失败: %s", server, exc)
            return CommandResult(server=server, ok=False, response="", error=str(exc))
        return CommandResult(server=server, ok=True, response=response, error=None)

    async def broadcast(self, cmd: str) -> dict[str, CommandResult]:
        """把同一条命令广播到全部服（R29）。"""

        results = await asyncio.gather(*(self.query(name, cmd) for name in self._order))
        return {result.server: result for result in results}

    async def broadcast_tellraw(self, text: str) -> dict[str, CommandResult]:
        """把一段文本通过 `tellraw @a` 广播到全部在线服。"""

        return await self.broadcast(self.build_tellraw(text))

    @staticmethod
    def build_tellraw(text: str) -> str:
        """构造 `tellraw @a {"text":"..."}`；超 1446 字节时逐字符收缩以保证可发送。"""

        payload = text or ""
        while True:
            command = "tellraw @a " + json.dumps({"text": payload}, ensure_ascii=False, separators=(",", ":"))
            if len(command.encode("utf-8")) <= AsyncRconClient.MAX_PAYLOAD_BYTES or not payload:
                return command
            payload = payload[:-1]

    # ------------------------------------------------------------------ 状态
    async def status(self) -> ServerStatusReport:
        """并发查 `/list` 并聚合；命令失败或响应不可解析的服记为离线。"""

        results = await asyncio.gather(*(self.query(name, LIST_COMMAND) for name in self._order))
        per_server: dict[str, PlayerList | None] = {}
        offline: list[str] = []
        total_online = 0
        for result in results:
            if not result.ok:
                per_server[result.server] = None
                offline.append(result.server)
                continue
            try:
                listing = parse_list_response(result.response)
            except ValueError as exc:
                self._logger.warning("[警告] RCON %s /list 响应无法解析（按离线处理）: %s", result.server, exc)
                per_server[result.server] = None
                offline.append(result.server)
                continue
            per_server[result.server] = listing
            total_online += listing.online
        return ServerStatusReport(per_server=per_server, offline=offline, total_online=total_online)
