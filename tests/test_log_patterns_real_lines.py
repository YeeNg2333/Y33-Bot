"""出厂默认日志模板的回归锁：三方逐字相等 + 四族真机真行可解析。

本文件锁两件事：

1. **三方相等**（模板字符串在仓库里有 6 份副本，分叉过一次就单测全绿也测不出失配）：
   `config.example.toml` 的 `[log_patterns]` ≡ `tests/conftest.py` 的三常量 ≡ `PLAN.md` §3.5 代码块；
2. **出厂默认真的能解析真机日志**：vanilla（≥1.21.2 与 ≤1.21.1 旧形态）、Fabric 26.1、Forge、NeoForge 1.21.4。

真行**内联为常量**，不读 `test-notes/`，也不放 `data/`（该目录名被 `.gitignore` 命中），保证离线可跑。
行尾的族名注明来源子目录，便于回溯（`test-notes/artifacts/<族>/`）。
"""

from __future__ import annotations

import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from conftest import CHAT_TEMPLATE, JOIN_TEMPLATE, QUIT_TEMPLATE, App
from y33bot.config import LogPatterns
from y33bot.mclog.patterns import CompiledPatterns, compile_patterns, parse_line

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_EXAMPLE = REPO_ROOT / "config.example.toml"
PLAN_MD = REPO_ROOT / "PLAN.md"

KINDS = ("join", "quit", "chat")

#: 夹具里的三常量（与 `config.example.toml` 必须逐字一致，否则测的就是两套模板）
FIXTURE_TEMPLATES: dict[str, str] = {"join": JOIN_TEMPLATE, "quit": QUIT_TEMPLATE, "chat": CHAT_TEMPLATE}

#: 语义用例用到的两条 Fabric 真行（同为 chat，只是 `#` 前缀不同）
FABRIC_261_PLAIN_CHAT = "[15:22:30] [Server thread/INFO]: [Not Secure] <Steve> 大家好，这是普通聊天（不该被转发）"
FABRIC_261_HASH_CHAT = "[15:22:31] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）"

#: 真机真行：(族, 行, kind, player, message)。chat 的 message 不含 `[Not Secure]` 标记。
REAL_LINES: tuple[tuple[str, str, str, str, str | None], ...] = (
    # vanilla ≥1.21.2（test-notes/artifacts/vanilla/1.21.x）：服务器线程 + `[Not Secure]` 聊天前缀
    ("vanilla-ge1.21.2-join", "[15:18:27] [Server thread/INFO]: Steve joined the game", "join", "Steve", None),
    ("vanilla-ge1.21.2-quit", "[15:18:31] [Server thread/INFO]: Steve left the game", "quit", "Steve", None),
    (
        "vanilla-ge1.21.2-chat",
        "[15:18:30] [Server thread/INFO]: [Not Secure] <Steve> #矩阵测试：带井号聊天（应被转发）",
        "chat",
        "Steve",
        "#矩阵测试：带井号聊天（应被转发）",
    ),
    # Fabric 26.1（test-notes/artifacts/fabric/26.1/real-chat-lines-raw-26.1.txt）
    ("fabric-26.1-join", "[15:22:28] [Server thread/INFO]: Steve joined the game", "join", "Steve", None),
    ("fabric-26.1-quit", "[15:22:33] [Server thread/INFO]: Steve left the game", "quit", "Steve", None),
    ("fabric-26.1-chat", FABRIC_261_HASH_CHAT, "chat", "Steve", "#大家好，这是带井号的聊天（应被转发）"),
    (
        "fabric-26.1-plain-chat",
        FABRIC_261_PLAIN_CHAT,
        "chat",
        "Steve",
        "大家好，这是普通聊天（不该被转发）",
    ),
    # Forge（test-notes/artifacts/forge/）：`1810月2026` 式时间戳 + logger 段，两种 logger 变体都有
    (
        "forge-join",
        "[1810月2026 15:35:33.486] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve joined the game",
        "join",
        "Steve",
        None,
    ),
    (
        "forge-chat",
        "[1810月2026 16:17:10.022] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: "
        "[Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）",
        "chat",
        "Steve",
        "#大家好，这是带井号的聊天（应被转发）",
    ),
    (
        # logger 段不以 `/` 结尾的变体：模板里的 logger 段不能强制 `\[[^\]]+/\]`
        "forge-quit-logger-without-slash",
        "[16:17:11] [Server thread/INFO] [minecraft/MinecraftServer]: Steve left the game",
        "quit",
        "Steve",
        None,
    ),
    # NeoForge 1.21.4（test-notes/artifacts/neoforge/1.21.4/）
    (
        "neoforge-1.21.4-join",
        "[1810月2026 15:25:45.610] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve joined the game",
        "join",
        "Steve",
        None,
    ),
    (
        "neoforge-1.21.4-quit",
        "[1810月2026 15:25:50.263] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve left the game",
        "quit",
        "Steve",
        None,
    ),
    (
        "neoforge-1.21.4-chat",
        "[1810月2026 15:25:48.701] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: "
        "[Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）",
        "chat",
        "Steve",
        "#大家好，这是带井号的聊天（应被转发）",
    ),
    # ≤1.21.1 旧形态（chat 走 `Async Chat Thread - #N`，见 README §5 / docs/smoke.md S3 的样例行）
    (
        "vanilla-le1.21.1-chat",
        "[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好",
        "chat",
        "Steve",
        "#大家好",
    ),
    (
        "vanilla-le1.21.1-chat-thread-12",
        "[12:00:09] [Async Chat Thread - #12/INFO]: <Alex> #hi 😀",
        "chat",
        "Alex",
        "#hi 😀",
    ),
    (
        "vanilla-le1.21.1-plain-chat",
        "[12:00:02] [Async Chat Thread - #0/INFO]: <Steve> 普通聊天",
        "chat",
        "Steve",
        "普通聊天",
    ),
)

#: 非事件行：模板放宽后不能顺手把这些行也当成事件
NON_EVENT_LINES: tuple[tuple[str, str], ...] = (
    (
        "forge-modlauncher",
        "[1810月2026 15:35:02.990] [main/INFO] [cpw.mods.modlauncher.Launcher/MODLAUNCHER]: "
        "ModLauncher running: args [--launchTarget, forge_server, nogui]",
    ),
    (
        "forge-dedicated-done",
        "[1810月2026 15:35:21.982] [Server thread/INFO] "
        '[net.minecraft.server.dedicated.DedicatedServer/]: Done (8.208s)! For help, type "help"',
    ),
)

#: 语义用例用到的两条 Fabric 真行（同为 chat，只是 `#` 前缀不同）
PLAIN_CHAT_LINE = FABRIC_261_PLAIN_CHAT
HASH_CHAT_LINE = FABRIC_261_HASH_CHAT


def _example_log_patterns() -> dict[str, str]:
    """`config.example.toml` 出货默认的三条模板 + encoding。"""

    data = tomllib.loads(CONFIG_EXAMPLE.read_text(encoding="utf-8"))
    patterns = data["log_patterns"]
    return {kind: patterns[kind] for kind in (*KINDS, "encoding")}


def _plan_section_toml() -> dict:
    """`PLAN.md` §3.5 的配置样板代码块（解析成 TOML，顺带验证它本身合法）。"""

    text = PLAN_MD.read_text(encoding="utf-8")
    start = text.index("### 3.5")
    section = text[start : text.index("### 3.6", start)]
    assert "```toml" in section, "PLAN.md §3.5 应含 ```toml 配置样板代码块"
    block = section.split("```toml", 1)[1].split("```", 1)[0]
    return tomllib.loads(block)


def _as_log_patterns(templates: dict[str, str]) -> LogPatterns:
    return LogPatterns(
        join=templates["join"],
        quit=templates["quit"],
        chat=templates["chat"],
        encoding=templates["encoding"],
    )


@pytest.fixture(scope="module")
def factory_patterns() -> CompiledPatterns:
    """出厂默认（`config.example.toml`）编译后的模板。"""

    return compile_patterns(_as_log_patterns(_example_log_patterns()))


# ------------------------------------------------------------------ 三方相等
@pytest.mark.parametrize("kind", KINDS)
def test_fixture_templates_equal_factory_defaults(kind: str) -> None:
    """夹具 ≡ 出厂默认：`tests/conftest.py` 的三常量不得与 `config.example.toml` 分叉。"""

    assert FIXTURE_TEMPLATES[kind] == _example_log_patterns()[kind]


@pytest.mark.parametrize("kind", KINDS)
def test_plan_section_equals_factory_defaults(kind: str) -> None:
    """PLAN.md §3.5 ≡ 出厂默认：配置样板是用户抄写的第一来源，抄错一份等于打死一族布局。"""

    assert _plan_section_toml()["log_patterns"][kind] == _example_log_patterns()[kind]


def test_factory_encoding_is_utf8() -> None:
    assert _example_log_patterns()["encoding"] == "utf-8"


# ------------------------------------------------------------------ 真机真行
@pytest.mark.parametrize(
    ("family", "line", "kind", "player", "message"),
    REAL_LINES,
    ids=[case[0] for case in REAL_LINES],
)
def test_real_line_parses_as_expected(
    factory_patterns: CompiledPatterns,
    family: str,
    line: str,
    kind: str,
    player: str,
    message: str | None,
) -> None:
    event = parse_line(factory_patterns, line)
    assert event is not None, f"{family} 布局未命中出厂默认模板: {line}"
    assert (event.kind, event.player, event.message) == (kind, player, message), f"{family}: {line}"
    assert event.server == ""  # 由 LogWatcher 填充
    assert event.raw == line


@pytest.mark.parametrize(("family", "line"), NON_EVENT_LINES, ids=[case[0] for case in NON_EVENT_LINES])
def test_non_event_line_does_not_parse(factory_patterns: CompiledPatterns, family: str, line: str) -> None:
    assert parse_line(factory_patterns, line) is None, f"{family} 被误判为事件: {line}"


def test_real_lines_cover_all_families_and_kinds() -> None:
    """样本自检：四族布局 + 旧形态都在，join/quit/chat 三类都有，避免用例被悄悄删空。"""

    families = {case[0].split("-")[0] for case in REAL_LINES}
    assert families == {"vanilla", "fabric", "forge", "neoforge"}
    assert {case[2] for case in REAL_LINES} == set(KINDS)
    assert any(case[0].startswith("vanilla-le1.21.1") for case in REAL_LINES)


# ------------------------------------------------------------------ 语义不变
async def test_plain_chat_is_still_ignored_by_bridge(app: App, caplog: pytest.LogCaptureFixture) -> None:
    """放宽模板 ≠ 放宽语义：不带 `#` 的普通聊天仍被 `bridge` 忽略（A8 / R11）。"""

    gateway = app.make_gateway()
    bridge = app.make_bridge(gateway=gateway)
    event = parse_line(compile_patterns(app.config.patterns), PLAIN_CHAT_LINE)
    assert event is not None
    assert event.kind == "chat"
    with caplog.at_level("INFO"):
        await bridge.handle_log_event(replace(event, server="main"))
    assert gateway.sent == []
    assert any("聊天非 # 开头" in record.getMessage() for record in caplog.records)


async def test_hash_chat_is_forwarded_by_bridge(app: App) -> None:
    """同一条真行改成 `#` 开头就该转发（证明上面那条不是被模板漏掉才“没发”）。"""

    gateway = app.make_gateway()
    bridge = app.make_bridge(gateway=gateway)
    event = parse_line(compile_patterns(app.config.patterns), HASH_CHAT_LINE)
    assert event is not None
    await bridge.handle_log_event(replace(event, server="main"))
    assert gateway.messages() == ["Steve@main: 大家好，这是带井号的聊天（应被转发）"]
