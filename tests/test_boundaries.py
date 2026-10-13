"""边界与失败分支补测（PLAN.md §6 T9）：配置 / 绑定 / 状态 / 日志模板 / 指令表 / QQ 文本归一化。

本文件只补「正常路径之外」的用例：空输入、越界值、类型错误、损坏文件、缺字段，
断言的是**用户可见的报错文案与最终状态**，不是内部实现细节。
逐模块的常规用例仍在 tests/test_config.py、test_binding.py、test_state.py 等文件里。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import config_text
from y33bot.binding import BindingError, BindingStore, is_valid_game_id
from y33bot.commands.registry import UNKNOWN_COMMAND_REPLY, CommandRegistry, CommandSpec
from y33bot.config import ConfigError, LogPatterns, load_config
from y33bot.mclog.patterns import PatternError, compile_patterns, parse_line
from y33bot.qq.gateway import normalize_content
from y33bot.state import StateStore

CONFIG = "config.toml"


# ==================================================================== 工具
def base_config(tmp_path: Path) -> str:
    """一份合法配置文本（日志文件已建好，路径相对配置文件所在目录）。"""

    log = tmp_path / "logs" / "main.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_bytes(b"")
    return config_text(log_path=log)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / CONFIG
    path.write_text(text, encoding="utf-8")
    return path


def load(tmp_path: Path, text: str):
    return load_config(write(tmp_path, text), {})


def expect_error(tmp_path: Path, text: str, fragment: str) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load(tmp_path, text)
    assert fragment in str(excinfo.value), str(excinfo.value)


# ==================================================================== config.py
def test_config_missing_table(tmp_path: Path) -> None:
    """整段缺失（[behavior] 改名）→ 明确指出缺哪一段。"""

    expect_error(tmp_path, base_config(tmp_path).replace("[behavior]", "[behavior_x]"), "缺少配置段 [behavior]")


def test_config_section_not_a_table(tmp_path: Path) -> None:
    expect_error(tmp_path, base_config(tmp_path).replace("[qq]", 'qq = "x"'), "配置项 [qq] 必须是表")


def test_config_required_string_missing(tmp_path: Path) -> None:
    broken = base_config(tmp_path).replace('app_id_env = "QQ_BOT_APP_ID"\n', "")
    expect_error(tmp_path, broken, "缺少必填配置项 qq.app_id_env")


def test_config_required_string_blank_and_wrong_type(tmp_path: Path) -> None:
    text = base_config(tmp_path)
    expect_error(tmp_path, text.replace('app_id_env = "QQ_BOT_APP_ID"', 'app_id_env = "   "'), "必须是非空字符串")
    expect_error(tmp_path, text.replace('app_id_env = "QQ_BOT_APP_ID"', "app_id_env = 42"), "必须是非空字符串")


def test_config_optional_string_wrong_type(tmp_path: Path) -> None:
    expect_error(
        tmp_path, base_config(tmp_path).replace('group_openid = "GROUP-OPENID-1"', "group_openid = 7"), "必须是字符串"
    )


def test_config_prefix_must_be_single_char(tmp_path: Path) -> None:
    text = base_config(tmp_path)
    expect_error(tmp_path, text.replace('command_prefix = "/"', 'command_prefix = "//"'), "必须是单字符")
    expect_error(tmp_path, text.replace('chat_prefix = "#"', 'chat_prefix = ""'), "必须是非空字符串")


def test_config_env_name_must_be_valid_identifier(tmp_path: Path) -> None:
    text = base_config(tmp_path)
    expect_error(tmp_path, text.replace('app_id_env = "QQ_BOT_APP_ID"', 'app_id_env = "1BAD-NAME"'), "qq.app_id_env")
    expect_error(
        tmp_path,
        text.replace('app_secret_env = "QQ_BOT_APP_SECRET"', 'app_secret_env = "with-dash"'),
        "qq.app_secret_env",
    )


def test_config_behavior_number_validation(tmp_path: Path) -> None:
    text = base_config(tmp_path)
    expect_error(tmp_path, text.replace("log_poll_interval = 0.05", "log_poll_interval = 0"), "必须 > 0")
    expect_error(tmp_path, text.replace("log_poll_interval = 0.05", 'log_poll_interval = "fast"'), "必须是数字")
    expect_error(tmp_path, text.replace("log_poll_interval = 0.05\n", ""), "缺少必填配置项 behavior.log_poll_interval")
    expect_error(tmp_path, text.replace("health_poll_interval = 5.0", "health_poll_interval = -1"), "必须 > 0")


@pytest.mark.parametrize(
    ("line", "fragment"),
    [
        ("max_line_length = 0", "必须 >= 1"),
        ("max_line_length = 1447", "必须 <= 1446"),
        ("max_line_length = 200.5", "必须是整数"),
        ("max_line_length = true", "必须是整数"),
    ],
)
def test_config_max_line_length_bounds(tmp_path: Path, line: str, fragment: str) -> None:
    expect_error(tmp_path, base_config(tmp_path).replace("max_line_length = 200", line), fragment)


def test_config_max_line_length_missing(tmp_path: Path) -> None:
    expect_error(
        tmp_path,
        base_config(tmp_path).replace("max_line_length = 200\n", ""),
        "缺少必填配置项 behavior.max_line_length",
    )


def test_config_ignored_prefixes_must_be_string_array(tmp_path: Path) -> None:
    text = base_config(tmp_path)
    expect_error(
        tmp_path,
        text.replace('ignored_chat_prefixes = ["[QQ]"]', 'ignored_chat_prefixes = "x"'),
        "必须是字符串数组",
    )
    expect_error(
        tmp_path,
        text.replace('ignored_chat_prefixes = ["[QQ]"]', "ignored_chat_prefixes = [1]"),
        "必须是字符串数组",
    )
    expect_error(tmp_path, text.replace('ignored_chat_prefixes = ["[QQ]"]\n', ""), "缺少必填配置项")


def test_config_behavior_accepts_empty_ignored_prefixes(tmp_path: Path) -> None:
    """空数组是合法值（PLAN.md §4.1：可空数组），不能误判为缺失。"""

    cfg = load(
        tmp_path,
        base_config(tmp_path).replace('ignored_chat_prefixes = ["[QQ]"]', "ignored_chat_prefixes = []"),
    )
    assert cfg.behavior.ignored_chat_prefixes == ()


def test_config_paths_required_keys(tmp_path: Path) -> None:
    text = base_config(tmp_path)
    expect_error(tmp_path, text.replace('bindings = "data/bindings.toml"\n', ""), "缺少必填配置项 paths.bindings")
    expect_error(tmp_path, text.replace('state = "data/state.json"', "state = 3"), "必须是非空字符串")


def test_config_absolute_paths_are_kept(tmp_path: Path) -> None:
    target = (tmp_path / "elsewhere" / "bindings.toml").as_posix()
    cfg = load(tmp_path, base_config(tmp_path).replace('bindings = "data/bindings.toml"', f'bindings = "{target}"'))
    assert cfg.bindings_path == Path(target)


def test_config_mc_servers_item_must_be_table(tmp_path: Path) -> None:
    """`mc_servers` 是数组但元素不是表（TOML 允许 `mc_servers = ["oops"]`，此时没有表数组）。"""

    text = 'mc_servers = ["oops"]\n' + base_config(tmp_path).split("[[mc_servers]]")[0]
    expect_error(tmp_path, text, "mc_servers 第 1 项必须是表")


def test_config_mc_servers_missing_or_empty(tmp_path: Path) -> None:
    text = base_config(tmp_path)
    start = text.index("[[mc_servers]]")
    end = text.index("[log_patterns]")
    expect_error(tmp_path, text[:start] + text[end:], "缺少配置段 [[mc_servers]]")


def test_config_server_name_must_match_pattern(tmp_path: Path) -> None:
    expect_error(tmp_path, base_config(tmp_path).replace('name = "main"', 'name = "bad name"'), "不合法")


def test_config_server_password_env_must_be_valid_identifier(tmp_path: Path) -> None:
    broken = base_config(tmp_path).replace('password_env = "MC_RCON_PASSWORD_MAIN"', 'password_env = "1-bad"')
    expect_error(tmp_path, broken, "password_env 不是合法环境变量名")


@pytest.mark.parametrize(
    ("line", "fragment"),
    [
        ("port = 0", "必须 >= 1"),
        ("port = 70000", "必须 <= 65535"),
        ('port = "25575"', "必须是整数"),
    ],
)
def test_config_server_port_bounds(tmp_path: Path, line: str, fragment: str) -> None:
    expect_error(tmp_path, base_config(tmp_path).replace("port = 25575", line), fragment)


def test_config_server_timeouts_default_and_validation(tmp_path: Path) -> None:
    text = base_config(tmp_path)
    defaulted = text.replace("connect_timeout = 1.0\n", "").replace("command_timeout = 1.0\n", "")
    cfg = load(tmp_path, defaulted)
    assert (cfg.servers[0].connect_timeout, cfg.servers[0].command_timeout) == (5.0, 5.0)
    expect_error(tmp_path, text.replace("connect_timeout = 1.0", "connect_timeout = 0"), "必须 > 0")
    expect_error(tmp_path, text.replace("command_timeout = 1.0", "command_timeout = -2"), "必须 > 0")


def test_config_read_failure_is_wrapped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """已存在但读不动（权限/IO 错误）→ ConfigError，而不是裸 OSError。"""

    path = write(tmp_path, base_config(tmp_path))

    def boom(self: Path, *args, **kwargs):
        raise OSError("disk on fire")

    monkeypatch.setattr(Path, "read_text", boom)
    with pytest.raises(ConfigError) as excinfo:
        load_config(path, {})
    assert "配置文件读取失败" in str(excinfo.value)


def test_config_lookup_helpers(tmp_path: Path) -> None:
    cfg = load(tmp_path, base_config(tmp_path))
    assert cfg.server("nope") is None
    assert cfg.server_names() == ["main"]

    server = cfg.server("main")
    assert server is not None
    # 主变量缺失 → 回退 MC_RCON_PASSWORD（A18）
    assert cfg.rcon_password(server, {"MC_RCON_PASSWORD": "fb"}) == "fb"
    assert cfg.rcon_password(server, {"MC_RCON_PASSWORD_MAIN": " main-pw "}) == "main-pw"
    assert cfg.rcon_passwords({"MC_RCON_PASSWORD_MAIN": "pw"}) == {"main": "pw"}
    with pytest.raises(ConfigError) as excinfo:
        cfg.rcon_password(server, {})
    assert "MC_RCON_PASSWORD" in str(excinfo.value) and "未设置" in str(excinfo.value)
    with pytest.raises(ConfigError):
        cfg.rcon_passwords({})


def test_config_app_credentials_requires_both(tmp_path: Path) -> None:
    cfg = load(tmp_path, base_config(tmp_path))
    assert cfg.app_credentials({"QQ_BOT_APP_ID": "id", "QQ_BOT_APP_SECRET": "sec"}) == ("id", "sec")
    with pytest.raises(ConfigError) as excinfo:
        cfg.app_credentials({})
    assert "QQ_BOT_APP_ID 未设置" in str(excinfo.value)
    with pytest.raises(ConfigError) as excinfo:
        cfg.app_credentials({"QQ_BOT_APP_ID": "id"})
    assert "QQ_BOT_APP_SECRET 未设置" in str(excinfo.value)
    assert cfg.qq.mc_to_qq_enabled is True


def test_config_mc_to_qq_disabled_when_group_openid_blank(tmp_path: Path) -> None:
    cfg = load(tmp_path, base_config(tmp_path).replace('group_openid = "GROUP-OPENID-1"', 'group_openid = "  "'))
    assert cfg.qq.mc_to_qq_enabled is False


def test_config_empty_file_is_rejected(tmp_path: Path) -> None:
    expect_error(tmp_path, "", "缺少配置段 [qq]")


# ==================================================================== binding.py
def test_binding_load_oserror_is_wrapped(tmp_path: Path) -> None:
    """路径存在但是目录（读不动）→ BindingError，且不去动这个路径。"""

    directory = tmp_path / "bindings-as-dir"
    directory.mkdir()
    with pytest.raises(BindingError) as excinfo:
        BindingStore.load(directory)
    assert "绑定表读取失败" in str(excinfo.value)
    assert directory.is_dir()


def test_binding_entry_must_be_table(tmp_path: Path) -> None:
    path = tmp_path / "bindings.toml"
    path.write_text('bindings = ["oops"]\n', encoding="utf-8")
    with pytest.raises(BindingError) as excinfo:
        BindingStore.load(path)
    assert "必须是表（table）" in str(excinfo.value)


def test_binding_entry_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "bindings.toml"
    path.write_text('[[bindings]]\ngame_id = "Steve"\n', encoding="utf-8")
    with pytest.raises(BindingError) as excinfo:
        BindingStore.load(path)
    assert "缺少 qq_openid" in str(excinfo.value) and path.read_text(encoding="utf-8") != ""

    path.write_text('[[bindings]]\nqq_openid = "OP-1"\n', encoding="utf-8")
    with pytest.raises(BindingError) as excinfo:
        BindingStore.load(path)
    assert "缺少 game_id" in str(excinfo.value)

    path.write_text('[[bindings]]\nqq_openid = "   "\ngame_id = "Steve"\n', encoding="utf-8")
    with pytest.raises(BindingError) as excinfo:
        BindingStore.load(path)
    assert "缺少 qq_openid" in str(excinfo.value)


def test_binding_whitespace_is_trimmed_on_load_and_bind(tmp_path: Path) -> None:
    path = tmp_path / "data" / "bindings.toml"  # 目录不存在 → save() 必须自己建
    store = BindingStore(path)
    store.bind("  OP-1  ", "  Steve  ")
    store.save()
    assert BindingStore.load(path).items() == {"OP-1": "Steve"}


def test_binding_lookup_unbind_and_membership(tmp_path: Path) -> None:
    store = BindingStore(tmp_path / "bindings.toml")
    store.bind("OP-B", "Alex")
    store.bind("OP-A", "Steve")
    assert store.lookup("OP-A") == "Steve"
    assert store.lookup("OP-MISSING") is None
    assert store.items() == {"OP-A": "Steve", "OP-B": "Alex"}  # 按 openid 排序
    assert len(store) == 2
    assert "OP-A" in store and "OP-X" not in store
    assert store.unbind("OP-A") is True
    assert store.unbind("OP-A") is False
    assert len(store) == 1


def test_binding_bind_rejects_blank_input(tmp_path: Path) -> None:
    store = BindingStore(tmp_path / "bindings.toml")
    with pytest.raises(BindingError) as excinfo:
        store.bind("   ", "Steve")
    assert "qq_openid 不能为空" in str(excinfo.value)
    with pytest.raises(BindingError):
        store.bind("OP-1", "ab")  # 太短
    with pytest.raises(BindingError):
        store.bind("OP-1", "a" * 17)  # 太长
    with pytest.raises(BindingError):
        store.bind("OP-1", "bad-name")  # 含非法字符
    assert len(store) == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Steve", True),
        ("Steve_123", True),
        ("ab", False),
        ("a" * 17, False),
        ("bad name", False),
        ("", False),
        (None, False),
    ],
)
def test_binding_is_valid_game_id(value: object, expected: bool) -> None:
    assert is_valid_game_id(value) is expected  # type: ignore[arg-type]


# ==================================================================== state.py
def test_state_load_non_dict_json_is_backed_up(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    store = StateStore.load(path)
    assert store.state.qq_msg_seq == 0 and store.state.servers == {}
    assert (tmp_path / "state.json.bak").exists()


def test_state_load_directory_path_is_tolerated(tmp_path: Path) -> None:
    """状态路径被误建成目录 → 备份后重置，不抛异常（服务不该因此起不来）。"""

    directory = tmp_path / "state-dir"
    directory.mkdir()
    store = StateStore.load(directory)
    assert store.state.qq_msg_seq == 0
    assert (tmp_path / "state-dir.bak").is_dir()


def test_state_bad_server_entry_is_skipped(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"version": 1, "qq": {"msg_seq": "nope"}, "servers": {"main": 42}}', encoding="utf-8")
    store = StateStore.load(path)
    assert store.state.servers == {}
    assert store.state.qq_msg_seq == 0


def test_state_fields_are_coerced(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        '{"version": 1, "servers": {"main": {"log_offset": -5, "log_size": "x",'
        ' "log_inode": null, "health_online": "yes", "health_changed_at": "x"}}}',
        encoding="utf-8",
    )
    state = StateStore.load(path).state.servers["main"]
    assert (state.log_offset, state.log_size, state.log_inode) == (0, 0, "")
    assert state.health_online is None
    assert state.health_changed_at == 0.0


def test_state_servers_must_be_a_dict(tmp_path: Path) -> None:
    """`servers` 是数组（人工改坏）→ 整块忽略，不抛异常。"""

    path = tmp_path / "state.json"
    path.write_text('{"version": 1, "servers": ["main"]}', encoding="utf-8")
    store = StateStore.load(path)
    assert store.state.servers == {}


def test_state_next_msg_seq_and_to_dict(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.json")
    assert store.next_msg_seq() == 1
    assert store.next_msg_seq() == 2
    store.server_state("main").health_online = False
    payload = store.to_dict()
    assert payload["version"] == 1
    assert payload["qq"] == {"msg_seq": 2}
    assert payload["servers"]["main"]["health_online"] is False


def test_state_server_state_is_cached(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.json")
    first = store.server_state("main")
    assert store.server_state("main") is first


# ==================================================================== mclog/patterns.py
class _MissingChatPatterns:
    """只有 join/quit 的伪 LogPatterns：用于验证「缺字段」是编译期错误。"""

    join = r"\[(?P<player>\w+)\] joined"
    quit = r"\[(?P<player>\w+)\] left"
    encoding = "utf-8"


def test_patterns_missing_field_is_rejected() -> None:
    with pytest.raises(PatternError) as excinfo:
        compile_patterns(_MissingChatPatterns())  # type: ignore[arg-type]
    assert "缺少字段: chat" in str(excinfo.value)


def test_patterns_accessor_and_parse_boundaries() -> None:
    compiled = compile_patterns(
        LogPatterns(
            join=r"\[(?P<player>\w+)\] joined",
            quit=r"\[(?P<player>\w+)\] left",
            chat=r"<(?P<player>\w+)> (?P<message>.*)",
        )
    )
    assert compiled.pattern("chat") is compiled.chat
    with pytest.raises(AttributeError):
        compiled.pattern("nope")

    # 空消息（chat 的 message 允许为空串）仍是一条事件，不返回 None
    event = parse_line(compiled, "<Steve> ")
    assert event is not None and event.message == ""
    assert parse_line(compiled, "完全不相干的一行") is None
    assert parse_line(compiled, "") is None


def test_patterns_empty_and_invalid_are_rejected() -> None:
    with pytest.raises(PatternError) as excinfo:
        compile_patterns(LogPatterns(join="   ", quit="x(?P<player>y)", chat="(?P<player>a)(?P<message>b)"))
    assert "不能为空" in str(excinfo.value)
    with pytest.raises(PatternError) as excinfo:
        compile_patterns(LogPatterns(join="([", quit="x(?P<player>y)", chat="(?P<player>a)(?P<message>b)"))
    assert "不是合法正则" in str(excinfo.value)


# ==================================================================== commands/registry.py
def test_command_spec_matches_name_and_alias() -> None:
    spec = CommandSpec(name="status", handler=lambda ctx, args: None, aliases=("s", "st"))  # type: ignore[arg-type]
    assert spec.matches("status") is True
    assert spec.matches("s") is True
    assert spec.matches("S") is False  # 别名大小写由 registry 归一化，spec 本身按字面比较
    assert spec.matches("nope") is False


def test_registry_get_and_alias_lookup() -> None:
    registry = CommandRegistry()

    @registry.register("Status", aliases=["s", "", "  "], desc="查询")
    async def handler(ctx, args):  # noqa: ANN001, ANN202
        return "ok"

    assert registry.names() == ["status"]
    spec = registry.get("STATUS")
    assert spec is not None and spec.name == "status"
    assert spec.aliases == ("s",)  # 空别名被丢弃
    assert registry.get("s") is spec
    assert registry.get("") is None
    assert registry.get("   ") is None
    assert registry.get("nope") is None


async def test_registry_dispatch_empty_line_is_unknown(app) -> None:  # noqa: ANN001
    registry = CommandRegistry()
    context = type("Ctx", (), {"config": app.config})()
    assert await registry.dispatch(context, "") == UNKNOWN_COMMAND_REPLY  # type: ignore[arg-type]
    assert await registry.dispatch(context, "   ") == UNKNOWN_COMMAND_REPLY  # type: ignore[arg-type]
    assert await registry.dispatch(context, "没有前缀") == UNKNOWN_COMMAND_REPLY  # type: ignore[arg-type]


def test_registry_add_rejects_duplicate_name() -> None:
    registry = CommandRegistry()
    registry.add(CommandSpec(name="dup", handler=lambda ctx, args: None))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="重复注册"):
        registry.add(CommandSpec(name="dup", handler=lambda ctx, args: None))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="指令名不能为空"):
        registry.register("   ")


async def test_bind_reports_save_failure(
    app, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # noqa: ANN001
    """写盘失败（磁盘满/权限）→ 群内固定失败文案 + 日志留痕，而不是抛异常。"""

    import logging

    from y33bot.commands.builtin import cmd_bind
    from y33bot.commands.registry import CommandContext
    from y33bot.models import MCGroupMessage

    context = CommandContext(
        config=app.config,
        bindings=app.bindings(),
        rcon=None,  # type: ignore[arg-type]
        state=app.state(),
        message=MCGroupMessage(
            group_openid="G-1", member_openid="OP-1", message_id="M-1", content="/bind Steve", received_at=0.0
        ),
        logger=logging.getLogger("y33bot.commands.builtin"),
    )

    def boom(self) -> None:
        raise BindingError("磁盘满了")

    monkeypatch.setattr(BindingStore, "save", boom)
    with caplog.at_level("ERROR"):
        assert await cmd_bind(context, ["Steve"]) == "绑定失败，请查看服务日志"
    assert any("绑定写入失败" in record.getMessage() for record in caplog.records)


# ==================================================================== qq/gateway.normalize_content
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("<@!123>", ""),
        ("<@123>   ", ""),
        ("<@!1><@!2> #hi", "#hi"),
        ("<@abc> #hi", "<@abc> #hi"),  # 只剥数字 @（A5）
        ("#hi\n#第二行", "#hi\n#第二行"),
    ],
)
def test_normalize_content_boundaries(raw: str, expected: str) -> None:
    assert normalize_content(raw) == expected
