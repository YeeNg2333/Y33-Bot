"""全部运行时数据结构（PLAN.md §3.3、§4.3、§4.4）。

本文件只定义数据形状，不含任何逻辑；字段名与顺序是**冻结签名**，
下游实现任务不得修改（新增字段须先改 PLAN.md）。

字段语义以 PLAN.md §4.3/§4.5 为准：
``health_online is None`` 表示尚未探测；``log_size``/``log_inode`` 仅用于诊断（A10）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class MCGroupMessage:
    """QQ 群内一条 @机器人 消息（``content`` 已剥离 @机器人 前缀，见 A5）。"""

    group_openid: str
    member_openid: str
    message_id: str
    content: str
    received_at: float


@dataclass(frozen=True)
class OutgoingGroupMessage:
    """要发到 QQ 群的一条文本消息；``reply_to_message_id=None`` 表示主动消息（A12）。"""

    group_openid: str
    text: str
    reply_to_message_id: str | None = None


@dataclass(frozen=True)
class MCLogEvent:
    """从 ``latest.log`` 解析出的一条事件（进服 / 退服 / 聊天）。"""

    server: str
    kind: Literal["join", "quit", "chat"]
    player: str | None
    message: str | None
    raw: str
    occurred_at: float


@dataclass(frozen=True)
class PlayerList:
    """RCON ``/list`` 的解析结果（R15；A15：不含 TPS）。"""

    online: int
    max_players: int
    players: list[str]
    raw: str


@dataclass(frozen=True)
class CommandResult:
    """单台 MC 服上一条命令的执行结果（失败只记日志、不重试，N7）。"""

    server: str
    ok: bool
    response: str
    error: str | None


@dataclass(frozen=True)
class ServerStatusReport:
    """``/status`` 的多服聚合结果（A1）：``per_server[name] is None`` 表示该服离线。"""

    per_server: dict[str, PlayerList | None]
    offline: list[str]
    total_online: int


@dataclass
class ServerState:
    """单台 MC 服的持久化运行状态（PLAN.md §4.3）。"""

    log_offset: int = 0
    log_size: int = 0
    log_inode: str | None = None
    health_online: bool | None = None
    health_changed_at: float | None = None


@dataclass
class RuntimeState:
    """``data/state.json`` 的整体结构（版本不符则备份后重置，§4.5）。"""

    version: int = 1
    msg_seq: int = 0
    servers: dict[str, ServerState] = field(default_factory=dict)
