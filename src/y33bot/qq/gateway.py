"""QQ 接入：网关协议与官方 SDK（qq-botpy）适配（PLAN.md §2.3 / §3.2 / A5 / A11 / A12 / R23）。

设计要点：
- `BotpyGateway` 把 SDK 回调翻译成 `MCGroupMessage`，交给注入的 handler，再把返回文本被动回复到群里；
- 被动回复 = 带 `msg_id` + `msg_seq=1`（5 分钟窗口）；主动消息 = 不带 `msg_id`，`msg_seq` 取持久化全局递增序号；
- 发送失败只记 `[错误]` 日志、不重试（N7 / A12）；
- `botpy` 采用惰性导入，缺依赖时 `run` 报明确错误，而 `check`/`simulate`/单测不需要它。
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ..models import MCGroupMessage, OutgoingGroupMessage

if TYPE_CHECKING:  # pragma: no cover - 仅类型标注
    from ..config import AppConfig
    from ..state import StateStore

__all__ = ["QQGateway", "BotpyGateway", "QQGatewayError", "MessageHandler", "normalize_content"]

logger = logging.getLogger("y33bot.qq.gateway")

_MENTION_RE = re.compile(r"^(?:<@!?\d+>\s*)+")

try:  # pragma: no cover - 取决于环境是否安装了 qq-botpy
    import botpy  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001 - 缺依赖不是致命错误，run 时才需要
    botpy = None  # type: ignore[assignment]


class QQGatewayError(RuntimeError):
    """QQ 网关不可用（缺少依赖、凭据错误、启动超时……）。"""


MessageHandler = Callable[[MCGroupMessage], Awaitable[str | None]]


def normalize_content(content: str) -> str:
    """防御性剥离开头的 `@机器人` 标记与空白（PLAN.md A5）。

    官方网关通常已去掉前缀，这里再兜一次，避免网关行为变化导致指令不识别。
    """

    return _MENTION_RE.sub("", content or "").strip()


@runtime_checkable
class QQGateway(Protocol):
    """QQ 侧收发接口；`BotpyGateway` 与 `FakeQQGateway` 都实现它。"""

    async def start(self) -> None:
        """启动网关（BotpyGateway 会等待登录完成，失败抛 `QQGatewayError`）。"""
        ...

    async def send_group_message(self, message: OutgoingGroupMessage) -> None:
        """发送一条群消息；`reply_to_message_id` 非空表示被动回复。"""
        ...

    async def close(self) -> None:
        """关闭网关（幂等）。"""
        ...

    async def wait_closed(self) -> None:
        """等待网关**自己**结束（正常返回或抛异常都算）。

        BUG-001：`Service.run()` 用它把「启动后网关任务结束」当成故障（`[错误]` + 非 0 退出），
        而不是默默常驻。实现必须可取消（优雅退出时会 cancel 这个等待），
        且**不能**在 `start()` 之前就返回。
        """
        ...


class BotpyGateway:
    """基于腾讯官方 SDK `qq-botpy` 的网关实现。"""

    def __init__(
        self,
        config: AppConfig,
        credentials: tuple[str, str],
        state: StateStore,
        handler: MessageHandler,
        *,
        startup_timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._app_id, self._app_secret = credentials
        self._state = state
        self._handler = handler
        self._startup_timeout = float(startup_timeout)
        self._logger = logger or logging.getLogger("y33bot.qq.gateway")
        self._client = None
        self._task: asyncio.Task[None] | None = None
        self._up_event: asyncio.Event | None = None
        self._up_error: BaseException | None = None

    # ------------------------------------------------------------------ 生命周期
    async def start(self) -> None:
        if botpy is None:
            raise QQGatewayError("qq-botpy 未安装：请执行 pip install qq-botpy==1.2.1")
        self._up_event = asyncio.Event()
        self._up_error = None
        self._client = self._build_client()
        self._task = asyncio.create_task(self._run_client(), name="y33bot-qq-gateway")
        try:
            await asyncio.wait_for(self._up_event.wait(), timeout=self._startup_timeout)
        except TimeoutError as exc:
            raise QQGatewayError(f"QQ 网关 {self._startup_timeout:g}s 内未就绪") from exc
        if self._up_error is not None:
            raise QQGatewayError(f"QQ 网关启动失败: {self._up_error}") from self._up_error

    def _build_client(self):
        gateway = self

        class _Client(botpy.Client):  # type: ignore[misc,name-defined]
            async def on_ready(self) -> None:
                gateway._logger.info("[启动] QQ 网关就绪")

            async def on_group_at_message_create(self, message) -> None:  # noqa: ANN001 - SDK 回调签名
                await gateway._on_group_at_message_create(message)

        intents = botpy.Intents(public_messages=True)
        # bot_log=None + ext_handlers=False：不写 botpy 自己的日志文件，统一走项目 logging（N5）
        return _Client(intents=intents, bot_log=None, ext_handlers=False)

    async def _run_client(self) -> None:
        client = self._client
        if client is None:  # pragma: no cover - start() 已保证
            return
        try:
            async with client as bot:
                coroutine = await bot.start(self._app_id, self._app_secret, ret_coro=True)
                self._logger.info("[启动] QQ 网关已连接")
                self._signal_up()
                if coroutine is not None:
                    await coroutine
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - SDK 内部异常必须留痕且不能拖垮服务
            self._logger.error("[错误] QQ 网关异常退出: %s", exc)
            self._signal_up(exc)

    def _signal_up(self, error: BaseException | None = None) -> None:
        if error is not None:
            self._up_error = error
        if self._up_event is not None and not self._up_event.is_set():
            self._up_event.set()

    async def close(self) -> None:
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        client = self._client
        self._client = None
        if client is not None:
            try:
                await client.close()
            except Exception as exc:  # noqa: BLE001 - 关闭失败只记日志
                self._logger.warning("[警告] 关闭 QQ 网关失败: %s", exc)

    async def wait_closed(self) -> None:
        """等待网关任务**自己**结束（BUG-001：`Service.run()` 用它检测「启动后网关失效」）。

        实现用 done-callback + `Event` 而不是直接 `await self._task`：等待方被取消（优雅退出）
        时不会把取消传导给网关任务本身；任务无论正常返回、抛异常还是被取消，都会唤醒等待方。
        """

        task = self._task
        if task is None:  # pragma: no cover - start() 成功之后才会有任务
            return
        ended = asyncio.Event()
        task.add_done_callback(lambda _task: ended.set())
        await ended.wait()

    # ------------------------------------------------------------------ 收
    async def _on_group_at_message_create(self, message) -> None:  # noqa: ANN001 - SDK 回调签名
        group_openid = str(getattr(message, "group_openid", None) or "")
        author = getattr(message, "author", None)
        member_openid = str(getattr(author, "member_openid", None) or "")
        message_id = str(getattr(message, "id", None) or "")
        content = normalize_content(str(getattr(message, "content", None) or ""))

        if not group_openid or not member_openid:
            self._logger.warning("[警告] 群消息缺少 group_openid/member_openid，已丢弃")
            return

        incoming = MCGroupMessage(
            group_openid=group_openid,
            member_openid=member_openid,
            message_id=message_id,
            content=content,
            received_at=time.time(),
        )
        reply: str | None = None
        try:
            reply = await self._handler(incoming)
        except Exception:  # noqa: BLE001 - 处理失败要留痕，且不阻塞后续事件
            self._logger.exception("[错误] 群消息处理失败")
        if not reply:
            return
        await self.send_group_message(
            OutgoingGroupMessage(
                group_openid=group_openid,
                text=reply,
                reply_to_message_id=message_id or None,
            )
        )

    # ------------------------------------------------------------------ 发
    async def send_group_message(self, message: OutgoingGroupMessage) -> None:
        """发送群消息；被动回复带 `msg_id`+`msg_seq=1`，主动消息用全局递增 `msg_seq`（A12）。"""

        client = self._client
        if client is None:
            raise QQGatewayError("QQ 网关未启动")
        group_openid = (message.group_openid or "").strip()
        text = message.text or ""
        if not group_openid or not text.strip():
            self._logger.warning("[警告] 群消息缺少 group_openid 或内容为空，已跳过")
            return

        if message.reply_to_message_id:
            msg_id: str | None = message.reply_to_message_id
            msg_seq = 1
        else:
            msg_id = None
            msg_seq = self._state.next_msg_seq()
            self._state.save()  # 主动消息序号必须落盘，避免重启后重复（A12）

        try:
            await client.api.post_group_message(
                group_openid=group_openid,
                msg_type=0,
                content=text,
                msg_id=msg_id,
                msg_seq=msg_seq,
            )
        except Exception as exc:  # noqa: BLE001 - 规格要求不重试（N7）
            self._logger.error("[错误] QQ 发送失败（不重试）: %s", exc)
        else:
            self._logger.info("[群消息] %s", text)
