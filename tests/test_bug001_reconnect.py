"""BUG-001 取证：`ret_coro=True` 下 SDK 自带的重连驱动不执行（S5/S6/S7）。

本文件的用例**不连 QQ**，只用假 connect 驱动 `botpy` 自己的 `ConnectionSession.multi_run()`
（源码 `botpy/connection.py:48-67`），或用假 `botpy.Client` 驱动我们的
`BotpyGateway._run_client()`（`src/y33bot/qq/gateway.py:123-138`）与 `Service.run()`
（`src/y33bot/service.py:205-221`）。

它证明的是「`qq-botpy==1.2.1` 的行为 + 我们对它的用法」；**不**证明真机上 QQ 断线时
一定走到这条路径（那条只能真机验证，见 `BUGS.md` 疑点 Q1/Q3）。
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from botpy.connection import ConnectionSession  # type: ignore[import-not-found]

from conftest import App
from y33bot.qq import gateway as gateway_module
from y33bot.qq.gateway import BotpyGateway
from y33bot.service import Service
from y33bot.state import StateStore


def _make_connection(connect_calls: list[dict]) -> ConnectionSession:
    """真 SDK 的 `ConnectionSession` + 假 connect（记录每次建连，并在结束时把会话回填队列）。"""

    connection: ConnectionSession | None = None

    async def connect(session: dict) -> None:
        connect_calls.append(session)
        await asyncio.sleep(0.02)  # 模拟「建连 + 收消息」的一段时间
        assert connection is not None
        connection.add(session)  # 等价于 botpy/gateway.py:66 on_closed 里的回填

    connection = ConnectionSession(
        max_async=1,
        connect=connect,
        dispatch=lambda *_args, **_kwargs: None,
        api=None,
    )
    return connection


def _new_session() -> dict:
    return {"session_id": "", "last_seq": 0, "intent": 1, "url": "wss://offline"}


async def test_multi_run_starts_each_session_once_and_never_again() -> None:
    """S6：`multi_run()` 先排空会话列表、再 `await asyncio.wait(...)`；回填的会话不会自己启动。"""

    calls: list[dict] = []
    connection = _make_connection(calls)
    session = _new_session()
    connection.add(session)

    await asyncio.wait_for(connection.multi_run(session_interval=0), timeout=5)
    assert calls == [session]
    assert connection._session_list == [session]  # 断线后会话被回填，队列非空
    await asyncio.sleep(0.1)
    assert calls == [session]  # ……但没有任何人再启动它：不复连

    # 反证：会话本身没坏，缺的只是「驱动」——再调一次 multi_run 就能重新启动
    await asyncio.wait_for(connection.multi_run(session_interval=0), timeout=5)
    assert calls == [session, session]


class _FakeSDKClient:
    """假 `botpy.Client`：`start(ret_coro=True)` 把真 SDK `multi_run()` 的协程还给调用方。

    照抄 `botpy/client.py:217-223`：`ret_coro=True` 时 `return coroutine`，
    `while not self._closed:` 这层重连驱动立即退出、再也不回来。
    """

    instances: list[_FakeSDKClient] = []

    def __init__(self, **_kwargs) -> None:
        self.connect_calls: list[dict] = []
        self._connection = _make_connection(self.connect_calls)
        self._connection.add(_new_session())
        self.closed = False
        _FakeSDKClient.instances.append(self)

    async def __aenter__(self) -> _FakeSDKClient:
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def start(self, app_id: str, secret: str, *, ret_coro: bool = False):
        assert ret_coro is True  # F5：我们固定用 ret_coro=True
        assert app_id and secret
        return self._connection.multi_run(session_interval=0)

    async def close(self) -> None:
        self.closed = True


async def test_service_stays_alive_when_sdk_gateway_coroutine_returns(
    app: App, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """整链复刻 H1：网关协程正常返回 → `_run_client` 静默结束 → `Service.run()` 仍常驻、无 `[错误]`。"""

    _FakeSDKClient.instances.clear()
    monkeypatch.setattr(
        gateway_module,
        "botpy",
        type("B", (), {"Client": _FakeSDKClient, "Intents": lambda **kwargs: kwargs}),
    )

    gateway = BotpyGateway(
        app.config,
        ("app-id", "app-secret"),
        StateStore.load(app.config.state_path),
        handler=lambda message: None,  # type: ignore[arg-type,return-value]
        startup_timeout=1.0,
    )
    service = Service(
        app.config,
        env=app.env,
        config_path=app.config_path,
        gateway=gateway,
        pool=app.make_pool(),
    )

    with caplog.at_level(logging.DEBUG):
        task = asyncio.create_task(service.run())
        try:
            for _ in range(100):
                if gateway._task is not None and gateway._task.done():
                    break
                await asyncio.sleep(0.02)
            assert gateway._task is not None and gateway._task.done() is True  # 网关协程已返回
            await asyncio.sleep(0.2)

            assert gateway._up_error is None
            assert task.done() is False  # 服务仍在 _wait_for_stop()：不退出、不重启、不告警
            assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

            fake = _FakeSDKClient.instances[0]
            assert len(fake.connect_calls) == 1  # 断线后没有第二次建连尝试
            assert len(fake._connection._session_list) == 1  # 会话还躺在队列里，永远等不到启动
            assert any("[启动] QQ 网关已连接" in r.getMessage() for r in caplog.records)
        finally:
            service._signal_flag.set()
            assert await asyncio.wait_for(task, timeout=10) == 0
