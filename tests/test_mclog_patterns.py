"""mclog.patterns 测试（PLAN.md A9 / R27 / T5）。"""

from __future__ import annotations

import dataclasses

import pytest

from conftest import CHAT_TEMPLATE, JOIN_TEMPLATE, QUIT_TEMPLATE
from y33bot.config import LogPatterns
from y33bot.mclog.patterns import (
    REQUIRED_GROUPS,
    CompiledPatterns,
    PatternError,
    compile_patterns,
    looks_like_event,
    parse_line,
)


def _patterns(**overrides) -> LogPatterns:
    return LogPatterns(
        join=overrides.get("join", JOIN_TEMPLATE),
        quit=overrides.get("quit", QUIT_TEMPLATE),
        chat=overrides.get("chat", CHAT_TEMPLATE),
        encoding=overrides.get("encoding", "utf-8"),
    )


def test_compile_adds_anchors() -> None:
    compiled = compile_patterns(_patterns())
    assert compiled.join.pattern.startswith("^")
    assert compiled.join.pattern.endswith("$")
    assert compiled.encoding == "utf-8"


def test_anchors_are_not_duplicated() -> None:
    compiled = compile_patterns(_patterns(join="^" + JOIN_TEMPLATE + "$"))
    assert compiled.join.pattern.count("^") == 1
    assert compiled.join.pattern.endswith("$")
    assert not compiled.join.pattern.endswith("$$")


def test_trailing_text_does_not_match() -> None:
    compiled = compile_patterns(_patterns())
    body = "[12:00:01] [Server thread/INFO]: Steve joined the game"
    assert parse_line(compiled, body) is not None
    assert parse_line(compiled, body + " extra") is None  # A9：行尾必须锚定


@pytest.mark.parametrize("kind", ["join", "quit", "chat"])
def test_empty_template_rejected(kind: str) -> None:
    with pytest.raises(PatternError, match="不能为空"):
        compile_patterns(_patterns(**{kind: "   "}))


def test_invalid_regex_rejected() -> None:
    with pytest.raises(PatternError, match="不是合法正则"):
        compile_patterns(_patterns(join="[unclosed"))


@pytest.mark.parametrize(
    ("kind", "template", "group"),
    [
        ("join", r"\[INFO\]: (?P<who>\w+) joined the game", "player"),
        ("quit", r"\[INFO\]: \w+ left the game", "player"),
        ("chat", r"<(?P<player>\w+)> (?P<text>.+)", "message"),
    ],
)
def test_missing_named_group(kind: str, template: str, group: str) -> None:
    with pytest.raises(PatternError, match=group):
        compile_patterns(_patterns(**{kind: template}))


def test_required_groups_table() -> None:
    assert REQUIRED_GROUPS["join"] == ("player",)
    assert REQUIRED_GROUPS["chat"] == ("player", "message")


def test_parse_join_quit_chat() -> None:
    compiled = compile_patterns(_patterns())
    join = parse_line(compiled, "[12:00:04] [Server thread/INFO]: Steve joined the game")
    assert join is not None
    assert (join.kind, join.player, join.message) == ("join", "Steve", None)
    assert join.server == ""  # 由 LogWatcher 填充
    assert join.raw.endswith("joined the game")
    assert join.occurred_at > 0

    quit_event = parse_line(compiled, "[12:00:05] [Server thread/INFO]: Steve left the game")
    assert quit_event is not None
    assert (quit_event.kind, quit_event.player) == ("quit", "Steve")

    chat = parse_line(compiled, "[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好")
    assert chat is not None
    assert (chat.kind, chat.player, chat.message) == ("chat", "Steve", "#大家好")


def test_parse_no_match() -> None:
    compiled = compile_patterns(_patterns())
    assert parse_line(compiled, "[12:00:01] [Server thread/INFO]: Preparing spawn area") is None
    assert parse_line(compiled, "") is None


def test_parse_strips_bom() -> None:
    compiled = compile_patterns(_patterns())
    event = parse_line(compiled, "\ufeff[12:00:04] [Server thread/INFO]: Alex joined the game")
    assert event is not None
    assert event.player == "Alex"


def test_chat_message_keeps_emoji() -> None:
    compiled = compile_patterns(_patterns())
    event = parse_line(compiled, "[12:00:01] [Async Chat Thread - #3/INFO]: <Alex> #hi 😀")
    assert event is not None
    assert event.message == "#hi 😀"


def test_compiled_patterns_is_frozen() -> None:
    compiled = compile_patterns(_patterns())
    assert isinstance(compiled, CompiledPatterns)
    with pytest.raises(dataclasses.FrozenInstanceError):
        compiled.encoding = "latin-1"  # type: ignore[misc]


def test_pattern_accessor() -> None:
    compiled = compile_patterns(_patterns())
    assert compiled.pattern("chat") is compiled.chat


# ------------------------------------------------- looks_like_event（BUG-004）
@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # log4j2 布局（Forge / NeoForge）：线程名后还挂一段 logger
        (
            "[1810月2026 15:35:33.486] [Server thread/INFO] "
            "[net.minecraft.server.MinecraftServer/]: Steve joined the game",
            "join",
        ),
        # 同一套 log4j2 布局，logger 段不以 `/` 结尾的版本
        ("[16:17:07] [Server thread/INFO] [minecraft/MinecraftServer]: Alex left the game", "quit"),
        # 1.21.2+ 多一层 `[Not Secure] ` 前缀；以及 1.21.1 及更早的旧聊天线程布局
        ("[14:30:09] [Server thread/INFO]: [Not Secure] <Steve> #大家好", "chat"),
        ("[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好", "chat"),
        # 无关行：服务端启动噪声 / 空行都不是候选
        ("[12:00:02] [Server thread/INFO]: Preparing spawn area: 12%", None),
        ("[12:00:00] [main/INFO]: Loading 45 mods:", None),
        ("", None),
    ],
)
def test_looks_like_event_judges_by_payload_not_layout(line: str, expected: str | None) -> None:
    """判别助手只看业务载荷：模板写错、加载器换布局时，这行仍要被认成「本该是个事件」。"""

    assert looks_like_event(line) == expected
