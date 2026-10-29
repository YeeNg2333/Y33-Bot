"""日志模板编译与单行解析（PLAN.md §3.2 / A9 / R27）。

设计要点：
- 模板来自配置（TOML），编译时自动补 `^` / `$` 锚点（A9），使用 `re.match`；
- 必须含规范要求的命名组（`join`/`quit` → `player`；`chat` → `player` + `message`），
  否则在配置加载阶段就报 `ConfigError`，把问题挡在启动前；
- `parse_line()` 的签名固定为 `(compiled, line)`（PLAN.md §3.3），事件里的 `server`
  由 `LogWatcher` 用 `dataclasses.replace()` 填充。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..models import LogEventKind, MCLogEvent

if TYPE_CHECKING:  # 避免 config <-> mclog.patterns 的运行时循环导入
    from ..config import LogPatterns

__all__ = [
    "PatternError",
    "CompiledPatterns",
    "REQUIRED_GROUPS",
    "compile_patterns",
    "parse_line",
    "looks_like_event",
]

#: 各模板必须提供的命名组
REQUIRED_GROUPS: dict[str, tuple[str, ...]] = {
    "join": ("player",),
    "quit": ("player",),
    "chat": ("player", "message"),
}

_KINDS: tuple[LogEventKind, ...] = ("join", "quit", "chat")

#: 聊天行的载荷特征：`<玩家名> `（与时间戳 / 线程名 / logger 段的布局无关）
_CHAT_SHAPE = re.compile(r"<\w+> ")


class PatternError(ValueError):
    """日志模板不可编译或缺少必需命名组。"""


@dataclass(frozen=True)
class CompiledPatterns:
    """编译后的三个模板 + 编码；由 `compile_patterns()` 产出。"""

    join: re.Pattern[str]
    quit: re.Pattern[str]
    chat: re.Pattern[str]
    encoding: str = "utf-8"

    def pattern(self, kind: str) -> re.Pattern[str]:
        return getattr(self, kind)


def _anchor(template: str) -> str:
    """模板未自带锚点时补上（A9：行首用 `^`，行尾用 `$`）。"""

    anchored = template
    if not anchored.startswith("^"):
        anchored = "^" + anchored
    if not anchored.endswith("$"):
        anchored = anchored + "$"
    return anchored


def _compile_one(kind: str, template: str) -> re.Pattern[str]:
    if not isinstance(template, str) or not template.strip():
        raise PatternError(f"日志模板 {kind} 不能为空")
    try:
        compiled = re.compile(_anchor(template))
    except re.error as exc:
        raise PatternError(f"日志模板 {kind} 不是合法正则: {exc}") from exc
    missing = [group for group in REQUIRED_GROUPS[kind] if group not in compiled.groupindex]
    if missing:
        raise PatternError(f"日志模板 {kind} 缺少命名组: {', '.join(missing)}")
    return compiled


def compile_patterns(patterns: LogPatterns) -> CompiledPatterns:
    """把 `LogPatterns` 编译成 `CompiledPatterns`；失败抛 `PatternError`。"""

    for kind in _KINDS:
        if not hasattr(patterns, kind):
            raise PatternError(f"日志模板缺少字段: {kind}")
    encoding = getattr(patterns, "encoding", "utf-8") or "utf-8"
    return CompiledPatterns(
        join=_compile_one("join", patterns.join),
        quit=_compile_one("quit", patterns.quit),
        chat=_compile_one("chat", patterns.chat),
        encoding=encoding,
    )


def parse_line(compiled: CompiledPatterns, line: str) -> MCLogEvent | None:
    """解析一行日志；命中返回事件（`server` 为空串，待调用方填充），否则返回 None。"""

    text = line.lstrip("\ufeff")
    for kind in _KINDS:
        match = compiled.pattern(kind).match(text)
        if match is None:
            continue
        groups = match.groupdict()
        player = groups.get("player")
        message = groups.get("message") if kind == "chat" else None
        return MCLogEvent(
            server="",
            kind=kind,
            player=player,
            message=message,
            raw=text,
            occurred_at=time.time(),
        )
    return None


def looks_like_event(text: str) -> str | None:
    """按**载荷特征**猜这一行可能是哪类事件，返回 `"join"` / `"quit"` / `"chat"` / `None`。

    与具体日志布局无关：只看业务载荷（`joined the game`、`left the game`、`<玩家名> `），
    不看时间戳格式、线程名（`Server thread` / `Async Chat Thread - #N`）或 log4j2 的 logger 段，
    因此模板写错（或 MC 版本/加载器换了布局）时依然认得出「这行本该是个事件」。

    用途：`LogWatcher` 的零事件看门狗（BUG-004）——只对候选行统计未命中，
    避免把服务端启动 INFO、mod 列表这类正常未匹配行算成故障；`check` 的模板自检也复用它。
    注意它**不解析事件内容**，命中事件请用 `parse_line()`。
    """

    if "joined the game" in text:
        return "join"
    if "left the game" in text:
        return "quit"
    if _CHAT_SHAPE.search(text):
        return "chat"
    return None
