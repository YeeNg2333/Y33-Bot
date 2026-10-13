"""内置指令：`/status`、`/bind`（PLAN.md §3.2 / §3.4 / R15 / R16 / A2 / A15）。"""

from __future__ import annotations

import logging

from ..binding import BindingError, is_valid_game_id
from ..bridge import format_status
from .registry import CommandContext, CommandRegistry

__all__ = ["BIND_USAGE", "INVALID_GAME_ID_REPLY", "cmd_status", "cmd_bind", "build_registry"]

logger = logging.getLogger("y33bot.commands.builtin")

#: 缺参数时的固定文案（PLAN.md A2）
BIND_USAGE = "用法: /bind <游戏ID>"

#: 游戏 ID 不合规时的固定文案（PLAN.md A2）
INVALID_GAME_ID_REPLY = "游戏ID 不合法"


async def cmd_status(ctx: CommandContext, args: list[str]) -> str:
    """`/status`：查所有服的 `/list`，按 PLAN.md §3.5 的格式回复（不含 TPS，A15）。"""

    report = await ctx.rcon.status()
    return format_status(report)


async def cmd_bind(ctx: CommandContext, args: list[str]) -> str:
    """`/bind <游戏ID>`：覆盖写入绑定表并回复结果（R16 / R20 / A2）。"""

    if not args:
        return BIND_USAGE
    game_id = args[0].strip()
    if not is_valid_game_id(game_id):
        return INVALID_GAME_ID_REPLY
    try:
        ctx.bindings.bind(ctx.message.member_openid, game_id)
        ctx.bindings.save()
    except BindingError as exc:
        ctx.logger.error("[错误] 绑定写入失败: %s", exc)
        return "绑定失败，请查看服务日志"
    ctx.logger.info("[绑定] %s -> %s", ctx.message.member_openid, game_id)
    return f"绑定成功: {game_id}"


def build_registry(registry: CommandRegistry | None = None) -> CommandRegistry:
    """构造内置指令表；`/status` 与 `/bind` 按 PLAN.md §3.4 的签名注册。"""

    reg = registry if registry is not None else CommandRegistry()
    reg.register("status", desc="查询服务器状态")(cmd_status)
    reg.register("bind", desc="绑定 OpenID ↔ 游戏ID")(cmd_bind)
    return reg
