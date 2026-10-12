"""bridge 模块测试：核心业务规则与文案（PLAN.md R1-R12 / R18 / R19 / R28 / A1-A8 / T7）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import App
from y33bot.binding import BindingStore
from y33bot.bridge import UNBOUND_REPLY, Bridge, format_status
from y33bot.commands.builtin import build_registry
from y33bot.models import MCGroupMessage, MCLogEvent, OutgoingGroupMessage, PlayerList, ServerStatusReport
from y33bot.rcon.pool import RconPool
from y33bot.state import StateStore

OPENID = "OPENID-1"
GAME_ID = "Steve"


def make_bridge(
    app: App,
    *,
    pool: RconPool | None = None,
    gateway=None,
    store: StateStore | None = None,
    bindings: BindingStore | None = None,
    registry=None,
    config=None,
) -> Bridge:
    return Bridge(
        config if config is not None else app.config,
        bindings if bindings is not None else app.bindings(),
        store if store is not None else app.state(),
        pool if pool is not None else app.make_pool(),
        registry if registry is not None else build_registry(),
        gateway if gateway is not None else app.make_gateway(),
    )


def bound_app(app: App, game_id: str = GAME_ID) -> BindingStore:
    store = app.bindings()
    store.bind(OPENID, game_id)
    store.save()
    return store


def message(content: str, *, openid: str = OPENID, group: str = "GROUP-1") -> MCGroupMessage:
    return MCGroupMessage(
        group_openid=group,
        member_openid=openid,
        message_id="MSG-1",
        content=content,
        received_at=1.0,
    )


def chat_event(message_text: str, *, player: str = GAME_ID) -> MCLogEvent:
    return MCLogEvent(
        server="main",
        kind="chat",
        player=player,
        message=message_text,
        raw=f"<{player}> {message_text}",
        occurred_at=1.0,
    )


def log_event(kind: str, *, player: str | None = GAME_ID) -> MCLogEvent:
    return MCLogEvent(server="main", kind=kind, player=player, message=None, raw="raw", occurred_at=1.0)


# ------------------------------------------------------------------ QQ → MC
async def test_forward_chat_single_line(app: App) -> None:
    bound_app(app)
    pool = app.make_pool()
    bridge = make_bridge(app, pool=pool)
    reply = await bridge.handle_group_message(message("#你好\n世界"))
    assert reply is None
    assert pool._clients["main"].commands == ['tellraw @a {"text":"[QQ] Steve: 你好"}']


async def test_forward_strips_media_markers(app: App) -> None:
    bound_app(app)
    pool = app.make_pool()
    bridge = make_bridge(app, pool=pool)
    assert await bridge.handle_group_message(message("#hi <image url=\"x\"/> there")) is None
    assert pool._clients["main"].commands == ['tellraw @a {"text":"[QQ] Steve: hi  there"}']


async def test_media_only_message_is_not_forwarded(app: App) -> None:
    bound_app(app)
    pool = app.make_pool()
    bridge = make_bridge(app, pool=pool)
    assert await bridge.handle_group_message(message("#<image url=\"x\"/>")) is None
    assert pool._clients["main"].commands == []


async def test_unbound_user_gets_hint(app: App) -> None:
    pool = app.make_pool()
    bridge = make_bridge(app, pool=pool)
    assert await bridge.handle_group_message(message("#你好", openid="UNKNOWN")) == UNBOUND_REPLY
    assert pool._clients["main"].commands == []


async def test_non_trigger_prefix_ignored(app: App, caplog: pytest.LogCaptureFixture) -> None:
    bound_app(app)
    pool = app.make_pool()
    bridge = make_bridge(app, pool=pool)
    with caplog.at_level("INFO"):
        assert await bridge.handle_group_message(message("普通消息")) is None
    assert pool._clients["main"].commands == []
    assert any("[忽略] 非触发前缀" in record.getMessage() for record in caplog.records)


async def test_empty_message_ignored(app: App) -> None:
    bridge = make_bridge(app)
    assert await bridge.handle_group_message(message("   ")) is None


async def test_message_without_openids_dropped(app: App, caplog: pytest.LogCaptureFixture) -> None:
    bridge = make_bridge(app)
    with caplog.at_level("WARNING"):
        assert await bridge.handle_group_message(message("#hi", openid="")) is None
        assert await bridge.handle_group_message(message("#hi", group="")) is None
    assert any("缺少 group_openid" in record.getMessage() for record in caplog.records)


async def test_command_reply_goes_back_to_group(app: App) -> None:
    pool = app.make_pool()
    pool._clients["main"].set_players(["Steve", "Alex"])
    bridge = make_bridge(app, pool=pool)
    reply = await bridge.handle_group_message(message("/status"))
    assert reply == "[服务器状态]\n在线: 2/20\n玩家: Steve, Alex"


async def test_bind_command_from_group(app: App) -> None:
    bridge = make_bridge(app)
    assert await bridge.handle_group_message(message("/bind Alex")) == "绑定成功: Alex"
    assert app.bindings().lookup(OPENID) == "Alex"


async def test_unknown_command_reply(app: App) -> None:
    bridge = make_bridge(app)
    assert await bridge.handle_group_message(message("/nope")) == "未知指令"


async def test_max_line_length_truncation(tmp_path: Path) -> None:
    app = App(tmp_path, max_line_length=10)
    bound_app(app)
    pool = app.make_pool()
    bridge = make_bridge(app, pool=pool)
    await bridge.handle_group_message(message("#" + "x" * 50))
    command = pool._clients["main"].commands[0]
    assert '"text":"[QQ] Steve: xxxxxxxxx…"' in command


# ------------------------------------------------------------------ MC → QQ
async def test_join_and_quit_notifications(app: App) -> None:
    gateway = app.make_gateway()
    bridge = make_bridge(app, gateway=gateway, pool=app.make_pool())
    await bridge.handle_log_event(log_event("join"))
    await bridge.handle_log_event(log_event("quit"))
    assert gateway.messages() == ["Steve进入游戏", "Steve退出游戏"]
    assert gateway.last().group_openid == "GROUP-OPENID-1"


async def test_join_without_player_is_ignored(app: App, caplog: pytest.LogCaptureFixture) -> None:
    gateway = app.make_gateway()
    bridge = make_bridge(app, gateway=gateway, pool=app.make_pool())
    with caplog.at_level("WARNING"):
        await bridge.handle_log_event(log_event("join", player=None))
    assert gateway.sent == []
    assert any("缺少玩家名" in record.getMessage() for record in caplog.records)


async def test_chat_forward_both_directions(app: App) -> None:
    gateway = app.make_gateway()
    pool = app.make_pool()
    bridge = make_bridge(app, gateway=gateway, pool=pool)
    await bridge.handle_log_event(chat_event("#大家好"))
    assert gateway.messages() == ["Steve: 大家好"]
    assert pool._clients["main"].commands == ['tellraw @a {"text":"[→QQ] Steve: 大家好"}']


async def test_chat_without_hash_not_forwarded(app: App, caplog: pytest.LogCaptureFixture) -> None:
    gateway = app.make_gateway()
    pool = app.make_pool()
    bridge = make_bridge(app, gateway=gateway, pool=pool)
    with caplog.at_level("INFO"):
        await bridge.handle_log_event(chat_event("普通聊天"))
    assert gateway.sent == []
    assert pool._clients["main"].commands == []
    assert any("聊天非 # 开头" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("prefix", ["[QQ] ", "[→QQ] "])
async def test_chat_loop_protection(app: App, prefix: str, caplog: pytest.LogCaptureFixture) -> None:
    gateway = app.make_gateway()
    pool = app.make_pool()
    bridge = make_bridge(app, gateway=gateway, pool=pool)
    with caplog.at_level("INFO"):
        await bridge.handle_log_event(chat_event(f"{prefix}Steve: 大家好"))
    assert gateway.sent == []
    assert pool._clients["main"].commands == []
    assert any("回环防护" in record.getMessage() for record in caplog.records)


async def test_empty_chat_after_hash_ignored(app: App) -> None:
    gateway = app.make_gateway()
    bridge = make_bridge(app, gateway=gateway, pool=app.make_pool())
    await bridge.handle_log_event(chat_event("#   "))
    assert gateway.sent == []


async def test_unknown_event_kind(app: App, caplog: pytest.LogCaptureFixture) -> None:
    bridge = make_bridge(app)
    with caplog.at_level("WARNING"):
        await bridge.handle_log_event(log_event("weird"))  # type: ignore[arg-type]
    assert any("未知日志事件类型" in record.getMessage() for record in caplog.records)


async def test_mc_to_qq_disabled_without_group_openid(tmp_path: Path) -> None:
    app = App(tmp_path, group_openid="")
    assert app.config.qq.mc_to_qq_enabled is False
    gateway = app.make_gateway()
    bridge = make_bridge(app, gateway=gateway, pool=app.make_pool())
    await bridge.handle_log_event(log_event("join"))
    assert gateway.sent == []


# ------------------------------------------------------------------ 健康
async def test_poll_health_flip_and_no_repeat(app: App) -> None:
    gateway = app.make_gateway()
    store = app.state()
    pool = app.make_pool(online={"main": False})
    bridge = make_bridge(app, gateway=gateway, pool=pool, store=store)

    assert await bridge.poll_health() == [("main", False)]
    assert gateway.messages() == ["[服务器状态] main 离线"]
    assert store.server_state("main").health_online is False

    assert await bridge.poll_health() == []
    assert gateway.messages() == ["[服务器状态] main 离线"]


async def test_poll_health_recovery(app: App) -> None:
    gateway = app.make_gateway()
    store = app.state()
    store.server_state("main").health_online = False
    pool = app.make_pool(online={"main": True})
    bridge = make_bridge(app, gateway=gateway, pool=pool, store=store)
    assert await bridge.poll_health() == [("main", True)]
    assert gateway.messages() == ["[服务器状态] main 上线"]


async def test_poll_health_multi_server(two_server_app: App) -> None:
    gateway = two_server_app.make_gateway()
    pool = two_server_app.make_pool(online={"main": True, "world2": False})
    bridge = make_bridge(two_server_app, gateway=gateway, pool=pool)
    flips = await bridge.poll_health()
    assert sorted(flips) == [("main", True), ("world2", False)]
    assert sorted(gateway.messages()) == ["[服务器状态] main 上线", "[服务器状态] world2 离线"]


# ------------------------------------------------------------------ 渲染
def _report_single() -> ServerStatusReport:
    listing = PlayerList(online=1, max_players=20, players=["Steve"], raw="")
    return ServerStatusReport(per_server={"main": listing}, offline=[], total_online=1)


def test_format_status_single() -> None:
    assert format_status(_report_single()) == "[服务器状态]\n在线: 1/20\n玩家: Steve"


def test_format_status_single_no_players() -> None:
    listing = PlayerList(online=0, max_players=20, players=[], raw="")
    report = ServerStatusReport(per_server={"main": listing}, offline=[], total_online=0)
    assert format_status(report) == "[服务器状态]\n在线: 0/20\n玩家: 无"


def test_format_status_all_offline() -> None:
    report = ServerStatusReport(per_server={"main": None, "world2": None}, offline=["main", "world2"], total_online=0)
    assert format_status(report) == "[服务器状态] 服务器离线"
    assert format_status(ServerStatusReport(per_server={}, offline=[], total_online=0)) == "[服务器状态] 服务器离线"


def test_format_status_multi_mixed() -> None:
    report = ServerStatusReport(
        per_server={
            "main": PlayerList(online=3, max_players=20, players=["a", "b", "c"], raw=""),
            "world2": None,
        },
        offline=["world2"],
        total_online=3,
    )
    assert format_status(report) == (
        "[服务器状态]\nmain: 在线 3/20 玩家: a, b, c\nworld2: 离线\n总计: 3 人在线"
    )


def test_bridge_format_status_delegates(app: App) -> None:
    bridge = make_bridge(app)
    assert bridge.format_status(_report_single()) == format_status(_report_single())


def test_format_to_mc() -> None:
    assert Bridge._format_to_mc("Steve", "你好") == "[QQ] Steve: 你好"


def test_single_line_helper(app: App) -> None:
    bridge = make_bridge(app)
    assert bridge._single_line("a\nb") == "a"
    assert bridge._single_line("") == ""
    assert bridge._single_line("  padded  ") == "padded"


def test_extract_text_helper(app: App) -> None:
    bridge = make_bridge(app)
    assert bridge._extract_text("<image/>hi") == "hi"
    assert bridge._extract_text("你好") == "你好"


def test_outgoing_message_reply_flag() -> None:
    passive = OutgoingGroupMessage(group_openid="g", text="t", reply_to_message_id="m")
    active = OutgoingGroupMessage(group_openid="g", text="t")
    assert passive.reply_to_message_id == "m"
    assert active.reply_to_message_id is None
