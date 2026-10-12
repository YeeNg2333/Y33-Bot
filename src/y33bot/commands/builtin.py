"""内置指令：``/status`` 与 ``/bind``（PLAN.md §3.2、§3.3；需求 R15、R16，假设 A2/A15）。

- ``/status``：RCON ``/list`` → 在线人数 + 在线玩家（不含 TPS，A15），文案由
  ``Bridge.format_status()`` 渲染（A1）；
- ``/bind <游戏ID>``：写绑定表（覆盖语义）→ 回 ``绑定成功: <游戏ID>``；
  缺参数回 ``用法: /bind <游戏ID>``，ID 不满足 ``^[A-Za-z0-9_]{3,16}$`` 回 ``游戏ID 不合法``（A2）；
- ``build_registry()`` 装配上面两条（``service`` 调用一次）。
"""

from __future__ import annotations

from y33bot.commands.registry import CommandContext, CommandRegistry


async def cmd_status(ctx: CommandContext, args: list[str]) -> str:
    """``/status``：查在线人数与玩家列表（来源 RCON ``/list``，R15）。"""
    raise NotImplementedError("T6：见 PLAN.md §3.2 / R15")


async def cmd_bind(ctx: CommandContext, args: list[str]) -> str:
    """``/bind <游戏ID>``：覆盖写入绑定表并回复结果（R16、A2）。"""
    raise NotImplementedError("T6：见 PLAN.md §3.2 / R16")


def build_registry() -> CommandRegistry:
    """构造并返回注册好内置指令的注册表（``/status``、``/bind``）。"""
    raise NotImplementedError("T6：见 PLAN.md §3.2")
