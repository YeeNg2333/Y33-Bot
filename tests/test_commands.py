"""commands 层测试：注册表、分发、`/status`、`/bind`（PLAN.md R13-R17 / A2 / A3 / T6）。"""

from __future__ import annotations

import logging

import pytest

from conftest import App
from y33bot.binding import BindingStore
from y33bot.commands.builtin import (
    BIND_USAGE,
    INVALID_GAME_ID_REPLY,
    build_registry,
    cmd_bind,
    cmd_status,
)
from y33bot.commands.registry import (
    HANDLER_ERROR_REPLY,
    UNKNOWN_COMMAND_REPLY,
    CommandContext,
    CommandRegistry,
    CommandSpec,
)
from y33bot.models import MCGroupMessage
from y33bot.rcon.pool import RconPool
from y33bot.state import StateStore


def _message(openid: str = "OPENID-1", content: str = "#hi") -> MCGroupMessage:
    return MCGroupMessage(
        group_openid="GROUP-1",
        member_openid=openid,
        message_id="MSG-1",
        content=content,
        received_at=1.0,
    )


def _context(app: App, *, pool: RconPool | None = None, bindings: BindingStore | None = None) -> CommandContext:
    return CommandContext(
        config=app.config,
        bindings=bindings if bindings is not None else app.bindings(),
        rcon=pool if pool is not None else app.make_pool(),
        state=StateStore.load(app.config.state_path),
        message=_message(),
        logger=logging.getLogger("y33bot.test"),
    )


# ------------------------------------------------------------------ 注册表
def test_register_decorator_and_lookup() -> None:
    registry = CommandRegistry()

    @registry.register("ping", aliases=["p"], desc="测试")
    async def _ping(ctx, args):  # pragma: no cover - 只注册
        return "pong"

    assert registry.names() == ["ping"]
    assert registry.get("ping") is not None
    assert registry.get("PING") is not None  # 大小写不敏感
    assert registry.get("p") is not None  # 别名
    assert registry.get("nope") is None
    assert registry.get("") is None
    assert len(registry) == 1
    assert registry.get("ping").desc == "测试"


def test_register_rejects_duplicates_and_empty_names() -> None:
    registry = CommandRegistry()
    registry.add(CommandSpec(name="a", handler=lambda ctx, args: None))
    with pytest.raises(ValueError, match="重复注册"):
        registry.add(CommandSpec(name="a", handler=lambda ctx, args: None))
    with pytest.raises(ValueError, match="不能为空"):
        registry.register("   ")


async def test_dispatch_unknown_command(app: App) -> None:
    registry = build_registry()
    ctx = _context(app)
    assert await registry.dispatch(ctx, "/unknowncmd") == UNKNOWN_COMMAND_REPLY
    assert await registry.dispatch(ctx, "status") == UNKNOWN_COMMAND_REPLY  # 缺前缀
    assert await registry.dispatch(ctx, "") == UNKNOWN_COMMAND_REPLY
    assert await registry.dispatch(ctx, "#status") == UNKNOWN_COMMAND_REPLY


async def test_dispatch_passes_args(app: App) -> None:
    registry = CommandRegistry()
    seen: list[list[str]] = []

    @registry.register("echo")
    async def _echo(ctx, args):
        seen.append(args)
        return "|".join(args)

    ctx = _context(app)
    assert await registry.dispatch(ctx, "/echo a b  c") == "a|b|c"
    assert seen == [["a", "b", "c"]]


async def test_dispatch_catches_handler_exception(app: App, caplog: pytest.LogCaptureFixture) -> None:
    registry = CommandRegistry()

    @registry.register("boom")
    async def _boom(ctx, args):
        raise RuntimeError("炸了")

    ctx = _context(app)
    with caplog.at_level("ERROR"):
        assert await registry.dispatch(ctx, "/boom") == HANDLER_ERROR_REPLY
    assert any("指令 /boom 执行失败" in record.message for record in caplog.records)


# ------------------------------------------------------------------ /bind
async def test_bind_requires_argument(app: App) -> None:
    ctx = _context(app)
    assert await cmd_bind(ctx, []) == BIND_USAGE


@pytest.mark.parametrize("bad", ["ab", "a" * 17, "bad-id", ""])
async def test_bind_rejects_invalid_game_id(app: App, bad: str) -> None:
    ctx = _context(app)
    assert await cmd_bind(ctx, [bad]) == INVALID_GAME_ID_REPLY


async def test_bind_writes_and_overwrites(app: App) -> None:
    ctx = _context(app)
    assert await cmd_bind(ctx, ["Steve"]) == "绑定成功: Steve"
    assert app.bindings().lookup("OPENID-1") == "Steve"
    assert await cmd_bind(ctx, ["Notch"]) == "绑定成功: Notch"
    assert app.bindings().items() == {"OPENID-1": "Notch"}


async def test_bind_is_global_across_servers(two_server_app: App) -> None:
    ctx = _context(two_server_app)
    assert await cmd_bind(ctx, ["Steve"]) == "绑定成功: Steve"
    assert two_server_app.bindings().lookup("OPENID-1") == "Steve"


# ------------------------------------------------------------------ /status
async def test_status_single_server(app: App) -> None:
    pool = app.make_pool()
    pool._clients["main"].set_players(["Steve"])
    ctx = _context(app, pool=pool)
    assert await cmd_status(ctx, []) == "[服务器状态]\n在线: 1/20\n玩家: Steve"


async def test_status_offline(app: App) -> None:
    pool = app.make_pool(online={"main": False})
    ctx = _context(app, pool=pool)
    assert await cmd_status(ctx, []) == "[服务器状态] 服务器离线"


async def test_status_multi_server(two_server_app: App) -> None:
    pool = two_server_app.make_pool()
    pool._clients["main"].set_players(["Steve", "Alex"])
    pool._clients["world2"].set_players([])
    ctx = _context(two_server_app, pool=pool)
    text = await cmd_status(ctx, [])
    lines = text.splitlines()
    assert lines[0] == "[服务器状态]"
    assert lines[1] == "main: 在线 2/20 玩家: Steve, Alex"
    assert lines[2] == "world2: 在线 0/20 玩家: 无"
    assert lines[3] == "总计: 2 人在线"


def test_build_registry_registers_expected_names() -> None:
    registry = build_registry()
    assert registry.names() == ["bind", "status"]
    assert registry.get("status").desc

    # 已有自定义指令的 registry 继续追加内置指令
    custom = CommandRegistry()

    @custom.register("ping")
    async def _ping(ctx, args):  # pragma: no cover - 只注册
        return "pong"

    assert build_registry(custom) is custom
    assert custom.names() == ["bind", "ping", "status"]

    # 重复注册同一内置指令必须报错，避免静默覆盖
    with pytest.raises(ValueError, match="重复注册"):
        build_registry(custom)
