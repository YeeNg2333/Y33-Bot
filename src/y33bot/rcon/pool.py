"""多服 RCON 编排（PLAN.md §2.4、§3.2；需求 R29：QQ→MC 全局广播）。

- ``broadcast_tellraw(text)``：把 ``[QQ] Steve: 你好`` 注入**所有**已连接的 MC 服；
- ``status()``：逐服 ``/list`` 并聚合成 ``ServerStatusReport``（离线的服进 ``offline``，A1）；
- 单服故障只让该服的结果 ``ok=False``，不影响其它服（PLAN.md §3.6）。

注入格式：``tellraw @a {"text":"..."}``，JSON 由 ``json.dumps(..., ensure_ascii=False)`` 生成，
命令整体做 1446 字节上限校验。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from y33bot.config import MCServerConfig
from y33bot.models import CommandResult, PlayerList, ServerStatusReport
from y33bot.rcon.client import AsyncRconClient
from y33bot.rcon.protocol import RconTransport


class RconPool:
    """按「服务器名 → 一条 RCON 连接」编排的多服池。"""

    def __init__(
        self,
        servers: Sequence[MCServerConfig],
        passwords: Mapping[str, str],
        *,
        factory: Callable[..., RconTransport] = AsyncRconClient,
    ) -> None:
        """``factory``：把连接实现换成替身（测试 / ``--dry-run``），形参同 ``AsyncRconClient``。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4")

    async def start(self) -> None:
        """逐服建连；**单服连不上只告警，不阻塞启动**（PLAN.md §3.6）。"""
        raise NotImplementedError("T4：见 PLAN.md §3.6")

    async def close(self) -> None:
        """关闭全部连接（幂等）。"""
        raise NotImplementedError("T4：见 PLAN.md §3.6")

    async def broadcast(self, cmd: str) -> dict[str, CommandResult]:
        """把同一条命令广播到所有服，返回 ``{server: CommandResult}``。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4")

    async def broadcast_tellraw(self, text: str) -> dict[str, CommandResult]:
        """把 ``text`` 用 ``tellraw @a`` 注入所有服（R29）。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4 / R29")

    async def query(self, server: str, cmd: str) -> CommandResult:
        """在指定服执行一条命令。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4")

    async def status(self) -> ServerStatusReport:
        """逐服 ``/list`` 并聚合（A1：离线的服出现在 ``offline`` 中）。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4 / R15")

    def server_names(self) -> list[str]:
        """按配置顺序返回服务器名。"""
        raise NotImplementedError("T4：见 PLAN.md §2.4")


def parse_list_response(text: str) -> PlayerList:
    """解析 ``/list`` 响应，如 ``There are 3 of a max of 20 players online: Steve, Alex``。"""
    raise NotImplementedError("T4：见 PLAN.md §2.4")
