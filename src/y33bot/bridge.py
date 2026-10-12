"""事件路由与文案渲染（核心业务；PLAN.md §3.3；需求 R1–R12、R19，假设 A1/A4/A6/A7/A8）。

职责边界：本模块**只做**「判断触发规则 + 渲染文本 + 调 gateway/rcon」，
不含文件 IO、不含 WebSocket、不含 RCON 协议细节（那些分别在 mclog / qq / rcon 里）。

必须遵守的文案与规则（验收断言对象）：

- 转发格式 ``[QQ] Steve: 你好``（R8）；进出通知 ``Steve进入游戏`` / ``Steve退出游戏``（R10、A4）。
- 未绑定回复 ``请先使用 /bind <游戏ID> 绑定``（R7）；``/`` 走指令、``#`` 走聊天（R6）。
- 富媒体标记 ``<...>`` 剔除，剔空则不转发（A6）；换行截断为单行并补 ``…``（A7）。
- 回环防护：游戏内聊天以 ``ignored_chat_prefixes``（默认 ``[QQ]`` / ``[→QQ]``）开头直接忽略（A8）。
- ``/status`` 富文本见 ``format_status()``（单服三行 / 多服逐行 + 总计 / 全离线一行，A1）。
- 健康提示只在状态**翻转**时发生一次（R19）。

方法名与签名来自 PLAN.md §3.3，不得修改。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from y33bot.binding import BindingStore
from y33bot.commands.registry import CommandRegistry
from y33bot.config import AppConfig
from y33bot.models import MCGroupMessage, MCLogEvent, ServerStatusReport
from y33bot.qq.gateway import QQGateway
from y33bot.rcon.pool import RconPool
from y33bot.state import StateStore


class Bridge:
    """把「QQ 群消息 / 日志事件 / 健康探测结果」翻译成「RCON 命令 / 群消息文本」。"""

    def __init__(
        self,
        config: AppConfig,
        bindings: BindingStore,
        state: StateStore,
        rcon: RconPool,
        registry: CommandRegistry,
        gateway: QQGateway,
        *,
        clock: Callable[[], float] = time.time,
        logger: logging.Logger | None = None,
    ) -> None:
        """装配四件依赖：绑定表、RCON 池、指令注册表、QQ 网关。"""
        raise NotImplementedError("T7：见 PLAN.md §3.3")

    async def handle_group_message(self, message: MCGroupMessage) -> str | None:
        """处理一条群消息：指令 → 回复文本；``#`` 转发 → 注入 MC；其它 → ``None``（忽略）。"""
        raise NotImplementedError("T7：见 PLAN.md §3.3 / R1、R2、R5–R8")

    async def handle_log_event(self, event: MCLogEvent) -> None:
        """处理一条日志事件：聊天（``#``）/ 进出通知 → 发 QQ 群；回环与普通聊天忽略。"""
        raise NotImplementedError("T7：见 PLAN.md §3.3 / R3、R4、R11、R12")

    async def poll_health(self) -> list[tuple[str, bool]]:
        """探测各服健康状态，返回发生翻转的 ``(server, online)`` 列表（R19）。"""
        raise NotImplementedError("T7：见 PLAN.md §3.3 / R19")

    def format_status(self, report: ServerStatusReport) -> str:
        """把 ``ServerStatusReport`` 渲染成 ``/status`` 回复文本（A1 的单服/多服/离线三种形态）。"""
        raise NotImplementedError("T7：见 PLAN.md §3.3 与 §5 S5-4")
