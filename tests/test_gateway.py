"""qq.gateway 测试：SDK 适配层的规则与文案（PLAN.md A5 / A12 / R23 / T7）。

botpy 的真实网关不在这里连：用桩对象替代 `client.api`。
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from conftest import App
from y33bot.models import MCGroupMessage, OutgoingGroupMessage
from y33bot.qq import gateway as gateway_module
from y33bot.qq.gateway import BotpyGateway, QQGatewayError, normalize_content
from y33bot.state import StateStore


class StubAPI:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def post_group_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": str(len(self.calls))}


class StubClient:
    def __init__(self) -> None:
        self.api = StubAPI()
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class StubAuthor:
    def __init__(self, member_openid: str | None) -> None:
        self.member_openid = member_openid


class StubMessage:
    def __init__(self, *, group_openid="G-1", message_id="M-1", content="#hi", member_openid="OP-1") -> None:
        self.group_openid = group_openid
        self.id = message_id
        self.content = content
        self.author = StubAuthor(member_openid)


def make_gateway(app: App, handler=None, state: StateStore | None = None) -> tuple[BotpyGateway, StubClient]:
    store = state if state is not None else StateStore.load(app.config.state_path)
    calls: list[MCGroupMessage] = []

    async def default_handler(message: MCGroupMessage) -> str | None:
        calls.append(message)
        return None

    gateway = BotpyGateway(
        app.config,
        ("app-id", "app-secret"),
        store,
        handler=handler if handler is not None else default_handler,
        logger=None,
    )
    client = StubClient()
    gateway._client = client  # 直接注入桩客户端
    gateway.calls = calls  # type: ignore[attr-defined]
    return gateway, client


# ------------------------------------------------------------------ 内容归一化
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("<@!1234> #你好", "#你好"),
        ("<@1234>#你好", "#你好"),
        ("   #你好  ", "#你好"),
        ("#你好", "#你好"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_content(raw, expected: str) -> None:
    assert normalize_content(raw) == expected


# ------------------------------------------------------------------ 发送
async def test_send_active_message_uses_persisted_seq(app: App) -> None:
    gateway, client = make_gateway(app)
    state = StateStore.load(app.config.state_path)
    state.state.qq_msg_seq = 36
    gateway._state = state

    await gateway.send_group_message(OutgoingGroupMessage(group_openid="G-1", text="主动消息"))
    assert client.api.calls[0] == {
        "group_openid": "G-1",
        "msg_type": 0,
        "content": "主动消息",
        "msg_id": None,
        "msg_seq": 37,
    }
    assert state.state.qq_msg_seq == 37
    # 序号必须落盘（A12），重启用同一个文件继续递增
    reloaded = StateStore.load(app.config.state_path)
    assert reloaded.state.qq_msg_seq == 37


async def test_send_passive_reply_uses_seq_one(app: App) -> None:
    gateway, client = make_gateway(app)
    await gateway.send_group_message(
        OutgoingGroupMessage(group_openid="G-1", text="被动回复", reply_to_message_id="MSG-9")
    )
    assert client.api.calls[0]["msg_id"] == "MSG-9"
    assert client.api.calls[0]["msg_seq"] == 1


async def test_send_skips_empty_payload(app: App, caplog: pytest.LogCaptureFixture) -> None:
    gateway, client = make_gateway(app)
    with caplog.at_level("WARNING"):
        await gateway.send_group_message(OutgoingGroupMessage(group_openid="G-1", text="   "))
        await gateway.send_group_message(OutgoingGroupMessage(group_openid="", text="hi"))
    assert client.api.calls == []
    assert len([r for r in caplog.records if "已跳过" in r.getMessage()]) == 2


async def test_send_without_client_raises(app: App) -> None:
    gateway, _client = make_gateway(app)
    gateway._client = None
    with pytest.raises(QQGatewayError, match="未启动"):
        await gateway.send_group_message(OutgoingGroupMessage(group_openid="G-1", text="hi"))


async def test_send_failure_is_logged_not_retried(app: App, caplog: pytest.LogCaptureFixture) -> None:
    gateway, client = make_gateway(app)

    async def boom(**kwargs):
        raise RuntimeError("API 500")

    client.api.post_group_message = boom  # type: ignore[method-assign]
    with caplog.at_level("ERROR"):
        await gateway.send_group_message(OutgoingGroupMessage(group_openid="G-1", text="hi"))
    assert any("QQ 发送失败（不重试）" in record.getMessage() for record in caplog.records)


# ------------------------------------------------------------------ 收
async def test_incoming_message_passes_to_handler_and_replies(app: App) -> None:
    received: list[MCGroupMessage] = []

    async def handler(message: MCGroupMessage) -> str | None:
        received.append(message)
        return "收到"

    gateway, client = make_gateway(app, handler=handler)
    await gateway._on_group_at_message_create(StubMessage(content="<@!42> #你好", member_openid="OP-9"))

    assert len(received) == 1
    assert received[0].content == "#你好"
    assert received[0].member_openid == "OP-9"
    assert received[0].message_id == "M-1"
    assert received[0].received_at > 0
    assert client.api.calls[0]["content"] == "收到"
    assert client.api.calls[0]["msg_id"] == "M-1"


async def test_incoming_message_without_openid_dropped(app: App, caplog: pytest.LogCaptureFixture) -> None:
    gateway, client = make_gateway(app)
    with caplog.at_level("WARNING"):
        await gateway._on_group_at_message_create(StubMessage(member_openid=None))
        await gateway._on_group_at_message_create(StubMessage(group_openid=""))
    assert client.api.calls == []
    assert len([r for r in caplog.records if "已丢弃" in r.getMessage()]) == 2


async def test_handler_exception_is_logged(app: App, caplog: pytest.LogCaptureFixture) -> None:
    async def boom(message: MCGroupMessage) -> str | None:
        raise RuntimeError("炸了")

    gateway, client = make_gateway(app, handler=boom)
    with caplog.at_level("ERROR"):
        await gateway._on_group_at_message_create(StubMessage())
    assert client.api.calls == []
    assert any("群消息处理失败" in record.getMessage() or record.exc_info for record in caplog.records)


async def test_no_reply_means_no_message(app: App) -> None:
    gateway, client = make_gateway(app)
    await gateway._on_group_at_message_create(StubMessage(content="#hi"))
    assert client.api.calls == []


# ------------------------------------------------------------------ 生命周期
async def test_start_requires_botpy(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gateway_module, "botpy", None)
    gateway, _client = make_gateway(app)
    with pytest.raises(QQGatewayError, match="qq-botpy 未安装"):
        await gateway.start()


async def test_start_fails_fast_when_gateway_never_comes_up(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    class StubBotpyClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc) -> None:
            return None

        async def start(self, *_args, **_kwargs):
            raise RuntimeError("凭据无效")

    monkeypatch.setattr(
        gateway_module,
        "botpy",
        type("B", (), {"Client": StubBotpyClient, "Intents": lambda **kwargs: kwargs}),
    )
    gateway = BotpyGateway(
        app.config,
        ("id", "secret"),
        StateStore.load(app.config.state_path),
        handler=lambda message: None,  # type: ignore[arg-type]
        startup_timeout=1.0,
    )
    with pytest.raises(QQGatewayError) as excinfo:
        await gateway.start()
    # BUG-005：`start()` 不再自加「QQ 网关启动失败」前缀（唯一前缀在 service.py），
    # 异常文案就是底层原因，且原始异常仍作为 cause 保留。
    assert str(excinfo.value) == "凭据无效"
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    await gateway.close()


async def test_close_is_idempotent(app: App) -> None:
    gateway, client = make_gateway(app)
    await gateway.close()
    await gateway.close()
    assert client.closed is True


async def test_close_cancels_running_task(app: App) -> None:
    import asyncio

    gateway, client = make_gateway(app)

    async def forever() -> None:
        await asyncio.sleep(3600)

    gateway._task = asyncio.create_task(forever())
    await gateway.close()
    assert gateway._task is None
    assert client.closed is True


# ------------------------------------------------------------------ 网关协程正常返回 = 静默（BUG-001 取证）
class _FakeSDKClient:
    """`botpy.Client` 的离线替身：`start(ret_coro=True)` 返回的协程「连上、随后结束」。

    `start()` 只返回协程对象、不 await 它 —— 与 `botpy/client.py:217-223`（`ret_coro=True` 时
    `return coroutine`）一致；协程体本身等价于 `botpy/connection.py:67` 的
    `await asyncio.wait(tasks)` 返回、`multi_run()` 结束。
    """

    instances: list[_FakeSDKClient] = []

    def __init__(self, **_kwargs) -> None:
        self.start_args: tuple[str, str, bool] | None = None
        self.closed = False
        _FakeSDKClient.instances.append(self)

    async def __aenter__(self) -> _FakeSDKClient:
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def start(self, app_id: str, secret: str, *, ret_coro: bool = False):
        self.start_args = (app_id, secret, ret_coro)
        assert ret_coro is True  # F5：我们固定用 ret_coro=True 起网关

        async def gateway_coroutine() -> None:
            await asyncio.sleep(0.05)

        return gateway_coroutine()

    async def close(self) -> None:
        self.closed = True


def _install_fake_botpy(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSDKClient.instances.clear()
    monkeypatch.setattr(
        gateway_module,
        "botpy",
        type("B", (), {"Client": _FakeSDKClient, "Intents": lambda **kwargs: kwargs}),
    )


async def test_gateway_coroutine_end_is_silent(
    app: App, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """BUG-001 取证 F2 / S7：SDK 网关协程「正常返回」时，`_run_client` 不抛异常、一行日志都不多打。

    修复后这一层仍然如此 —— 承担告警与退出的是 `Service.run()`（经 `wait_closed()` 观察，
    见 `tests/test_service.py::test_run_returns_1_when_gateway_dies_after_start`）。
    """

    _install_fake_botpy(monkeypatch)
    gateway = BotpyGateway(
        app.config,
        ("app-id", "app-secret"),
        StateStore.load(app.config.state_path),
        handler=lambda message: None,  # type: ignore[arg-type,return-value]
        startup_timeout=1.0,
    )

    with caplog.at_level(logging.DEBUG):
        await gateway.start()
        fake = _FakeSDKClient.instances[0]
        assert fake.start_args == ("app-id", "app-secret", True)
        assert gateway._up_event is not None and gateway._up_event.is_set()
        assert any("[启动] QQ 网关已连接" in record.getMessage() for record in caplog.records)

        task = gateway._task
        assert task is not None
        await asyncio.wait_for(task, timeout=5)  # 网关协程结束
        assert task.done() is True
        assert task.exception() is None  # 没有异常 → 走不到 except
        assert gateway._up_error is None  # 也没有 error 回填
        await asyncio.sleep(0.05)
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []  # 无 [错误]/[警告]

    await gateway.close()
    assert fake.closed is True


async def test_send_token_refresh_failure_is_logged(
    app: App, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """BUG-001 取证 S2/S3 + F6：SDK 取 token 失败会冒到我们的 except，留下 `[错误] QQ 发送失败（不重试）`。

    整链用的是真 SDK：`BotAPI.post_group_message`（`botpy/api.py:1423-1424`）
    → `BotHttp.request`（`botpy/http.py:156`、`177` 处 `await self.check_session()`）
    → `Token.check_token`（`botpy/robot.py:39-41`）→ `update_access_token`（被替换为抛错）。
    一条网络请求都没发出去，所以不需要凭据、也不需要网络。
    """

    from botpy.api import BotAPI  # type: ignore[import-not-found]
    from botpy.http import BotHttp  # type: ignore[import-not-found]
    from botpy.robot import Token  # type: ignore[import-not-found]

    async def boom(self) -> None:  # noqa: ANN001 - 与 SDK 方法同签名
        raise RuntimeError("获取token失败，请检查appid和secret填写是否正确！")

    monkeypatch.setattr(Token, "update_access_token", boom)

    gateway, client = make_gateway(app)
    http = BotHttp(timeout=5, app_id="app-id", secret="expired-secret")  # access_token 初值为 None
    client.api = BotAPI(http)  # type: ignore[assignment]

    with caplog.at_level(logging.ERROR):
        await gateway.send_group_message(
            OutgoingGroupMessage(group_openid="G-1", text="hi", reply_to_message_id="MSG-9")
        )

    messages = [record.getMessage() for record in caplog.records]
    assert any("QQ 发送失败（不重试）" in item for item in messages), messages
    assert any("获取token失败" in item for item in messages), messages  # SDK 的原因被带上去了
    await http.close()


# ------------------------------------------------------------------ 网关任务结束的观测点（BUG-001 修复）
async def test_wait_closed_returns_when_gateway_coroutine_ends(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """`wait_closed()` 是「网关任务结束」的观测点：SDK 协程一返回它就返回。"""

    _install_fake_botpy(monkeypatch)
    gateway = BotpyGateway(
        app.config,
        ("app-id", "app-secret"),
        StateStore.load(app.config.state_path),
        handler=lambda message: None,  # type: ignore[arg-type,return-value]
        startup_timeout=1.0,
    )
    await gateway.start()
    await asyncio.wait_for(gateway.wait_closed(), timeout=5)

    assert gateway._task is not None and gateway._task.done() is True
    await gateway.close()
    assert _FakeSDKClient.instances[0].closed is True


async def test_wait_closed_before_start_returns_immediately(app: App) -> None:
    """没启动过的网关没有任务可等：直接返回，不会挂住调用方。"""

    gateway = BotpyGateway(
        app.config,
        ("app-id", "app-secret"),
        StateStore.load(app.config.state_path),
        handler=lambda message: None,  # type: ignore[arg-type,return-value]
    )
    await asyncio.wait_for(gateway.wait_closed(), timeout=1)


async def test_wait_closed_cancel_does_not_kill_gateway_task(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """优雅退出会 cancel 这个等待：取消不能传导给网关任务本身（否则就变成「网关被我们弄死」）。"""

    _install_fake_botpy(monkeypatch)
    gateway = BotpyGateway(
        app.config,
        ("app-id", "app-secret"),
        StateStore.load(app.config.state_path),
        handler=lambda message: None,  # type: ignore[arg-type,return-value]
        startup_timeout=1.0,
    )
    await gateway.start()

    waiter = asyncio.create_task(gateway.wait_closed())
    await asyncio.sleep(0.01)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    task = gateway._task
    assert task is not None and task.done() is False  # 网关任务仍然在跑
    await gateway.close()
    assert task.cancelled() or task.done()


# ------------------------------------------------------------------ BUG-005：错误文案可读化 + 去双前缀
@pytest.mark.parametrize(
    "text",
    ["'NoneType' object is not subscriptable", "'NoneType' object has no attribute 'get'"],
)
def test_describe_gateway_error_explains_sdk_none_timeout(text: str) -> None:
    """BUG-005：SDK 把超时吞成 None 后的两种内部异常都翻译成「平台接口无响应」，并保留原文。

    两条文本来自真机日志（`BUGS.md` BUG-005「原始证据」）：`/gateway/bot` 超时抛
    `not subscriptable`，`/users/@me` 超时抛 `has no attribute 'get'`。
    """

    message = gateway_module._describe_gateway_error(TypeError(text))
    assert message.startswith("QQ 平台接口无响应（SDK 把超时吞成 None")
    assert message.endswith("：" + text)


@pytest.mark.parametrize("exc", [RuntimeError("凭据无效"), ValueError("{'code': 10004, 'message': '机器人不存在'}")])
def test_describe_gateway_error_keeps_other_errors_verbatim(exc: Exception) -> None:
    """非 NoneType 异常不套「超时」帽子：凭据错 / 网络错要能一眼区分（BUG-005 的核心诉求）。"""

    assert gateway_module._describe_gateway_error(exc) == str(exc)


async def test_run_client_logs_readable_message_and_keeps_traceback(
    app: App, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """BUG-005：`_run_client` 的 `[错误]` 用可读文案，原始 traceback 只降到 DEBUG 保留。"""

    class NoneTypeFailingClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc) -> None:
            return None

        async def start(self, *_args, **_kwargs):
            # 复刻真机那一步：SDK 把超时吞成 None（botpy/http.py:181-195 隐式 return None）后，
            # `botpy/client.py:171` 的 `_ws_ap["session_start_limit"]` 抛的就是这条文本。
            raise TypeError("'NoneType' object is not subscriptable")

        async def close(self) -> None:
            return None

    monkeypatch.setattr(
        gateway_module,
        "botpy",
        type("B", (), {"Client": NoneTypeFailingClient, "Intents": lambda **kwargs: kwargs}),
    )
    gateway = BotpyGateway(
        app.config,
        ("app-id", "app-secret"),
        StateStore.load(app.config.state_path),
        handler=lambda message: None,  # type: ignore[arg-type,return-value]
        startup_timeout=1.0,
    )

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(QQGatewayError) as excinfo:
            await gateway.start()
        await asyncio.sleep(0.05)

    expected = (
        "QQ 平台接口无响应（SDK 把超时吞成 None，多为 /users/@me 或 /gateway/bot 超时）："
        "'NoneType' object is not subscriptable"
    )
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR] == [
        "[错误] QQ 网关异常退出: " + expected
    ]
    stack = [r for r in caplog.records if r.getMessage().startswith("[调试] QQ 网关异常原始堆栈")]
    assert len(stack) == 1 and stack[0].levelno == logging.DEBUG
    # traceback 必须真的在消息里：`cli._PlainFormatter` 只输出 `record.getMessage()`。
    traceback_text = stack[0].getMessage()
    assert "Traceback (most recent call last)" in traceback_text
    assert "TypeError: 'NoneType' object is not subscriptable" in traceback_text

    # 双前缀没了：`start()` 的文案本身就是可读原因，前缀只在 service.py 加一层。
    assert str(excinfo.value) == expected
    assert not str(excinfo.value).startswith("QQ 网关启动失败")
    await gateway.close()
