"""qq.gateway 测试：SDK 适配层的规则与文案（PLAN.md A5 / A12 / R23 / T7）。

botpy 的真实网关不在这里连：用桩对象替代 `client.api`。
"""

from __future__ import annotations

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
    with pytest.raises(QQGatewayError, match="启动失败"):
        await gateway.start()
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
