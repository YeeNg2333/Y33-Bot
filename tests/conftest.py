"""共享夹具：临时 config / 日志 / 状态 / 绑定，以及离线替身装配。"""

from __future__ import annotations

from pathlib import Path

import pytest

from y33bot.binding import BindingStore
from y33bot.bridge import Bridge
from y33bot.commands.builtin import build_registry
from y33bot.config import AppConfig, load_config
from y33bot.mclog.watcher import LogWatcher
from y33bot.qq.fakes import FakeQQGateway
from y33bot.rcon.fakes import FakeRconTransport
from y33bot.rcon.pool import RconPool
from y33bot.state import StateStore

JOIN_TEMPLATE = (
    r"\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\]"
    r"(?: \[[^\]]+\])?: (?P<player>\w+) joined the game"
)
QUIT_TEMPLATE = (
    r"\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\]"
    r"(?: \[[^\]]+\])?: (?P<player>\w+) left the game"
)
CHAT_TEMPLATE = (
    r"\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\]"
    r"(?: \[[^\]]+\])?: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)"
)

DEFAULT_ENV = {
    "QQ_BOT_APP_ID": "102000000",
    "QQ_BOT_APP_SECRET": "test-secret",
    "MC_RCON_PASSWORD_MAIN": "main-secret",
    "MC_RCON_PASSWORD_WORLD2": "world2-secret",
}


def config_text(
    *,
    log_path: Path,
    second_log_path: Path | None = None,
    group_openid: str = "GROUP-OPENID-1",
    max_line_length: int = 200,
    ignored_chat_prefixes: tuple[str, ...] = ("[QQ]",),
    log_poll_interval: float = 0.05,
    health_poll_interval: float = 5.0,
    join: str = JOIN_TEMPLATE,
    quit_: str = QUIT_TEMPLATE,
    chat: str = CHAT_TEMPLATE,
) -> str:
    ignored = ", ".join(f'"{item}"' for item in ignored_chat_prefixes)
    text = f"""
[qq]
group_openid = "{group_openid}"
app_id_env = "QQ_BOT_APP_ID"
app_secret_env = "QQ_BOT_APP_SECRET"
command_prefix = "/"
chat_prefix = "#"

[behavior]
log_poll_interval = {log_poll_interval}
health_poll_interval = {health_poll_interval}
max_line_length = {max_line_length}
ignored_chat_prefixes = [{ignored}]

[paths]
bindings = "data/bindings.toml"
state = "data/state.json"

[[mc_servers]]
name = "main"
host = "127.0.0.1"
port = 25575
password_env = "MC_RCON_PASSWORD_MAIN"
log_path = "{log_path.as_posix()}"
connect_timeout = 1.0
command_timeout = 1.0
"""
    if second_log_path is not None:
        text += f"""
[[mc_servers]]
name = "world2"
host = "127.0.0.1"
port = 25576
password_env = "MC_RCON_PASSWORD_WORLD2"
log_path = "{second_log_path.as_posix()}"
connect_timeout = 1.0
command_timeout = 1.0
"""
    text += f"""
[log_patterns]
join = '{join}'
quit = '{quit_}'
chat = '{chat}'
encoding = "utf-8"
"""
    return text


class App:
    """一个临时的 y33bot 运行目录：config.toml + 日志 + data/。"""

    def __init__(self, root: Path, *, second_server: bool = False, **options) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.env = dict(DEFAULT_ENV)
        self.log_path = root / "logs" / "main.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_bytes(b"")
        self.second_log_path = None
        if second_server:
            self.second_log_path = root / "logs" / "world2.log"
            self.second_log_path.write_bytes(b"")
        self.config_path = root / "config.toml"
        self.config_path.write_text(
            config_text(
                log_path=self.log_path,
                second_log_path=self.second_log_path,
                **options,
            ),
            encoding="utf-8",
        )
        self.config: AppConfig = load_config(self.config_path, self.env)

    # ------------------------------------------------------------ 文件操作
    def write_log(self, text: str, *, server: str = "main") -> None:
        path = self.log_path if server == "main" else self.second_log_path
        assert path is not None
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def truncate_log(self, *, server: str = "main") -> None:
        path = self.log_path if server == "main" else self.second_log_path
        assert path is not None
        path.write_bytes(b"")

    def state(self) -> StateStore:
        return StateStore.load(self.config.state_path)

    def bindings(self) -> BindingStore:
        return BindingStore.load(self.config.bindings_path)

    # ------------------------------------------------------------ 组件装配
    def make_pool(self, online: dict[str, bool] | None = None, *, responses: dict[str, dict] | None = None):
        endpoints = {(server.host, server.port): server.name for server in self.config.servers}
        flags = dict(online or {})
        canned = dict(responses or {})

        def factory(host: str, port: int, password: str, *, connect_timeout: float = 5.0, command_timeout: float = 5.0):
            name = endpoints.get((host, port), host)
            return FakeRconTransport(
                host=host,
                port=port,
                password=password,
                connect_timeout=connect_timeout,
                command_timeout=command_timeout,
                online=flags.get(name, True),
                responses=canned.get(name, {}),
            )

        return RconPool(self.config.servers, self.config.rcon_passwords(self.env), factory=factory)

    def make_gateway(self) -> FakeQQGateway:
        return FakeQQGateway()

    def make_bridge(self, pool=None, gateway=None, registry=None) -> Bridge:
        return Bridge(
            self.config,
            self.bindings(),
            self.state(),
            pool if pool is not None else self.make_pool(),
            registry if registry is not None else build_registry(),
            gateway if gateway is not None else self.make_gateway(),
        )

    def make_watcher(self, server: str = "main") -> LogWatcher:
        target = self.config.server(server)
        assert target is not None
        return LogWatcher(target, self.config.patterns, self.state())


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(tmp_path)


@pytest.fixture
def two_server_app(tmp_path: Path) -> App:
    return App(tmp_path, second_server=True)


# ------------------------------------------------------------------ check 输出断言
def check_items(lines: list[str], labels: list[str]) -> dict[str, str]:
    """按 `[<label>] ` 前缀取 `check` 的输出行，并断言「各出现一次 + 顺序与给定一致」。

    `check` 的行序是契约（PLAN.md §3.4），但行号会随自检项增减而位移，
    所以断言一律按前缀取行，不硬编码索引（`[日志 main]` 与 `[日志模板 main]`
    靠标签末尾的空格区分，互不误配）。
    """

    found: dict[str, str] = {}
    cursor = 0
    for label in labels:
        prefix = f"[{label}] "
        positions = [index for index, line in enumerate(lines) if line.startswith(prefix)]
        assert len(positions) == 1, f"期望恰好一行以 {prefix!r} 开头，实际 {positions!r}；完整输出：{lines!r}"
        assert positions[0] >= cursor, f"顺序错：{prefix!r} 落在第 {positions[0]} 行；完整输出：{lines!r}"
        cursor = positions[0] + 1
        found[label] = lines[positions[0]]
    return found


def check_item(lines: list[str], label: str) -> str:
    """单个自检项的输出行（`check_items` 的单标签简写）。"""

    return check_items(lines, [label])[label]
