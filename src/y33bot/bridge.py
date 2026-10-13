"""事件路由与文案渲染：本项目的核心业务（PLAN.md §3.2 / §3.3 / §3.5）。

覆盖 R1–R12、R18、R19、R28 与假设 A1/A4/A6/A7/A8。

事件流向：
    QQ 群消息 ──(handle_group_message)──► 指令表 或 RCON tellraw
    MC 日志事件 ─(handle_log_event)────► QQ 群 / RCON 回显
    健康轮询 ───(poll_health)─────────► 状态翻转时发一次通知
"""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING

from .models import MCGroupMessage, MCLogEvent, OutgoingGroupMessage, ServerStatusReport

if TYPE_CHECKING:  # pragma: no cover - 仅类型标注
    from collections.abc import Callable

    from .binding import BindingStore
    from .commands.registry import CommandContext, CommandRegistry
    from .config import AppConfig
    from .qq.gateway import QQGateway
    from .rcon.pool import RconPool
    from .state import StateStore

__all__ = ["Bridge", "format_status", "UNBOUND_REPLY", "MEDIA_MARKER_RE"]

#: 未绑定用户发 `#` 消息时的固定回复（PLAN.md R7）
UNBOUND_REPLY = "请先使用 /bind <游戏ID> 绑定"

#: QQ 富媒体标记（PLAN.md A6）
MEDIA_MARKER_RE = re.compile(r"<[^<>]*>")

#: 全部离线时的固定文案（PLAN.md A1 / IDEA §3.5）
ALL_OFFLINE_REPLY = "[服务器状态] 服务器离线"

_EMPTY_PLAYERS = "无"


def format_status(report: ServerStatusReport) -> str:
    """渲染 `/status` 回复文本（PLAN.md §3.5 三行格式 + A1 多服/离线规则）。"""

    names = list(report.per_server)
    if not names or all(report.per_server[name] is None for name in names):
        return ALL_OFFLINE_REPLY

    if len(names) == 1:
        listing = report.per_server[names[0]]
        if listing is None:  # pragma: no cover - 上面已经排除了全离线
            return ALL_OFFLINE_REPLY
        players = ", ".join(listing.players) if listing.players else _EMPTY_PLAYERS
        return "\n".join(
            [
                "[服务器状态]",
                f"在线: {listing.online}/{listing.max_players}",
                f"玩家: {players}",
            ]
        )

    lines = ["[服务器状态]"]
    for name in names:
        listing = report.per_server[name]
        if listing is None:
            lines.append(f"{name}: 离线")
            continue
        players = ", ".join(listing.players) if listing.players else _EMPTY_PLAYERS
        lines.append(f"{name}: 在线 {listing.online}/{listing.max_players} 玩家: {players}")
    lines.append(f"总计: {report.total_online} 人在线")
    return "\n".join(lines)


class Bridge:
    """把「QQ 事件 / 日志事件 / 健康状态」翻译成「RCON 注入 / 群消息」。"""

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
        self._config = config
        self._bindings = bindings
        self._state = state
        self._rcon = rcon
        self._registry = registry
        self._gateway = gateway
        self._clock = clock
        self._logger = logger or logging.getLogger("y33bot.bridge")
        self._warned_no_group = False

    # ------------------------------------------------------------------ QQ → MC
    async def handle_group_message(self, message: MCGroupMessage) -> str | None:
        """处理一条 QQ 群 @机器人 消息；返回需要被动回复到群里的文本（无回复返回 None）。"""

        if not (message.group_openid or "").strip() or not (message.member_openid or "").strip():
            self._logger.warning("[警告] 群消息缺少 group_openid/member_openid，已丢弃")
            return None

        content = (message.content or "").strip()
        if not content:
            self._logger.debug("[忽略] 空消息")
            return None

        if content.startswith(self._config.qq.command_prefix):
            return await self._registry.dispatch(self._build_context(message), content)

        if content.startswith(self._config.qq.chat_prefix):
            return await self._forward_to_mc(message, content)

        self._logger.info("[忽略] 非触发前缀")
        return None

    async def _forward_to_mc(self, message: MCGroupMessage, content: str) -> str | None:
        game_id = self._bindings.lookup(message.member_openid)
        if not game_id:
            self._logger.debug("[忽略] 未绑定用户，已回复绑定提示")
            return UNBOUND_REPLY

        body = content[len(self._config.qq.chat_prefix) :]
        text = self._single_line(self._extract_text(body))
        if not text:
            self._logger.debug("[忽略] 内容为空（仅富媒体标记），不转发")
            return None

        await self._rcon.broadcast_tellraw(self._format_to_mc(game_id, text))
        return None

    # ------------------------------------------------------------------ MC → QQ
    async def handle_log_event(self, event: MCLogEvent) -> None:
        """处理一条 MC 日志事件（进出通知 / 聊天转发）。"""

        if event.kind in ("join", "quit"):
            if not event.player:
                self._logger.warning("[警告] %s 事件缺少玩家名，已忽略: %s", event.kind, event.raw)
                return
            verb = "进入游戏" if event.kind == "join" else "退出游戏"
            await self._send_to_group(f"{event.player}{verb}")
            return

        if event.kind == "chat":
            await self._handle_chat_event(event)
            return

        self._logger.warning("[警告] 未知日志事件类型 %r，已忽略", event.kind)

    async def _handle_chat_event(self, event: MCLogEvent) -> None:
        message = event.message or ""

        for prefix in self._config.behavior.ignored_chat_prefixes:
            if prefix and message.startswith(prefix):
                self._logger.info("[忽略] 回环防护：命中 ignored_chat_prefixes")
                return

        if not message.startswith(self._config.qq.chat_prefix):
            self._logger.info("[忽略] 聊天非 # 开头，不转发")
            return

        body = self._single_line(message[len(self._config.qq.chat_prefix) :].lstrip())
        if not body:
            self._logger.debug("[忽略] 聊天内容为空，不转发")
            return

        player = event.player or "?"
        await self._send_to_group(f"{player}: {body}")  # R11：发到 QQ 群
        await self._rcon.broadcast_tellraw(f"[→QQ] {player}: {body}")  # R11：游戏内回显

    # ------------------------------------------------------------------ 健康
    async def poll_health(self) -> list[tuple[str, bool]]:
        """探测全部服；返回发生翻转的 `(服务器名, 是否在线)`，且每个翻转发一次通知（R19）。"""

        report = await self._rcon.status()
        flips: list[tuple[str, bool]] = []
        for name in self._rcon.server_names():
            online = report.per_server.get(name) is not None
            server_state = self._state.server_state(name)
            if server_state.health_online == online:
                self._logger.debug("[忽略] 状态未变化，不重复提示")
                continue
            server_state.health_online = online
            server_state.health_changed_at = self._clock()
            flips.append((name, online))
            await self._send_to_group(f"[服务器状态] {name} {'上线' if online else '离线'}")
        return flips

    # ------------------------------------------------------------------ 渲染
    def format_status(self, report: ServerStatusReport) -> str:
        """`/status` 的回复文本（PLAN.md §3.5 / A1）。"""

        return format_status(report)

    def _extract_text(self, text: str) -> str:
        """剔除 QQ 富媒体标记（A6）。"""

        return MEDIA_MARKER_RE.sub("", text or "").strip()

    def _single_line(self, text: str) -> str:
        """取第一行并按 `max_line_length` 截断，被截断时末尾补 `…`（A7）。"""

        line = (text or "").split("\n", 1)[0].strip()
        limit = max(1, int(self._config.behavior.max_line_length))
        if len(line) > limit:
            return line[: limit - 1] + "…"
        return line

    @staticmethod
    def _format_to_mc(game_id: str, text: str) -> str:
        """转发到游戏内的固定格式（PLAN.md R8）。"""

        return f"[QQ] {game_id}: {text}"

    # ------------------------------------------------------------------ 内部
    def _build_context(self, message: MCGroupMessage) -> CommandContext:
        from .commands.registry import CommandContext

        return CommandContext(
            config=self._config,
            bindings=self._bindings,
            rcon=self._rcon,
            state=self._state,
            message=message,
            logger=self._logger,
        )

    async def _send_to_group(self, text: str) -> bool:
        """按配置的 `group_openid` 发一条主动消息；未配置时告警并跳过（A11）。"""

        group_openid = (self._config.qq.group_openid or "").strip()
        if not group_openid:
            if not self._warned_no_group:
                self._logger.warning("[警告] [qq] group_openid 未配置，MC→QQ 方向已禁用（消息不发送）")
                self._warned_no_group = True
            return False
        await self._gateway.send_group_message(OutgoingGroupMessage(group_openid=group_openid, text=text))
        return True
