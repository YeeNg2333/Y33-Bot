"""CLI 契约测试（PLAN.md §3.4 / S1-S4 / T8）。

stdout 文案是验收断言对象，因此这里断言完整输出行，而不是「包含」。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import DEFAULT_ENV, App
from y33bot import __version__
from y33bot.cli import main

CONFIG = "config.toml"


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> App:
    """把 CLI 的 CWD 切到临时 App 目录，并注入环境变量（CLI 只读 os.environ）。"""

    for key, value in DEFAULT_ENV.items():
        monkeypatch.setenv(key, value)
    app = App(tmp_path)
    monkeypatch.chdir(tmp_path)
    return app


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, list[str], str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out.strip().splitlines(), captured.err


# ------------------------------------------------------------------ 基础
def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == f"y33bot {__version__}"


def test_missing_config(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    code = main(["check", "--config", "nope.toml"])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out.strip().splitlines() == ["[配置] FAIL 配置文件不存在: nope.toml", "FAIL"]


def test_run_missing_config(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["run", "--config", "nope.toml"]) == 1
    assert "配置文件不存在" in capsys.readouterr().err


def test_usage_error_exit_code_2(workdir: App) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["simulate", "log-event", "--server", "main"])  # 缺 --line / --kind
    assert excinfo.value.code == 2


# ------------------------------------------------------------------ check（S1）
def test_check_reports_failure_for_unreachable_rcon(workdir: App, capsys) -> None:
    text = workdir.config_path.read_text(encoding="utf-8")
    workdir.config_path.write_text(text.replace("port = 25575", "port = 34567"), encoding="utf-8")
    code, lines, _err = run(["check", "--config", CONFIG], capsys)

    assert code == 1
    assert lines[0] == "[配置] OK config.toml 解析成功，1 个 MC 服"
    assert lines[1] == "[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置"
    assert lines[2].startswith("[RCON main] FAIL 无法连接 127.0.0.1:34567:")
    assert lines[3] == f"[日志 main] OK {workdir.log_path} 可读，偏移 0 字节"
    assert lines[4] == "[绑定] OK 0 条"
    assert lines[5] == "FAIL"


def test_check_reports_missing_secret(workdir: App, capsys, monkeypatch) -> None:
    monkeypatch.delenv("QQ_BOT_APP_SECRET")
    code, lines, _err = run(["check", "--config", CONFIG], capsys)
    assert code == 1
    assert lines[1] == "[QQ] FAIL 环境变量 QQ_BOT_APP_SECRET 未设置"


def test_check_reports_missing_rcon_password(workdir: App, capsys, monkeypatch) -> None:
    monkeypatch.delenv("MC_RCON_PASSWORD_MAIN")
    code, lines, _err = run(["check", "--config", CONFIG], capsys)
    assert code == 1
    assert lines[2].startswith("[RCON main] FAIL 无法连接 127.0.0.1:25575:")
    assert "MC_RCON_PASSWORD_MAIN" in lines[2]


def test_check_missing_log_file(workdir: App, capsys) -> None:
    workdir.log_path.unlink()
    code, lines, _err = run(["check", "--config", CONFIG], capsys)
    assert code == 1
    assert lines[3].startswith("[日志 main] FAIL")
    assert "不存在" in lines[3]


# ------------------------------------------------------------------ bind（S2/S5-5）
def test_bind_set_list_remove(workdir: App, capsys) -> None:
    code, lines, _err = run(["bind", "set", "1A2B3C4D", "Steve", "--config", CONFIG], capsys)
    assert code == 0
    assert lines == ["[绑定] 已写入 1A2B3C4D -> Steve (data/bindings.toml)"]

    code, lines, _err = run(["bind", "list", "--config", CONFIG], capsys)
    assert code == 0
    assert lines == ["[绑定] 1A2B3C4D -> Steve"]

    code, lines, _err = run(["bind", "set", "1A2B3C4D", "Alex", "--config", CONFIG], capsys)
    assert code == 0
    code, lines, _err = run(["bind", "list", "--config", CONFIG], capsys)
    assert lines == ["[绑定] 1A2B3C4D -> Alex"]

    code, lines, _err = run(["bind", "remove", "1A2B3C4D", "--config", CONFIG], capsys)
    assert code == 0
    assert lines == ["[绑定] 已移除 1A2B3C4D"]
    code, lines, _err = run(["bind", "list", "--config", CONFIG], capsys)
    assert lines == ["[绑定] 无绑定记录"]

    code, lines, _err = run(["bind", "remove", "1A2B3C4D", "--config", CONFIG], capsys)
    assert lines == ["[绑定] 未找到 1A2B3C4D"]


def test_bind_set_invalid_game_id(workdir: App, capsys) -> None:
    code, _lines, err = run(["bind", "set", "1A2B3C4D", "ab", "--config", CONFIG], capsys)
    assert code == 1
    assert "游戏ID 不合法" in err


# ------------------------------------------------------------------ commands（QQ 管理端指令面板）
def test_commands_prints_management_panel_list(workdir: App, capsys) -> None:
    """`commands` 打印管理端要填的清单：指令名带当前前缀 + 面板字数限制内的短描述。"""

    code, lines, _err = run(["commands", "--config", CONFIG], capsys)
    assert code == 0
    assert lines == ["[指令] /bind 绑定游戏ID", "[指令] /status 查询在线状态"]


def test_commands_follows_config_prefix(workdir: App, capsys) -> None:
    """指令名用的是配置里的 `command_prefix`：改了前缀，管理端清单跟着变。"""

    text = workdir.config_path.read_text(encoding="utf-8")
    workdir.config_path.write_text(text.replace('command_prefix = "/"', 'command_prefix = "!"'), encoding="utf-8")
    code, lines, _err = run(["commands", "--config", CONFIG], capsys)
    assert code == 0
    assert lines == ["[指令] !bind 绑定游戏ID", "[指令] !status 查询在线状态"]


def test_commands_missing_config(capsys, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["commands", "--config", "nope.toml"]) == 1
    assert "配置文件不存在" in capsys.readouterr().err


# ------------------------------------------------------------------ simulate（S2）
def test_simulate_forward_to_mc(workdir: App, capsys) -> None:
    run(["bind", "set", "1A2B3C4D", "Steve", "--config", CONFIG], capsys)
    code, lines, _err = run(
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


def test_simulate_unbound_user(workdir: App, capsys) -> None:
    code, lines, _err = run(
        ["simulate", "group-message", "--openid", "UNKNOWN", "--content", "#hi", "--dry-run", "--config", CONFIG],
        capsys,
    )
    assert code == 0
    assert lines == ["[群消息] 请先使用 /bind <游戏ID> 绑定"]


def test_simulate_non_trigger_prefix(workdir: App, capsys) -> None:
    code, lines, _err = run(
        ["simulate", "group-message", "--openid", "X", "--content", "普通消息", "--dry-run", "--config", CONFIG],
        capsys,
    )
    assert code == 0
    assert lines == ["[忽略] 非触发前缀"]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("/bind", "[群消息] 用法: /bind <游戏ID>"),
        ("/unknowncmd", "[群消息] 未知指令"),
    ],
)
def test_simulate_command_replies(workdir: App, capsys, content: str, expected: str) -> None:
    code, lines, _err = run(
        ["simulate", "group-message", "--openid", "X", "--content", content, "--dry-run", "--config", CONFIG],
        capsys,
    )
    assert code == 0
    assert lines == [expected]


def test_simulate_status(workdir: App, capsys) -> None:
    code, lines, _err = run(
        ["simulate", "group-message", "--openid", "X", "--content", "/status", "--dry-run", "--config", CONFIG],
        capsys,
    )
    assert code == 0
    # /status 会真的查一次 RCON（dry-run 下用假连接），所以先出现命令回显行
    assert lines == [
        "[RCON main] /list",
        "[群消息] [服务器状态]",
        "[群消息] 在线: 0/20",
        "[群消息] 玩家: 无",
    ]


# ------------------------------------------------------------------ simulate（S3/S4）
def test_simulate_log_event_chat(workdir: App, capsys) -> None:
    code, lines, _err = run(
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
    assert lines == ["[群消息] Steve@main: 大家好"]  # v0.2：只在群里出现，游戏内不再回显


def test_simulate_log_event_plain_chat(workdir: App, capsys) -> None:
    code, lines, _err = run(
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
    assert code == 0
    assert lines == ["[忽略] 聊天非 # 开头，不转发"]


def test_simulate_log_event_loop_protection(workdir: App, capsys) -> None:
    code, lines, _err = run(
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
    assert code == 0
    assert lines == ["[忽略] 回环防护：命中 ignored_chat_prefixes"]


def test_simulate_log_event_join_quit(workdir: App, capsys) -> None:
    code, lines, _err = run(
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
    assert code == 0
    assert lines == ["[群消息] Steve进入了main"]

    code, lines, _err = run(
        ["simulate", "log-event", "--server", "main", "--kind", "quit", "--player", "Steve", "--config", CONFIG],
        capsys,
    )
    assert code == 0
    assert lines == ["[群消息] Steve退出了main"]


def test_simulate_log_event_unmatched_line(workdir: App, capsys) -> None:
    code, _lines, err = run(
        [
            "simulate",
            "log-event",
            "--server",
            "main",
            "--line",
            "随便一行日志",
            "--dry-run",
            "--config",
            CONFIG,
        ],
        capsys,
    )
    assert code == 1
    assert "未匹配任何模板" in err


def test_simulate_log_event_unknown_server(workdir: App, capsys) -> None:
    code, _lines, err = run(
        ["simulate", "log-event", "--server", "nope", "--kind", "join", "--player", "Steve", "--config", CONFIG],
        capsys,
    )
    assert code == 1
    assert "未知服务器" in err


def test_simulate_health_notifies_once(workdir: App, capsys) -> None:
    args = ["simulate", "health", "--server", "main", "--offline", "--dry-run", "--config", CONFIG]
    code, lines, _err = run(args, capsys)
    assert code == 0
    assert "[群消息] [服务器状态] main 离线" in lines

    code, lines, _err = run(args, capsys)
    assert code == 0
    assert lines[-1] == "[忽略] 状态未变化，不重复提示"  # 只提示一次（R19）

    code, lines, _err = run(
        ["simulate", "health", "--server", "main", "--online", "--dry-run", "--config", CONFIG], capsys
    )
    assert code == 0
    assert "[群消息] [服务器状态] main 上线" in lines
