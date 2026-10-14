"""端到端验收：PLAN.md §5 的 S1-S4、S6 离线可复现版本（假 RCON + FakeQQGateway + 临时日志）。

真实端到端（S5：真 QQ 群 + 真 MC 服）无法在 CI 里跑，见 docs/smoke.md 的手工步骤。
本文件按 PLAN.md §5 的文案逐条断言。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import DEFAULT_ENV, App
from y33bot.cli import main
from y33bot.mclog.watcher import LogWatcher
from y33bot.state import StateStore

CONFIG = "config.toml"


@pytest.fixture
def acceptance_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> App:
    for key, value in DEFAULT_ENV.items():
        monkeypatch.setenv(key, value)
    app = App(tmp_path)
    monkeypatch.chdir(tmp_path)
    return app


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, list[str]]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out.strip().splitlines()


# ------------------------------------------------------------------ S1
def test_s1_check_reports_each_item(acceptance_dir: App, capsys) -> None:
    """S1：环境与配置自检 —— 逐项结果 + 末行 FAIL/OK 与退出码。"""

    text = acceptance_dir.config_path.read_text(encoding="utf-8")
    acceptance_dir.config_path.write_text(text.replace("port = 25575", "port = 34567"), encoding="utf-8")

    code, lines = run(["check", "--config", CONFIG, "--no-probe"], capsys)
    assert code == 1
    assert lines[0] == "[配置] OK config.toml 解析成功，1 个 MC 服"
    assert lines[1] == "[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，未探活（--no-probe），group_openid 已配置"
    assert lines[2].startswith("[RCON main] FAIL 无法连接 127.0.0.1:34567:")
    assert lines[3] == f"[日志 main] OK {acceptance_dir.log_path} 可读，偏移 0 字节"
    assert lines[4] == "[绑定] OK 0 条"
    assert lines[5] == "FAIL"


# ------------------------------------------------------------------ S2
def test_s2_bind_then_forward(acceptance_dir: App, capsys) -> None:
    """S2：/bind 写入 + `#` 消息换行截断后转发到全部 MC 服。"""

    code, lines = run(["bind", "set", "1A2B3C4D", "Steve", "--config", CONFIG], capsys)
    assert code == 0
    assert lines == ["[绑定] 已写入 1A2B3C4D -> Steve (data/bindings.toml)"]

    code, lines = run(
        [
            "simulate",
            "group-message",
            "--openid",
            "1A2B3C4D",
            "--content",
            "#你好\n世界",
            "--dry-run",
            "--config",
            CONFIG,
        ],
        capsys,
    )
    assert code == 0
    assert lines == ['[RCON main] tellraw @a {"text":"[QQ] Steve: 你好"}']


def test_s2_unbound_and_non_trigger(acceptance_dir: App, capsys) -> None:
    """S2：未绑定只回提示（无 RCON 行）；非触发前缀只记忽略。"""

    code, lines = run(
        ["simulate", "group-message", "--openid", "UNKNOWN", "--content", "#hi", "--dry-run", "--config", CONFIG],
        capsys,
    )
    assert code == 0
    assert lines == ["[群消息] 请先使用 /bind <游戏ID> 绑定"]

    code, lines = run(
        ["simulate", "group-message", "--openid", "UNKNOWN", "--content", "普通消息", "--dry-run", "--config", CONFIG],
        capsys,
    )
    assert code == 0
    assert lines == ["[忽略] 非触发前缀"]

    code, lines = run(
        ["simulate", "group-message", "--openid", "UNKNOWN", "--content", "/bind", "--dry-run", "--config", CONFIG],
        capsys,
    )
    assert code == 0
    assert lines == ["[群消息] 用法: /bind <游戏ID>"]


def test_s2_two_servers_broadcast(acceptance_dir_two: App, capsys) -> None:
    """R29：QQ→MC 全局广播到所有 RCON 连接的服。"""

    code, lines = run(["bind", "set", "OP-1", "Steve", "--config", CONFIG], capsys)
    assert code == 0
    code, lines = run(
        ["simulate", "group-message", "--openid", "OP-1", "--content", "#hi", "--dry-run", "--config", CONFIG],
        capsys,
    )
    assert code == 0
    assert lines == [
        '[RCON main] tellraw @a {"text":"[QQ] Steve: hi"}',
        '[RCON world2] tellraw @a {"text":"[QQ] Steve: hi"}',
    ]


# ------------------------------------------------------------------ S3
def test_s3_chat_forward_and_loop_guard(acceptance_dir: App, capsys) -> None:
    """S3：`#` 聊天双向转发；非 `#` 不转发；回环前缀被拦。"""

    code, lines = run(
        [
            "simulate",
            "log-event",
            "--server",
            "main",
            "--line",
            "[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好",
            "--dry-run",
            "--config",
            CONFIG,
        ],
        capsys,
    )
    assert code == 0
    assert lines == ["[群消息] Steve@main: 大家好"]

    code, lines = run(
        [
            "simulate",
            "log-event",
            "--server",
            "main",
            "--line",
            "[12:00:02] [Async Chat Thread - #0/INFO]: <Steve> 普通聊天",
            "--dry-run",
            "--config",
            CONFIG,
        ],
        capsys,
    )
    assert lines == ["[忽略] 聊天非 # 开头，不转发"]

    code, lines = run(
        [
            "simulate",
            "log-event",
            "--server",
            "main",
            "--line",
            "[12:00:03] [Async Chat Thread - #0/INFO]: <Steve> [QQ] Steve: 大家好",
            "--dry-run",
            "--config",
            CONFIG,
        ],
        capsys,
    )
    assert lines == ["[忽略] 回环防护：命中 ignored_chat_prefixes"]


# ------------------------------------------------------------------ S4
def test_s4_join_quit_and_health_once(acceptance_dir: App, capsys) -> None:
    """S4：进出通知文案 + 健康翻转只提示一次。"""

    code, lines = run(
        [
            "simulate",
            "log-event",
            "--server",
            "main",
            "--line",
            "[12:00:04] [Server thread/INFO]: Steve joined the game",
            "--dry-run",
            "--config",
            CONFIG,
        ],
        capsys,
    )
    assert lines == ["[群消息] Steve进入了main"]

    code, lines = run(
        [
            "simulate",
            "log-event",
            "--server",
            "main",
            "--line",
            "[12:00:05] [Server thread/INFO]: Steve left the game",
            "--dry-run",
            "--config",
            CONFIG,
        ],
        capsys,
    )
    assert lines == ["[群消息] Steve退出了main"]

    args = ["simulate", "health", "--server", "main", "--offline", "--dry-run", "--config", CONFIG]
    code, lines = run(args, capsys)
    assert "[群消息] [服务器状态] main 离线" in lines

    code, lines = run(args, capsys)
    assert lines[-1] == "[忽略] 状态未变化，不重复提示"


# ------------------------------------------------------------------ S6
def test_s6_log_rotation(acceptance_dir: App, caplog: pytest.LogCaptureFixture) -> None:
    """S6：日志缩小（轮转）后偏移重置为 0，并解析新写入的日志行。"""

    join_line = "[12:00:04] [Server thread/INFO]: Steve joined the game\n"
    other_line = "[12:00:05] [Server thread/INFO]: Alex joined the game\n"
    acceptance_dir.write_log(join_line + other_line)

    server = acceptance_dir.config.server("main")
    assert server is not None
    store = StateStore.load(acceptance_dir.config.state_path)
    watcher = LogWatcher(server, acceptance_dir.config.patterns, store)
    assert len(watcher.poll_new_events()) == 2
    store.save()

    # 手动清空（模拟 latest.log 被重命名/清空）后写入一行
    acceptance_dir.truncate_log()
    acceptance_dir.write_log(join_line)

    with caplog.at_level("WARNING"):
        events = watcher.poll_new_events()
    assert [event.kind for event in events] == ["join"]
    assert any("日志文件缩小" in record.getMessage() for record in caplog.records)
    assert store.server_state("main").log_offset == len(join_line)


@pytest.fixture
def acceptance_dir_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> App:
    for key, value in DEFAULT_ENV.items():
        monkeypatch.setenv(key, value)
    app = App(tmp_path, second_server=True)
    monkeypatch.chdir(tmp_path)
    return app
