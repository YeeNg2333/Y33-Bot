"""Y33-Bot：Minecraft（Java Vanilla）与 QQ 群之间的双向消息互通服务。

模块边界、函数签名、CLI 契约以仓库根目录的 ``PLAN.md`` 为唯一技术依据；
需求来源为 ``IDEA.md``（需求冻结）。

骨架阶段（PLAN.md §6 T1）：本包各模块只提供签名与文档字符串，
未实现的函数体统一 ``raise NotImplementedError``，等 T2–T8 逐个填充。
入口例外：``y33bot.cli`` 的 ``--version`` / ``check`` 在骨架阶段即可运行（见 cli 模块文档）。
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
