"""指令注册与分发（PLAN.md §3.2 / §3.4 / R13 / R14 / R17 / A3）。

装饰器式注册；`dispatch()` 的输入是「已含前缀的一整行」，例如 `/status 1`。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..models import MCGroupMessage

if TYPE_CHECKING:  # pragma: no cover - 仅类型标注
    from ..binding import BindingStore
    from ..config import AppConfig
    from ..rcon.pool import RconPool
    from ..state import StateStore

__all__ = [
    "UNKNOWN_COMMAND_REPLY",
    "HANDLER_ERROR_REPLY",
    "CommandSpec",
    "CommandContext",
    "Handler",
    "CommandRegistry",
]

#: 未注册指令的固定回复（PLAN.md A3：不加标点、不附帮助）
UNKNOWN_COMMAND_REPLY = "未知指令"

#: 指令处理函数抛异常时的兜底回复（异常本身会带堆栈写进日志，不会被吞掉）
HANDLER_ERROR_REPLY = "指令执行失败"


@dataclass
class CommandContext:
    """一次指令调用的上下文（PLAN.md §3.3）。"""

    config: AppConfig
    bindings: BindingStore
    rcon: RconPool
    state: StateStore
    message: MCGroupMessage
    logger: logging.Logger


Handler = Callable[[CommandContext, list[str]], Awaitable[str]]


@dataclass
class CommandSpec:
    """一条已注册的指令。"""

    name: str
    handler: Handler
    desc: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def matches(self, token: str) -> bool:
        return token == self.name or token in self.aliases


class CommandRegistry:
    """指令表：注册（装饰器）、查询、分发。"""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("y33bot.commands")
        self._specs: dict[str, CommandSpec] = {}

    # ------------------------------------------------------------------ 注册
    def register(self, name: str, *, aliases: Sequence[str] = (), desc: str = "") -> Callable[[Handler], Handler]:
        """装饰器式注册。"""

        if not name or not name.strip():
            raise ValueError("指令名不能为空")
        cleaned = name.strip().lower()

        def decorator(handler: Handler) -> Handler:
            self.add(
                CommandSpec(
                    name=cleaned,
                    handler=handler,
                    desc=desc,
                    aliases=tuple(alias.strip().lower() for alias in aliases if alias and alias.strip()),
                )
            )
            return handler

        return decorator

    def add(self, spec: CommandSpec) -> None:
        """直接登记一条 `CommandSpec`（供 `builtin.build_registry()` 与测试使用）。"""

        if spec.name in self._specs:
            raise ValueError(f"指令重复注册: {spec.name}")
        aliases = tuple(alias for alias in spec.aliases if alias != spec.name)
        self._specs[spec.name] = CommandSpec(name=spec.name, handler=spec.handler, desc=spec.desc, aliases=aliases)

    # ------------------------------------------------------------------ 查询
    def get(self, name: str) -> CommandSpec | None:
        """按名字或别名取指令（大小写不敏感）。"""

        token = (name or "").strip().lower()
        if not token:
            return None
        spec = self._specs.get(token)
        if spec is not None:
            return spec
        for candidate in self._specs.values():
            if token in candidate.aliases:
                return candidate
        return None

    def names(self) -> list[str]:
        """全部已注册指令名（排序，便于 `--help`/测试断言）。"""

        return sorted(self._specs)

    def __len__(self) -> int:
        return len(self._specs)

    # ------------------------------------------------------------------ 分发
    async def dispatch(self, ctx: CommandContext, line: str) -> str:
        """解析并执行一行指令；未知指令返回 `未知指令`（A3）。"""

        prefix = ctx.config.qq.command_prefix
        text = (line or "").strip()
        if not text or not text.startswith(prefix):
            return UNKNOWN_COMMAND_REPLY
        parts = text.split()
        head = parts[0][len(prefix) :]
        spec = self.get(head)
        if spec is None:
            return UNKNOWN_COMMAND_REPLY
        args = parts[1:]
        try:
            return await spec.handler(ctx, args)
        except Exception:  # noqa: BLE001 - 指令异常不能拖垮常驻服务，但必须留痕
            ctx.logger.exception("[错误] 指令 /%s 执行失败", spec.name)
            return HANDLER_ERROR_REPLY
