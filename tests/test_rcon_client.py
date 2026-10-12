"""AsyncRconClient 测试：内存假 RCON 服务器（PLAN.md §2.4 / A13 / A14 / T4）。"""

from __future__ import annotations

import asyncio
import struct

import pytest

from y33bot.rcon.client import AsyncRconClient
from y33bot.rcon.protocol import (
    RconAuthError,
    RconConnectError,
    RconDisconnectedError,
    RconError,
    RconTimeoutError,
    RconTransport,
)

AUTH = 3
COMMAND = 2
RESPONSE = 0
AUTH_RESPONSE = 2


class FakeRconServer:
    """只实现 Vanilla 用到的那部分 RCON 语义。"""

    def __init__(
        self,
        *,
        password: str = "secret",
        extra_auth_packet: bool = False,
        silent: bool = False,
        split_response: int = 1,
        close_after: int | None = None,
    ) -> None:
        self.password = password
        self.extra_auth_packet = extra_auth_packet
        self.silent = silent
        self.split_response = split_response
        self.close_after = close_after
        self.commands: list[str] = []
        self.connections = 0
        self._server: asyncio.AbstractServer | None = None

    async def __aenter__(self) -> FakeRconServer:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.stop()

    @property
    def port(self) -> int:
        assert self._server is not None
        return self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    # ------------------------------------------------------------ 协议
    @staticmethod
    async def _read_packet(reader: asyncio.StreamReader) -> tuple[int, int, bytes]:
        header = await reader.readexactly(4)
        (size,) = struct.unpack("<i", header)
        data = await reader.readexactly(size)
        req_id, pkt_type = struct.unpack("<ii", data[:8])
        return req_id, pkt_type, data[8:-2]

    @staticmethod
    def _write(writer: asyncio.StreamWriter, req_id: int, pkt_type: int, body: bytes) -> None:
        packet = struct.pack("<ii", req_id, pkt_type) + body + b"\x00\x00"
        writer.write(struct.pack("<i", len(packet)) + packet)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        served = 0
        try:
            while True:
                try:
                    req_id, pkt_type, body = await self._read_packet(reader)
                except (asyncio.IncompleteReadError, ConnectionResetError):
                    return
                if pkt_type == AUTH:
                    if body.decode() == self.password:
                        self._write(writer, req_id, AUTH_RESPONSE, b"")
                        if self.extra_auth_packet:
                            self._write(writer, req_id, RESPONSE, b"")
                    else:
                        self._write(writer, -1, AUTH_RESPONSE, b"")
                    await writer.drain()
                    continue
                if pkt_type == COMMAND:
                    self.commands.append(body.decode())
                    served += 1
                    if self.close_after is not None and self.connections == 1 and served >= self.close_after:
                        writer.close()
                        return
                    if not self.silent:
                        chunks = self._split(body.decode())
                        for chunk in chunks:
                            self._write(writer, req_id, RESPONSE, chunk.encode())
                        await writer.drain()
                    continue
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except (OSError, ConnectionError):
                pass

    def _split(self, command: str) -> list[str]:
        text = f"answer:{command}"
        if self.split_response <= 1:
            return [text]
        size = max(1, len(text) // self.split_response + 1)
        return [text[index : index + size] for index in range(0, len(text), size)]


async def _client(server: FakeRconServer, **kwargs) -> AsyncRconClient:
    client = AsyncRconClient(
        "127.0.0.1", server.port, server.password, connect_timeout=2.0, command_timeout=2.0, **kwargs
    )
    await client.connect()
    return client


async def test_auth_and_command_roundtrip() -> None:
    async with FakeRconServer(password="secret") as server:
        client = await _client(server)
        try:
            assert client.connected is True
            assert isinstance(client, RconTransport)
            assert await client.command("/list") == "answer:/list"
            assert server.commands == ["/list"]
        finally:
            await client.close()
        assert client.connected is False


async def test_auth_failure() -> None:
    async with FakeRconServer(password="right") as server:
        client = AsyncRconClient("127.0.0.1", server.port, "wrong", connect_timeout=2.0)
        with pytest.raises(RconAuthError, match="密码错误"):
            await client.connect()
        assert client.connected is False


async def test_extra_auth_packet_is_swallowed() -> None:
    async with FakeRconServer(extra_auth_packet=True) as server:
        client = await _client(server)
        try:
            assert await client.command("ping") == "answer:ping"
        finally:
            await client.close()


async def test_multi_packet_response_is_joined() -> None:
    async with FakeRconServer(split_response=4) as server:
        client = await _client(server)
        try:
            assert await client.command("hello") == "answer:hello"
        finally:
            await client.close()


async def test_payload_limit_rejected() -> None:
    async with FakeRconServer() as server:
        client = await _client(server)
        try:
            with pytest.raises(RconError, match="1446 字节上限"):
                await client.command("x" * 1447)
            assert server.commands == []  # 没有真的发出去
            assert await client.command("x" * 1446) == "answer:" + "x" * 1446
        finally:
            await client.close()


async def test_command_timeout() -> None:
    async with FakeRconServer(silent=True) as server:
        client = await _client(server)
        try:
            with pytest.raises(RconTimeoutError, match="命令超时"):
                await client.command("/list")
            assert client.connected is False  # 超时后连接被丢弃
        finally:
            await client.close()


async def test_connect_to_closed_port_fails() -> None:
    async with FakeRconServer() as server:
        port = server.port
    await server.stop()
    client = AsyncRconClient("127.0.0.1", port, "secret", connect_timeout=0.5)
    with pytest.raises(RconConnectError, match="127.0.0.1"):
        await client.connect()
    assert client.connected is False


async def test_reconnects_on_next_command_without_resending() -> None:
    async with FakeRconServer(close_after=1) as server:
        client = await _client(server)
        try:
            with pytest.raises(RconDisconnectedError):
                await client.command("first")
            assert client.connected is False
            assert await client.command("second") == "answer:second"
            assert server.connections == 2
            assert server.commands == ["first", "second"]
        finally:
            await client.close()


async def test_concurrent_commands_are_serialized() -> None:
    async with FakeRconServer() as server:
        client = await _client(server)
        try:
            results = await asyncio.gather(*(client.command(f"cmd{index}") for index in range(6)))
            assert results == [f"answer:cmd{index}" for index in range(6)]
        finally:
            await client.close()


async def test_close_is_idempotent() -> None:
    async with FakeRconServer() as server:
        client = await _client(server)
        await client.close()
        await client.close()
        assert client.connected is False


async def test_command_before_connect_auto_connects() -> None:
    async with FakeRconServer() as server:
        client = AsyncRconClient("127.0.0.1", server.port, server.password, connect_timeout=2.0, command_timeout=2.0)
        try:
            assert client.connected is False
            assert await client.command("auto") == "answer:auto"
            assert client.connected is True
        finally:
            await client.close()


async def test_endpoint_property() -> None:
    client = AsyncRconClient("127.0.0.1", 25575, "secret")
    assert client.endpoint == "127.0.0.1:25575"


async def test_command_after_server_stop_raises_disconnected() -> None:
    async with FakeRconServer(close_after=1) as server:
        client = await _client(server)
        try:
            with pytest.raises(RconDisconnectedError):
                await client.command("first")
            await server.stop()
            with pytest.raises(RconConnectError):
                await client.command("second")
        finally:
            await client.close()
