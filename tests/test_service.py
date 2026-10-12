"""service 测试：装配、常驻循环、优雅退出、启动自检（PLAN.md §3.2 / S1 / S5-7 / T8）。"""

from __future__ import annotations

import asyncio
import signal

import pytest

from conftest import App
from y33bot.qq.gateway import QQGatewayError
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


def make_service(app: App, *, gateway=None, pool=None, env=None) -> Service:
    return Service(
        app.config,
        env=app.env if env is None else env,
        config_path=app.config_path,
        gateway=gateway,
        pool=pool,
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
    assert labels["RCON main"].detail == "/list -> There are 1 of a max of 20 players online: Steve"
    assert labels["日志 main"].detail == f"{app.log_path} 可读，偏移 0 字节"
    assert labels["绑定"].detail == "1 条"
    assert all(item.ok for item in results)


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
        assert gateway.messages() == ["Steve进入游戏"]
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
