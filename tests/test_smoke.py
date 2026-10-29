"""冒烟测试：入口可运行、自检契约成立、仓库无硬编码密钥。

本文件由 T1（骨架任务 t_8442a7d5）建立，当时锁的是「骨架阶段」行为：未实现子命令返回退出码 3、
日志模板可任意简化。T2–T8 补齐实现后按 `PLAN.md` 的**最终契约**重写：

- 未实现子命令 → 现行契约是 `bind list` 正常工作、用法错误退出码 2（PLAN.md §3.4）；
- 日志模板 → 现行契约要求命名组（PLAN.md §4.1 / A9），简化模板会加载失败；
- `run` → 现行契约是常驻服务，缺 QQ 凭据启动即失败（退出码 1），不再是「打印健康状态后退出 0」。

原有意图（入口可运行 / 边界明确 / 仓库无密钥 / 依赖锁定）保持不变，且全部用例仍然完全离线。
"""

from __future__ import annotations

import asyncio
import importlib
import re
import socket
import struct
import tomllib
from pathlib import Path

import pytest

import y33bot
from conftest import check_item, check_items
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

#: Vanilla `/list` 应答（用于让 `check` 走通一次真实 RCON 往返）
LIST_RESPONSE = "There are 0 of a max of 20 players online:"


def _free_port() -> int:
    """取一个当前没人监听的端口（用于构造“RCON 连不上”的场景）。"""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _write_config(tmp_path: Path, *, port: int, log_path: Path) -> Path:
    """按 PLAN.md §3.5 的结构生成一份临时 config.toml（模板带命名组，符合 §4.1）。"""

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
ignored_chat_prefixes = ["[QQ]"]

[paths]
bindings = "data/bindings.toml"
state = "data/state.json"

[[mc_servers]]
name = "main"
host = "127.0.0.1"
port = {port}
password_env = "MC_RCON_PASSWORD_MAIN"
log_path = "{log_path.as_posix()}"
connect_timeout = 1.0
command_timeout = 1.0

[log_patterns]
join = '\\[\\d{{2}}:\\d{{2}}:\\d{{2}}\\] \\[Server thread/INFO\\]: (?P<player>\\w+) joined the game'
quit = '\\[\\d{{2}}:\\d{{2}}:\\d{{2}}\\] \\[Server thread/INFO\\]: (?P<player>\\w+) left the game'
chat = '\\[\\d{{2}}:\\d{{2}}:\\d{{2}}\\] \\[Async Chat Thread - #\\d+/INFO\\]: <(?P<player>\\w+)> (?P<message>.+)'
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


class MiniRconServer:
    """最小 RCON 服务端：鉴权 + 对任意命令回一句 `/list` 应答，只为让 `check` 真连一次。"""

    def __init__(self, password: str = "test-rcon-password", response: str = LIST_RESPONSE) -> None:
        self._password = password
        self._response = response
        self._server: asyncio.AbstractServer | None = None
        self.port = 0
        self.commands: list[str] = []

    async def __aenter__(self) -> MiniRconServer:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = int(self._server.sockets[0].getsockname()[1])
        return self

    async def __aexit__(self, *_exc) -> None:
        assert self._server is not None
        self._server.close()
        await self._server.wait_closed()

    @staticmethod
    def _write(writer: asyncio.StreamWriter, req_id: int, pkt_type: int, body: str) -> None:
        packet = struct.pack("<ii", req_id, pkt_type) + body.encode() + b"\x00\x00"
        writer.write(struct.pack("<i", len(packet)) + packet)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                header = await reader.readexactly(4)
                (size,) = struct.unpack("<i", header)
                data = await reader.readexactly(size)
                req_id, pkt_type = struct.unpack("<ii", data[:8])
                body = data[8:-2].decode(errors="replace")
                if pkt_type == 3:  # AUTH
                    if body == self._password:
                        self._write(writer, req_id, 2, "")
                    else:
                        self._write(writer, -1, 2, "")
                elif pkt_type == 2:  # EXECCOMMAND
                    self.commands.append(body)
                    self._write(writer, req_id, 0, self._response)
                else:  # pragma: no cover - 协议内没有别的类型
                    continue
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError, OSError):
            return
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except (OSError, ConnectionError):  # pragma: no cover - 关闭竞态
                pass


# ------------------------------------------------------------------ 入口
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


# ------------------------------------------------------------------ check
async def test_check_passes_with_reachable_rcon(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    ready_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RCON 可达 + 环境就绪时 `check` 逐项 OK、末行 `OK`、退出码 0（PLAN.md §5 S1）。"""

    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "latest.log"
    log_path.write_text("[12:00:00] [Server thread/INFO]: Steve joined the game\n", encoding="utf-8")

    async with MiniRconServer() as server:
        config_path = _write_config(tmp_path, port=server.port, log_path=log_path)
        # cli.main 内部会 asyncio.run()，因此放到线程里跑，避免与测试自己的事件循环冲突
        # --no-probe：本用例测的是 RCON 真连；QQ 项的真探活（默认行为）在 test_cli.py 里用替身覆盖
        exit_code = await asyncio.to_thread(cli.main, ["check", "--config", str(config_path), "--no-probe"])
        assert server.commands == ["/list"]

    lines = capsys.readouterr().out.splitlines()
    assert exit_code == 0
    items = check_items(lines, ["配置", "QQ", "RCON main", "日志 main", "日志模板 main", "绑定"])
    assert items["配置"] == "[配置] OK config.toml 解析成功，1 个 MC 服"
    assert items["QQ"] == "[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，未探活（--no-probe），group_openid 已配置"
    assert items["RCON main"] == f"[RCON main] OK /list -> {LIST_RESPONSE}"
    assert items["日志 main"].startswith("[日志 main] OK") and items["日志 main"].endswith("偏移 0 字节")
    # 日志里的 joined 那行能被现行模板解析 → 模板项按事件类型计数
    assert items["日志模板 main"] == "[日志模板 main] OK 样例行 1 条全部命中（join 1）"
    assert items["绑定"] == "[绑定] OK 0 条"
    assert lines[-1] == "OK"


def test_check_fails_without_secrets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """缺 app_id 时 `[QQ] FAIL`，末行 FAIL 且退出码 1（PLAN.md §5 S1）。"""

    monkeypatch.delenv("QQ_BOT_APP_ID", raising=False)
    monkeypatch.delenv("QQ_BOT_APP_SECRET", raising=False)
    log_path = tmp_path / "latest.log"
    log_path.write_text("", encoding="utf-8")
    config_path = _write_config(tmp_path, port=_free_port(), log_path=log_path)

    assert cli.main(["check", "--config", str(config_path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "[QQ] FAIL 环境变量 QQ_BOT_APP_ID 未设置" in lines
    assert lines[-1] == "FAIL"


def test_check_reports_unreachable_rcon(tmp_path: Path, capsys: pytest.CaptureFixture[str], ready_env: None) -> None:
    """RCON 端口不通时 `[RCON main] FAIL 无法连接 …`，其它项照常检查（§3.6：不阻塞启动）。"""

    log_path = tmp_path / "latest.log"
    log_path.write_text("", encoding="utf-8")
    port = _free_port()
    config_path = _write_config(tmp_path, port=port, log_path=log_path)

    assert cli.main(["check", "--config", str(config_path), "--no-probe"]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert check_item(lines, "RCON main").startswith(f"[RCON main] FAIL 无法连接 127.0.0.1:{port}")
    assert check_item(lines, "日志 main").startswith("[日志 main] OK")
    assert check_item(lines, "日志模板 main") == "[日志模板 main] OK 未找到可判定的样例行，跳过"


def test_check_reports_missing_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """配置文件不存在：`[配置] FAIL` + 末行 FAIL（退出码 1）。"""

    missing = tmp_path / "missing.toml"
    assert cli.main(["check", "--config", str(missing)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("[配置] FAIL")
    assert lines[-1] == "FAIL"


def _break_join_template(config_path: Path) -> None:
    """把 join 模板改成「真机行打不中」的形态（模拟 BUG-004：布局换了、模板没跟）。"""

    text = config_path.read_text(encoding="utf-8")
    broken = text.replace("joined the game", "has joined the game")
    assert broken != text, "假配置里没有可替换的 join 模板片段"
    config_path.write_text(broken, encoding="utf-8")


async def _check_output(config_path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, list[str]]:
    """真跑一次 `check`：`cli.main` 内部会 `asyncio.run()`，因此放到线程里跑。"""

    exit_code = await asyncio.to_thread(cli.main, ["check", "--config", str(config_path), "--no-probe"])
    return exit_code, capsys.readouterr().out.splitlines()


async def test_check_template_item_all_hit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ready_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """末尾候选样例行全部命中：按事件类型计数、紧跟同台服的日志项、退出码 0（BUG-004）。"""

    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "latest.log"
    log_path.write_text(
        "[12:00:04] [Server thread/INFO]: Steve joined the game\n"
        "[12:00:05] [Server thread/INFO]: Steve left the game\n"
        "[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #hi\n",
        encoding="utf-8",
    )

    async with MiniRconServer() as server:
        config_path = _write_config(tmp_path, port=server.port, log_path=log_path)
        exit_code, lines = await _check_output(config_path, capsys)

    template_line = "[日志模板 main] OK 样例行 3 条全部命中（join 1 / quit 1 / chat 1）"
    assert exit_code == 0
    assert template_line in lines
    # 逐服相邻：模板项紧跟在同台服的日志项之后
    assert lines[lines.index(template_line) - 1].startswith("[日志 main] OK")
    assert lines[-1] == "OK"


async def test_check_template_item_all_miss_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ready_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """含候选但全部未命中（模板写错）→ FAIL + 指向 README §13，并参与退出码（1）。"""

    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "latest.log"
    log_path.write_text("[12:00:04] [Server thread/INFO]: Steve joined the game\n" * 3, encoding="utf-8")

    async with MiniRconServer() as server:
        config_path = _write_config(tmp_path, port=server.port, log_path=log_path)
        _break_join_template(config_path)
        exit_code, lines = await _check_output(config_path, capsys)

    assert exit_code == 1
    assert "[日志模板 main] FAIL 3 条样例行全部未命中：请按 README §13 调整 [log_patterns]" in lines
    assert lines[-1] == "FAIL"


async def test_check_template_item_skips_without_candidates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ready_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """纯启动噪声（无候选行）→ OK 跳过，不算失败，退出码 0。"""

    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "latest.log"
    noise = "".join(
        f"[12:00:0{index % 10}] [Server thread/INFO]: Preparing spawn area: {index % 100}%\n" for index in range(100)
    )
    log_path.write_text(noise, encoding="utf-8")

    async with MiniRconServer() as server:
        config_path = _write_config(tmp_path, port=server.port, log_path=log_path)
        exit_code, lines = await _check_output(config_path, capsys)

    assert exit_code == 0
    assert "[日志模板 main] OK 未找到可判定的样例行，跳过" in lines
    assert lines[-1] == "OK"


async def test_check_template_item_skips_when_log_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ready_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`latest.log` 不存在：模板项照旧 OK 跳过（失败只由日志项记），check 不崩。"""

    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "latest.log"  # 故意不创建：check 应当照常逐项打印
    assert not log_path.exists()

    async with MiniRconServer() as server:
        config_path = _write_config(tmp_path, port=server.port, log_path=log_path)
        exit_code, lines = await _check_output(config_path, capsys)

    assert exit_code == 1  # 由「日志 main」项导致，不是模板项
    assert any(line.startswith("[日志 main] FAIL") for line in lines)
    assert "[日志模板 main] OK 未找到可判定的样例行，跳过" in lines
    assert not any(line.startswith("[日志模板 main] FAIL") for line in lines)


# ------------------------------------------------------------------ run / 子命令
def test_run_fails_fast_without_qq_credentials(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`run` 缺 QQ 凭据时启动即失败：先打印启动日志，再 `[错误]`，退出码 1（§3.6 / A11）。"""

    monkeypatch.delenv("QQ_BOT_APP_ID", raising=False)
    monkeypatch.delenv("QQ_BOT_APP_SECRET", raising=False)
    monkeypatch.setenv("MC_RCON_PASSWORD_MAIN", "test-rcon-password")
    log_path = tmp_path / "latest.log"
    log_path.write_text("", encoding="utf-8")
    config_path = _write_config(tmp_path, port=_free_port(), log_path=log_path)

    assert cli.main(["run", "--config", str(config_path)]) == 1
    out = capsys.readouterr().err  # run 的日志走 stderr（§3.6）
    assert "[启动] y33bot 0.1.0" in out
    assert "[启动] 日志监听已启动: main" in out
    assert "[错误] 环境变量 QQ_BOT_APP_ID 未设置" in out


def test_subcommands_are_implemented(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ready_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """骨架期的「未实现 → 退出码 3」已被最终实现取代：bind / simulate 都真的工作（§3.4）。"""

    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "latest.log"
    log_path.write_text("", encoding="utf-8")
    config_path = _write_config(tmp_path, port=_free_port(), log_path=log_path)

    assert cli.main(["bind", "list", "--config", str(config_path)]) == 0
    assert capsys.readouterr().out.strip() == "[绑定] 无绑定记录"

    assert cli.main(["bind", "set", "OP-1", "Steve", "--config", str(config_path)]) == 0
    assert "已写入 OP-1 -> Steve" in capsys.readouterr().out

    assert (
        cli.main(
            [
                "simulate",
                "log-event",
                "--server",
                "main",
                "--kind",
                "join",
                "--player",
                "Steve",
                "--dry-run",
                "--config",
                str(config_path),
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == "[群消息] Steve进入了main"

    # 用法错误（既没有 --line 也没有 --kind）由 argparse 处理 → 退出码 2
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["simulate", "log-event", "--server", "main", "--config", str(config_path)])
    assert excinfo.value.code == 2


# ------------------------------------------------------------------ 仓库约定
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
