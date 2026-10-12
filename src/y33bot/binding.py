"""绑定表读写：OpenID ↔ 游戏ID 一对一，TOML 持久化（PLAN.md §3.2 / §4.2 / R20-R23 / §4.5.5）。"""

from __future__ import annotations

import logging
import os
import re
import tomllib
from collections.abc import Mapping
from pathlib import Path

import tomli_w

logger = logging.getLogger("y33bot.binding")

__all__ = ["BindingError", "BindingStore", "GAME_ID_PATTERN", "is_valid_game_id"]

#: MC Java 版用户名规则（PLAN.md A2 / §4.5.3）
GAME_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,16}$")


class BindingError(Exception):
    """绑定表缺失、损坏或写入内容不合法。

    读到损坏的绑定表时**不覆盖**原文件，保护人工数据（PLAN.md §4.5.5）。
    """


def is_valid_game_id(value: str) -> bool:
    return isinstance(value, str) and GAME_ID_PATTERN.match(value) is not None


class BindingStore:
    """`data/bindings.toml` 的内存视图 + 原子落盘。"""

    def __init__(self, path: Path, bindings: Mapping[str, str] | None = None) -> None:
        self.path = Path(path)
        self._bindings: dict[str, str] = dict(bindings or {})

    # ------------------------------------------------------------------ 读
    @classmethod
    def load(cls, path: Path) -> BindingStore:
        """加载绑定表；文件不存在返回空表，内容非法抛 `BindingError`。"""

        p = Path(path)
        if not p.exists():
            return cls(p)
        try:
            raw = tomllib.loads(p.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise BindingError(f"绑定表不是合法 TOML（未覆盖原文件）: {p}: {exc}") from exc
        except OSError as exc:
            raise BindingError(f"绑定表读取失败: {p}: {exc}") from exc

        entries = raw.get("bindings", [])
        if not isinstance(entries, list):
            raise BindingError(f"绑定表格式错误: {p} 的 bindings 必须是数组")
        bindings: dict[str, str] = {}
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                raise BindingError(f"绑定表第 {index} 条必须是表（table）: {p}")
            openid = entry.get("qq_openid")
            game_id = entry.get("game_id")
            if not isinstance(openid, str) or not openid.strip():
                raise BindingError(f"绑定表第 {index} 条缺少 qq_openid: {p}")
            if not isinstance(game_id, str) or not game_id.strip():
                raise BindingError(f"绑定表第 {index} 条缺少 game_id: {p}")
            bindings[openid.strip()] = game_id.strip()
        return cls(p, bindings)

    # ------------------------------------------------------------------ 用
    def lookup(self, qq_openid: str) -> str | None:
        """按 OpenID 查游戏ID；未绑定返回 None（PLAN.md R9 / N9）。"""

        return self._bindings.get(qq_openid)

    def bind(self, qq_openid: str, game_id: str) -> None:
        """写入一条绑定；同 OpenID 覆盖旧值，等价于「解绑后重新绑定」（R20）。"""

        openid = (qq_openid or "").strip()
        gid = (game_id or "").strip()
        if not openid:
            raise BindingError("qq_openid 不能为空")
        if not is_valid_game_id(gid):
            raise BindingError(f"游戏ID 不合法: {game_id!r}")
        self._bindings[openid] = gid

    def unbind(self, qq_openid: str) -> bool:
        """删除一条绑定；返回是否真的删掉了。"""

        return self._bindings.pop(qq_openid, None) is not None

    def items(self) -> dict[str, str]:
        """返回按 OpenID 排序的副本。"""

        return dict(sorted(self._bindings.items()))

    def __len__(self) -> int:
        return len(self._bindings)

    def __contains__(self, qq_openid: object) -> bool:
        return qq_openid in self._bindings

    # ------------------------------------------------------------------ 写
    def save(self) -> None:
        """原子落盘（临时文件 + os.replace）。"""

        data = {"bindings": [{"qq_openid": openid, "game_id": gid} for openid, gid in sorted(self._bindings.items())]}
        try:
            text = tomli_w.dumps(data)
        except (TypeError, ValueError) as exc:  # pragma: no cover - 纯防御
            raise BindingError(f"绑定表序列化失败: {exc}") from exc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.path)
        logger.debug("[绑定] 已落盘 %s（%d 条）", self.path, len(self._bindings))
