"""命令行入口。stdout 文案即验收断言对象（PLAN.md §3.4）。

子命令一览::

    python -m y33bot --version                          # 打印 y33bot 0.1.0
    python -m y33bot run    --config config.toml        # 常驻服务（QQ 网关 + 日志轮询 + 健康轮询）
    python -m y33bot check  --config config.toml        # 启动自检，退出码 0 通过 / 1 失败
    python -m y33bot bind list | bind set <openid> <game_id> | bind remove <openid>
    python -m y33bot simulate group-message --openid <id> --content '<文本>' [--dry-run]
    python -m y33bot simulate log-event --server <name> --line '<一行日志>' [--dry-run]
    python -m y33bot simulate log-event --server <name> --kind join|quit --player <name>
    python -m y33bot simulate health --server <name> --online|--offline [--dry-run]

输出行前缀固定：``[群消息] `` / ``[RCON <server>] `` / ``[忽略] `` / ``[警告] `` / ``[错误] ``。

骨架阶段（T1）边界
------------------
本文件在 T1 提供**可运行的入口与自检**，其余模块只有签名占位（函数体 raise
NotImplementedError）。因此 ``check`` 用标准库 ``tomllib`` + ``socket`` 直接做最小自检
（配置解析 / 环境变量 / RCON 端口可达 / 日志可读 / 绑定条数）；T8 接入 ``config.load_config()``、
``RconPool``、``BindingStore`` 后替换成真实模块调用，但自检逐行文案与退出码保持不变。
``bind`` / ``simulate`` 在骨架阶段返回退出码 3（未实现），避免出现“静默跑通”的假绿。
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import socket
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from y33bot import __version__

DEFAULT_CONFIG = "config.toml"
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_NOT_IMPLEMENTED = 3

QQ_DEFAULT_APP_ID_ENV = "QQ_BOT_APP_ID"
QQ_DEFAULT_APP_SECRET_ENV = "QQ_BOT_APP_SECRET"


def build_parser() -> argparse.ArgumentParser:
    """构造 argparse 解析器（子命令与参数即 PLAN.md §3.4 的契约）。"""
    parser = argparse.ArgumentParser(
        prog="y33bot",
        description="MC（Java Vanilla）与 QQ 群之间的双向消息互通服务。",
    )
    parser.add_argument("--version", action="version", version=f"y33bot {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="命令")

    run_parser = subparsers.add_parser("run", help="常驻服务（QQ 网关 + 日志轮询 + 健康轮询）")
    run_parser.add_argument(
        "--config", default=DEFAULT_CONFIG, help="配置文件路径（默认 config.toml）"
    )
    run_parser.add_argument("--verbose", action="store_true", help="日志级别提升为 DEBUG")

    check_parser = subparsers.add_parser("check", help="启动自检：退出码 0 通过 / 1 失败")
    check_parser.add_argument(
        "--config", default=DEFAULT_CONFIG, help="配置文件路径（默认 config.toml）"
    )
    check_parser.add_argument("--verbose", action="store_true", help="日志级别提升为 DEBUG")

    bind_parser = subparsers.add_parser("bind", help="绑定表维护（OpenID ↔ 游戏ID）")
    bind_parser.add_argument("action", choices=["list", "set", "remove"])
    bind_parser.add_argument("openid", nargs="?", help="QQ member_openid（list 时可省略）")
    bind_parser.add_argument("game_id", nargs="?", help="MC 游戏 ID（仅 set 需要）")
    bind_parser.add_argument(
        "--config", default=DEFAULT_CONFIG, help="配置文件路径（默认 config.toml）"
    )

    sim_parser = subparsers.add_parser("simulate", help="离线复现验收场景 S2–S4（PLAN.md §5）")
    sim_sub = sim_parser.add_subparsers(dest="sim_kind", required=True, metavar="场景")

    group_message = sim_sub.add_parser("group-message", help="模拟 @机器人 群消息（QQ→MC）")
    group_message.add_argument("--openid", required=True, help="发送者 member_openid")
    group_message.add_argument("--content", required=True, help="消息正文（已去 @机器人 前缀）")
    group_message.add_argument("--group-openid", default="", help="群 openid（默认取 config.toml）")
    group_message.add_argument("--dry-run", action="store_true", help="用 RCON 替身，不发真实命令")
    group_message.add_argument("--config", default=DEFAULT_CONFIG, help="配置文件路径")

    log_event = sim_sub.add_parser("log-event", help="模拟一行日志（MC→QQ）")
    log_event.add_argument("--server", required=True, help="服务器名（config.toml 中的 name）")
    log_event.add_argument("--line", help="直接给一行完整日志文本")
    log_event.add_argument(
        "--kind", choices=["join", "quit"], help="按语义构造事件（配合 --player）"
    )
    log_event.add_argument("--player", help="玩家名（配合 --kind）")
    log_event.add_argument("--dry-run", action="store_true", help="用 RCON 替身，不发真实命令")
    log_event.add_argument("--config", default=DEFAULT_CONFIG, help="配置文件路径")

    health = sim_sub.add_parser("health", help="模拟健康状态翻转（只提示一次）")
    health_state = health.add_mutually_exclusive_group(required=True)
    health_state.add_argument("--online", action="store_true", help="模拟服务器上线")
    health_state.add_argument("--offline", action="store_true", help="模拟服务器离线")
    health.add_argument("--server", required=True, help="服务器名（config.toml 中的 name）")
    health.add_argument("--dry-run", action="store_true", help="用 RCON 替身，不发真实消息")
    health.add_argument("--config", default=DEFAULT_CONFIG, help="配置文件路径")

    return parser


def _configure_logging(verbose: bool) -> None:
    """统一 logging 配置（PLAN.md §3.6）：logger 名 ``y33bot.<模块>``，输出到 stderr。"""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _load_toml(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """读取并解析 TOML。返回 ``(数据, 错误文案)``，两者互斥。"""
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"配置文件不存在: {path}"
    except tomllib.TOMLDecodeError as exc:
        return None, f"{path} 解析失败: {exc}"
    except OSError as exc:
        return None, f"{path} 读取失败: {exc}"


def _resolve(base: Path, value: str) -> Path:
    """相对路径按配置文件所在目录解析（PLAN.md §4.1）。"""
    candidate = Path(value)
    return candidate if candidate.is_absolute() else base / candidate


def _check_items(config_path: Path, data: dict[str, Any], env: Mapping[str, str]) -> bool:
    """打印逐项自检结果行，返回是否全部通过。

    骨架阶段直接读 TOML + 探测 TCP；T8 替换为 ``Service.startup_checks()``
    （``config.load_config()`` + ``RconPool`` + ``BindingStore``），逐行文案不变。
    """
    ok = True
    servers: list[dict[str, Any]] = data.get("mc_servers", [])

    qq: dict[str, Any] = data.get("qq", {})
    app_id_env = str(qq.get("app_id_env", QQ_DEFAULT_APP_ID_ENV))
    app_secret_env = str(qq.get("app_secret_env", QQ_DEFAULT_APP_SECRET_ENV))
    if not env.get(app_id_env):
        print(f"[QQ] FAIL 环境变量 {app_id_env} 未设置")
        ok = False
    elif not env.get(app_secret_env):
        print(f"[QQ] FAIL 环境变量 {app_secret_env} 未设置")
        ok = False
    else:
        target = (
            "group_openid 已配置"
            if qq.get("group_openid")
            else "group_openid 未配置（MC→QQ 方向禁用）"
        )
        print(f"[QQ] OK app_id 已设置 (env {app_id_env})，{target}")

    for server in servers:
        name = str(server.get("name", "?"))
        host = str(server.get("host", "127.0.0.1"))
        port = int(server.get("port", 25575))
        timeout = float(server.get("connect_timeout", 5.0))
        try:
            with socket.create_connection((host, port), timeout=timeout):
                pass
        except OSError as exc:
            print(f"[RCON {name}] FAIL 无法连接 {host}:{port}: {exc}")
            ok = False
        else:
            print(
                f"[RCON {name}] OK 端口可达 {host}:{port}"
                "（骨架阶段仅探测 TCP，登录/命令由 T4 实装）"
            )

    for server in servers:
        name = str(server.get("name", "?"))
        log_path = _resolve(config_path.parent, str(server.get("log_path", "")))
        try:
            with log_path.open("rb") as handle:
                offset = handle.seek(0, io.SEEK_END)
        except OSError as exc:
            print(f"[日志 {name}] FAIL {log_path} 不可读: {exc}")
            ok = False
        else:
            print(f"[日志 {name}] OK {log_path} 可读，偏移 {offset} 字节")

    paths: dict[str, Any] = data.get("paths", {})
    bindings_path = _resolve(config_path.parent, str(paths.get("bindings", "data/bindings.toml")))
    if not bindings_path.is_file():
        print("[绑定] OK 0 条")
    else:
        bindings, error = _load_toml(bindings_path)
        if bindings is None:
            print(f"[绑定] FAIL {error}")
            ok = False
        else:
            print(f"[绑定] OK {len(bindings.get('bindings', []))} 条")

    return ok


def _cmd_check(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    """``check``：启动自检（逐项结果行 + 末行 OK/FAIL，退出码 0/1）。"""
    config_path = Path(args.config)
    data, error = _load_toml(config_path)
    if data is None:
        print(f"[配置] FAIL {error}")
        print("FAIL")
        return EXIT_FAIL

    servers: list[dict[str, Any]] = data.get("mc_servers", [])
    print(f"[配置] OK {config_path} 解析成功，{len(servers)} 个 MC 服")
    ok = _check_items(config_path, data, env)
    print("OK" if ok else "FAIL")
    return EXIT_OK if ok else EXIT_FAIL


def _cmd_run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    """``run``：骨架阶段打印启动自检与健康状态后退出 0（常驻循环由 T8 接入）。

    退出码语义：配置不可读 → 1；其余情况 0（单服 RCON 故障只告警，不阻塞启动，PLAN.md §3.6）。
    """
    config_path = Path(args.config)
    data, error = _load_toml(config_path)
    if data is None:
        print(f"[错误] {error}")
        return EXIT_FAIL

    servers: list[dict[str, Any]] = data.get("mc_servers", [])
    print(f"[启动] y33bot {__version__}（config={config_path}，{len(servers)} 个 MC 服）")
    print("[启动] 启动自检：")
    if _check_items(config_path, data, env):
        print("[启动] 启动自检通过")
    else:
        print("[警告] 自检存在失败项；按 PLAN.md §3.6 单服故障只告警、不阻塞启动")
    print("[警告] 骨架阶段：常驻任务（QQ 网关 / 日志轮询 / 健康轮询）尚未接入，见 PLAN.md §6 T8")
    print("[启动] 无常驻任务可运行，自检完成后退出（退出码 0）")
    return EXIT_OK


def _cmd_bind(args: argparse.Namespace) -> int:
    """``bind``：骨架阶段未实现（binding.BindingStore 由 T3 实装）。"""
    target = " ".join(str(part) for part in (args.openid, args.game_id) if part)
    print(
        f"[错误] bind {args.action} {target}".rstrip() + " 尚未实现（骨架阶段）：见 PLAN.md §6 T3"
    )
    return EXIT_NOT_IMPLEMENTED


def _cmd_simulate(args: argparse.Namespace) -> int:
    """``simulate``：骨架阶段未实现（bridge / qq.fakes / rcon.fakes 由 T4/T7 实装）。"""
    print(f"[错误] simulate {args.sim_kind} 尚未实现（骨架阶段）：见 PLAN.md §6 T4/T7")
    return EXIT_NOT_IMPLEMENTED


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 主入口：返回进程退出码（``run``/``check`` 0 通过、1 失败、2 用法错误、3 未实现）。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        _configure_logging(args.verbose)
        return _cmd_run(args, os.environ)
    if args.command == "check":
        return _cmd_check(args, os.environ)
    if args.command == "bind":
        return _cmd_bind(args)
    if args.command == "simulate":
        return _cmd_simulate(args)

    parser.print_help()
    return EXIT_USAGE
