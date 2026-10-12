"""绑定表读写：``data/bindings.toml``（PLAN.md §4.2、§4.5；需求 R20–R23）。

语义要点（实现时的硬约束）：

- **覆盖语义**：同一 ``qq_openid`` 再次 ``bind()`` 即覆盖，等价于“解绑后再绑定”，
  不做二次确认（R20）。
- **与服务器无关**：一张全局表，所有 MC 服通用（R21）。
- **原子落盘**：临时文件 + ``os.replace()``，避免半截文件（§3.6）。
- **失败保护**：解析失败抛 ``BindingError`` 且**不覆盖**原文件（§4.5-5），保护人工数据。
- 身份来源是 ``member_openid``（非 QQ 号，R23）。

方法名来自 PLAN.md §3.2；参数与返回类型是实现细节，可由 T3 细化，方法名不得改。
"""

from __future__ import annotations

from pathlib import Path


class BindingError(Exception):
    """绑定表读取/解析/写入失败（不覆盖原文件）。"""


class BindingStore:
    """``data/bindings.toml`` 的读写门面（内存表 + 显式 ``save()``）。"""

    def __init__(self, path: Path) -> None:
        """``path`` 为绑定表文件路径；父目录不存在时由 ``save()`` 创建。"""
        raise NotImplementedError("T3：见 PLAN.md §4.2 / §4.5")

    def load(self) -> None:
        """从磁盘加载绑定表；文件不存在视为空表，解析失败抛 ``BindingError``。"""
        raise NotImplementedError("T3：见 PLAN.md §4.5-5")

    def lookup(self, qq_openid: str) -> str | None:
        """查 ``openid → game_id``；未绑定返回 ``None``（N9：仅绑定用户可转发）。"""
        raise NotImplementedError("T3：见 PLAN.md §4.2")

    def bind(self, qq_openid: str, game_id: str) -> None:
        """覆盖写入一条绑定（不落盘；由调用方或实现决定何时 ``save()``）。"""
        raise NotImplementedError("T3：见 PLAN.md §4.2 / R20")

    def unbind(self, qq_openid: str) -> bool:
        """删除一条绑定，返回是否确实删除了（规范不做解绑指令，仅供 CLI 使用）。"""
        raise NotImplementedError("T3：见 PLAN.md §4.2")

    def items(self) -> list[tuple[str, str]]:
        """返回全部 ``(qq_openid, game_id)``（顺序稳定，便于 diff 与打印）。"""
        raise NotImplementedError("T3：见 PLAN.md §4.2")

    def save(self) -> None:
        """原子写入 ``data/bindings.toml``（临时文件 + ``os.replace()``）。"""
        raise NotImplementedError("T3：见 PLAN.md §3.6")
