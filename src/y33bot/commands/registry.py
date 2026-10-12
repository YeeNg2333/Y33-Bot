"""指令注册表与上下文（PLAN.md §3.3）。

签名来自 PLAN.md §3.3（``CommandRegistry.register/get/names/dispatch``、``CommandContext``），
不得修改；``CommandSpec`` 是注册项的数据形状（PLAN.md §3.2 只给了名字，字段为实现细节）。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field

from y33bot.binding import BindingStore
from y33bot.config import AppConfig
from y33bot.models import MCGroupMessage
from y33bot.rcon.pool import RconPool
from y33bot.state import StateStore

Handler = Callable[["CommandContext", list[str]], Awaitable[str]]


@dataclass
class CommandContext:
    """一次指令调用能拿到的全部依赖（由 ``bridge`` 装配）。"""

    config: AppConfig
    bindings: BindingStore
    rcon: RconPool
    state: StateStore
    message: MCGroupMessage
    logger: logging.Logger


@dataclass(frozen=True)
class CommandSpec:
    """一条已注册指令：名称、别名、描述与处理函数。"""

    name: str
    handler: Handler
    aliases: tuple[str, ...] = ()
    desc: str = ""


@dataclass
class CommandRegistry:
    """名称 → 指令的注册表；名称与别名共用一张索引。"""

    _specs: dict[str, CommandSpec] = field(default_factory=dict)

    def register(
        self,
        name: str,
        *,
        aliases: Sequence[str] = (),
        desc: str = "",
    ) -> Callable[[Handler], Handler]:
        """装饰器：注册 ``name``（含 ``aliases``）；重复名称覆盖旧项。"""
        raise NotImplementedError("T6：见 PLAN.md §3.3 / R13")

    def get(self, name: str) -> CommandSpec | None:
        """按名称或别名取指令；未知返回 ``None``。"""
        raise NotImplementedError("T6：见 PLAN.md §3.3")

    def names(self) -> list[str]:
        """返回全部指令名（按注册顺序，用于帮助文案与测试）。"""
        raise NotImplementedError("T6：见 PLAN.md §3.3")

    async def dispatch(self, ctx: CommandContext, line: str) -> str:
        """分发一行带前缀的指令文本，返回要回复到群里的文本。

        未注册指令返回固定 ``未知指令``（A3）；触发格式 ``/status``（不带空格，R14）。
        """
        raise NotImplementedError("T6：见 PLAN.md §3.3 / A3")
