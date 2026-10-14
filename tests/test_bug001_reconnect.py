"""BUG-001 回归：`ret_coro=True` 下 SDK 自带的重连驱动不执行（S5/S6/S7），我们据此报错退出。

本文件的用例**不连 QQ**，只用假 connect 驱动 `botpy` 自己的 `ConnectionSession.multi_run()`
（源码 `botpy/connection.py:48-67`），或用假 `botpy.Client` 驱动我们的
`BotpyGateway._run_client()`（`src/y33bot/qq/gateway.py`）与 `Service.run()`
（`src/y33bot/service.py`）。

背景：SDK 在 `ret_coro=True` 时把重连驱动（`while not self._closed`）交给我们，而它的
`multi_run()` 是一次性的（会话被回填后没人再启动）。所以「网关协程结束」= 收方向永久失效，
**不能**默默常驻：修复后 `Service.run()` 必须打 `[错误]` 并以非 0 退出，交给 `systemd`/`nssm` 拉起。

真机上 token 过期是否一定触发这条路径仍未验证（见 `BUGS.md` 疑点 Q1/Q3）。
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


async def test_service_reports_and_exits_when_sdk_gateway_coroutine_returns(
    app: App, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """整链回归：网关协程正常返回 → `Service.run()` 打 `[错误]`、返回 1（修复前：静默常驻）。"""

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
        code = await asyncio.wait_for(service.run(), timeout=10)

    assert code == 1  # 非 0 退出：交给 systemd/nssm 拉起（用户 2026-10-15 拍板的口径）
    messages = [record.getMessage() for record in caplog.records]
    assert any(message == "[错误] QQ 网关已断开（收不到群消息），进程退出等待重启" for message in messages)
    assert any("[停止] 已退出" in message for message in messages)  # 仍然走优雅关闭

    fake = _FakeSDKClient.instances[0]
    assert len(fake.connect_calls) == 1  # 断线后没有第二次建连：我们不假装能自愈
    assert len(fake._connection._session_list) == 1  # 会话还躺在队列里，永远等不到启动
    assert fake.closed is True  # 退出路径走完了 shutdown()，网关被真正关掉
    assert gateway._task is None and gateway._client is None
    assert any("[启动] QQ 网关已连接" in message for message in messages)
