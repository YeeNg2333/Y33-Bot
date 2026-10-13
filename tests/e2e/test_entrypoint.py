"""真·入口端到端（PLAN.md §3.4 / §5 S1-S4 / §6 T10）。

与 `test_acceptance.py` 的分工：

- `test_acceptance.py` 在**同一进程**里调 `main(argv)`，快，用于逐条断言文案；
- 本文件**真的起子进程**跑 `python -m y33bot …`：argparse → 配置解析 → 桥 → RCON 替身 →
  stdout 契约 → 退出码，全部按验收场景逐条断言。它同时覆盖 `__main__.py` 这条真实入口，
  并保证「在干净的部署目录里、只靠仓库内容 + 三个环境变量」就能跑起来（无网络、无 QQ、无 MC）。

真实端到端（S5：真 QQ 群 + 真 MC 服）需要真实凭据与游戏服，见 `docs/smoke.md` 与 `docs/acceptance.md`。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import config_text

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
CONFIG = "config.toml"
TIMEOUT = 90

#: 只注入假凭据；不读宿主机上可能存在的真实 QQ/RCON 变量（离线保证）
BASE_ENV = {
    "QQ_BOT_APP_ID": "102000000",
    "QQ_BOT_APP_SECRET": "e2e-fake-secret",
    "MC_RCON_PASSWORD_MAIN": "e2e-fake-password",
}
UNREACHABLE_PORT = 34567


@pytest.fixture
def deploy_dir(tmp_path: Path) -> Path:
    """一个干净的部署目录：config.toml + logs/latest.log（data/ 由程序自己建）。"""

    logs = tmp_path / "logs"
    logs.mkdir()
    log_path = logs / "latest.log"
    log_path.write_bytes(b"")
    text = config_text(log_path=log_path).replace("port = 25575", f"port = {UNREACHABLE_PORT}")
    (tmp_path / CONFIG).write_text(text, encoding="utf-8")
    return tmp_path


def run_cli(cwd: Path, *argv: str, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """在 `cwd` 里真跑一次 CLI；返回带解码后 stdout/stderr 的 CompletedProcess。"""

    env = dict(os.environ)
    env.pop("QQ_BOT_APP_ID", None)
    env.pop("QQ_BOT_APP_SECRET", None)
    env.pop("MC_RCON_PASSWORD", None)
    env.update(BASE_ENV)
    env.update({"PYTHONPATH": str(SRC_DIR), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    if env_overrides is not None:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "y33bot", *argv],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT,
    )


def lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    return result.stdout.strip().splitlines()


# ------------------------------------------------------------------ 版本与用法
def test_main_module_exposes_cli_entry() -> None:
    """`python -m y33bot` 的模块本体：`y33bot.__main__.main` 就是 `cli.main`（同一个入口）。"""

    import importlib

    from y33bot.cli import main as cli_main

    module = importlib.import_module("y33bot.__main__")
    assert module.main is cli_main


def test_entrypoint_version(deploy_dir: Path) -> None:
    """`python -m y33bot --version` → 版本号 + 退出码 0（PLAN.md §3.4）。"""

    from y33bot import __version__

    result = run_cli(deploy_dir, "--version")
    assert result.returncode == 0
    assert lines(result) == [f"y33bot {__version__}"]


def test_entrypoint_usage_error_is_exit_code_2(deploy_dir: Path) -> None:
    result = run_cli(deploy_dir, "simulate", "log-event", "--server", "main")
    assert result.returncode == 2
    assert "log-event 需要 --line" in result.stderr

    result = run_cli(deploy_dir)  # 缺子命令
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


# ------------------------------------------------------------------ S1
def test_entrypoint_s1_check_reports_each_item(deploy_dir: Path) -> None:
    """S1：逐项自检 + 末行 FAIL + 退出码 1（RCON 端口故意不可达）。"""

    result = run_cli(deploy_dir, "check", "--config", CONFIG)
    assert result.returncode == 1
    out = lines(result)
    assert out[0] == "[配置] OK config.toml 解析成功，1 个 MC 服"
    assert out[1] == "[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置"
    assert out[2].startswith(f"[RCON main] FAIL 无法连接 127.0.0.1:{UNREACHABLE_PORT}:")
    assert out[3].endswith("可读，偏移 0 字节") and "[日志 main] OK" in out[3]
    assert out[4] == "[绑定] OK 0 条"
    assert out[5] == "FAIL"
    assert len(out) == 6
    # 明细日志走 stderr（§3.6），stdout 只有契约行
    assert "[警告] RCON main 命令失败" in result.stderr


def test_entrypoint_s1_check_missing_secret(deploy_dir: Path) -> None:
    """缺 QQ secret → `[QQ] FAIL …未设置`，仍然逐项打印完再收尾。"""

    result = run_cli(deploy_dir, "check", "--config", CONFIG, env_overrides={"QQ_BOT_APP_SECRET": ""})
    assert result.returncode == 1
    assert lines(result)[1] == "[QQ] FAIL 环境变量 QQ_BOT_APP_SECRET 未设置"
    assert lines(result)[-1] == "FAIL"


def test_entrypoint_check_missing_config(deploy_dir: Path) -> None:
    result = run_cli(deploy_dir, "check", "--config", "nope.toml")
    assert result.returncode == 1
    assert lines(result) == ["[配置] FAIL 配置文件不存在: nope.toml", "FAIL"]


# ------------------------------------------------------------------ S2
def test_entrypoint_s2_bind_then_forward(deploy_dir: Path) -> None:
    """S2：/bind 落盘（跨进程可见）+ `#` 消息只转发第一行到 MC。"""

    result = run_cli(deploy_dir, "bind", "set", "1A2B3C4D", "Steve", "--config", CONFIG)
    assert result.returncode == 0
    assert lines(result) == ["[绑定] 已写入 1A2B3C4D -> Steve (data/bindings.toml)"]
    assert "Steve" in (deploy_dir / "data" / "bindings.toml").read_text(encoding="utf-8")

    result = run_cli(deploy_dir, "bind", "list", "--config", CONFIG)
    assert result.returncode == 0
    assert lines(result) == ["[绑定] 1A2B3C4D -> Steve"]

    result = run_cli(
        deploy_dir,
        "simulate",
        "group-message",
        "--openid",
        "1A2B3C4D",
        "--content",
        "#你好\n世界",  # 第二行按 A7 被截断
        "--dry-run",
        "--config",
        CONFIG,
    )
    assert result.returncode == 0
    assert lines(result) == ['[RCON main] tellraw @a {"text":"[QQ] Steve: 你好"}']


def test_entrypoint_s2_hints_and_unknown_command(deploy_dir: Path) -> None:
    """S2：未绑定 → 绑定提示（不碰 RCON）；缺参数/未知指令 → 固定文案。"""

    def simulate(content: str) -> list[str]:
        result = run_cli(
            deploy_dir,
            "simulate",
            "group-message",
            "--openid",
            "UNKNOWN",
            "--content",
            content,
            "--dry-run",
            "--config",
            CONFIG,
        )
        assert result.returncode == 0
        return lines(result)

    assert simulate("#hi") == ["[群消息] 请先使用 /bind <游戏ID> 绑定"]
    assert simulate("普通消息") == ["[忽略] 非触发前缀"]
    assert simulate("/bind") == ["[群消息] 用法: /bind <游戏ID>"]
    assert simulate("/unknowncmd") == ["[群消息] 未知指令"]


# ------------------------------------------------------------------ S3 + S4
def test_entrypoint_s3_s4_events_and_health_flip(deploy_dir: Path) -> None:
    """S3/S4：聊天双向转发、回环防护、进出通知、健康翻转只提示一次（状态跨进程持久化）。"""

    result = run_cli(
        deploy_dir,
        "simulate",
        "log-event",
        "--server",
        "main",
        "--line",
        "[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好",
        "--dry-run",
        "--config",
        CONFIG,
    )
    assert result.returncode == 0
    assert lines(result) == ["[群消息] Steve: 大家好", '[RCON main] tellraw @a {"text":"[→QQ] Steve: 大家好"}']

    result = run_cli(
        deploy_dir,
        "simulate",
        "log-event",
        "--server",
        "main",
        "--line",
        "[12:00:04] [Server thread/INFO]: Steve joined the game",
        "--dry-run",
        "--config",
        CONFIG,
    )
    assert result.returncode == 0
    assert lines(result) == ["[群消息] Steve进入游戏"]

    health = ("simulate", "health", "--server", "main", "--offline", "--dry-run", "--config", CONFIG)
    first = run_cli(deploy_dir, *health)
    assert first.returncode == 0
    assert "[群消息] [服务器状态] main 离线" in lines(first)

    second = run_cli(deploy_dir, *health)
    assert second.returncode == 0
    assert lines(second)[-1] == "[忽略] 状态未变化，不重复提示"
    assert "health_online" in (deploy_dir / "data" / "state.json").read_text(encoding="utf-8")


def test_entrypoint_run_fails_fast_without_credentials(deploy_dir: Path) -> None:
    """S5 的离线可复现部分：缺 QQ 凭据时 `run` 立刻以退出码 1 结束，且不影响 RCON 告警文案。"""

    result = run_cli(
        deploy_dir,
        "run",
        "--config",
        CONFIG,
        env_overrides={"QQ_BOT_APP_ID": "", "QQ_BOT_APP_SECRET": ""},
    )
    assert result.returncode == 1
    assert "[启动] y33bot" in result.stderr
    assert "日志监听已启动: main" in result.stderr
    assert "环境变量 QQ_BOT_APP_ID 未设置" in result.stderr
