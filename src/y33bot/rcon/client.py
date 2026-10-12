"""自研异步 RCON 客户端（PLAN.md §2.4 / A13 / A14）。

Valve RCON 二进制协议（全部小端）：

    size(int32) | req_id(int32) | type(int32) | body(utf-8) | \\x00\\x00
    size = 4 + 4 + len(body) + 2

实现要点（与 PLAN.md §2.4 一一对应）：
- `LOGIN(3)` 鉴权，响应 id `-1` → `RconAuthError`；
- **多包响应**：读完首个 `RESPONSE(0)` 包后在 `drain_timeout` 内继续读后续包并拼接（Vanilla 长输出会分多包）；
- `asyncio.Lock` 串行化同一条连接上的命令（并发调用必须配对请求/响应）；
- 命令体 > 1446 字节直接拒绝（协议硬限）；
- 断连后**下一次调用**自动重连，但不重发当前命令（A14）；
- `connect_timeout` / `command_timeout` 可配，超时抛 `RconTimeoutError`。
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import struct
from typing import TYPE_CHECKING

from .protocol import (
    RconAuthError,
    RconConnectError,
    RconDisconnectedError,
    RconError,
    RconTimeoutError,
)

if TYPE_CHECKING:  # pragma: no cover
    from asyncio import StreamReader, StreamWriter

__all__ = ["AsyncRconClient"]

_TYPE_RESPONSE = 0
_TYPE_COMMAND = 2
_TYPE_AUTH = 3

_HEADER = struct.Struct("<ii")
_MAX_PACKET_BYTES = 1 << 20  # 单包上限（防御畸形长度字段）


class AsyncRconClient:
    """一条 RCON 连接；非线程安全，请在同一个事件循环内使用。"""

    MAX_PAYLOAD_BYTES = 1446

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        *,
        connect_timeout: float = 5.0,
        command_timeout: float = 5.0,
        drain_timeout: float = 0.1,
        logger: logging.Logger | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._password = password
        self._connect_timeout = float(connect_timeout)
        self._command_timeout = float(command_timeout)
        self._drain_timeout = float(drain_timeout)
        self._logger = logger or logging.getLogger("y33bot.rcon.client")
        self._ids = itertools.count(1)
        self._lock = asyncio.Lock()
        self._reader: StreamReader | None = None
        self._writer: StreamWriter | None = None

    # ------------------------------------------------------------------ 属性
    @property
    def connected(self) -> bool:
        writer = self._writer
        return writer is not None and not writer.is_closing()

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"

    # ------------------------------------------------------------------ 连接
    async def connect(self) -> None:
        """建立连接并鉴权（已连接则直接返回）。"""

        async with self._lock:
            await self._ensure_connected()

    async def _ensure_connected(self) -> None:
        """调用方必须已持有 `self._lock`。"""

        if self.connected:
            return
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self._connect_timeout
            )
        except TimeoutError as exc:
            await self._drop()
            raise RconConnectError(f"连接 {self.endpoint} 超时（{self._connect_timeout}s）") from exc
        except OSError as exc:
            await self._drop()
            raise RconConnectError(f"连接 {self.endpoint} 失败: {exc}") from exc

        try:
            await self._authenticate()
        except RconError:
            await self._drop()
            raise
        except (OSError, asyncio.IncompleteReadError, ConnectionError) as exc:
            await self._drop()
            raise RconConnectError(f"RCON 鉴权握手中断 {self.endpoint}: {exc}") from exc
        self._logger.debug("[RCON %s] 已连接", self.endpoint)

    async def _authenticate(self) -> None:
        req_id = next(self._ids)
        await self._send(req_id, _TYPE_AUTH, self._password)
        try:
            pkt_id, _pkt_type, _body = await asyncio.wait_for(
                self._read_packet(), timeout=self._command_timeout
            )
        except TimeoutError as exc:
            raise RconTimeoutError(f"RCON 鉴权响应超时（{self._command_timeout}s）: {self.endpoint}") from exc
        if pkt_id == -1:
            raise RconAuthError(f"RCON 鉴权失败（密码错误）: {self.endpoint}")
        if pkt_id != req_id:
            raise RconError(f"RCON 鉴权响应 id 异常: 期望 {req_id}，收到 {pkt_id}")
        # 少数服务端在鉴权响应后会补一个空 RESPONSE 包，先清掉以免污染后续命令
        await self._drain()

    async def _drain(self, max_packets: int = 4) -> None:
        for _ in range(max_packets):
            try:
                await asyncio.wait_for(self._read_packet(), timeout=self._drain_timeout)
            except TimeoutError:
                return
            except RconError:
                return

    # ------------------------------------------------------------------ 命令
    async def command(self, cmd: str) -> str:
        """执行一条命令；未连接先自动重连，读失败抛 `RconDisconnectedError`。"""

        payload_len = len((cmd or "").encode("utf-8"))
        if payload_len > self.MAX_PAYLOAD_BYTES:
            raise RconError(
                f"命令超过 {self.MAX_PAYLOAD_BYTES} 字节上限（实际 {payload_len} 字节，RCON 协议硬限）"
            )

        async with self._lock:
            if not self.connected:
                await self._ensure_connected()  # 断连自动重连；但不重发上一条命令（A14）

            req_id = next(self._ids)
            try:
                await self._send(req_id, _TYPE_COMMAND, cmd)
            except (OSError, ConnectionError) as exc:
                await self._drop()
                raise RconDisconnectedError(f"RCON 发送失败（连接已断开）: {exc}") from exc
            except RconError:
                raise

            chunks: list[bytes] = []
            first = True
            while True:
                timeout = self._command_timeout if first else self._drain_timeout
                try:
                    pkt_id, _pkt_type, body = await asyncio.wait_for(self._read_packet(), timeout=timeout)
                except TimeoutError as exc:
                    if first:
                        await self._drop()
                        raise RconTimeoutError(
                            f"RCON 命令超时（{self._command_timeout}s）: {cmd!r}"
                        ) from exc
                    break
                except RconError as exc:
                    await self._drop()
                    if first:
                        raise RconDisconnectedError(f"RCON 连接中断: {exc}") from exc
                    self._logger.warning("[警告] RCON 多包响应读取中断: %s", exc)
                    break
                if first:
                    first = False
                if pkt_id != req_id:
                    self._logger.warning("[警告] RCON 响应 id 不匹配（期望 %s，收到 %s），已丢弃", req_id, pkt_id)
                    continue
                chunks.append(body)

            return b"".join(chunks).decode("utf-8", errors="replace").rstrip("\x00")

    async def close(self) -> None:
        """关闭连接（幂等）。"""

        async with self._lock:
            await self._drop()

    # ------------------------------------------------------------------ 内部
    async def _send(self, req_id: int, pkt_type: int, body: str) -> None:
        writer = self._writer
        if writer is None:
            raise RconDisconnectedError("RCON 连接未建立")
        payload = (body or "").encode("utf-8")
        packet = _HEADER.pack(req_id, pkt_type) + payload + b"\x00\x00"
        writer.write(struct.pack("<i", len(packet)) + packet)
        await writer.drain()

    async def _read_packet(self) -> tuple[int, int, bytes]:
        reader = self._reader
        if reader is None:
            raise RconDisconnectedError("RCON 连接未建立")
        try:
            header = await reader.readexactly(4)
            (size,) = struct.unpack("<i", header)
            if size < 10 or size > _MAX_PACKET_BYTES:
                raise RconDisconnectedError(f"RCON 响应长度非法: {size}")
            data = await reader.readexactly(size)
        except asyncio.IncompleteReadError as exc:
            raise RconDisconnectedError(f"RCON 连接被对端关闭: {exc}") from exc
        except (OSError, ConnectionError) as exc:
            raise RconDisconnectedError(f"RCON 读取失败: {exc}") from exc
        req_id, pkt_type = _HEADER.unpack_from(data, 0)
        body = data[8:]
        # 协议规定包体以两个 NUL 结尾（size 里已计入），拼包前必须去掉，否则多包响应会夹 NUL
        if body.endswith(b"\x00\x00"):
            body = body[:-2]
        return req_id, pkt_type, body

    async def _drop(self) -> None:
        """丢弃当前连接（不抛异常）；调用方必须已持有 `self._lock`。"""

        writer = self._writer
        self._reader = None
        self._writer = None
        if writer is None:
            return
        try:
            writer.close()
            await writer.wait_closed()
        except (OSError, ConnectionError, asyncio.CancelledError):
            pass
