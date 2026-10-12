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
from .mclog.watcher import LogWatcher
from .models import MCGroupMessage
from .qq.gateway import BotpyGateway, QQGateway, QQGatewayError
from .rcon.pool import LIST_COMMAND, RconPool
from .state import StateStore

if TYPE_CHECKING:  # pragma: no cover - 仅类型标注
    from collections.abc import Mapping

__all__ = ["CheckResult", "Service"]

logger = logging.getLogger("y33bot.service")


@dataclass(frozen=True)
class CheckResult:
    """`check` 子命令的一行结果（PLAN.md §3.4）。"""

    label: str
    ok: bool
    detail: str


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
    ) -> None:
        self._config = config
        self._env: dict[str, str] = dict(env if env is not None else os.environ)
        self._config_path = Path(config_path) if config_path is not None else None
        self._logger = logger or logging.getLogger("y33bot.service")
        self._gateway = gateway
        self._pool = pool

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

        # ---- QQ 凭据
        try:
            config.app_credentials(self._env)
        except ConfigError as exc:
            results.append(CheckResult("QQ", False, str(exc)))
        else:
            group = "group_openid 已配置" if config.qq.mc_to_qq_enabled else "group_openid 未配置（MC→QQ 方向禁用）"
            results.append(CheckResult("QQ", True, f"app_id 已设置 (env {config.qq.app_id_env})，{group}"))

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

        # ---- 日志文件
        state_store = StateStore.load(config.state_path)
        for server in config.servers:
            path = Path(server.log_path)
            saved = state_store.state.servers.get(server.name)
            offset = int(saved.log_offset) if saved is not None else 0
            if not path.exists():
                results.append(CheckResult(f"日志 {server.name}", False, f"{path} 不存在（启动后会持续重试）"))
                continue
            try:
                with path.open("rb") as handle:
                    handle.read(1)
            except OSError as exc:
                results.append(CheckResult(f"日志 {server.name}", False, f"{path} 不可读: {exc}"))
            else:
                results.append(CheckResult(f"日志 {server.name}", True, f"{path} 可读，偏移 {offset} 字节"))

        # ---- 绑定表
        try:
            store = BindingStore.load(config.bindings_path)
        except BindingError as exc:
            results.append(CheckResult("绑定", False, str(exc)))
        else:
            results.append(CheckResult("绑定", True, f"{len(store)} 条"))

        return results

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
        try:
            await self._wait_for_stop()
        finally:
            for task in (log_task, health_task):
                task.cancel()
            await asyncio.gather(log_task, health_task, return_exceptions=True)
            await self.shutdown()
        return 0

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

    async def _wait_for_stop(self) -> None:
        """等待退出信号；Windows 用 0.5s 轮询兜住「同步信号处理器唤不醒休眠的事件循环」。"""

        stop_event = self._stop_event
        assert stop_event is not None
        while True:
            if self._signal_flag.is_set() or stop_event.is_set():
                return
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.5)
                return
            except TimeoutError:
                continue
            except KeyboardInterrupt:  # pragma: no cover - 默认 SIGINT 处理器
                self._logger.info("[停止] 收到 Ctrl+C")
                return


def monotonic() -> float:  # pragma: no cover - 供调试
    return time.monotonic()
