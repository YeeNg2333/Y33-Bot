"""RCON 层：协议接口、自研异步客户端、多服编排与离线替身（PLAN.md §2.4、§3.2）。

只暴露 ``RconTransport`` 这一层抽象：真实实现 ``AsyncRconClient`` 与测试替身
``FakeRconTransport`` 可互换（A13：不使用第三方 RCON 库）。
"""

from __future__ import annotations
