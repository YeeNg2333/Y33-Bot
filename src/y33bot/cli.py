"""命令行入口：run / check / bind / simulate（PLAN.md §3.4 CLI 契约）。

stdout 文案即验收断言对象，输出行前缀固定：
`[群消息] `、`[RCON <server>] `、`[忽略] `、`[警告] `、`[错误] `。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

from . import __version__
from .binding import BindingError, BindingStore, is_valid_game_id
from .bridge import Bridge
from .commands.builtin import build_registry
from .config import AppConfig, ConfigError, load_config
from .mclog.patterns import compile_patterns, parse_line
from .models import MCGroupMessage, MCLogEvent
from .qq.fakes import FakeQQGateway
from .qq.gateway import normalize_content
from .rcon.fakes import FakeRconTransport
from .rcon.pool import RconPool
from .service import Service
from .state import StateStore

__all__ = ["main"]

_LOG = logging.getLogger("y33bot.cli")


# ----------------------------------------------------------------- 日志脚手架
class _PlainFormatter(logging.Formatter):
    """只输出消息本身（消息里已经带了 `[xxx] ` 前缀）。"""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        return record.getMessage()


def _setup_logging(level: int, *, to_stdout: bool) -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    stream = sys.stdout if to_stdout else sys.stderr
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_PlainFormatter())
    handler.setLevel(level)
    root.addHandler(handler)
    root.setLevel(level)


def _display_path(path: Path) -> str:
    """相对 CWD 时打印相对路径（POSIX 风格），避免 CI 输出里出现长绝对路径。"""

    try:
        relative = os.path.relpath(path, Path.cwd())
    except ValueError:  # pragma: no cover - 跨盘符
        return str(path)
    if relative.startswith(".."):
        return str(path)
    return Path(relative).as_posix()


def _load_or_error(path: str) -> AppConfig | None:
    try:
        return load_config(path, os.environ)
    except ConfigError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return None


def _make_pool(config: AppConfig, *, dry_run: bool, factory=None) -> RconPool:
    passwords = config.rcon_passwords(os.environ)
    if factory is not None:
        return RconPool(config.servers, passwords, factory=factory)
    if dry_run:
        return RconPool(config.servers, passwords, factory=FakeRconTransport)
    return RconPool(config.servers, passwords)


# ----------------------------------------------------------------- 子命令：run
def _cmd_run(args: argparse.Namespace) -> int:
    _setup_logging(logging.DEBUG if args.verbose else logging.INFO, to_stdout=False)
    config = _load_or_error(args.config)
    if config is None:
        return 1
    service = Service(config, env=os.environ, config_path=Path(args.config))
    try:
        return asyncio.run(service.run())
    except KeyboardInterrupt:  # pragma: no cover - 默认 SIGINT 处理器兜底
        print("[停止] 收到 Ctrl+C", file=sys.stderr)
        return 0


# ----------------------------------------------------------------- 子命令：check
def _cmd_check(args: argparse.Namespace) -> int:
    _setup_logging(logging.INFO if args.verbose else logging.WARNING, to_stdout=False)
    try:
        config = load_config(args.config, os.environ)
    except ConfigError as exc:
        print(f"[配置] FAIL {exc}")
        print("FAIL")
        return 1
    service = Service(config, env=os.environ, config_path=Path(args.config))
    results = asyncio.run(service.startup_checks())
    passed = True
    for item in results:
        passed = passed and item.ok
        print(f"[{item.label}] {'OK' if item.ok else 'FAIL'} {item.detail}")
    print("OK" if passed else "FAIL")
    return 0 if passed else 1


# ----------------------------------------------------------------- 子命令：bind
def _cmd_bind(args: argparse.Namespace) -> int:
    _setup_logging(logging.INFO if args.verbose else logging.WARNING, to_stdout=False)
    config = _load_or_error(args.config)
    if config is None:
        return 1
    try:
        store = BindingStore.load(config.bindings_path)
    except BindingError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1

    if args.action == "list":
        items = store.items()
        if not items:
            print("[绑定] 无绑定记录")
        for openid, game_id in items.items():
            print(f"[绑定] {openid} -> {game_id}")
        return 0

    if args.action == "set":
        openid = args.openid.strip()
        game_id = args.game_id.strip()
        if not openid:
            print("[错误] openid 不能为空", file=sys.stderr)
            return 1
        if not is_valid_game_id(game_id):
            print("[错误] 游戏ID 不合法（^[A-Za-z0-9_]{3,16}$）", file=sys.stderr)
            return 1
        try:
            store.bind(openid, game_id)
            store.save()
        except BindingError as exc:
            print(f"[错误] {exc}", file=sys.stderr)
            return 1
        print(f"[绑定] 已写入 {openid} -> {game_id} ({_display_path(config.bindings_path)})")
        return 0

    removed = store.unbind(args.openid.strip())
    if removed:
        store.save()
    print(f"[绑定] {'已移除' if removed else '未找到'} {args.openid.strip()}")
    return 0


# ----------------------------------------------------------------- 子命令：simulate
async def _simulate_group_message(args: argparse.Namespace, config: AppConfig) -> int:
    store = StateStore.load(config.state_path)
    try:
        bindings = BindingStore.load(config.bindings_path)
    except BindingError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    pool = _make_pool(config, dry_run=args.dry_run)
    gateway = FakeQQGateway()
    bridge = Bridge(config, bindings, store, pool, build_registry(), gateway)

    group_openid = (args.group_openid or config.qq.group_openid or "simulate-group").strip()
    message = MCGroupMessage(
        group_openid=group_openid,
        member_openid=args.openid,
        message_id=args.message_id,
        content=normalize_content(args.content),
        received_at=time.time(),
    )
    try:
        reply = await bridge.handle_group_message(message)
    finally:
        await pool.close()
    if reply:
        for line in reply.splitlines():
            print(f"[群消息] {line}")
    return 0


async def _simulate_log_event(args: argparse.Namespace, config: AppConfig) -> int:
    server = config.server(args.server)
    if server is None:
        print(f"[错误] 未知服务器: {args.server}", file=sys.stderr)
        return 1

    if args.line is not None:
        parsed = parse_line(compile_patterns(config.patterns), args.line)
        if parsed is None:
            print("[警告] 日志行未匹配任何模板", file=sys.stderr)
            return 1
        event = replace(parsed, server=server.name, occurred_at=time.time())
    else:
        event = MCLogEvent(
            server=server.name,
            kind=args.kind,
            player=args.player,
            message=None,
            raw=f"simulate {args.kind} {args.player}",
            occurred_at=time.time(),
        )

    store = StateStore.load(config.state_path)
    try:
        bindings = BindingStore.load(config.bindings_path)
    except BindingError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    pool = _make_pool(config, dry_run=args.dry_run)
    gateway = FakeQQGateway()
    bridge = Bridge(config, bindings, store, pool, build_registry(), gateway)
    try:
        await bridge.handle_log_event(event)
    finally:
        await pool.close()
    return 0


async def _simulate_health(args: argparse.Namespace, config: AppConfig) -> int:
    server = config.server(args.server)
    if server is None:
        print(f"[错误] 未知服务器: {args.server}", file=sys.stderr)
        return 1

    want_online = bool(args.online)
    target = (server.host, server.port)

    def factory(host: str, port: int, password: str, *, connect_timeout: float = 5.0, command_timeout: float = 5.0):
        is_target = (host, port) == target
        return FakeRconTransport(
            host=host,
            port=port,
            password=password,
            connect_timeout=connect_timeout,
            command_timeout=command_timeout,
            online=(want_online if is_target else True),
        )

    store = StateStore.load(config.state_path)
    try:
        bindings = BindingStore.load(config.bindings_path)
    except BindingError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    pool = _make_pool(config, dry_run=True, factory=factory)
    gateway = FakeQQGateway()
    bridge = Bridge(config, bindings, store, pool, build_registry(), gateway)
    try:
        flips = await bridge.poll_health()
    finally:
        await pool.close()
    if flips:
        store.save()
    else:
        print("[忽略] 状态未变化，不重复提示")
    return 0


def _cmd_simulate(args: argparse.Namespace) -> int:
    _setup_logging(logging.INFO, to_stdout=True)
    config = _load_or_error(args.config)
    if config is None:
        return 1
    if args.what == "group-message":
        return asyncio.run(_simulate_group_message(args, config))
    if args.what == "log-event":
        return asyncio.run(_simulate_log_event(args, config))
    return asyncio.run(_simulate_health(args, config))


# ----------------------------------------------------------------- 解析器
def _add_config_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="config.toml", help="配置文件路径（默认 config.toml）")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="y33bot", description="Minecraft ↔ QQ 群消息互通机器人")
    parser.add_argument("--version", action="version", version=f"y33bot {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="常驻运行（QQ 网关 + 日志轮询 + 健康轮询）")
    _add_config_option(run)
    run.add_argument("--verbose", action="store_true", help="输出 DEBUG 日志")
    run.set_defaults(func=_cmd_run)

    check = sub.add_parser("check", help="启动自检：退出码 0 通过 / 1 失败")
    _add_config_option(check)
    check.add_argument("--verbose", action="store_true", help="输出更多日志")
    check.set_defaults(func=_cmd_check)

    bind = sub.add_parser("bind", help="绑定表维护（list/set/remove）")
    bind_sub = bind.add_subparsers(dest="action", required=True)
    bind_list = bind_sub.add_parser("list", help="列出全部绑定")
    _add_config_option(bind_list)
    bind_list.add_argument("--verbose", action="store_true")
    bind_list.set_defaults(func=_cmd_bind)
    bind_set = bind_sub.add_parser("set", help="写入绑定（同 openid 覆盖）")
    _add_config_option(bind_set)
    bind_set.add_argument("openid")
    bind_set.add_argument("game_id")
    bind_set.add_argument("--verbose", action="store_true")
    bind_set.set_defaults(func=_cmd_bind)
    bind_remove = bind_sub.add_parser("remove", help="删除绑定")
    _add_config_option(bind_remove)
    bind_remove.add_argument("openid")
    bind_remove.add_argument("--verbose", action="store_true")
    bind_remove.set_defaults(func=_cmd_bind)

    simulate = sub.add_parser("simulate", help="离线模拟一条事件（默认 QQ 侧永远离线）")
    sim_sub = simulate.add_subparsers(dest="what", required=True)

    group_message = sim_sub.add_parser("group-message", help="模拟一条群 @机器人 消息")
    _add_config_option(group_message)
    group_message.add_argument("--openid", required=True, help="发送者 member_openid")
    group_message.add_argument("--content", required=True, help="消息文本（含 / 或 # 前缀）")
    group_message.add_argument("--group-openid", default="", help="群 openid（默认取配置）")
    group_message.add_argument("--message-id", default="simulate-1", help="消息 id")
    group_message.add_argument("--dry-run", action="store_true", help="用假 RCON，不做网络 IO")
    group_message.set_defaults(func=_cmd_simulate)

    log_event = sim_sub.add_parser("log-event", help="模拟一条 MC 日志事件")
    _add_config_option(log_event)
    log_event.add_argument("--server", required=True, help="MC 服名称（配置里的 name）")
    log_event.add_argument("--line", default=None, help="一整行日志文本")
    log_event.add_argument("--kind", choices=("join", "quit"), default=None, help="直接构造进出事件")
    log_event.add_argument("--player", default=None, help="配合 --kind 使用的玩家名")
    log_event.add_argument("--dry-run", action="store_true", help="用假 RCON，不做网络 IO")
    log_event.set_defaults(func=_cmd_simulate)

    health = sim_sub.add_parser("health", help="模拟一次健康探测（离线用假 RCON 模拟）")
    _add_config_option(health)
    health.add_argument("--server", required=True, help="MC 服名称（配置里的 name）")
    health_mode = health.add_mutually_exclusive_group(required=True)
    health_mode.add_argument("--online", action="store_true", help="模拟该服在线")
    health_mode.add_argument("--offline", action="store_true", help="模拟该服离线")
    health.add_argument("--dry-run", action="store_true", help="兼容用参数（本子命令始终离线）")
    health.set_defaults(func=_cmd_simulate)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口；返回进程退出码。"""

    parser = _build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "what", None) == "log-event" and args.line is None:
        if args.kind is None or args.player is None:
            parser.error("log-event 需要 --line，或同时提供 --kind 与 --player")
    return int(args.func(args))
