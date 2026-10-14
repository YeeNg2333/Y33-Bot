"""`qq.probe` 测试：凭据探活的解析与失败文案（BUG-001 的 R5 / PLAN.md §3.4）。

全程离线：真正的网络出口只有 `probe._post_token()`，这里一律 monkeypatch 掉它，
只验证「平台回什么 → 我们怎么说」这层语义。
"""

from __future__ import annotations

import asyncio

import pytest

from y33bot.qq import probe as probe_module
from y33bot.qq.probe import TOKEN_URL, QQProbeError, parse_token, probe_access_token


# ------------------------------------------------------------------ 解析（纯函数）
def test_parse_token_returns_expires_in() -> None:
    assert parse_token({"access_token": "abc", "expires_in": "7200"}) == 7200
    assert parse_token({"access_token": "abc", "expires_in": 7200}) == 7200


@pytest.mark.parametrize(
    "payload",
    [
        {"code": 100007, "message": "appid or secret is invalid"},  # 凭据无效
        {"access_token": "", "expires_in": "7200"},  # token 为空
        {"access_token": "abc"},  # 缺 expires_in
        {"access_token": "abc", "expires_in": None},
        {"access_token": "abc", "expires_in": "两小时"},
        ["not", "a", "dict"],
        "boom",
    ],
)
def test_parse_token_rejects_bad_payload(payload: object) -> None:
    with pytest.raises(QQProbeError):
        parse_token(payload)


# ------------------------------------------------------------------ 真探活（网络出口被替换）
async def test_probe_access_token_posts_credentials_and_returns_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, float]] = []

    def fake_post(app_id: str, app_secret: str, timeout: float) -> object:
        calls.append((app_id, app_secret, timeout))
        return {"access_token": "tok", "expires_in": "7200"}

    monkeypatch.setattr(probe_module, "_post_token", fake_post)
    assert await probe_access_token("app-id", "secret", timeout=1.5) == 7200
    assert calls == [("app-id", "secret", 1.5)]


async def test_probe_access_token_surfaces_platform_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(_app_id: str, _app_secret: str, _timeout: float) -> object:
        return {"code": 100007, "message": "appid or secret is invalid"}

    monkeypatch.setattr(probe_module, "_post_token", fake_post)
    with pytest.raises(QQProbeError) as excinfo:
        await probe_access_token("app-id", "bad-secret")
    assert "code=100007" in str(excinfo.value)
    assert "appid or secret is invalid" in str(excinfo.value)


async def test_probe_access_token_uses_http_post_to_token_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_post_token()` 的真实现：POST 到平台地址，body 是 appId + clientSecret（不发真请求）。"""

    captured: dict[str, object] = {}

    class StubResponse:
        def __enter__(self) -> StubResponse:
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def read(self) -> bytes:
            return b'{"access_token": "tok", "expires_in": "7200"}'

    def fake_urlopen(request, timeout=None):  # noqa: ANN001 - 与 urllib 同签名
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = request.data
        captured["timeout"] = timeout
        return StubResponse()

    monkeypatch.setattr(probe_module.urllib.request, "urlopen", fake_urlopen)
    payload = probe_module._post_token("app-id", "secret", 2.0)

    assert captured["url"] == TOKEN_URL
    assert captured["method"] == "POST"
    assert captured["body"] == b'{"appId": "app-id", "clientSecret": "secret"}'
    assert captured["timeout"] == 2.0
    assert payload == {"access_token": "tok", "expires_in": "7200"}


async def test_post_token_wraps_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    def fake_urlopen(request, timeout=None):  # noqa: ANN001 - 与 urllib 同签名
        raise urllib.error.URLError("getaddrinfo failed")

    monkeypatch.setattr(probe_module.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(QQProbeError, match="无法连接"):
        await asyncio.to_thread(probe_module._post_token, "app-id", "secret", 1.0)


async def test_post_token_wraps_http_error_body(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    class StubHTTPError(urllib.error.HTTPError):
        def __init__(self) -> None:
            super().__init__(TOKEN_URL, 403, "Forbidden", {}, None)  # type: ignore[arg-type]

        def read(self) -> bytes:  # type: ignore[override]
            return b'{"code": 100007, "message": "appid or secret is invalid"}'

    def fake_urlopen(request, timeout=None):  # noqa: ANN001 - 与 urllib 同签名
        raise StubHTTPError()

    monkeypatch.setattr(probe_module.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(QQProbeError) as excinfo:
        await asyncio.to_thread(probe_module._post_token, "app-id", "secret", 1.0)
    assert "HTTP 403" in str(excinfo.value)
    assert "appid or secret is invalid" in str(excinfo.value)


async def test_post_token_wraps_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubResponse:
        def __enter__(self) -> StubResponse:
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def read(self) -> bytes:
            return b"<html>502 Bad Gateway</html>"

    monkeypatch.setattr(probe_module.urllib.request, "urlopen", lambda *_a, **_k: StubResponse())
    with pytest.raises(QQProbeError, match="不是合法 JSON"):
        await asyncio.to_thread(probe_module._post_token, "app-id", "secret", 1.0)
