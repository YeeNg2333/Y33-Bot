"""QQ 凭据可用性探活（BUG-001 的 R5 / PLAN.md §3.4）。

`check` 的 QQ 项不再只判「环境变量非空」：这里真向平台取一次 `access_token`
（`POST https://bots.qq.com/app/getAppAccessToken`），把「变量填了」升级成「凭据可用」。

分层是为了让 CI 保持完全离线：

- `_post_token()` 是**唯一**发网络请求的函数，测试一律 monkeypatch 它（或直接替换 `probe_access_token`）；
- `parse_token()` 是纯函数，可离线断言解析与报错文案（缺 `access_token`、`expires_in` 类型不对……）。

刻意不依赖 `qq-botpy` 的 `Token`：那条路径需要 `aiohttp` 会话与 SDK 客户端实例，
在「只做一次自检」的 CLI 里既重又难替换；一个 POST + 纯函数解析足够表达「凭据可用」。
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request

__all__ = ["DEFAULT_TIMEOUT", "TOKEN_URL", "QQProbeError", "parse_token", "probe_access_token"]

#: 平台取 token 的地址（官方文档：`POST /app/getAppAccessToken`，body 为 appId + clientSecret）
TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"

DEFAULT_TIMEOUT = 5.0

#: 唯一的请求发出者：**显式不带代理**。
#:
#: 不用 `urllib.request.urlopen()` 的默认 opener，是因为它会继承系统代理（Windows 上还会读注册表）：
#: 本机实测系统代理 `127.0.0.1:7897` 不运行时，经它取 token 会 `SSL: UNEXPECTED_EOF_WHILE_READING`，
#: 而 `bots.qq.com` 直连可用 —— 那样会把「本机代理没开」误报成「凭据不可用」，
#: 恰好破坏探活存在的意义（区分凭据/配置问题与平台抖动）。
#: 因此这里固定不带代理，让探活结果只反映「凭据 + 平台」本身。
#: 单测一律替换这个对象（见 `tests/test_qq_probe.py`），CI 保持完全离线。
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class QQProbeError(RuntimeError):
    """探活失败：凭据无效、平台报错、网络不可达、响应不是预期 JSON……"""


def parse_token(payload: object) -> int:
    """从平台响应里取 `expires_in`（秒）；缺字段或平台报错一律 `QQProbeError`。"""

    if not isinstance(payload, dict):
        raise QQProbeError(f"响应不是 JSON 对象: {payload!r}")
    token = payload.get("access_token")
    if not token:
        code = payload.get("code", "-")
        message = payload.get("message") or payload.get("msg") or payload
        raise QQProbeError(f"平台返回错误: code={code} message={message}")
    raw_expires = payload.get("expires_in")
    if isinstance(raw_expires, bool) or not isinstance(raw_expires, (int, str)):
        raise QQProbeError(f"响应缺少有效的 expires_in: {payload!r}")
    try:
        return int(raw_expires)
    except ValueError:
        raise QQProbeError(f"响应缺少有效的 expires_in: {payload!r}") from None


def _post_token(app_id: str, app_secret: str, timeout: float) -> object:
    """取一次 access_token 的原始响应（**唯一的网络出口**；测试 monkeypatch 这个函数）。"""

    body = json.dumps({"appId": app_id, "clientSecret": app_secret}).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:  # 平台用 HTTP 状态码表达错误时会走这里
        detail = exc.read().decode("utf-8", "replace")
        raise QQProbeError(f"HTTP {exc.code} {exc.reason}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:  # 域名解析失败 / 超时 / 断网
        raise QQProbeError(f"无法连接 {TOKEN_URL}: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise QQProbeError(f"响应不是合法 JSON: {raw}") from exc


async def probe_access_token(app_id: str, app_secret: str, *, timeout: float = DEFAULT_TIMEOUT) -> int:
    """真取一次 `access_token`：成功返回有效期（秒），失败抛 `QQProbeError`。"""

    payload = await asyncio.to_thread(_post_token, app_id, app_secret, timeout)
    return parse_token(payload)
