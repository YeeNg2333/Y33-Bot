"""T1 骨架冒烟测试：入口可运行、自检契约成立、仓库无硬编码密钥。

这一层只锁 T1 的交付边界（PLAN.md §6 T1）；各业务模块的单元测试与覆盖率门槛由 T9/T10 补齐。
所有用例完全离线（最多在本机 loopback 上开一个监听端口），CI 与本地一致。
"""

from __future__ import annotations

import importlib
import re
import socket
import tomllib
from pathlib import Path

import pytest

import y33bot
from y33bot import cli

REPO_ROOT = Path(__file__).resolve().parents[1]

PLAN_MODULES = [
    "y33bot",
    "y33bot.cli",
    "y33bot.config",
    "y33bot.models",
    "y33bot.binding",
    "y33bot.state",
    "y33bot.bridge",
    "y33bot.service",
    "y33bot.rcon.protocol",
    "y33bot.rcon.client",
    "y33bot.rcon.pool",
    "y33bot.rcon.fakes",
    "y33bot.mclog.patterns",
    "y33bot.mclog.watcher",
    "y33bot.qq.gateway",
    "y33bot.qq.fakes",
    "y33bot.commands.registry",
    "y33bot.commands.builtin",
]


def _free_port() -> int:
    """取一个当前没人监听的端口（用于构造“RCON 连不上”的场景）。"""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _write_config(tmp_path: Path, *, port: int, log_path: Path) -> Path:
    """按 PLAN.md §3.5 的结构生成一份临时 config.toml。"""
    config = f"""[qq]
group_openid = "TEST-GROUP-OPENID"
app_id_env = "QQ_BOT_APP_ID"
app_secret_env = "QQ_BOT_APP_SECRET"
command_prefix = "/"
chat_prefix = "#"

[behavior]
log_poll_interval = 0.5
health_poll_interval = 30.0
max_line_length = 200
ignored_chat_prefixes = ["[QQ]", "[→QQ]"]

[paths]
bindings = "data/bindings.toml"
state = "data/state.json"

[[mc_servers]]
name = "main"
host = "127.0.0.1"
port = {port}
password_env = "MC_RCON_PASSWORD_MAIN"
log_path = "{log_path.as_posix()}"

[log_patterns]
join = 'joined the game'
quit = 'left the game'
chat = 'chat'
encoding = "utf-8"
"""
    path = tmp_path / "config.toml"
    path.write_text(config, encoding="utf-8")
    return path


@pytest.fixture()
def ready_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """注入“已配置好”的密钥环境（值都是假值，不涉密）。"""
    monkeypatch.setenv("QQ_BOT_APP_ID", "test-app-id")
    monkeypatch.setenv("QQ_BOT_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("MC_RCON_PASSWORD_MAIN", "test-rcon-password")


def test_version_prints_plan_contract(capsys: pytest.CaptureFixture[str]) -> None:
    """`python -m y33bot --version` 打印 ``y33bot 0.1.0`` 并以 0 退出（PLAN.md §3.4）。"""
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == "y33bot 0.1.0"


def test_version_matches_package_and_pyproject() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert y33bot.__version__ == project["version"] == "0.1.0"


def test_all_plan_modules_import_and_document_boundaries() -> None:
    """PLAN.md §3.1 的模块全部可导入，且都带模块级 docstring（说明边界）。"""
    for name in PLAN_MODULES:
        module = importlib.import_module(name)
        assert module.__doc__, f"{name} 缺少模块级 docstring"


def test_missing_subcommand_is_usage_error() -> None:
    """用法错误由 argparse 处理，退出码 2（PLAN.md §3.4）。"""
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2


def test_check_passes_when_port_reachable_and_env_ready(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ready_env: None
) -> None:
    """干净环境下 `check` 逐项打印健康状态，全通过时末行 OK 且退出码 0。"""
    log_path = tmp_path / "latest.log"
    log_path.write_text(
        "[12:00:00] [Server thread/INFO]: Steve joined the game\n", encoding="utf-8"
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        port = int(listener.getsockname()[1])
        config_path = _write_config(tmp_path, port=port, log_path=log_path)
        exit_code = cli.main(["check", "--config", str(config_path)])
    finally:
        listener.close()

    lines = capsys.readouterr().out.splitlines()
    assert exit_code == 0
    assert lines[0] == f"[配置] OK {config_path} 解析成功，1 个 MC 服"
    assert any(line.startswith(f"[RCON main] OK 端口可达 127.0.0.1:{port}") for line in lines)
    assert any(line.startswith("[日志 main] OK") for line in lines)
    assert any(line.endswith(f"偏移 {log_path.stat().st_size} 字节") for line in lines), (
        "日志偏移应等于文件当前字节数"
    )
    assert "[绑定] OK 0 条" in lines
    assert lines[-1] == "OK"


def test_check_fails_without_secrets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """缺 app_id 时 `[QQ] FAIL`，末行 FAIL 且退出码 1（PLAN.md §5 S1）。"""
    monkeypatch.delenv("QQ_BOT_APP_ID", raising=False)
    log_path = tmp_path / "latest.log"
    log_path.write_text("", encoding="utf-8")
    config_path = _write_config(tmp_path, port=_free_port(), log_path=log_path)

    assert cli.main(["check", "--config", str(config_path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "[QQ] FAIL 环境变量 QQ_BOT_APP_ID 未设置" in lines
    assert lines[-1] == "FAIL"


def test_check_reports_unreachable_rcon(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ready_env: None
) -> None:
    """RCON 端口不通时 `[RCON main] FAIL 无法连接 …`，其它项照常检查。"""
    log_path = tmp_path / "latest.log"
    log_path.write_text("", encoding="utf-8")
    port = _free_port()
    config_path = _write_config(tmp_path, port=port, log_path=log_path)

    assert cli.main(["check", "--config", str(config_path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert any(line.startswith(f"[RCON main] FAIL 无法连接 127.0.0.1:{port}") for line in lines)


def test_check_reports_missing_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """配置文件不存在：`[配置] FAIL` + 末行 FAIL（退出码 1）。"""
    missing = tmp_path / "missing.toml"
    assert cli.main(["check", "--config", str(missing)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("[配置] FAIL")
    assert lines[-1] == "FAIL"


def test_run_prints_health_then_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ready_env: None
) -> None:
    """骨架阶段 `run` 打印启动自检与健康状态后退出 0（单服故障不阻塞启动，§3.6）。"""
    log_path = tmp_path / "latest.log"
    log_path.write_text("", encoding="utf-8")
    config_path = _write_config(tmp_path, port=_free_port(), log_path=log_path)

    assert cli.main(["run", "--config", str(config_path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("[启动] y33bot 0.1.0")
    assert "[警告] 自检存在失败项" in out
    assert "[警告] 骨架阶段" in out


def test_unimplemented_subcommands_return_exit_3(capsys: pytest.CaptureFixture[str]) -> None:
    """骨架阶段未实现的子命令返回退出码 3，不假装成功。"""
    assert cli.main(["bind", "list"]) == 3
    exit_code = cli.main(
        ["simulate", "log-event", "--server", "main", "--kind", "join", "--player", "Steve"]
    )
    assert exit_code == 3
    out = capsys.readouterr().out
    assert out.count("[错误]") == 2


def test_pyproject_locks_runtime_dependencies() -> None:
    """运行时依赖锁版本、依赖数量保持最少（PLAN.md §2.1/§2.2）。"""
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["requires-python"] == ">=3.11,<3.14"
    assert project["dependencies"] == ["qq-botpy==1.2.1", "tomli-w==1.2.0"]


def test_example_config_covers_plan_keys_and_patterns() -> None:
    """config.example.toml 覆盖 PLAN.md §4.1 的必填键，且三条模板可编译、命名组齐全。"""
    data = tomllib.loads((REPO_ROOT / "config.example.toml").read_text(encoding="utf-8"))
    assert {"qq", "behavior", "paths", "mc_servers", "log_patterns"} <= set(data)
    server = data["mc_servers"][0]
    assert {"name", "host", "port", "password_env", "log_path"} <= set(server)
    for key in ("join", "quit", "chat"):
        re.compile(data["log_patterns"][key])
    assert "player" in data["log_patterns"]["chat"]
    assert "message" in data["log_patterns"]["chat"]


def test_env_example_has_no_values() -> None:
    """`.env.example` 只列变量名，不允许出现值（仓库不得存密钥，PLAN.md §6 T1）。"""
    for raw in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        assert value == "", f"{key} 在 .env.example 中不应带值"
