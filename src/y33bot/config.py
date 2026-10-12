"""配置加载与校验（PLAN.md §3.3、§4.1；密钥约定见 A18）。

冻结接口::

    load_config(path, env=None) -> AppConfig
    ConfigError

约定：

- 配置只读一次（不热重载，N4）；失败即 ``ConfigError``，进程退出码 1。
- 密钥**永不写入配置文件**：只写环境变量名（``QQ_BOT_APP_ID`` / ``QQ_BOT_APP_SECRET`` /
  ``MC_RCON_PASSWORD_<SERVER 大写>``，缺失回退 ``MC_RCON_PASSWORD``），值在
  ``AppConfig.app_credentials()`` / ``AppConfig.rcon_password()`` 里从 env 取。
- ``qq.group_openid`` 留空 → MC→QQ 方向禁用并告警，服务仍正常启动（A11）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    """配置缺失、格式错误或校验不通过（启动即失败，退出码 1）。"""


@dataclass(frozen=True)
class MCServerConfig:
    """单台 MC 服的 RCON 连接与日志位置（PLAN.md §4.1）。"""

    name: str
    host: str
    port: int
    password_env: str
    log_path: Path
    connect_timeout: float = 5.0
    command_timeout: float = 5.0


@dataclass(frozen=True)
class QQConfig:
    """QQ 侧配置（PLAN.md §4.1；A11、A18）。"""

    group_openid: str = ""
    app_id_env: str = "QQ_BOT_APP_ID"
    app_secret_env: str = "QQ_BOT_APP_SECRET"
    command_prefix: str = "/"
    chat_prefix: str = "#"


@dataclass(frozen=True)
class LogPatterns:
    """日志模板：格式变化只改 TOML，不改代码（R27）。"""

    join: str
    quit: str
    chat: str
    encoding: str = "utf-8"


@dataclass(frozen=True)
class Behavior:
    """轮询间隔与文案行为参数（PLAN.md §4.1；A7、A8）。"""

    log_poll_interval: float = 0.5
    health_poll_interval: float = 30.0
    max_line_length: int = 200
    ignored_chat_prefixes: tuple[str, ...] = ("[QQ]", "[→QQ]")


@dataclass(frozen=True)
class AppConfig:
    """进程级配置视图；密钥只在调用下面两个方法时从 ``env`` 读取。"""

    qq: QQConfig
    servers: list[MCServerConfig]
    patterns: LogPatterns
    behavior: Behavior
    bindings_path: Path
    state_path: Path

    def rcon_password(self, server: MCServerConfig, env: Mapping[str, str]) -> str:
        """取该服 RCON 密码：``server.password_env`` → 回退 ``MC_RCON_PASSWORD``。"""
        raise NotImplementedError("T2：见 PLAN.md §4.1 / A18")

    def app_credentials(self, env: Mapping[str, str]) -> tuple[str, str]:
        """取 ``(app_id, app_secret)``；任一缺失抛 ``ConfigError``。"""
        raise NotImplementedError("T2：见 PLAN.md §4.1 / A18")


def load_config(path: Path, env: Mapping[str, str] | None = None) -> AppConfig:
    """读取并校验 ``config.toml``；失败抛 ``ConfigError``（PLAN.md §4.1 校验规则）。"""
    raise NotImplementedError("T2：见 PLAN.md §4.1")
