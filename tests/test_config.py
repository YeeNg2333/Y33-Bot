"""config 模块测试（PLAN.md §4.1 / §4.5 / T2）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import DEFAULT_ENV, App, config_text
from y33bot.config import ConfigError, load_config


def test_load_example_config(tmp_path: Path) -> None:
    """仓库内的 config.example.toml 必须能被直接加载（S1 前置）。"""

    example = Path(__file__).resolve().parents[1] / "config.example.toml"
    config = load_config(example, DEFAULT_ENV)
    assert [server.name for server in config.servers] == ["main"]
    assert config.behavior.max_line_length == 200
    assert config.behavior.ignored_chat_prefixes == ("[QQ]", "[→QQ]")
    assert config.qq.mc_to_qq_enabled is True
    # 相对路径按配置文件所在目录解析
    assert config.bindings_path == example.resolve().parent / "data" / "bindings.toml"
    assert config.state_path == example.resolve().parent / "data" / "state.json"


def test_paths_resolve_relative_to_config(tmp_path: Path) -> None:
    app = App(tmp_path)
    assert app.config.bindings_path == tmp_path / "data" / "bindings.toml"
    assert app.config.server("main").log_path == app.log_path
    assert app.config.server_names() == ["main"]
    assert app.config.server("nope") is None


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="配置文件不存在"):
        load_config(tmp_path / "nope.toml")


def test_invalid_toml(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("this is not toml", encoding="utf-8")
    with pytest.raises(ConfigError, match="不是合法 TOML"):
        load_config(path)


@pytest.mark.parametrize(
    ("patch", "match"),
    [
        ("[behavior]", "缺少配置段"),
        ("[paths]", "缺少配置段"),
    ],
)
def test_missing_sections(tmp_path: Path, patch: str, match: str) -> None:
    app = App(tmp_path)
    text = app.config_path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith(patch)]
    app.config_path.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(ConfigError, match=match):
        load_config(app.config_path)


def _write_and_load(tmp_path: Path, text: str):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return load_config(path, DEFAULT_ENV)


def _base_text(tmp_path: Path) -> str:
    return config_text(log_path=tmp_path / "main.log")


@pytest.mark.parametrize(
    ("old", "new", "match"),
    [
        ('name = "main"', 'name = "bad name!"', "name 不合法"),
        ("port = 25575", "port = 70000", "port 必须 <= 65535"),
        ("port = 25575", "port = 0", "port 必须 >= 1"),
        ('password_env = "MC_RCON_PASSWORD_MAIN"', 'password_env = "1bad"', "合法环境变量名"),
        ("max_line_length = 200", "max_line_length = 0", "max_line_length 必须 >= 1"),
        ("max_line_length = 200", "max_line_length = 2000", "max_line_length 必须 <= 1446"),
        ("log_poll_interval = 0.05", "log_poll_interval = 0", "log_poll_interval 必须 > 0"),
        ("health_poll_interval = 5.0", "health_poll_interval = -1", "health_poll_interval 必须 > 0"),
        ('chat_prefix = "#"', 'chat_prefix = "##"', "必须是单字符"),
        ('encoding = "utf-8"', "encoding = 5", "必须是字符串"),
        ('ignored_chat_prefixes = ["[QQ]", "[→QQ]"]', "ignored_chat_prefixes = 5", "字符串数组"),
    ],
)
def test_field_validation(tmp_path: Path, old: str, new: str, match: str) -> None:
    text = _base_text(tmp_path).replace(old, new, 1)
    assert text != _base_text(tmp_path), f"测试用例未命中待替换片段: {old}"
    with pytest.raises(ConfigError, match=match):
        _write_and_load(tmp_path, text)


def test_duplicate_server_names(tmp_path: Path) -> None:
    text = _base_text(tmp_path)
    block = text[text.index("[[mc_servers]]") : text.index("[log_patterns]")]
    text = text.replace("[log_patterns]", block + "\n[log_patterns]")
    with pytest.raises(ConfigError, match="名称重复"):
        _write_and_load(tmp_path, text)


def test_missing_mc_servers(tmp_path: Path) -> None:
    text = _base_text(tmp_path)
    start = text.index("[[mc_servers]]")
    end = text.index("[log_patterns]")
    with pytest.raises(ConfigError, match=r"\[\[mc_servers\]\]"):
        _write_and_load(tmp_path, text[:start] + text[end:])


def test_pattern_without_named_group(tmp_path: Path) -> None:
    text = _base_text(tmp_path).replace("(?P<player>\\w+) joined", "\\w+ joined", 1)
    with pytest.raises(ConfigError, match="日志模板校验失败"):
        _write_and_load(tmp_path, text)


def test_pattern_invalid_regex(tmp_path: Path) -> None:
    text = _base_text(tmp_path).replace("join = '", "join = '(", 1)
    with pytest.raises(ConfigError, match="日志模板校验失败"):
        _write_and_load(tmp_path, text)


def test_credentials_and_passwords(tmp_path: Path) -> None:
    app = App(tmp_path)
    server = app.config.server("main")
    assert server is not None
    assert app.config.app_credentials(app.env) == ("102000000", "test-secret")
    assert app.config.rcon_password(server, app.env) == "main-secret"
    assert app.config.rcon_password(server, {"MC_RCON_PASSWORD": "fallback"}) == "fallback"
    with pytest.raises(ConfigError, match="MC_RCON_PASSWORD_MAIN"):
        app.config.rcon_password(server, {})
    with pytest.raises(ConfigError, match="QQ_BOT_APP_SECRET"):
        app.config.app_credentials({"QQ_BOT_APP_ID": "1"})


def test_app_id_env_name_validation(tmp_path: Path) -> None:
    text = _base_text(tmp_path).replace('app_id_env = "QQ_BOT_APP_ID"', 'app_id_env = "1bad"')
    with pytest.raises(ConfigError, match="不是合法环境变量名"):
        _write_and_load(tmp_path, text)
