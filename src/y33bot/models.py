"""运行时数据结构（PLAN.md §3.3 / §4.4）。

本模块只放纯数据结构，不依赖项目内其它模块，便于所有层自由引用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "LogEventKind",
    "MCGroupMessage",
    "OutgoingGroupMessage",
    "MCLogEvent",
    "PlayerList",
    "CommandResult",
    "ServerStatusReport",
]

LogEventKind = Literal["join", "quit", "chat"]


@dataclass(frozen=True)
class MCGroupMessage:
    """一条来自 QQ 群的 @机器人 消息。

    `content` 由 `qq.gateway._normalize_content()` 做过防御性剥离 @机器人 前缀（PLAN.md A5）。
    """

    group_openid: str
    member_openid: str
    message_id: str
    content: str
    received_at: float


@dataclass(frozen=True)
class OutgoingGroupMessage:
    """待发送到 QQ 群的文本；`reply_to_message_id=None` 表示主动消息（PLAN.md A12）。"""

    group_openid: str
    text: str
    reply_to_message_id: str | None = None


@dataclass(frozen=True)
class MCLogEvent:
    """从 MC `latest.log` 解析出的一条事件；`server` 由 LogWatcher 填充。"""

    server: str
    kind: LogEventKind
    player: str | None
    message: str | None
    raw: str
    occurred_at: float


@dataclass(frozen=True)
class PlayerList:
    """RCON `/list` 的解析结果。"""

    online: int
    max_players: int
    players: list[str]
    raw: str


@dataclass(frozen=True)
class CommandResult:
    """一次 RCON 命令的执行结果。`ok=False` 时 `error` 必非空。"""

    server: str
    ok: bool
    response: str
    error: str | None


@dataclass(frozen=True)
class ServerStatusReport:
    """多服聚合状态；`per_server[server] is None` 表示该服离线。"""

    per_server: dict[str, PlayerList | None]
    offline: list[str]
    total_online: int
