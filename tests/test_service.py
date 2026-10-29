"""service 测试：装配、常驻循环、优雅退出、启动自检（PLAN.md §3.2 / S1 / S5-7 / T8）。"""

from __future__ import annotations

import asyncio
import logging
import signal

import pytest

from conftest import App
from y33bot.qq import gateway as gateway_module
from y33bot.qq.gateway import BotpyGateway, QQGatewayError
from y33bot.qq.probe import QQProbeError
from y33bot.service import Service
from y33bot.state import StateStore

JOIN_LINE = "[12:00:04] [Server thread/INFO]: Steve joined the game\n"


class BrokenGateway:
    """启动必失败的网关桩。"""

    def __init__(self) -> None:
        self.closed = False

    async def start(self) -> None:
        raise QQGatewayError("凭据无效")

    async def send_group_message(self, message) -> None:  # pragma: no cover - 不会被调用
        return None

    async def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:  # pragma: no cover - 启动就失败，走不到监视阶段
        return None


async def passing_probe(app_id: str, app_secret: str) -> int:
    """离线探活替身：假装凭据可用（有效期 7200s）。真探活会发 HTTPS，测试一律替换掉。"""

    assert app_id and app_secret
    return 7200


async def failing_probe(_app_id: str, _app_secret: str) -> int:
    """离线探活替身：模拟「凭据无效 / 平台报错」。"""

    raise QQProbeError("平台返回错误: code=100007 message=appid or secret invalid")


def make_service(app: App, *, gateway=None, pool=None, env=None, probe=None, probe_qq: bool = True) -> Service:
    return Service(
        app.config,
        env=app.env if env is None else env,
        config_path=app.config_path,
        gateway=gateway,
        pool=pool,
        qq_probe=probe if probe is not None else passing_probe,
        probe_qq=probe_qq,
    )


# ------------------------------------------------------------------ 自检
async def test_startup_checks_all_green(app: App) -> None:
    pool = app.make_pool()
    pool._clients["main"].set_players(["Steve"])
    (app.config.bindings_path).parent.mkdir(parents=True, exist_ok=True)
    store = app.bindings()
    store.bind("OP-1", "Steve")
    store.save()

    service = make_service(app, pool=pool)
    results = await service.startup_checks()
    labels = {item.label: item for item in results}

    assert labels["配置"].detail == f"{app.config_path.name} 解析成功，1 个 MC 服"
    assert labels["QQ"].ok is True
    assert labels["QQ"].detail == (
        "access_token 获取成功（有效期 7200s），app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置"
    )
    assert labels["RCON main"].detail == "/list -> There are 1 of a max of 20 players online: Steve"
    assert labels["日志 main"].detail == f"{app.log_path} 可读，偏移 0 字节"
    assert labels["绑定"].detail == "1 条"
    assert all(item.ok for item in results)


async def test_startup_checks_reports_unusable_credentials(app: App) -> None:
    """BUG-001 的 R5：凭据「填了但不可用」必须 FAIL（旧行为是照样打印 `[QQ] OK`）。"""

    service = make_service(app, pool=app.make_pool(), probe=failing_probe)
    results = await service.startup_checks()
    qq = [item for item in results if item.label == "QQ"][0]
    assert qq.ok is False
    assert qq.detail == "access_token 获取失败: 平台返回错误: code=100007 message=appid or secret invalid"
    assert not all(item.ok for item in results)


async def test_startup_checks_without_probe_keeps_offline_path(app: App) -> None:
    """`--no-probe`（`probe_qq=False`）：完全不碰网络，只报告「变量填了、未探活」。"""

    def explode(*_args, **_kwargs):  # pragma: no cover - 被调用即失败
        raise AssertionError("--no-probe 不该调用探活函数")

    service = make_service(app, pool=app.make_pool(), probe=explode, probe_qq=False)
    results = await service.startup_checks()
    qq = [item for item in results if item.label == "QQ"][0]
    assert qq.ok is True
    assert qq.detail == "app_id 已设置 (env QQ_BOT_APP_ID)，未探活（--no-probe），group_openid 已配置"


async def test_service_default_probe_is_the_real_one(app: App) -> None:
    """默认装配指向真探活（`check` 不传 `--no-probe` 时才会真的取一次 access_token）。"""

    from y33bot.qq.probe import probe_access_token

    assert Service(app.config, env=app.env)._qq_probe is probe_access_token


async def test_startup_checks_reports_broken_bindings(app: App) -> None:
    app.config.bindings_path.parent.mkdir(parents=True, exist_ok=True)
    app.config.bindings_path.write_text("[[bindings]", encoding="utf-8")
    service = make_service(app, pool=app.make_pool())
    results = await service.startup_checks()
    binding = [item for item in results if item.label == "绑定"][0]
    assert binding.ok is False
    assert "绑定表" in binding.detail


async def test_startup_checks_missing_credentials(app: App) -> None:
    service = make_service(app, pool=app.make_pool(), env={"MC_RCON_PASSWORD_MAIN": "x"})
    results = await service.startup_checks()
    qq = [item for item in results if item.label == "QQ"][0]
    assert qq.ok is False
    assert "QQ_BOT_APP_ID" in qq.detail


async def test_startup_checks_reports_offline_server(app: App) -> None:
    service = make_service(app, pool=app.make_pool(online={"main": False}))
    results = await service.startup_checks()
    rcon = [item for item in results if item.label == "RCON main"][0]
    assert rcon.ok is False
    assert rcon.detail.startswith("无法连接 127.0.0.1:25575:")


# ------------------------------------------------------------------ 常驻运行
async def test_run_polls_log_pushes_and_persists_offset(app: App) -> None:
    gateway = app.make_gateway()
    service = make_service(app, gateway=gateway, pool=app.make_pool())
    original = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    task = asyncio.create_task(service.run())
    try:
        for _ in range(40):
            if gateway.started:
                break
            await asyncio.sleep(0.02)
        assert gateway.started is True

        app.write_log(JOIN_LINE)
        for _ in range(60):
            if gateway.messages():
                break
            await asyncio.sleep(0.05)
        assert gateway.messages() == ["Steve进入了main"]
    finally:
        service._signal_flag.set()
        code = await asyncio.wait_for(task, timeout=10)
        for sig, handler in original.items():
            signal.signal(sig, handler)

    assert code == 0
    state = StateStore.load(app.config.state_path)
    assert state.server_state("main").log_offset == len(JOIN_LINE)  # S5-7：退出时偏移已落盘
    assert gateway.started is False  # shutdown 关掉了网关


async def test_run_returns_1_when_gateway_fails(app: App) -> None:
    broken = BrokenGateway()
    service = make_service(app, gateway=broken, pool=app.make_pool())
    assert await asyncio.wait_for(service.run(), timeout=10) == 1
    assert broken.closed is True


async def test_gateway_startup_failure_logs_single_readable_prefix(
    app: App, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """BUG-005：启动期失败只留**一层**前缀，且原因是可读文案（真机曾是 `QQ 网关启动失败: QQ 网关启动失败: …`）。

    整链用真 `BotpyGateway` + 假 `botpy.Client`（只把 SDK 那两条 `NoneType` 异常离线复刻出来），
    不连 QQ；`Service.run()` 的最终输出就是运维真正看到的那两行。
    """

    class NoneTypeFailingClient:
        """复刻 SDK 吞掉超时后返回 `None` 的那一步（`botpy/http.py:181-195` / `botpy/client.py:171`）。"""

        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc) -> None:
            return None

        async def start(self, *_args, **_kwargs):
            raise TypeError("'NoneType' object is not subscriptable")

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
    service = make_service(app, gateway=gateway, pool=app.make_pool())

    with caplog.at_level(logging.INFO):
        assert await asyncio.wait_for(service.run(), timeout=10) == 1

    reason = (
        "QQ 平台接口无响应（SDK 把超时吞成 None，多为 /users/@me 或 /gateway/bot 超时）："
        "'NoneType' object is not subscriptable"
    )
    startup_errors = [record.getMessage() for record in caplog.records if "QQ 网关启动失败" in record.getMessage()]
    assert startup_errors == ["[错误] QQ 网关启动失败: " + reason]  # 一层前缀 + 可读原因
    assert gateway._task is None  # shutdown() 真的关掉了网关


async def test_run_returns_1_without_credentials(app: App) -> None:
    service = make_service(app, pool=app.make_pool(), env={"MC_RCON_PASSWORD_MAIN": "x"})
    assert await asyncio.wait_for(service.run(), timeout=10) == 1


async def test_run_returns_1_when_rcon_password_missing(app: App) -> None:
    service = make_service(app, gateway=app.make_gateway(), pool=None, env={})
    assert await asyncio.wait_for(service.run(), timeout=10) == 1


async def test_run_returns_1_for_corrupt_bindings(app: App) -> None:
    app.config.bindings_path.parent.mkdir(parents=True, exist_ok=True)
    app.config.bindings_path.write_text("[[bindings]", encoding="utf-8")
    service = make_service(app, gateway=app.make_gateway(), pool=app.make_pool())
    assert await asyncio.wait_for(service.run(), timeout=10) == 1


async def test_run_warns_when_group_openid_missing(tmp_path) -> None:
    app = App(tmp_path, group_openid="")
    gateway = app.make_gateway()
    service = make_service(app, gateway=gateway, pool=app.make_pool())

    task = asyncio.create_task(service.run())
    for _ in range(40):
        if gateway.started:
            break
        await asyncio.sleep(0.02)
    app.write_log(JOIN_LINE)
    await asyncio.sleep(0.2)
    service._signal_flag.set()
    assert await asyncio.wait_for(task, timeout=10) == 0
    assert gateway.sent == []  # MC→QQ 方向已禁用


async def test_on_group_message_before_ready(app: App, caplog: pytest.LogCaptureFixture) -> None:
    service = make_service(app)
    with caplog.at_level("WARNING"):
        assert await service._on_group_message(None) is None  # type: ignore[arg-type]
    assert any("服务尚未就绪" in record.getMessage() for record in caplog.records)


async def test_on_group_message_delegates_to_bridge(app: App) -> None:
    """`run()` 把 `_on_group_message` 当作网关 handler 注入：群消息要真的走到 `Bridge`。"""

    from y33bot.models import MCGroupMessage

    service = make_service(app, pool=app.make_pool())
    service._bridge = app.make_bridge(pool=service._pool)

    reply = await service._on_group_message(
        MCGroupMessage(
            group_openid="G-1",
            member_openid="OP-1",
            message_id="M-1",
            content="#你好",
            received_at=0.0,
        )
    )
    assert reply == "请先使用 /bind <游戏ID> 绑定"  # 未绑定 → 指令/转发都走 Bridge 的既有规则


# ------------------------------------------------------------------ 网关启动后失效必须报错退出（BUG-001 修复）
class DyingGateway:
    """桩网关：`start()` 成功，随后网关任务自己结束（等价于 SDK 网关协程「正常返回」）。

    `wait_closed()` 返回即代表「网关任务结束」；正常实现见
    `src/y33bot/qq/gateway.py` 的 `BotpyGateway.wait_closed()`。
    """

    def __init__(self, *, delay: float = 0.02) -> None:
        self.started = False
        self.ended = False
        self.closed = False
        self._delay = delay

    async def start(self) -> None:
        self.started = True

    async def send_group_message(self, message) -> None:  # pragma: no cover - 本用例不发消息
        return None

    async def wait_closed(self) -> None:
        await asyncio.sleep(self._delay)
        self.ended = True

    async def close(self) -> None:
        self.closed = True


async def test_run_returns_1_when_gateway_dies_after_start(app: App, caplog: pytest.LogCaptureFixture) -> None:
    """BUG-001 修复：启动成功后网关任务结束 → 打 `[错误]` 并以非 0 退出（交给 systemd/nssm 拉起）。

    修复前这里是「静默失效」：`run()` 继续等停止信号、日志里一条 `[错误]` 都没有。
    """

    gateway = DyingGateway()
    service = make_service(app, gateway=gateway, pool=app.make_pool())
    original = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    with caplog.at_level(logging.DEBUG):
        try:
            code = await asyncio.wait_for(service.run(), timeout=10)
        finally:
            for sig, handler in original.items():
                signal.signal(sig, handler)

    assert gateway.started is True and gateway.ended is True
    assert code == 1  # 非 0 退出（与启动失败同一个退出码）
    messages = [record.getMessage() for record in caplog.records]
    errors = [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]
    assert errors == ["[错误] QQ 网关已断开（收不到群消息），进程退出等待重启"]
    assert gateway.closed is True  # 仍然走 shutdown()，不是硬崩
    assert any("[停止] 已退出" in message for message in messages)


async def test_run_returns_0_when_stopped_by_signal(app: App, caplog: pytest.LogCaptureFixture) -> None:
    """对照：收到停止信号（我们自己主动关闭）仍是退出码 0，且没有任何 `[错误]`。"""

    gateway = app.make_gateway()
    service = make_service(app, gateway=gateway, pool=app.make_pool())
    original = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    with caplog.at_level(logging.DEBUG):
        task = asyncio.create_task(service.run())
        try:
            for _ in range(50):
                if gateway.started:
                    break
                await asyncio.sleep(0.02)
            assert gateway.started is True
            service._signal_flag.set()  # 等价于收到 SIGINT/SIGTERM
            code = await asyncio.wait_for(task, timeout=10)
        finally:
            if not task.done():  # pragma: no cover - 兜底，避免用例挂住
                task.cancel()
            for sig, handler in original.items():
                signal.signal(sig, handler)

    assert code == 0
    assert [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR] == []
    assert gateway.started is False  # shutdown 关掉了网关
