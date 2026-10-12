"""运行状态持久化：日志偏移、健康状态、msg_seq（PLAN.md §3.2 / §4.3 / §4.5.4 / A12）。

介质为 `data/state.json`，写入使用「临时文件 + os.replace()」原子替换。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("y33bot.state")

__all__ = ["STATE_VERSION", "ServerState", "RuntimeState", "StateStore"]

STATE_VERSION = 1


@dataclass
class ServerState:
    """单个 MC 服的运行状态。`health_online=None` 表示尚未探测（PLAN.md §4.3）。"""

    log_offset: int = 0
    log_size: int = 0
    log_inode: str = ""
    health_online: bool | None = None
    health_changed_at: float = 0.0


@dataclass
class RuntimeState:
    """整个进程的运行状态根对象。"""

    version: int = STATE_VERSION
    qq_msg_seq: int = 0
    servers: dict[str, ServerState] = field(default_factory=dict)


def _backup(path: Path) -> Path:
    """把坏状态文件改名为 `*.bak`（不静默丢数据，PLAN.md §4.5.4）。"""

    backup = path.with_name(path.name + ".bak")
    try:
        os.replace(path, backup)
    except OSError as exc:  # pragma: no cover - 纯防御
        logger.warning("[警告] 状态备份失败 %s: %s", path, exc)
    return backup


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


class StateStore:
    """`data/state.json` 的读写封装。"""

    def __init__(self, path: Path, state: RuntimeState | None = None) -> None:
        self.path = Path(path)
        self.state = state if state is not None else RuntimeState()

    # ------------------------------------------------------------------ 读
    @classmethod
    def load(cls, path: Path) -> StateStore:
        """加载状态；文件缺失返回空状态，损坏或版本不符则备份后重置。"""

        p = Path(path)
        if not p.exists():
            return cls(p)
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            backup = _backup(p)
            logger.warning("[警告] 运行状态解析失败（%s），已备份为 %s 并重置", exc, backup.name)
            return cls(p)
        if not isinstance(raw, dict):
            backup = _backup(p)
            logger.warning("[警告] 运行状态结构非法，已备份为 %s 并重置", backup.name)
            return cls(p)
        version = raw.get("version")
        if version != STATE_VERSION:
            backup = _backup(p)
            logger.warning(
                "[警告] 运行状态版本不匹配（期望 %s，实际 %r），已备份为 %s 并重置",
                STATE_VERSION,
                version,
                backup.name,
            )
            return cls(p)

        qq_raw = raw.get("qq")
        msg_seq = 0
        if isinstance(qq_raw, dict):
            msg_seq = _as_int(qq_raw.get("msg_seq"), 0)

        servers: dict[str, ServerState] = {}
        servers_raw = raw.get("servers")
        if isinstance(servers_raw, dict):
            for name, data in servers_raw.items():
                if not isinstance(data, dict):
                    logger.warning("[警告] 忽略非法的服务器状态项: %r", name)
                    continue
                health = data.get("health_online")
                servers[str(name)] = ServerState(
                    log_offset=max(0, _as_int(data.get("log_offset"), 0)),
                    log_size=max(0, _as_int(data.get("log_size"), 0)),
                    log_inode=str(data.get("log_inode") or ""),
                    health_online=health if isinstance(health, bool) else None,
                    health_changed_at=_as_float(data.get("health_changed_at"), 0.0),
                )
        return cls(p, RuntimeState(version=STATE_VERSION, qq_msg_seq=msg_seq, servers=servers))

    # ------------------------------------------------------------------ 用
    def server_state(self, name: str) -> ServerState:
        """取（必要时创建）某服务器的状态。"""

        state = self.state.servers.get(name)
        if state is None:
            state = ServerState()
            self.state.servers[name] = state
        return state

    def next_msg_seq(self) -> int:
        """全局递增的主动消息序号（PLAN.md A12）。"""

        self.state.qq_msg_seq += 1
        return self.state.qq_msg_seq

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "qq": {"msg_seq": self.state.qq_msg_seq},
            "servers": {name: asdict(state) for name, state in sorted(self.state.servers.items())},
        }

    # ------------------------------------------------------------------ 写
    def save(self) -> None:
        """原子落盘；写失败只记日志不抛出（服务不应因状态写盘失败而中断）。"""

        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=2).encode("utf-8")
        try:
            _atomic_write_bytes(self.path, payload)
        except OSError as exc:
            logger.warning("[警告] 运行状态写盘失败 %s: %s", self.path, exc)
        else:
            logger.debug("[状态] 已落盘 %s", self.path)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
