"""组件装配、常驻任务与优雅退出（PLAN.md §3.2、§3.6；任务 T8）。

``Service`` 负责把各层接起来（三件套并发，单进程 asyncio）：

- QQ 网关：``qq.gateway.BotpyGateway.start()``，收到群消息 → ``Bridge.handle_group_message()``；
- 日志轮询：每个 MC 服一个 ``mclog.watcher.LogWatcher``，用 ``asyncio.to_thread()`` 调同步
  ``poll_new_events()``，再交给 ``Bridge.handle_log_event()``；
- 健康轮询：按 ``health_poll_interval`` 调 ``Bridge.poll_health()``。

启动与退出：``startup_checks()`` 在启动时逐项自检（CLI ``check`` 复用其输出契约），
``run()`` 常驻直到收到取消信号，``shutdown()`` 取消任务、关闭 RCON 与网关并落盘状态。

方法名来自 PLAN.md §3.2（``run`` / ``startup_checks`` / ``shutdown``）；构造与返回类型由 T8 定稿。
"""

from __future__ import annotations

from collections.abc import Mapping

from y33bot.config import AppConfig


class Service:
    """常驻服务的装配与生命周期门面。"""

    def __init__(self, config: AppConfig, *, env: Mapping[str, str] | None = None) -> None:
        """``env`` 缺省用 ``os.environ``（密钥只在装配时读取，不热重载）。"""
        raise NotImplementedError("T8：见 PLAN.md §3.2")

    async def startup_checks(self) -> list[str]:
        """逐项自检，返回「逐项结果行」（格式见 PLAN.md §3.4，CLI ``check`` 直接打印）。"""
        raise NotImplementedError("T8：见 PLAN.md §3.4 / §5 S1")

    async def run(self) -> None:
        """启动三个常驻任务并等待其结束（Ctrl+C 触发 ``shutdown()``）。"""
        raise NotImplementedError("T8：见 PLAN.md §3.2 / §2.7")

    async def shutdown(self) -> None:
        """优雅退出：取消任务、关闭 RCON/网关、落盘 ``state.json``（§2.6）。"""
        raise NotImplementedError("T8：见 PLAN.md §2.6 / §3.6")
