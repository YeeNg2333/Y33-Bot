"""组件装配、常驻任务、优雅退出、启动自检（PLAN.md §3.2 / §2.7 / §3.6 / S1 / S5）。

常驻三个任务：QQ 网关（由 `qq.gateway` 自己起任务）、日志轮询、健康轮询。
所有写盘（state/bindings）都走原子替换；退出时保证 `state.json` 的 `log_offset` 与文件大小一致。
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from . import __version__
from .binding import BindingError, BindingStore
from .bridge import Bridge
from .commands.builtin import build_registry
from .commands.registry import CommandRegistry
from .config import AppConfig, ConfigError
from .mclog.patterns import CompiledPatterns, compile_patterns, looks_like_event, parse_line
from .mclog.watcher import LogWatcher
from .models import MCGroupMessage
from .qq.gateway import BotpyGateway, QQGateway, QQGatewayError
from .qq.probe import probe_access_token
from .rcon.pool import LIST_COMMAND, RconPool
from .state import StateStore

if TYPE_CHECKING:  # pragma: no cover - 仅类型标注
    from collections.abc import Awaitable, Callable, Mapping

    #: QQ 凭据探活的可注入签名（`check` 用真探活；测试注入假实现即可完全离线）
    QQProbe = Callable[[str, str], Awaitable[int]]

__all__ = ["CheckResult", "Service"]

logger = logging.getLogger("y33bot.service")

#: 探活失败归因用的关键字（BUG-005 修复方向 3）：命中前者 = 凭据/配置问题，命中后者 = 网络不可达。
#: 目的是让启动失败的首行日志就能分清「我们配置错了」还是「平台/网络抖动」。
#: 100007 = appid/secret 无效，10004 = 机器人不存在（本机实测平台原文），两者都是配置问题而非抖动。
_CREDENTIAL_HINTS = (
    "100007",
    "10004",
    "appid or secret",
    "invalid",
    "unauthorized",
    "机器人不存在",
    "secret invalid",
)
_NETWORK_HINTS = (
    "ssl",
    "eof",
    "timed out",
    "timeout",
    "connection",
    "urlopen",
    "proxy",
    "getaddrinfo",
    "unreachable",
    "network",
)
#: 平台侧抖动（限流 / 请求超时 / 5xx）：**不是**凭据错，也不是本机网络问题。
#: 这几个必须先于 `_NETWORK_HINTS` 判，否则 `HTTP 408 Request Timeout` 会被 "timeout" 抢走。
_PLATFORM_HINTS = (
    "http 408",
    "http 429",
    "too many requests",
    "rate limit",
    "http 5",
)


def _describe_probe_error(exc: BaseException) -> str:
    """把探活异常翻成一句可读原因（风格对齐 `gateway._describe_gateway_error`：原文保留在冒号后）。

    三类归因（顺序即优先级）：

    - 平台明确说凭据/机器人不对（`code=100007`、`code=10004 机器人不存在`、HTTP 401/403）→ 凭据/配置问题；
    - 平台限流/超时/5xx（HTTP 408、429、5xx、`too many requests`）→ 平台侧抖动，**不是**凭据错；
    - 连接层报错（SSL EOF / 超时 / DNS）→ 网络不可达，**不是**凭据错；
    - 其余（响应不是 JSON……）→ 平台侧抖动。

    注意：**绝不能把「HTTP 4xx」整体判成凭据问题** —— `408 Request Timeout` / `429 Too Many Requests`
    用的是合法凭据，误判会让运维去改 app_id/app_secret，而启动策略是失败即退出，等于领错方向。
    """

    text = str(exc).strip() or exc.__class__.__name__
    lowered = text.lower()
    if any(hint in lowered for hint in _CREDENTIAL_HINTS):
        advice = "凭据/配置问题：app_id 或 app_secret 无效，不是平台抖动"
    elif any(hint in lowered for hint in _PLATFORM_HINTS):
        advice = "平台接口报错（接口抖动）：稍后重跑即可，本进程不重试"
    elif any(hint in lowered for hint in _NETWORK_HINTS):
        advice = "网络不可达（不是凭据错）：检查本机网络/代理后重跑"
    else:
        advice = "平台接口报错（接口抖动）：稍后重跑即可，本进程不重试"
    return f"{text}（{advice}）"


#: `check` 的模板自检只看日志末尾这么多行：够覆盖一次上线/聊天，又不必读整份日志（BUG-004）
TEMPLATE_SAMPLE_LINES = 200

#: 计数输出的事件类型顺序（与 `looks_like_event()` 的取值一致）
_EVENT_KIND_ORDER = ("join", "quit", "chat")


@dataclass(frozen=True)
class CheckResult:
    """`check` 子命令的一行结果（PLAN.md §3.4）。"""

    label: str
    ok: bool
    detail: str


def _tail_lines(path: Path, *, limit: int, encoding: str) -> list[str]:
    """读文件末尾最多 `limit` 个非空行（尾插顺序不变）。

    从尾部按块回读，`latest.log` 再大也不会整份读进内存；文件不存在 / 打不开 / 读取
    中途失败一律返回空列表，让调用方按「没有可判定的样例行」处理，绝不把 `check` 打成异常。
    """

    block = 8192
    remaining = 0
    data = b""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            remaining = handle.tell()
            while remaining > 0 and data.count(b"\n") <= limit:
                step = min(block, remaining)
                remaining -= step
                handle.seek(remaining)
                data = handle.read(step) + data
    except OSError:
        return []

    lines = data.split(b"\n")
    if remaining > 0:  # 首段是从中间截断的半行，丢弃
        lines = lines[1:]
    texts = [line.decode(encoding, errors="replace").rstrip("\r") for line in lines]
    return [text for text in texts if text.strip()][-limit:]


def _format_counts(counts: dict[str, int]) -> str:
    """把命中计数渲染成 `join a / quit b / chat c`（只列出现过的类型，顺序固定）。"""

    return " / ".join(f"{kind} {counts[kind]}" for kind in _EVENT_KIND_ORDER if counts.get(kind))


def _template_check(server_name: str, compiled: CompiledPatterns, log_path: Path) -> CheckResult:
    """`[日志模板 <name>]`：拿 `latest.log` 末尾样例行反过来验证 `[log_patterns]` 是否还能用。

    判别分两步，与日志布局无关（BUG-004：模板写错时没人发现）：
    先用 `looks_like_event()` 按载荷特征挑出「本该是事件」的候选行，
    再逐条 `parse_line()` 看现行模板是否真的命中。
    - 有候选且全部命中 → OK；
    - 有候选但 0 命中 / 部分命中 → FAIL（提示按 README §13 调模板）；
    - 没有候选（含日志缺失、读不出来）→ OK 跳过，不算失败（安静服务端不能误报）。
    """

    label = f"日志模板 {server_name}"
    lines = _tail_lines(log_path, limit=TEMPLATE_SAMPLE_LINES, encoding=compiled.encoding)
    samples = [(line, looks_like_event(line)) for line in lines]
    candidates = [(line, kind) for line, kind in samples if kind is not None]
    total = len(candidates)
    if total == 0:
        return CheckResult(label, True, "未找到可判定的样例行，跳过")

    counts: dict[str, int] = {}
    matched = 0
    for line, _kind in candidates:
        event = parse_line(compiled, line)
        if event is None:
            continue
        matched += 1
        counts[event.kind] = counts.get(event.kind, 0) + 1

    if matched == total:
        return CheckResult(label, True, f"样例行 {total} 条全部命中（{_format_counts(counts)}）")
    if matched == 0:
        return CheckResult(label, False, f"{total} 条样例行全部未命中：请按 README §13 调整 [log_patterns]")
    return CheckResult(
        label,
        False,
        f"{total} 条样例行中 {matched} 条命中、{total - matched} 条未命中：请按 README §13 调整 [log_patterns]",
    )


class Service:
    """把配置、RCON、日志监听、指令表、网关装配成一个常驻进程。"""

    def __init__(
        self,
        config: AppConfig,
        *,
        env: Mapping[str, str] | None = None,
        config_path: Path | None = None,
        gateway: QQGateway | None = None,
        pool: RconPool | None = None,
        logger: logging.Logger | None = None,
        qq_probe: QQProbe | None = None,
        probe_qq: bool = True,
    ) -> None:
        self._config = config
        self._env: dict[str, str] = dict(env if env is not None else os.environ)
        self._config_path = Path(config_path) if config_path is not None else None
        self._logger = logger or logging.getLogger("y33bot.service")
        self._gateway = gateway
        self._pool = pool
        self._qq_probe: QQProbe = qq_probe if qq_probe is not None else probe_access_token
        self._probe_qq = probe_qq

        self._state: StateStore | None = None
        self._bindings: BindingStore | None = None
        self._bridge: Bridge | None = None
        self._registry: CommandRegistry | None = None
        self._watchers: dict[str, LogWatcher] = {}
        self._stop_event: asyncio.Event | None = None
        self._signal_flag = threading.Event()

    # ------------------------------------------------------------------ 自检
    async def startup_checks(self) -> list[CheckResult]:
        """逐项自检；不抛异常，全部问题以 `CheckResult(ok=False)` 返回（PLAN.md §3.4）。"""

        config = self._config
        results: list[CheckResult] = []

        name = self._config_path.name if self._config_path is not None else "config.toml"
        results.append(CheckResult("配置", True, f"{name} 解析成功，{len(config.servers)} 个 MC 服"))

        # ---- QQ 凭据：先判存在，再（默认）真探活取一次 access_token（BUG-001 的 R5）
        try:
            app_id, app_secret = config.app_credentials(self._env)
        except ConfigError as exc:
            results.append(CheckResult("QQ", False, str(exc)))
        else:
            group = "group_openid 已配置" if config.qq.mc_to_qq_enabled else "group_openid 未配置（MC→QQ 方向禁用）"
            if not self._probe_qq:
                no_probe = f"app_id 已设置 (env {config.qq.app_id_env})，未探活（--no-probe），{group}"
                results.append(CheckResult("QQ", True, no_probe))
            else:
                try:
                    expires_in = await self._qq_probe(app_id, app_secret)
                except Exception as exc:  # noqa: BLE001 - 自检不抛异常，探活失败一律落成 FAIL 行
                    results.append(CheckResult("QQ", False, f"access_token 获取失败: {exc}"))
                else:
                    results.append(
                        CheckResult(
                            "QQ",
                            True,
                            f"access_token 获取成功（有效期 {expires_in}s），"
                            f"app_id 已设置 (env {config.qq.app_id_env})，{group}",
                        )
                    )

        # ---- RCON（可用则真连一次 /list）
        passwords: dict[str, str] = {}
        missing: dict[str, str] = {}
        for server in config.servers:
            try:
                passwords[server.name] = config.rcon_password(server, self._env)
            except ConfigError as exc:
                missing[server.name] = str(exc)
        pool: RconPool | None = self._pool
        created = False
        if pool is None and passwords:
            pool = RconPool([server for server in config.servers if server.name in passwords], passwords)
            created = True
        try:
            for server in config.servers:
                target = f"无法连接 {server.host}:{server.port}"
                if server.name in missing or pool is None:
                    reason = missing.get(server.name, "未配置 RCON 密码")
                    results.append(CheckResult(f"RCON {server.name}", False, f"{target}: {reason}"))
                    continue
                result = await pool.query(server.name, LIST_COMMAND)
                if result.ok:
                    results.append(CheckResult(f"RCON {server.name}", True, f"/list -> {result.response.strip()}"))
                else:
                    results.append(CheckResult(f"RCON {server.name}", False, f"{target}: {result.error}"))
        finally:
            if created and pool is not None:
                await pool.close()

        # ---- 日志文件 + 日志模板自检（同一份 latest.log，模板项紧跟日志项之后）
        compiled = compile_patterns(config.patterns)  # 配置加载阶段已校验过，这里不会失败
        state_store = StateStore.load(config.state_path)
        for server in config.servers:
            path = Path(server.log_path)
            saved = state_store.state.servers.get(server.name)
            offset = int(saved.log_offset) if saved is not None else 0
            if not path.exists():
                results.append(CheckResult(f"日志 {server.name}", False, f"{path} 不存在（启动后会持续重试）"))
            else:
                try:
                    with path.open("rb") as handle:
                        handle.read(1)
                except OSError as exc:
                    results.append(CheckResult(f"日志 {server.name}", False, f"{path} 不可读: {exc}"))
                else:
                    results.append(CheckResult(f"日志 {server.name}", True, f"{path} 可读，偏移 {offset} 字节"))
            # 日志缺失 / 不可读也照样出一行 OK 跳过：模板自检只对「看得见的样例行」负责
            results.append(_template_check(server.name, compiled, path))

        # ---- 绑定表
        try:
            store = BindingStore.load(config.bindings_path)
        except BindingError as exc:
            results.append(CheckResult("绑定", False, str(exc)))
        else:
            results.append(CheckResult("绑定", True, f"{len(store)} 条"))

        return results

    # ------------------------------------------------------------------ 启动探活
    async def _probe_before_gateway(self, credentials: tuple[str, str]) -> bool:
        """起 QQ 网关前探活一次：`True` = 凭据可用，可以继续原有启动流程。

        BUG-005 修复方向 3 / issue #3：平台「凭据错」与「sgroup 接口抖动」原来的报错长得一样，
        启动前先取一次 `access_token` 就能把两者分开（`[错误]` 首行直接写明归因）。

        口径（PLAN.md §7，N7 / PLAN.md:498 不变）：**只试一次**——失败立刻返回 `False`，
        由调用方打日志并以非 0 退出，交给 `systemd`/`nssm` 拉起；这里没有 `while` 重试、没有退避参数。

        探活实现可注入（`qq_probe`，默认 `qq.probe.probe_access_token`），CI 与单测用替身，全程离线。
        """

        app_id, app_secret = credentials
        self._logger.debug("[启动] QQ 凭据探活（一次，不重试）…")
        try:
            expires_in = await self._qq_probe(app_id, app_secret)
        except Exception as exc:  # noqa: BLE001 - 探活失败要落成一行可读日志，不把栈甩给运维
            self._logger.error(
                "[错误] QQ 凭据探活失败（启动前一次性检查，不重试，未启动网关）: %s",
                _describe_probe_error(exc),
            )
            return False
        self._logger.debug("[启动] QQ 凭据探活通过（access_token 有效期 %ss）", expires_in)
        return True

    # ------------------------------------------------------------------ 常驻
    async def run(self) -> int:
        """装配全部组件并常驻运行；返回进程退出码。"""

        config = self._config
        self._stop_event = asyncio.Event()
        self._signal_flag = threading.Event()
        self._install_signal_handlers()
        self._logger.info("[启动] y33bot %s（%d 个 MC 服）", __version__, len(config.servers))

        self._state = StateStore.load(config.state_path)
        try:
            self._bindings = BindingStore.load(config.bindings_path)
        except BindingError as exc:
            self._logger.error("[错误] %s", exc)
            return 1

        try:
            passwords = config.rcon_passwords(self._env)
        except ConfigError as exc:
            self._logger.error("[错误] %s", exc)
            return 1

        if self._pool is None:
            self._pool = RconPool(config.servers, passwords)
        await self._pool.start()

        for server in config.servers:
            self._watchers[server.name] = LogWatcher(server, config.patterns, self._state)
            self._logger.info("[启动] 日志监听已启动: %s", server.name)

        self._registry = build_registry()

        if self._gateway is None:
            try:
                credentials = config.app_credentials(self._env)
            except ConfigError as exc:
                self._logger.error("[错误] %s", exc)
                await self._pool.close()
                return 1
            # BUG-005 修复方向 3：真登录前先探活一次，把「凭据/配置问题」与「sgroup 接口抖动」分开。
            # 探活只跟真实 SDK 网关走；网关是注入的替身（单测/离线路径）时由调用方自己负责，不触网。
            if not await self._probe_before_gateway(credentials):
                await self.shutdown()
                return 1
            self._gateway = BotpyGateway(config, credentials, self._state, handler=self._on_group_message)

        self._bridge = Bridge(
            config,
            self._bindings,
            self._state,
            self._pool,
            self._registry,
            self._gateway,
        )

        if not config.qq.mc_to_qq_enabled:
            self._logger.warning("[警告] [qq] group_openid 未配置，MC→QQ 方向已禁用")

        try:
            await self._gateway.start()
        except (QQGatewayError, RuntimeError) as exc:
            self._logger.error("[错误] QQ 网关启动失败: %s", exc)
            await self.shutdown()
            return 1

        log_task = asyncio.create_task(self._log_loop(), name="y33bot-log-loop")
        health_task = asyncio.create_task(self._health_loop(), name="y33bot-health-loop")
        # BUG-001：网关「启动后自己结束」= 运行期失效，必须被发现（见 _wait_for_stop）
        watch_task = asyncio.create_task(self._gateway.wait_closed(), name="y33bot-qq-gateway-watch")
        stopped = False
        try:
            stopped = await self._wait_for_stop(watch_task)
            if not stopped:
                self._logger.error("[错误] QQ 网关已断开（收不到群消息），进程退出等待重启")
        finally:
            for task in (log_task, health_task, watch_task):
                task.cancel()
            await asyncio.gather(log_task, health_task, watch_task, return_exceptions=True)
            await self.shutdown()
        return 0 if stopped else 1

    async def shutdown(self) -> None:
        """优雅退出：停网关 → 关 RCON → 落盘状态。"""

        self._logger.info("[停止] 正在关闭…")
        if self._gateway is not None:
            try:
                await self._gateway.close()
            except Exception as exc:  # noqa: BLE001 - 关闭失败不应阻断退出
                self._logger.warning("[警告] 关闭 QQ 网关失败: %s", exc)
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception as exc:  # noqa: BLE001
                self._logger.warning("[警告] 关闭 RCON 连接失败: %s", exc)
        if self._state is not None:
            self._state.save()
        self._logger.info("[停止] 已退出")

    # ------------------------------------------------------------------ 循环
    async def _log_loop(self) -> None:
        interval = self._config.behavior.log_poll_interval
        while True:
            await asyncio.sleep(interval)
            dirty = False
            for name, watcher in self._watchers.items():
                try:
                    events = await asyncio.to_thread(watcher.poll_new_events)
                except Exception:  # noqa: BLE001 - 单服异常不能拖垮轮询
                    self._logger.exception("[错误] 日志轮询异常: %s", name)
                    continue
                if events:
                    dirty = True
                for event in events:
                    try:
                        assert self._bridge is not None
                        await self._bridge.handle_log_event(event)
                    except Exception:  # noqa: BLE001
                        self._logger.exception("[错误] 处理日志事件失败: %s", event)
            if dirty and self._state is not None:
                self._state.save()

    async def _health_loop(self) -> None:
        interval = self._config.behavior.health_poll_interval
        while True:
            await asyncio.sleep(interval)
            try:
                assert self._bridge is not None
                flips = await self._bridge.poll_health()
            except Exception:  # noqa: BLE001
                self._logger.exception("[错误] 健康轮询异常")
                continue
            if flips and self._state is not None:
                self._state.save()

    # ------------------------------------------------------------------ 回调
    async def _on_group_message(self, message: MCGroupMessage) -> str | None:
        if self._bridge is None:  # pragma: no cover - 正常装配顺序下不会发生
            self._logger.warning("[警告] 服务尚未就绪，群消息已丢弃")
            return None
        return await self._bridge.handle_group_message(message)

    # ------------------------------------------------------------------ 信号
    def _install_signal_handlers(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover - run() 一定在事件循环里
            return
        installed = 0
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._on_loop_signal)
                installed += 1
            except (NotImplementedError, AttributeError, ValueError, RuntimeError):
                try:
                    signal.signal(sig, self._on_sync_signal)
                except (ValueError, OSError, RuntimeError):  # pragma: no cover - 非主线程
                    pass
        if installed == 0:
            self._logger.debug("[启动] 使用同步信号处理器（平台不支持 add_signal_handler）")

    def _on_loop_signal(self) -> None:
        self._logger.info("[停止] 收到退出信号")
        self._signal_flag.set()
        if self._stop_event is not None:
            self._stop_event.set()

    def _on_sync_signal(self, signum: int, _frame) -> None:  # noqa: ANN001 - signal 回调
        self._logger.info("[停止] 收到信号 %s，准备退出", signum)
        self._signal_flag.set()
        event = self._stop_event
        if event is not None:
            try:
                event.set()
            except RuntimeError:  # pragma: no cover - 跨线程 set 理论上安全，兜一层
                pass

    async def _wait_for_stop(self, gateway_task: asyncio.Task[None] | None = None) -> bool:
        """等待退出信号；返回 `True` = 收到停止信号（都能优雅退出），`False` = 网关任务先结束。

        传入 `gateway_task` 时同时监视它（BUG-001：网关协程结束 = 运行期失效，要报错并非 0 退出）；
        两者同时就绪时按「我们自己主动关闭」处理（优雅退出不报错）。
        Windows 用 0.5s 轮询兜住「同步信号处理器唤不醒休眠的事件循环」。
        """

        stop_event = self._stop_event
        assert stop_event is not None
        while True:
            signalled = self._signal_flag.is_set() or stop_event.is_set()
            gateway_gone = gateway_task is not None and gateway_task.done()
            if signalled or gateway_gone:
                return signalled
            waiter = asyncio.ensure_future(stop_event.wait())
            waiters: tuple[asyncio.Future, ...] = (waiter,) if gateway_task is None else (waiter, gateway_task)
            try:
                await asyncio.wait(waiters, timeout=0.5, return_when=asyncio.FIRST_COMPLETED)
            except KeyboardInterrupt:  # pragma: no cover - 默认 SIGINT 处理器
                self._logger.info("[停止] 收到 Ctrl+C")
                return True
            finally:
                if not waiter.done():
                    waiter.cancel()


def monotonic() -> float:  # pragma: no cover - 供调试
    return time.monotonic()
