"""`latest.log` 增量读取：字节偏移、轮转重置、残行缓冲（PLAN.md §3.2 / §3.7 / A10 / A20 / R24-R26）。

同步实现（`Path.open` + `seek` + 正则），由 `service` 用 `asyncio.to_thread()` 调度。
"""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from ..models import MCLogEvent
from .patterns import CompiledPatterns, compile_patterns, parse_line

if TYPE_CHECKING:
    from ..config import LogPatterns, MCServerConfig
    from ..state import StateStore

__all__ = ["LogWatcher", "MAX_BUFFER_BYTES"]

#: 残行缓冲上限：防止「永不含换行」的畸形文件把内存吃光
MAX_BUFFER_BYTES = 64 * 1024


class LogWatcher:
    """单台 MC 服一个实例；`poll_new_events()` 串行推进该服的字节偏移。"""

    def __init__(
        self,
        server: MCServerConfig,
        patterns: LogPatterns,
        store: StateStore,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._server = server
        self._store = store
        self._logger = logger or logging.getLogger(f"y33bot.mclog.watcher.{server.name}")
        self._compiled: CompiledPatterns = compile_patterns(patterns)
        self._buffer: bytes = b""
        self._missing_warned = False

    @property
    def server(self) -> MCServerConfig:
        return self._server

    @property
    def compiled(self) -> CompiledPatterns:
        return self._compiled

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    # ------------------------------------------------------------------ 轮询
    def poll_new_events(self) -> list[MCLogEvent]:
        """读取自上次偏移以来的新增内容，返回解析出的事件（同步阻塞，勿在事件循环里直接调用）。"""

        state = self._store.server_state(self._server.name)
        path = Path(self._server.log_path)

        try:
            stat = path.stat()
        except OSError as exc:
            if not self._missing_warned:
                self._logger.warning("[警告] 日志文件不可读 %s: %s（下一轮继续尝试）", path, exc)
                self._missing_warned = True
            return []
        self._missing_warned = False

        size = stat.st_size
        inode = str(getattr(stat, "st_ino", "") or "")
        offset = max(0, int(state.log_offset or 0))
        rotated = False

        if state.log_offset > size:
            self._logger.warning(
                "[警告] 日志文件缩小（size=%d < offset=%d），偏移重置为 0", size, state.log_offset
            )
            rotated = True
        elif state.log_inode and inode and state.log_inode != inode:
            self._logger.warning("[警告] 日志文件已轮转（inode %s -> %s），偏移重置为 0", state.log_inode, inode)
            rotated = True

        if rotated:
            offset = 0
            state.log_offset = 0
            self._buffer = b""

        state.log_size = size
        state.log_inode = inode

        if offset == size:
            return []

        try:
            with path.open("rb") as handle:
                handle.seek(offset)
                chunk = handle.read()
        except OSError as exc:
            self._logger.warning("[警告] 日志读取失败 %s: %s", path, exc)
            return []

        if not chunk:
            return []

        state.log_offset = offset + len(chunk)
        events: list[MCLogEvent] = []
        for raw_line in self._split_lines(chunk):
            text = raw_line.decode(self._compiled.encoding, errors="replace").rstrip("\r")
            if not text.strip():
                continue
            event = parse_line(self._compiled, text)
            if event is None:
                self._logger.debug("[忽略] 日志行未匹配任何模板: %s", text)
                continue
            events.append(replace(event, server=self._server.name))
        return events

    # ------------------------------------------------------------------ 内部
    def _split_lines(self, chunk: bytes) -> list[bytes]:
        """按换行切分；最后一段缺换行则留在缓冲区，等下次凑齐（A20）。"""

        data = self._buffer + chunk
        if data.endswith(b"\n"):
            self._buffer = b""
            return data.split(b"\n")[:-1]

        index = data.rfind(b"\n")
        if index < 0:
            lines: list[bytes] = []
            self._buffer = data
        else:
            lines = data[:index].split(b"\n")
            self._buffer = data[index + 1 :]

        if len(self._buffer) > MAX_BUFFER_BYTES:
            self._logger.warning("[警告] 残行缓冲超过 %d 字节，强制作为整行解析", MAX_BUFFER_BYTES)
            lines.append(self._buffer)
            self._buffer = b""
        return lines
