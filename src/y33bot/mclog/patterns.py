"""日志模板编译与单行解析（PLAN.md §2.5、§3.2、§4.1；需求 R27，假设 A9）。

规则：

- 模板来自 ``config.toml`` 的 ``[log_patterns]``：Vanilla 版本升级只改 TOML，不改代码（R27）。
- 编译时若模板未自带 ``^``/``$`` 则自动补锚点，匹配统一用 ``re.match``（A9）——
  原模板没有行尾锚点，不补会误匹配到别的行。
- 命名组校验：``join``/``quit`` 必须含 ``player``；``chat`` 必须含 ``player`` 与 ``message``
  否则视为配置错误（启动即失败）。
- ``parse_line()`` 逐个模板尝试，命中即返回；都不命中返回 ``None``。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from y33bot.config import LogPatterns
from y33bot.models import MCLogEvent


@dataclass(frozen=True)
class CompiledPatterns:
    """编译后的三条正则（模板补锚点后的产物）。

    说明：``LogPatterns`` 只给出正则文本，``re.Pattern`` 才是可执行形态，
    因此这里需要一层编译结果；``parse_line()`` 的参数类型即本类（T5 可细化字段）。
    """

    join: re.Pattern[str]
    quit: re.Pattern[str]
    chat: re.Pattern[str]
    encoding: str = "utf-8"


def compile_patterns(patterns: LogPatterns) -> CompiledPatterns:
    """编译并校验三条模板；模板非法或缺命名组时抛 ``ValueError``（启动即失败）。"""
    raise NotImplementedError("T5：见 PLAN.md §2.5 / A9")


def parse_line(
    compiled: CompiledPatterns,
    line: str,
    *,
    server: str = "",
    occurred_at: float | None = None,
) -> MCLogEvent | None:
    """把一行日志解析成 ``MCLogEvent``；不命中任何模板返回 ``None``。

    ``server`` / ``occurred_at`` 由 ``LogWatcher`` 传入：PLAN.md §3.2 只给了 ``(cp, line)``，
    而 ``MCLogEvent`` 需要来源服与时间戳，故这两个参数以关键字形式补齐。
    """
    raise NotImplementedError("T5：见 PLAN.md §2.5")
