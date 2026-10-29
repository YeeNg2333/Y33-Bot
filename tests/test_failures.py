"""失败分支补测（PLAN.md §6 T9）：RCON 客户端/连接池、QQ 网关、常驻服务、CLI。

这些用例专门打「异常才走的那几行」：对端行为不合法（畸形包、id 不匹配、半途断连）、
依赖返回坏数据、写盘/关闭失败、参数不合法。断言的是**可观测结果**（抛出的异常类型与文案、
记录到的日志、退出码、stdout/stderr），不是内部调用顺序。
"""

from __future__ import annotations

import asyncio
import struct
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import DEFAULT_ENV, App, config_text
from y33bot.binding import BindingError, BindingStore
from y33bot.cli import _display_path, main
from y33bot.config import load_config
from y33bot.mclog.watcher import LogWatcher
from y33bot.qq import gateway as gateway_module
from y33bot.qq.fakes import FakeQQGateway
from y33bot.qq.gateway import BotpyGateway, QQGateway, QQGatewayError
from y33bot.rcon.client import AsyncRconClient
from y33bot.rcon.fakes import DEFAULT_LIST_RESPONSE, FakeRconTransport
from y33bot.rcon.pool import LIST_COMMAND, RconPool, parse_list_response
from y33bot.rcon.protocol import (
    RconConnectError,
    RconDisconnectedError,
    RconError,
    RconTimeoutError,
    RconTransport,
)
from y33bot.service import Service
from y33bot.state import StateStore

CONFIG = "config.toml"
AUTH, COMMAND, RESPONSE, AUTH_RESPONSE = 3, 2, 0, 2


# ==================================================================== 脚本化 RCON 服务器
def frame(req_id: int, pkt_type: int, body: bytes, *, terminate: bool = True) -> bytes:
    """手工构造一个 RCON 包；`terminate=False` 用于造「缺 NUL 结尾」的畸形包。"""

    payload = body + (b"\x00\x00" if terminate else b"")
    packet = struct.pack("<ii", req_id, pkt_type) + payload
    return struct.pack("<i", len(packet)) + packet


class ScriptedServer:
    """按回调脚本回包的 RCON 服务器：可以回正常包、畸形包，或直接断开。

    `stop()` 会主动关掉所有已建立的连接，再带超时地 `wait_closed()`：
    Python 3.12 的 `wait_closed()` 会等所有 handler 结束，任何一个测试忘记 close 客户端
    都不应该把整个测试会话挂死。
    """

    def __init__(self, on_command=None, *, auth_reply: bool = True) -> None:
        self.on_command = on_command
        self.auth_reply = auth_reply
        self.commands: list[str] = []
        self._writers: list[asyncio.StreamWriter] = []
        self._server: asyncio.AbstractServer | None = None

    async def __aenter__(self) -> ScriptedServer:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.stop()

    @property
    def port(self) -> int:
        assert self._server is not None
        return self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for writer in list(self._writers):
            try:
                writer.close()
            except OSError:  # pragma: no cover - 已经关掉了
                pass
        self._writers.clear()
        if self._server is not None:
            self._server.close()
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=1.0)
            except TimeoutError:  # pragma: no cover - 极端情况下不阻塞会话
                pass
            self._server = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._writers.append(writer)
        try:
            while True:
                header = await reader.readexactly(4)
                (size,) = struct.unpack("<i", header)
                data = await reader.readexactly(size)
                req_id, pkt_type = struct.unpack("<ii", data[:8])
                body = data[8:-2]
                if pkt_type == AUTH:
                    if self.auth_reply:
                        writer.write(frame(req_id, AUTH_RESPONSE, b""))
                        await writer.drain()
                    continue
                self.commands.append(body.decode())
                if self.on_command is not None:
                    result = self.on_command(req_id, body.decode(), writer)
                    if asyncio.iscoroutine(result):
                        result = await result
                    if result == "close":
                        writer.close()
                        return
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError, OSError):
            return
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except (OSError, ConnectionError):  # pragma: no cover - 关闭失败无所谓
                pass


async def connected_client(server: ScriptedServer, **kwargs) -> AsyncRconClient:
    client = AsyncRconClient("127.0.0.1", server.port, "secret", connect_timeout=1.0, command_timeout=0.3, **kwargs)
    await client.connect()
    return client


# ==================================================================== AsyncRconClient 失败分支
async def test_client_rejects_illegal_packet_size() -> None:
    """对端报出 < 10 的包长（畸形）→ 断连错误，且连接被丢弃。"""

    def respond(req_id: int, _cmd: str, writer: asyncio.StreamWriter):
        writer.write(struct.pack("<i", 4) + b"\x00\x00\x00\x00")

    async with ScriptedServer(respond) as server:
        client = await connected_client(server)
        with pytest.raises(RconDisconnectedError, match="长度非法"):
            await client.command("/list")
        assert client.connected is False


async def test_client_auth_id_mismatch_is_an_error() -> None:
    """鉴权响应的 id 既不是 -1（密码错误）也不是请求 id → 协议异常，连接被丢弃。"""

    async with ScriptedServer() as server:
        client = AsyncRconClient("127.0.0.1", server.port, "secret", connect_timeout=1.0)

        async def fake_read_packet():
            return 4242, AUTH_RESPONSE, b""

        client._read_packet = fake_read_packet  # type: ignore[method-assign]
        with pytest.raises(RconError, match="鉴权响应 id 异常"):
            await client.connect()
        assert client.connected is False


async def test_client_auth_timeout() -> None:
    """鉴权响应不来 → RconTimeoutError（不是连接错误）。"""

    async with ScriptedServer(auth_reply=False) as server:
        client = AsyncRconClient("127.0.0.1", server.port, "secret", connect_timeout=1.0, command_timeout=0.1)
        with pytest.raises(RconTimeoutError, match="鉴权响应超时"):
            await client.connect()
        assert client.connected is False
        await client.close()


async def test_client_auth_handshake_interrupted(monkeypatch: pytest.MonkeyPatch) -> None:
    """握手中发送失败（对端重置连接）→ RconConnectError「鉴权握手中断」，而不是裸 ConnectionError。"""

    class ResettingWriter:
        def write(self, _data: bytes) -> None:
            pass

        async def drain(self) -> None:
            raise ConnectionResetError("对端复位了连接")

        def close(self) -> None:
            pass

        async def wait_closed(self) -> None:
            return None

        def is_closing(self) -> bool:
            return False

    async def fake_open_connection(host: str, port: int):
        return SimpleNamespace(readexactly=None), ResettingWriter()

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    client = AsyncRconClient("127.0.0.1", 25575, "secret", connect_timeout=1.0, command_timeout=0.5)
    with pytest.raises(RconConnectError, match="鉴权握手中断"):
        await client.connect()
    assert client.connected is False


async def test_client_peer_close_during_handshake_is_disconnected() -> None:
    """对端在鉴权后立刻关闭 → 读包阶段判定为「连接被对端关闭」（不是连接错误）。"""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readexactly(4)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        client = AsyncRconClient("127.0.0.1", port, "secret", connect_timeout=1.0, command_timeout=0.5)
        with pytest.raises(RconDisconnectedError, match="连接被对端关闭"):
            await client.connect()
        assert client.connected is False
    finally:
        server.close()
        await server.wait_closed()


async def test_client_connect_oserror_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*_args, **_kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(asyncio, "open_connection", boom)
    client = AsyncRconClient("10.255.255.1", 25575, "secret", connect_timeout=0.2)
    with pytest.raises(RconConnectError, match="连接 10.255.255.1:25575 失败"):
        await client.connect()
    assert client.connected is False


async def test_client_connect_twice_is_a_noop() -> None:
    """已连接时再 connect() 直接返回（不重连、不重复鉴权）。"""

    async with ScriptedServer() as server:
        client = await connected_client(server)
        await client.connect()
        assert client.connected is True
        assert server.commands == []  # 只有鉴权包，没有多余命令
        await client.close()


async def test_client_send_rcon_error_is_reraised_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """发送阶段抛的 RCON 层错误原样上抛（不要被包装成「连接已断开」）。"""

    async with ScriptedServer() as server:
        client = await connected_client(server)

        async def boom(*_args, **_kwargs):
            raise RconDisconnectedError("发送前就发现没连上")

        monkeypatch.setattr(client, "_send", boom)
        with pytest.raises(RconDisconnectedError, match="发送前就发现没连上"):
            await client.command("/list")


async def test_client_read_oserror_is_wrapped_as_disconnected() -> None:
    """读包时底层 OSError（不是半包）→ RconDisconnectedError「读取失败」。"""

    class FailingReader:
        async def readexactly(self, _n: int) -> bytes:
            raise OSError("socket 坏了")

    client = AsyncRconClient("127.0.0.1", 25575, "secret")
    client._reader = FailingReader()  # type: ignore[assignment]
    with pytest.raises(RconDisconnectedError, match="读取失败"):
        await client._read_packet()


async def test_client_drop_ignores_close_errors() -> None:
    """`_drop()` 是尽力而为：close()/wait_closed() 抛错也要静默（退出路径不能被它打断）。"""

    class BrokenWriter:
        def close(self) -> None:
            raise OSError("关不掉")

        async def wait_closed(self) -> None:
            raise ConnectionError("也等不到")

        def is_closing(self) -> bool:
            return False

    client = AsyncRconClient("127.0.0.1", 25575, "secret")
    client._writer = BrokenWriter()  # type: ignore[assignment]
    client._reader = object()  # type: ignore[assignment]
    await client._drop()
    assert client._writer is None and client._reader is None


async def test_client_ignores_mismatched_response_id(caplog: pytest.LogCaptureFixture) -> None:
    """先来一个 id 不匹配的包（丢弃 + 告警），再来正确的包 → 仍返回正确响应。"""

    def respond(req_id: int, _cmd: str, writer: asyncio.StreamWriter):
        writer.write(frame(req_id + 99, RESPONSE, b"stale"))
        writer.write(frame(req_id, RESPONSE, b"fresh"))

    async with ScriptedServer(respond) as server:
        client = await connected_client(server)
        with caplog.at_level("WARNING"):
            assert await client.command("/list") == "fresh"
        assert any("响应 id 不匹配" in record.getMessage() for record in caplog.records)
        await client.close()


async def test_client_keeps_body_without_nul_terminator() -> None:
    """对端发的包体没有 `\\x00\\x00` 结尾（非标准但常见于第三方实现）→ 原样返回，不去尾。"""

    def respond(req_id: int, _cmd: str, writer: asyncio.StreamWriter):
        writer.write(frame(req_id, RESPONSE, b"raw-answer", terminate=False))

    async with ScriptedServer(respond) as server:
        client = await connected_client(server)
        assert await client.command("/list") == "raw-answer"
        await client.close()


async def test_client_multi_packet_read_interrupted_by_disconnect(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """多包响应的第 2 个包读不到（对端断开）→ 保留已收到的部分 + 告警（不整体失败）。"""

    state = {"sent": False}

    def respond(req_id: int, _cmd: str, writer: asyncio.StreamWriter):
        if state["sent"]:
            return "close"
        state["sent"] = True
        writer.write(frame(req_id, RESPONSE, b"first-chunk"))
        return "close"

    async with ScriptedServer(respond) as server:
        client = await connected_client(server)
        with caplog.at_level("WARNING"):
            assert await client.command("/list") == "first-chunk"
        assert client.connected is False


async def test_client_send_failure_is_disconnected(monkeypatch: pytest.MonkeyPatch) -> None:
    async with ScriptedServer(lambda *_args: None) as server:
        client = await connected_client(server)

        async def boom(*_args, **_kwargs):
            raise OSError("broken pipe")

        monkeypatch.setattr(client, "_send", boom)
        with pytest.raises(RconDisconnectedError, match="发送失败"):
            await client.command("/list")
        assert client.connected is False


async def test_client_send_and_read_without_connection() -> None:
    client = AsyncRconClient("127.0.0.1", 25575, "secret")
    with pytest.raises(RconDisconnectedError, match="连接未建立"):
        await client._send(1, COMMAND, "/list")
    with pytest.raises(RconDisconnectedError, match="连接未建立"):
        await client._read_packet()


async def test_client_drain_swallows_errors() -> None:
    """`_drain()` 是「尽力清空」：读到坏包或读不到都不该抛给调用方。"""

    client = AsyncRconClient("127.0.0.1", 25575, "secret")

    async def broken():
        raise RconDisconnectedError("坏了")

    client._read_packet = broken  # type: ignore[method-assign]
    await client._drain()


async def test_rcon_transport_protocol_stubs_are_noop() -> None:
    """`RconTransport` 的方法体是文档占位（`...`）：await 后返回 None，说明协议只声明不实现。"""

    probe = object()
    assert await RconTransport.connect(probe) is None  # type: ignore[arg-type]
    assert await RconTransport.command(probe, "/list") is None  # type: ignore[arg-type]
    assert await RconTransport.close(probe) is None  # type: ignore[arg-type]
    assert RconTransport.connected.__get__(probe) is None


async def test_qq_gateway_protocol_stubs_are_noop() -> None:
    probe = object()
    assert await QQGateway.start(probe) is None  # type: ignore[arg-type]
    assert await QQGateway.send_group_message(probe, None) is None  # type: ignore[arg-type]
    assert await QQGateway.close(probe) is None  # type: ignore[arg-type]


# ==================================================================== RconPool / 解析 / 替身
def make_server(name: str, port: int = 25575):
    from y33bot.config import MCServerConfig

    return MCServerConfig(name=name, host="127.0.0.1", port=port, password_env="PW", log_path=Path("x.log"))


@pytest.mark.parametrize(
    ("raw", "online", "max_players", "players"),
    [
        ("There are 0 of a max of 20 players online:", 0, 20, []),
        ("There are 2 of a max of 20 players online: Steve, Alex", 2, 20, ["Steve", "Alex"]),
        ("there are 1 of a max of 100 players online:  Steve , Alex ", 1, 100, ["Steve", "Alex"]),
        ("There are 1 of a max of 20 players online:Steve", 1, 20, ["Steve"]),
    ],
)
def test_parse_list_response_variants(raw: str, online: int, max_players: int, players: list[str]) -> None:
    listing = parse_list_response(raw)
    assert (listing.online, listing.max_players, listing.players) == (online, max_players, players)


@pytest.mark.parametrize("raw", ["", "   ", "未知输出", "There are a lot of players"])
def test_parse_list_response_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError, match="无法解析 /list 响应"):
        parse_list_response(raw)


def test_pool_rejects_duplicate_names_and_missing_passwords() -> None:
    with pytest.raises(ValueError, match="MC 服名称重复"):
        RconPool([make_server("main"), make_server("main", 25576)], {"main": "pw"}, factory=FakeRconTransport)
    with pytest.raises(ValueError, match="缺少 MC 服 main 的 RCON 密码"):
        RconPool([make_server("main")], {}, factory=FakeRconTransport)


async def test_pool_query_unknown_server_and_start_warning(caplog: pytest.LogCaptureFixture) -> None:
    pool = RconPool([make_server("main")], {"main": "pw"}, factory=FakeRconTransport)
    result = await pool.query("nope", LIST_COMMAND)
    assert result.ok is False and result.error == "未知服务器: nope"

    # 单服离线：start() 只告警，不抛异常（PLAN.md §3.6）
    offline = RconPool(
        [make_server("main")],
        {"main": "pw"},
        factory=lambda **kwargs: FakeRconTransport(**kwargs, online=False),
    )
    with caplog.at_level("WARNING"):
        await offline.start()
    assert any("连接失败（服务继续" in record.getMessage() for record in caplog.records)
    await offline.close()
    assert pool.server_names() == ["main"]


async def test_pool_status_marks_unparseable_as_offline(caplog: pytest.LogCaptureFixture) -> None:
    pool = RconPool(
        [make_server("main")],
        {"main": "pw"},
        factory=lambda **kwargs: FakeRconTransport(**kwargs, responses={LIST_COMMAND: "服务端在胡说"}),
    )
    with caplog.at_level("WARNING"):
        report = await pool.status()
    assert report.per_server == {"main": None}
    assert report.offline == ["main"]
    assert report.total_online == 0
    assert any("无法解析" in record.getMessage() for record in caplog.records)


async def test_pool_broadcast_and_tellraw_shrinking() -> None:
    pool = RconPool([make_server("main")], {"main": "pw"}, factory=FakeRconTransport)
    results = await pool.broadcast_tellraw("你好")
    assert list(results) == ["main"]
    assert results["main"].ok is True

    # 超长文本：逐字符收缩到 1446 字节上限以内
    command = RconPool.build_tellraw("阿" * 2000)
    assert len(command.encode("utf-8")) <= AsyncRconClient.MAX_PAYLOAD_BYTES
    assert command.startswith("tellraw @a ")
    assert RconPool.build_tellraw("") == 'tellraw @a {"text":""}'
    await pool.close()


async def test_fake_rcon_transport_boundaries(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeRconTransport("127.0.0.1", 25575, "pw")
    assert fake.connected is False
    await fake.connect()
    assert fake.connected is True

    # 未配置响应时 /list 走默认文案；其他命令回空串
    assert await fake.command("/list") == DEFAULT_LIST_RESPONSE
    assert await fake.command("say hi") == ""
    assert fake.commands == ["/list", "say hi"]

    listing = fake.set_players(["Steve", "Alex"])
    assert await fake.command("/list") == listing.raw
    assert parse_list_response(await fake.command("/list")).players == ["Steve", "Alex"]

    with pytest.raises(RconError, match="1446 字节上限"):
        await fake.command("x" * 1447)

    await fake.close()
    assert fake.connected is False

    off = FakeRconTransport("127.0.0.1", 25576, "pw", online=False)
    with pytest.raises(RconConnectError, match="假 RCON 服务器离线"):
        await off.connect()
    with pytest.raises(RconConnectError, match="假 RCON 服务器离线"):
        await off.command("/list")  # 命令会自动尝试重连 → 同样失败


async def test_fake_qq_gateway_boundaries() -> None:
    gateway = FakeQQGateway()
    assert gateway.last() is None and gateway.messages() == []
    await gateway.start()
    assert gateway.started is True
    from y33bot.models import OutgoingGroupMessage

    await gateway.send_group_message(OutgoingGroupMessage(group_openid="G-1", text="一"))
    await gateway.send_group_message(OutgoingGroupMessage(group_openid="G-1", text="二"))
    assert gateway.messages() == ["一", "二"]
    assert gateway.last() is not None and gateway.last().text == "二"  # type: ignore[union-attr]
    gateway.clear()
    assert gateway.messages() == []
    await gateway.close()
    assert gateway.started is False
    assert isinstance(gateway, QQGateway)


# ==================================================================== qq/gateway 生命周期
class StubSdkMessage:
    group_openid = "G-1"
    id = "M-1"
    content = "#你好"

    class _Author:
        member_openid = "OP-1"

    author = _Author()


def stub_botpy(*, ret_coro: bool) -> SimpleNamespace:
    """假 botpy：`Client.start()` 里主动触发 SDK 的 on_ready / 群消息回调。"""

    class StubClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc) -> None:
            return None

        async def start(self, app_id, app_secret, *, ret_coro: bool = False):
            assert app_id and app_secret
            await self.on_ready()
            await self.on_group_at_message_create(StubSdkMessage())
            if not ret_coro:
                return None

            async def waiter() -> None:
                await asyncio.sleep(0)

            return waiter()

        async def close(self) -> None:
            self.closed = True

    return SimpleNamespace(Client=StubClient, Intents=lambda **kwargs: kwargs)


async def test_gateway_start_success_runs_sdk_callbacks(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """`start()` 成功路径：网关就绪、SDK 回调被转发给 handler（on_ready + 群消息）。"""

    monkeypatch.setattr(gateway_module, "botpy", stub_botpy(ret_coro=False))
    seen: list[str] = []

    async def handler(message) -> str | None:  # noqa: ANN001
        seen.append(message.content)
        return None

    gateway = BotpyGateway(app.config, ("id", "secret"), app.state(), handler=handler, startup_timeout=2.0)
    await gateway.start()
    assert gateway._up_event is not None and gateway._up_event.is_set()
    gateway._signal_up(RuntimeError("重复就绪"))  # 事件已 set → 只记错误，不重复 set
    assert gateway._up_error is not None
    await asyncio.sleep(0)
    assert seen == ["#你好"]
    await gateway.close()
    assert gateway._task is None


async def test_gateway_start_success_awaits_returned_coroutine(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """`bot.start(..., ret_coro=True)` 返回协程时也要 await（否则网关任务会提前结束）。"""

    monkeypatch.setattr(gateway_module, "botpy", stub_botpy(ret_coro=True))

    async def handler(_message) -> str | None:  # noqa: ANN001
        return None

    gateway = BotpyGateway(app.config, ("id", "secret"), app.state(), handler=handler, startup_timeout=2.0)
    await gateway.start()
    await asyncio.sleep(0)
    await gateway.close()


async def test_gateway_start_times_out_when_never_ready(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """SDK 一直不回调 on_ready → startup_timeout 后快速失败（不无限等）。"""

    class HangingClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc) -> None:
            return None

        async def start(self, *_args, **_kwargs):
            await asyncio.sleep(30)

        async def close(self) -> None:
            return None

    monkeypatch.setattr(gateway_module, "botpy", SimpleNamespace(Client=HangingClient, Intents=lambda **kwargs: kwargs))
    gateway = BotpyGateway(app.config, ("id", "secret"), app.state(), handler=lambda _m: None, startup_timeout=0.05)  # type: ignore[arg-type]
    with pytest.raises(QQGatewayError, match="内未就绪"):
        await gateway.start()
    await gateway.close()


async def test_gateway_run_client_propagates_cancellation(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """取消网关任务时 `CancelledError` 必须继续往上抛（否则 asyncio 会认为退出异常）。"""

    class HangingClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc) -> None:
            return None

        async def start(self, *_args, **_kwargs):
            await asyncio.sleep(30)

        async def close(self) -> None:
            return None

    monkeypatch.setattr(gateway_module, "botpy", SimpleNamespace(Client=HangingClient, Intents=lambda **kwargs: kwargs))
    gateway = BotpyGateway(app.config, ("id", "secret"), app.state(), handler=lambda _m: None)  # type: ignore[arg-type]
    gateway._client = gateway._build_client()
    task = asyncio.create_task(gateway._run_client())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_gateway_close_swallows_client_errors(app: App, caplog: pytest.LogCaptureFixture) -> None:
    class BrokenClient:
        async def close(self) -> None:
            raise RuntimeError("SDK 关闭失败")

    gateway = BotpyGateway(app.config, ("id", "secret"), app.state(), handler=lambda _m: None)  # type: ignore[arg-type]
    gateway._client = BrokenClient()
    with caplog.at_level("WARNING"):
        await gateway.close()
    assert any("关闭 QQ 网关失败" in record.getMessage() for record in caplog.records)
    assert gateway._client is None


# ==================================================================== mclog/watcher 失败分支
def make_watcher(app: App, store: StateStore) -> LogWatcher:
    server = app.config.server("main")
    assert server is not None
    return LogWatcher(server, app.config.patterns, store)


def test_watcher_inode_change_triggers_rotation(app: App, caplog: pytest.LogCaptureFixture) -> None:
    """inode 变化（size 没变小）也要判定为轮转：偏移归零、整文件重读、告警一次。"""

    line = "[12:00:01] [Server thread/INFO]: Steve joined the game\n"
    app.write_log(line)
    store = app.state()
    watcher = make_watcher(app, store)
    assert len(watcher.poll_new_events()) == 1

    store.server_state("main").log_inode = "1"  # 与真实 inode 不同（Windows 下 inode 通常为 0）
    app.write_log(line)
    with caplog.at_level("WARNING"):
        events = watcher.poll_new_events()
    assert any("日志文件已轮转" in record.getMessage() for record in caplog.records)
    assert store.server_state("main").log_offset == len(line) * 2
    assert [event.player for event in events] == ["Steve", "Steve"]  # 偏移归零 → 整文件重读


def test_watcher_read_failure_is_reported(app: App, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    app.write_log("[12:00:01] [Server thread/INFO]: Steve joined the game\n")
    watcher = make_watcher(app, app.state())
    real_open = Path.open

    def fake_open(self: Path, *args, **kwargs):
        if self.name == "main.log":
            raise OSError("被 MC 独占")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)
    with caplog.at_level("WARNING"):
        assert watcher.poll_new_events() == []
    assert any("日志读取失败" in record.getMessage() for record in caplog.records)


def test_watcher_empty_read_returns_nothing(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """stat 说文件有内容、read() 却拿到空（正好被截断）→ 返回空，不推进偏移。"""

    app.write_log("[12:00:01] [Server thread/INFO]: Steve joined the game\n")
    store = app.state()
    watcher = make_watcher(app, store)

    class EmptyHandle:
        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def seek(self, *_args) -> int:
            return 0

        def read(self) -> bytes:
            return b""

    real_open = Path.open

    def fake_open(self: Path, *args, **kwargs):
        if self.name == "main.log":
            return EmptyHandle()
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)
    assert watcher.poll_new_events() == []
    assert store.server_state("main").log_offset == 0


def test_watcher_skips_blank_lines(app: App) -> None:
    app.write_log("\n   \n[12:00:01] [Server thread/INFO]: Steve joined the game\n\n")
    watcher = make_watcher(app, app.state())
    events = watcher.poll_new_events()
    assert [event.player for event in events] == ["Steve"]


def test_watcher_partial_line_is_buffered_then_completed(app: App) -> None:
    first = "[12:00:01] [Server thread/INFO]: Steve joined the game\n"
    partial = "[12:00:02] [Server thread/INFO]: Alex jo"
    app.write_log(first + partial)
    watcher = make_watcher(app, app.state())

    events = watcher.poll_new_events()
    assert [event.player for event in events] == ["Steve"]
    assert watcher.buffered_bytes == len(partial)  # 残行留在缓冲区

    app.write_log("ined the game\n")
    events = watcher.poll_new_events()
    assert [event.player for event in events] == ["Alex"]
    assert watcher.buffered_bytes == 0


# ==================================================================== service.py 失败分支
class RecordingState(StateStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.saves = 0

    def save(self) -> None:
        self.saves += 1
        super().save()


class BrokenClose:
    async def close(self) -> None:
        raise RuntimeError("关不掉")


def make_service(app: App, **kwargs) -> Service:
    return Service(app.config, env=app.env, config_path=app.config_path, **kwargs)


async def test_service_shutdown_tolerates_close_failures(app: App, caplog: pytest.LogCaptureFixture) -> None:
    service = make_service(app, gateway=BrokenClose(), pool=BrokenClose())
    service._state = RecordingState(app.config.state_path)
    with caplog.at_level("WARNING"):
        await service.shutdown()
    messages = [record.getMessage() for record in caplog.records]
    assert any("关闭 QQ 网关失败" in message for message in messages)
    assert any("关闭 RCON 连接失败" in message for message in messages)
    assert service._state.saves == 1  # 关闭失败也必须落盘
    assert (app.config.state_path).exists()


async def test_service_startup_checks_unreadable_log(app: App) -> None:
    """日志路径存在但打不开（这里是目录）→ 该项 FAIL，而不是抛异常。"""

    log_dir = app.root / "logs" / "as-dir.log"
    log_dir.mkdir()
    config_path = app.root / "config2.toml"
    config_path.write_text(config_text(log_path=log_dir), encoding="utf-8")
    config = load_config(config_path, app.env)
    pool = RconPool(config.servers, config.rcon_passwords(app.env), factory=FakeRconTransport)
    service = Service(config, env=app.env, config_path=config_path, pool=pool)
    results = await service.startup_checks()
    log_result = next(item for item in results if item.label == "日志 main")
    assert log_result.ok is False and "不可读" in log_result.detail
    # 同一份「读不出来的 latest.log」也让模板项走跳过分支：OK + 不影响退出码
    template_result = next(item for item in results if item.label == "日志模板 main")
    assert template_result.ok is True
    assert template_result.detail == "未找到可判定的样例行，跳过"


async def test_service_log_loop_survives_watcher_and_bridge_errors(app: App, caplog: pytest.LogCaptureFixture) -> None:
    """轮询/处理单个事件失败都不能让常驻循环退出（只留痕）。"""

    from y33bot.models import MCLogEvent

    class BrokenWatcher:
        def poll_new_events(self):
            raise RuntimeError("日志文件炸了")

    class OneEventWatcher:
        def poll_new_events(self):
            return [MCLogEvent(server="main", kind="join", player="Steve", message=None, raw="x", occurred_at=0.0)]

    class BrokenBridge:
        async def handle_log_event(self, _event) -> None:
            raise RuntimeError("桥炸了")

    service = make_service(app)
    service._state = RecordingState(app.config.state_path)
    service._watchers = {"main": BrokenWatcher()}  # type: ignore[dict-item]
    service._bridge = BrokenBridge()  # type: ignore[assignment]

    with caplog.at_level("ERROR"):
        task = asyncio.create_task(service._log_loop())
        await asyncio.sleep(0.15)
        service._watchers = {"main": OneEventWatcher()}  # type: ignore[dict-item]
        await asyncio.sleep(0.15)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    messages = [record.getMessage() for record in caplog.records]
    assert any("日志轮询异常" in message for message in messages)
    assert any("处理日志事件失败" in message for message in messages)
    assert service._state.saves >= 1  # 有事件就必须落盘偏移


async def test_service_health_loop_reports_errors_and_saves_flips(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    app = App(tmp_path, health_poll_interval=0.05)  # 缩短轮询间隔，避免测试等 5s

    class FlakyBridge:
        def __init__(self) -> None:
            self.calls = 0

        async def poll_health(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("探测炸了")
            return [("main", True)]

    service = make_service(app)
    service._state = RecordingState(app.config.state_path)
    service._bridge = FlakyBridge()  # type: ignore[assignment]

    with caplog.at_level("ERROR"):
        task = asyncio.create_task(service._health_loop())
        await asyncio.sleep(0.2)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert any("健康轮询异常" in record.getMessage() for record in caplog.records)
    assert service._state.saves >= 1


async def test_service_signal_handlers_prefer_loop(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """事件循环支持 add_signal_handler 时优先用它；回调置位停止事件。"""

    installed: list[int] = []
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(type(loop), "add_signal_handler", lambda self, sig, cb: installed.append(sig))

    service = make_service(app)
    service._install_signal_handlers()
    assert len(installed) == 2  # SIGINT + SIGTERM

    service._stop_event = asyncio.Event()
    service._on_loop_signal()
    assert service._signal_flag.is_set() and service._stop_event.is_set()


async def test_service_signal_handlers_fall_back_to_signal_module(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """平台不支持 add_signal_handler（Windows）→ 退回 signal.signal，同步回调同样能停服务。"""

    import signal as signal_module

    def unsupported(self, *_args, **_kwargs):
        raise NotImplementedError("Windows 不支持")

    recorded: dict[int, object] = {}
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(type(loop), "add_signal_handler", unsupported)
    monkeypatch.setattr(signal_module, "signal", lambda sig, handler: recorded.__setitem__(sig, handler) or handler)

    service = make_service(app)
    service._install_signal_handlers()
    assert set(recorded) == {signal_module.SIGINT, signal_module.SIGTERM}

    service._stop_event = asyncio.Event()
    handler = recorded[signal_module.SIGINT]
    handler(signal_module.SIGINT, None)  # type: ignore[operator]
    assert service._signal_flag.is_set() and service._stop_event.is_set()


async def test_service_wait_for_stop_polls_and_returns(app: App) -> None:
    """事件循环休眠唤不醒时，0.5s 轮询兜底仍能返回（Windows 同步信号场景）。"""

    service = make_service(app)
    service._stop_event = asyncio.Event()

    async def stop_later() -> None:
        await asyncio.sleep(0.6)  # 跨过至少一次 0.5s 超时
        service._stop_event.set()

    stopper = asyncio.create_task(stop_later())
    await asyncio.wait_for(service._wait_for_stop(), timeout=3.0)
    await stopper
    assert service._stop_event.is_set()


async def test_service_run_closes_pool_when_credentials_missing(app: App, caplog: pytest.LogCaptureFixture) -> None:
    """缺 QQ 凭据时 `run` 退出前必须关掉已经连上的 RCON（不留悬挂连接）。"""

    pool = app.make_pool()
    await pool.start()
    service = Service(app.config, env={"MC_RCON_PASSWORD_MAIN": "pw"}, config_path=app.config_path, pool=pool)
    with caplog.at_level("ERROR"):
        assert await service.run() == 1
    assert any("QQ_BOT_APP_ID" in record.getMessage() for record in caplog.records)
    assert all(not client.connected for client in pool._clients.values())  # type: ignore[attr-defined]


async def test_service_run_builds_gateway_from_credentials(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """凭据齐全时 `run` 会用它们构造真网关（这里把 `BotpyGateway` 换成桩，避免真连 QQ）。"""

    from y33bot import service as service_module

    created: dict[str, object] = {}

    class StubBotpy:
        def __init__(self, config, credentials, state, *, handler=None, **_kwargs) -> None:
            created["credentials"] = credentials
            created["config_is_same"] = config is app.config
            created["handler"] = handler
            self.closed = False
            self._closed: asyncio.Event | None = asyncio.Event()

        async def start(self) -> None:
            created["started"] = True

        async def send_group_message(self, _message) -> None:  # pragma: no cover - run 里不会调用
            return None

        async def wait_closed(self) -> None:
            # 真网关会等 SDK 协程结束；这个桩一直等到 close()（= 优雅退出），不误报「网关断开」
            assert self._closed is not None
            await self._closed.wait()

        async def close(self) -> None:
            self.closed = True
            assert self._closed is not None
            self._closed.set()

    monkeypatch.setattr(service_module, "BotpyGateway", StubBotpy)
    service = Service(app.config, env=app.env, config_path=app.config_path, pool=app.make_pool())

    task = asyncio.create_task(service.run())
    await asyncio.sleep(0.1)  # 等网关/监听起好
    service._on_loop_signal()  # 触发优雅退出
    assert await task == 0
    assert created["credentials"] == (app.env["QQ_BOT_APP_ID"], app.env["QQ_BOT_APP_SECRET"])
    assert created["started"] is True and created["config_is_same"] is True
    assert callable(created["handler"])


async def test_service_run_rejects_corrupt_bindings(app: App, caplog: pytest.LogCaptureFixture) -> None:
    app.config.bindings_path.parent.mkdir(parents=True, exist_ok=True)
    app.config.bindings_path.write_text("这不是 TOML =", encoding="utf-8")
    service = make_service(app)
    with caplog.at_level("ERROR"):
        assert await service.run() == 1
    assert any("错误" in record.getMessage() for record in caplog.records)


# ==================================================================== CLI 失败分支
@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> App:
    for key, value in DEFAULT_ENV.items():
        monkeypatch.setenv(key, value)
    app = App(tmp_path)
    monkeypatch.chdir(tmp_path)
    return app


def corrupt_bindings(app: App) -> None:
    app.config.bindings_path.parent.mkdir(parents=True, exist_ok=True)
    app.config.bindings_path.write_text("这不是 TOML =", encoding="utf-8")


def run(argv: Sequence[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, list[str], str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out.strip().splitlines(), captured.err


def test_cli_bind_reads_corrupt_file(workdir: App, capsys) -> None:
    corrupt_bindings(workdir)
    code, _out, err = run(["bind", "list", "--config", CONFIG], capsys)
    assert code == 1 and "绑定表不是合法 TOML" in err

    code, _out, err = run(["bind", "set", "OP-1", "Steve", "--config", CONFIG], capsys)
    assert code == 1 and "绑定表不是合法 TOML" in err


def test_cli_bind_missing_config(workdir: App, capsys) -> None:
    code, _out, err = run(["bind", "list", "--config", "nope.toml"], capsys)
    assert code == 1 and "配置文件不存在" in err


def test_cli_bind_set_blank_openid(workdir: App, capsys) -> None:
    code, _out, err = run(["bind", "set", "   ", "Steve", "--config", CONFIG], capsys)
    assert code == 1 and "openid 不能为空" in err


def test_cli_bind_save_failure_is_reported(workdir: App, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(self, _openid, _game_id):
        raise BindingError("磁盘满了")

    monkeypatch.setattr(BindingStore, "bind", boom)
    code, _out, err = run(["bind", "set", "OP-1", "Steve", "--config", CONFIG], capsys)
    assert code == 1 and "磁盘满了" in err


def test_cli_bind_empty_list_and_missing_remove(workdir: App, capsys) -> None:
    code, out, _err = run(["bind", "list", "--config", CONFIG], capsys)
    assert code == 0 and out == ["[绑定] 无绑定记录"]
    code, out, _err = run(["bind", "remove", "OP-MISSING", "--config", CONFIG], capsys)
    assert code == 0 and out == ["[绑定] 未找到 OP-MISSING"]


def test_cli_simulate_reports_corrupt_bindings(workdir: App, capsys) -> None:
    corrupt_bindings(workdir)
    code, _out, err = run(
        ["simulate", "group-message", "--openid", "OP-1", "--content", "#hi", "--dry-run", "--config", CONFIG],
        capsys,
    )
    assert code == 1 and "绑定表不是合法 TOML" in err

    code, _out, err = run(
        ["simulate", "log-event", "--server", "main", "--kind", "join", "--player", "Steve", "--config", CONFIG],
        capsys,
    )
    assert code == 1 and "绑定表不是合法 TOML" in err


def test_cli_simulate_health_unknown_server(workdir: App, capsys) -> None:
    code, _out, err = run(["simulate", "health", "--server", "nope", "--offline", "--config", CONFIG], capsys)
    assert code == 1 and "未知服务器: nope" in err


def test_cli_simulate_bad_config(workdir: App, capsys) -> None:
    code, _out, err = run(
        ["simulate", "group-message", "--openid", "OP-1", "--content", "#hi", "--dry-run", "--config", "nope.toml"],
        capsys,
    )
    assert code == 1 and "配置文件不存在" in err


def test_cli_display_path_for_outside_path(workdir: App) -> None:
    """不在 CWD 之下（含 `..`）时打印绝对路径，方便定位真实文件。"""

    outside = workdir.root.parent / "other" / "bindings.toml"
    assert _display_path(outside) == str(outside)
    assert _display_path(workdir.config.bindings_path) == "data/bindings.toml"
