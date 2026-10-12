"""配置加载与校验（PLAN.md §3.2 / §3.5 / §4.1 / §4.5 / A18）。

只读不写；密钥一律走环境变量，仓内不存真实凭据。
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .mclog.patterns import PatternError, compile_patterns

__all__ = [
    "AppConfig",
    "Behavior",
    "ConfigError",
    "LogPatterns",
    "MCServerConfig",
    "QQConfig",
    "load_config",
]

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigError(Exception):
    """配置缺失、类型错误或校验失败（启动即失败，退出码 1）。"""


# ---------------------------------------------------------------- 数据结构
@dataclass(frozen=True)
class MCServerConfig:
    """一台 MC 服的连接与日志配置。"""

    name: str
    host: str
    port: int
    password_env: str
    log_path: Path
    connect_timeout: float = 5.0
    command_timeout: float = 5.0


@dataclass(frozen=True)
class QQConfig:
    """QQ 侧配置；`group_openid` 为空则 MC→QQ 方向禁用（A11）。"""

    group_openid: str = ""
    app_id_env: str = "QQ_BOT_APP_ID"
    app_secret_env: str = "QQ_BOT_APP_SECRET"
    command_prefix: str = "/"
    chat_prefix: str = "#"

    @property
    def mc_to_qq_enabled(self) -> bool:
        return bool(self.group_openid.strip())


@dataclass(frozen=True)
class LogPatterns:
    """日志模板（TOML 可改，不改代码，R27）。"""

    join: str
    quit: str
    chat: str
    encoding: str = "utf-8"


@dataclass(frozen=True)
class Behavior:
    """行为参数（PLAN.md §3.5 / N6）。"""

    log_poll_interval: float = 0.5
    health_poll_interval: float = 30.0
    max_line_length: int = 200
    ignored_chat_prefixes: tuple[str, ...] = ("[QQ]", "[→QQ]")


@dataclass(frozen=True)
class AppConfig:
    """整份配置的运行时视图。"""

    qq: QQConfig
    servers: list[MCServerConfig]
    patterns: LogPatterns
    behavior: Behavior
    bindings_path: Path
    state_path: Path

    # ------------------------------------------------------------ 便捷访问
    def server(self, name: str) -> MCServerConfig | None:
        for server in self.servers:
            if server.name == name:
                return server
        return None

    def server_names(self) -> list[str]:
        return [server.name for server in self.servers]

    def rcon_password(self, server: MCServerConfig, env: Mapping[str, str]) -> str:
        """取该服的 RCON 密码：先 `password_env`，再回退 `MC_RCON_PASSWORD`（A18）。"""

        primary = (env.get(server.password_env) or "").strip()
        if primary:
            return primary
        fallback = (env.get("MC_RCON_PASSWORD") or "").strip()
        if fallback:
            return fallback
        raise ConfigError(f"环境变量 {server.password_env} 未设置（回退变量 MC_RCON_PASSWORD 也未设置）")

    def rcon_passwords(self, env: Mapping[str, str]) -> dict[str, str]:
        """一次性取全部服的密码；缺任意一个即抛 `ConfigError`。"""

        return {server.name: self.rcon_password(server, env) for server in self.servers}

    def app_credentials(self, env: Mapping[str, str]) -> tuple[str, str]:
        """取 QQ 机器人 AppID/Secret；缺失即抛 `ConfigError`。"""

        app_id = (env.get(self.qq.app_id_env) or "").strip()
        secret = (env.get(self.qq.app_secret_env) or "").strip()
        if not app_id:
            raise ConfigError(f"环境变量 {self.qq.app_id_env} 未设置")
        if not secret:
            raise ConfigError(f"环境变量 {self.qq.app_secret_env} 未设置")
        return app_id, secret


# ---------------------------------------------------------------- 校验工具
def _table(raw: Mapping[str, Any], key: str, path: Path) -> Mapping[str, Any]:
    value = raw.get(key)
    if value is None:
        raise ConfigError(f"缺少配置段 [{key}]（{path}）")
    if not isinstance(value, dict):
        raise ConfigError(f"配置项 [{key}] 必须是表（table）（{path}）")
    return value


def _req_str(table: Mapping[str, Any], key: str, label: str) -> str:
    if key not in table:
        raise ConfigError(f"缺少必填配置项 {label}")
    value = table[key]
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"配置项 {label} 必须是非空字符串")
    return value


def _opt_str(table: Mapping[str, Any], key: str, label: str, default: str = "") -> str:
    value = table.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"配置项 {label} 必须是字符串")
    return value


def _req_int(
    table: Mapping[str, Any], key: str, label: str, *, minimum: int | None = None, maximum: int | None = None
) -> int:
    if key not in table:
        raise ConfigError(f"缺少必填配置项 {label}")
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"配置项 {label} 必须是整数")
    if minimum is not None and value < minimum:
        raise ConfigError(f"配置项 {label} 必须 >= {minimum}（实际 {value}）")
    if maximum is not None and value > maximum:
        raise ConfigError(f"配置项 {label} 必须 <= {maximum}（实际 {value}）")
    return value


def _float_value(table: Mapping[str, Any], key: str, label: str, default: float | None, *, positive: bool) -> float:
    if key not in table:
        if default is None:
            raise ConfigError(f"缺少必填配置项 {label}")
        return default
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"配置项 {label} 必须是数字")
    number = float(value)
    if positive and number <= 0:
        raise ConfigError(f"配置项 {label} 必须 > 0（实际 {number}）")
    return number


def _req_list_str(table: Mapping[str, Any], key: str, label: str) -> list[str]:
    if key not in table:
        raise ConfigError(f"缺少必填配置项 {label}")
    value = table[key]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigError(f"配置项 {label} 必须是字符串数组")
    return list(value)


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path


def _single_char(value: str, label: str) -> str:
    if len(value) != 1:
        raise ConfigError(f"配置项 {label} 必须是单字符（实际 {value!r}）")
    return value


# ---------------------------------------------------------------- 主入口
def load_config(path: str | Path, env: Mapping[str, str] | None = None) -> AppConfig:
    """读取并校验 `config.toml`；任何问题抛 `ConfigError`（`env` 仅用于后续取密钥）。"""

    del env  # 密钥在 AppConfig 的方法里按需读取，加载阶段不强制存在（S1 需要它可缺）
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"配置文件不存在: {config_path}")
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"配置文件不是合法 TOML: {config_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"配置文件读取失败: {config_path}: {exc}") from exc

    base = config_path.resolve().parent

    # ---- [qq]
    qq_table = _table(raw, "qq", config_path)
    qq = QQConfig(
        group_openid=_opt_str(qq_table, "group_openid", "qq.group_openid", ""),
        app_id_env=_req_str(qq_table, "app_id_env", "qq.app_id_env"),
        app_secret_env=_req_str(qq_table, "app_secret_env", "qq.app_secret_env"),
        command_prefix=_single_char(_req_str(qq_table, "command_prefix", "qq.command_prefix"), "qq.command_prefix"),
        chat_prefix=_single_char(_req_str(qq_table, "chat_prefix", "qq.chat_prefix"), "qq.chat_prefix"),
    )
    if qq.app_id_env and not _ENV_NAME_RE.match(qq.app_id_env):
        raise ConfigError(f"配置项 qq.app_id_env 不是合法环境变量名: {qq.app_id_env!r}")
    if qq.app_secret_env and not _ENV_NAME_RE.match(qq.app_secret_env):
        raise ConfigError(f"配置项 qq.app_secret_env 不是合法环境变量名: {qq.app_secret_env!r}")

    # ---- [behavior]
    behavior_table = _table(raw, "behavior", config_path)
    behavior = Behavior(
        log_poll_interval=_float_value(
            behavior_table, "log_poll_interval", "behavior.log_poll_interval", None, positive=True
        ),
        health_poll_interval=_float_value(
            behavior_table, "health_poll_interval", "behavior.health_poll_interval", None, positive=True
        ),
        max_line_length=_req_int(
            behavior_table, "max_line_length", "behavior.max_line_length", minimum=1, maximum=1446
        ),
        ignored_chat_prefixes=tuple(
            _req_list_str(behavior_table, "ignored_chat_prefixes", "behavior.ignored_chat_prefixes")
        ),
    )

    # ---- [paths]
    paths_table = _table(raw, "paths", config_path)
    bindings_path = _resolve(base, _req_str(paths_table, "bindings", "paths.bindings"))
    state_path = _resolve(base, _req_str(paths_table, "state", "paths.state"))

    # ---- [[mc_servers]]
    servers_raw = raw.get("mc_servers")
    if not isinstance(servers_raw, list) or not servers_raw:
        raise ConfigError("缺少配置段 [[mc_servers]]，至少需要一个 MC 服")
    servers: list[MCServerConfig] = []
    seen: set[str] = set()
    for index, item in enumerate(servers_raw, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"mc_servers 第 {index} 项必须是表（table）")
        name = _req_str(item, "name", f"mc_servers[{index}].name")
        if not _NAME_RE.match(name):
            raise ConfigError(f"配置项 mc_servers[{index}].name 不合法（^[A-Za-z0-9_-]{{1,32}}$）: {name!r}")
        if name in seen:
            raise ConfigError(f"mc_servers 名称重复: {name}")
        seen.add(name)
        password_env = _req_str(item, "password_env", f"mc_servers[{index}].password_env")
        if not _ENV_NAME_RE.match(password_env):
            raise ConfigError(f"配置项 mc_servers[{index}].password_env 不是合法环境变量名: {password_env!r}")
        servers.append(
            MCServerConfig(
                name=name,
                host=_req_str(item, "host", f"mc_servers[{index}].host"),
                port=_req_int(item, "port", f"mc_servers[{index}].port", minimum=1, maximum=65535),
                password_env=password_env,
                log_path=_resolve(base, _req_str(item, "log_path", f"mc_servers[{index}].log_path")),
                connect_timeout=_float_value(
                    item, "connect_timeout", f"mc_servers[{index}].connect_timeout", 5.0, positive=True
                ),
                command_timeout=_float_value(
                    item, "command_timeout", f"mc_servers[{index}].command_timeout", 5.0, positive=True
                ),
            )
        )

    # ---- [log_patterns]
    patterns_table = _table(raw, "log_patterns", config_path)
    patterns = LogPatterns(
        join=_req_str(patterns_table, "join", "log_patterns.join"),
        quit=_req_str(patterns_table, "quit", "log_patterns.quit"),
        chat=_req_str(patterns_table, "chat", "log_patterns.chat"),
        encoding=_opt_str(patterns_table, "encoding", "log_patterns.encoding", "utf-8") or "utf-8",
    )
    try:
        compile_patterns(patterns)
    except PatternError as exc:
        raise ConfigError(f"日志模板校验失败: {exc}") from exc

    return AppConfig(
        qq=qq,
        servers=servers,
        patterns=patterns,
        behavior=behavior,
        bindings_path=bindings_path,
        state_path=state_path,
    )
