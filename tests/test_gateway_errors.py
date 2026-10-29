"""BUG-005 文案层回归：网关异常翻译 / `start()` 双前缀 / `run` 启动探活失败（issue #3）。

覆盖四类语义（卡 t_f43e4dc9）：

1. `_describe_gateway_error()` 把 SDK 吞成 `None` 的两种 `NoneType` 异常翻成「QQ 平台接口无响应」，**原文不吞**；
2. 其余异常原样透传（不加前缀、也不误贴「超时」帽子）；
3. `start()` 自己不再加「QQ 网关启动失败」前缀 ⇒ 运维看到的那一行只有 **一层**前缀；
4. `Service.run()` 启动探活失败：只试一次、退出码非 0、日志首行带可读归因（原文保留）。

全程离线：botpy 用桩类替代（不建连接）、探活用注入替身、RCON 用 `conftest.FakeRconTransport`。
本文件不使用 `skip` / `xfail` —— 任何一条不成立都应该红。
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from conftest import App
from y33bot.qq import gateway as gateway_module
from y33bot.qq.gateway import BotpyGateway, QQGatewayError, _describe_gateway_error
from y33bot.qq.probe import QQProbeError
from y33bot.service import Service
from y33bot.state import StateStore

# BUG-005 的两条原文（SDK `botpy/http.py:181-195` 吞掉超时后，`botpy/robot.py` / `client.py` 当 dict 用）。
NOT_SUBSCRIPTABLE = "'NoneType' object is not subscriptable"
NO_ATTRIBUTE_GET = "'NoneType' object has no attribute 'get'"

NO_RESPONSE = "QQ 平台接口无响应"
SERVICE_PREFIX = "QQ 网关启动失败"
DOUBLE_PREFIX = f"{SERVICE_PREFIX}: {SERVICE_PREFIX}"
PROBE_PREFIX = "[错误] QQ 凭据探活失败（启动前一次性检查，不重试，未启动网关）: "


class NoneTypeClient:
    """复刻「SDK 超时后返回 `None`、随后被当 dict 用」的那一步（不建任何连接）。"""

    def __init__(self, **_kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def start(self, *_args, **_kwargs):
        raise TypeError(NOT_SUBSCRIPTABLE)


def _install_stub_botpy(monkeypatch: pytest.MonkeyPatch, client_class: type) -> None:
    """把模块级 `botpy` 换成只有 `Client` / `Intents` 的替身（`BotpyGateway` 只用到这两个）。"""

    monkeypatch.setattr(
        gateway_module,
        "botpy",
        type("StubBotpy", (), {"Client": client_class, "Intents": lambda **kwargs: kwargs}),
    )


def _make_real_gateway(app: App, *, startup_timeout: float = 1.0) -> BotpyGateway:
    return BotpyGateway(
        app.config,
        ("app-id", "app-secret"),
        StateStore.load(app.config.state_path),
        handler=lambda message: None,  # type: ignore[arg-type,return-value]
        startup_timeout=startup_timeout,
    )


def _make_service(app: App, **kwargs) -> Service:
    """直接装配 `Service`（不 import `test_service` 的辅助函数，保持文件独立）。"""

    kwargs.setdefault("pool", app.make_pool())
    return Service(
        app.config,
        env=app.env,
        config_path=app.config_path,
        **kwargs,
    )


class FailingGateway:
    """启动即失败、其余方法齐全的网关桩（`Service.run()` 的失败路径只需要这三步）。"""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.started = False
        self.closed = False

    async def start(self) -> None:
        self.started = True
        raise self._exc

    async def send_group_message(self, message) -> None:  # pragma: no cover - 启动就失败，走不到发消息
        return None

    async def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:  # pragma: no cover - 启动就失败，走不到监视阶段
        return None


def _errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]


# ---------------------------------------------------------------- 1) 两种 NoneType 异常 → 可读文案 + 原文
@pytest.mark.parametrize(
    ("exc_class", "original"),
    [(TypeError, NOT_SUBSCRIPTABLE), (AttributeError, NO_ATTRIBUTE_GET)],
)
def test_describe_gateway_error_translates_none_type_exceptions(exc_class: type[Exception], original: str) -> None:
    """SDK 把超时吞成 `None` 的两条原文，都要变成「QQ 平台接口无响应」且**保留原文**。"""

    described = _describe_gateway_error(exc_class(original))

    assert NO_RESPONSE in described
    assert original in described  # 原文不被吞：运维还要靠它去搜 SDK 源码
    assert described.endswith(original)
    assert described != original  # 真的加了归因，不是原样返回

    # 命中的是「超时」语义，不是凭据错：文案里要点明 SDK 把超时吞成了 None。
    assert "超时" in described
    assert "凭据" not in described


# ---------------------------------------------------------------- 2) 其它异常原样透传
@pytest.mark.parametrize(
    "exc",
    [
        ValueError("boom"),
        RuntimeError("凭据无效"),
        OSError("无法连接 https://bots.qq.com: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING]>"),
    ],
)
def test_describe_gateway_error_passes_other_exceptions_through(exc: BaseException) -> None:
    """非 `NoneType` 异常一律原样返回：不加前缀，也不许被误贴成「平台无响应」。"""

    described = _describe_gateway_error(exc)

    assert described == str(exc)
    assert not described.startswith(SERVICE_PREFIX)
    assert NO_RESPONSE not in described


# ---------------------------------------------------------------- 3) 双前缀消失
async def test_start_error_has_no_self_prefix(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """`BotpyGateway.start()` 抛出的异常文案就是底层原因，不许自带「QQ 网关启动失败」。"""

    _install_stub_botpy(monkeypatch, NoneTypeClient)
    gateway = _make_real_gateway(app)

    with pytest.raises(QQGatewayError) as excinfo:
        await gateway.start()

    reason = str(excinfo.value)
    assert SERVICE_PREFIX not in reason
    assert DOUBLE_PREFIX not in reason
    assert reason.startswith(NO_RESPONSE)  # 可读归因还在
    assert NOT_SUBSCRIPTABLE in reason
    assert isinstance(excinfo.value.__cause__, TypeError)  # 原始异常仍可追溯
    await gateway.close()


async def test_run_logs_gateway_startup_failure_with_single_prefix(app: App, caplog: pytest.LogCaptureFixture) -> None:
    """真机上那行 `[错误]` 只留一层前缀：`QQ 网关启动失败: <可读原因>`。

    用注入替身网关（不触网、跳过启动前探活），断言的就是运维在 `run` 里看到的原文。
    """

    reason = _describe_gateway_error(AttributeError(NO_ATTRIBUTE_GET))
    gateway = FailingGateway(QQGatewayError(reason))
    service = _make_service(app, gateway=gateway)

    with caplog.at_level(logging.INFO):
        assert await asyncio.wait_for(service.run(), timeout=10) == 1

    errors = _errors(caplog)
    startup_errors = [message for message in errors if SERVICE_PREFIX in message]
    assert startup_errors == [f"[错误] {SERVICE_PREFIX}: {reason}"]
    assert startup_errors[0].count(SERVICE_PREFIX) == 1
    assert DOUBLE_PREFIX not in startup_errors[0]
    assert NO_ATTRIBUTE_GET in startup_errors[0]  # 原文不吞
    assert gateway.closed is True  # shutdown() 关掉了网关


# ---------------------------------------------------------------- 4) run 启动探活失败
@pytest.mark.parametrize(
    ("exc", "advice"),
    [
        (QQProbeError("平台返回错误: code=100007 message=appid or secret invalid"), "凭据/配置问题"),
        (QQProbeError("HTTP 429 Too Many Requests: <html>rate limited</html>"), "接口抖动"),
        (
            QQProbeError("无法连接 https://bots.qq.com: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING]>"),
            "网络不可达",
        ),
    ],
)
async def test_run_exits_nonzero_with_readable_reason_when_startup_probe_fails(
    app: App, caplog: pytest.LogCaptureFixture, exc: BaseException, advice: str
) -> None:
    """探活失败：只试一次、返回 1、日志首行写清归因，且根本没构造真网关。

    探活是注入替身（`qq_probe`），`gateway` 不注入 = 走真网关分支，所以探活一定会被执行；
    整条路径不发起任何真实网络请求。
    """

    calls: list[tuple[str, str]] = []

    async def failing_probe(app_id: str, app_secret: str) -> int:
        calls.append((app_id, app_secret))
        raise exc

    service = _make_service(app, qq_probe=failing_probe)

    with caplog.at_level(logging.DEBUG):
        code = await asyncio.wait_for(service.run(), timeout=10)

    assert code == 1  # 退出码非 0：交给 systemd/nssm 拉起
    assert len(calls) == 1  # 只尝试一次：没有重试、没有退避

    errors = _errors(caplog)
    assert len(errors) == 1  # 只有探活这一条 [错误]，网关那条不会出现
    assert errors[0].startswith(PROBE_PREFIX)
    assert str(exc) in errors[0]  # 可读原因 + 原文都在
    assert advice in errors[0]
    assert "不重试" in errors[0]
    assert SERVICE_PREFIX not in errors[0]  # 探活失败就不该再去起网关
    assert service._gateway is None
