"""指令层：装饰器式注册框架与内置指令（PLAN.md §3.3；需求 R13、R14、R16、R17，假设 A2/A3）。

设计要点：

- **注册**：``@registry.register("status", aliases=[], desc="查询服务器状态")``，名称唯一，
  别名与小写名都可命中（R13）；
- **分发**：``dispatch(ctx, line)`` 接收带前缀的整行（如 ``/status 1``），剥前缀 + 切参数后
  找 handler；未注册指令返回固定文案 ``未知指令``（A3、R17）；
- **错误文案**：``/bind`` 缺参数回 ``用法: /bind <游戏ID>``，ID 不合法回 ``游戏ID 不合法``（A2）；
- 本层不碰 TOML 与 RCON 细节，只通过 ``CommandContext`` 拿绑定表 / RCON 池 / 状态。
"""

from __future__ import annotations
