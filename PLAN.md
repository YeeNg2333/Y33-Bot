# Y33-Bot 实施计划（PLAN.md）

**来源**：`IDEA.md` v1.0（需求冻结，2026-10-13 全文逐条抽取）
**目标读者**：实现者 / 测试者 / 文档编写者（对应看板卡 `t_8442a7d5`、`t_68925b93`、`t_7b86eb6b`、`t_bcf892eb`）
**效力**：本文档是唯一技术依据。模块边界、函数签名、CLI 契约、配置结构、数据文件结构、验收场景均已在此定稿，实现任务不得自行改设计；如确有必要偏离，必须在提交信息中写明并同步修改本文件。

---

## 0. 假设清单

IDEA.md 未定义或存在歧义之处，本计划采用以下假设。**每条假设都有唯一实现载体，且被至少一个验收场景或单元测试覆盖**；下游任务不得再自行解释。

| # | 假设 / 决策 | 理由 | 落地位置 |
|---|---|---|---|
| A1 | `/status` 多服输出：单服时严格按 IDEA §3.5 的三行格式；多服时逐服一行 + `总计: N 人在线`；全部离线时输出 `[服务器状态] 服务器离线` | IDEA §3.5 只给了单服格式，§3.8 又要求多服对一群，需要补齐多服渲染 | `bridge.format_status()`，S5-4 |
| A2 | `/bind` 缺参数回复 `用法: /bind <游戏ID>`；游戏 ID 不满足 `^[A-Za-z0-9_]{3,16}$` 回复 `游戏ID 不合法` | 规范未定义错误文案；ID 规则取自 MC Java 版用户名规则 | `commands.builtin.cmd_bind()`，S5-5，`test_commands.py` |
| A3 | 未注册指令的回复文本固定为 `未知指令`（不加标点、不附帮助） | IDEA §3.4 原文「回复"未知指令"」 | `CommandRegistry.dispatch()`，S5-6 |
| A4 | 进出通知文本为 `{玩家名}进入了{服名}` / `{玩家名}退出了{服名}`，服名取 `[[mc_servers]].name`，不加 `【】` | v0.2 真机反馈（`需求1.txt` 53–55 行）：一群对多服时必须能分辨来源；同时修正 `需求1.txt` B7 的"不加服名"、IDEA §3.3/§3.8（偏离记录见 §7） | `bridge.handle_log_event()`，S4 |
| A5 | 群消息的 `@机器人` 前缀去掉由官方网关保证；服务内仍做一次防御性剥离（去掉开头的 `<@!...>` 或空白） | IDEA §3.2 注明 content 已去前缀，防御性处理避免网关行为变化导致指令不识别 | `qq.gateway._normalize_content()`，`test_bridge.py` |
| A6 | 富媒体标记（形如 `<...>`）在转发前剔除；剔除后为空则整条不转发、不回复 | IDEA §4「只提取文字部分，忽略图片/附件」 | `bridge._extract_text()`，S2，`test_bridge.py` |
| A7 | 换行处理：取第一个 `\n` 之前的部分，再按 `max_line_length`（默认 200 字符）截断，被截断时末尾补 `…`（省略号计入 200） | IDEA §4「换行处截断，仅显示单行」，未给长度上限；RCON 单条命令有 1446 字节硬上限 | `bridge._single_line()`，S2，`test_bridge.py` |
| A8 | 回环防护：游戏内聊天若以服务注入标记开头则忽略（配置项 `ignored_chat_prefixes` 可覆盖）；v0.2 起服务只注入 `[QQ]` 一个标记，默认值即 `["[QQ]"]`，且该判断先于 `#` 判断 | IDEA §4「回环过滤：待测试，若触发再处理」——注入标记一旦落回日志即构成回环；`[→QQ]` 随游戏内回显一起取消（§7） | `bridge.handle_log_event()`，S3，`test_bridge.py` |
| A9 | `[log_patterns]` 模板编译时自动补 `^` / `$`（若模板未自带），匹配用 `re.match` | IDEA 原模板无锚点，`re.match` 只能锚定行首，行尾不锚定会误匹配 | `mclog.patterns.compile_patterns()`，`test_mclog_patterns.py` |
| A10 | 日志轮转只按规范规则处理：`当前大小 < 持久化偏移` → 偏移重置为 0 并重读；同时把 `st_ino`/`st_size` 写入日志便于人工排查，不引入其它策略 | IDEA §3.7 明确「检测文件大小 < 偏移量时重置为 0」 | `mclog.watcher.LogWatcher.poll_new_events()`，S6 |
| A11 | MC→QQ 主动消息必须有目标群：`[qq] group_openid` 为必填才能启用该方向；缺失时该方向禁用并打印告警，服务仍正常启动 | 官方 `post_group_message` 需要 `group_openid`；IDEA §3.3 未提目标群来源 | `config.load_config()`、`service.Service.run()`，`test_config.py` |
| A12 | QQ 主动消息失败不重试（规格「重试：不重试」），仅记 `logging` 日志；主动消息的 `msg_seq` 全局递增并持久化到 `state.json` | 官方约束：相同 `msg_id + msg_seq` 重复发送失败；主动消息有频控 | `qq.gateway.BotpyGateway.send_group_message()`，`state.StateStore`，`test_state.py` |
| A13 | RCON 采用**自研 async 客户端**（仅标准库 asyncio，约 150 行），不使用第三方 RCON 库 | 见 §2.8 的核验证据：`mcnexus` 的官方仓库/文档站均 404（2026-10-13 核验）；`aio-mc-rcon` 3.5.0 源码只读一个响应包、无并发锁，不满足规格「支持多包响应」 | `rcon/client.py`，`test_rcon_client.py` |
| A14 | RCON 断连后**不自动重发**当前命令，仅在下一次调用时自动重连 | 规格要求「自动重连」但不要求重发；重发聊天消息会重复注入，副作用大于收益 | `rcon/client.py`，`test_rcon_client.py` |
| A15 | TPS 不做（规范已确认 Vanilla 无 `/tps`），`/status` 字段只有在线人数与在线玩家 | IDEA §3.5 与 §6 | `commands.builtin.cmd_status()`，S5-4 |
| A16 | 不引入数据库/缓存：绑定用 TOML、运行状态用 JSON、配置用 TOML | IDEA §3.6/§3.7/§4 | `binding.py`、`state.py`、`config.py` |
| A17 | 不做热重载、敏感词、黑名单、频率限制、解绑确认、图片处理、权限审批、后期功能预留结构 | IDEA §4 与 §5 全部为负向项 | 见 §1.4 |
| A18 | 环境变量命名约定：`QQ_BOT_APP_ID`、`QQ_BOT_APP_SECRET`、`MC_RCON_PASSWORD_<SERVER_NAME 大写>`（回退 `MC_RCON_PASSWORD`） | IDEA 只写「走环境变量」，需要具体名字才能写文档与 CI | `config.AppConfig.secrets`，S1，`.env.example` |
| A19 | 目标解释器 Python ≥3.11（`tomllib`），本机开发用 `python3`(3.12.10) 与 CI 一致；上限 `<3.14`（依赖 wheel 在 3.14 覆盖存疑） | IDEA §4 要求 Python、跨平台；本机 `python3`=3.12.10、`python`=3.14.7 | `pyproject.toml`、`.github/workflows/ci.yml` |
| A20 | 日志按 UTF-8 读取、`errors="replace"`；未以换行结尾的残行留在缓冲区，等下次轮询凑齐后再解析 | Vanilla 日志为 UTF-8；避免单条坏字节或半行攻击打挂轮询 | `mclog.watcher.LogWatcher`，`test_mclog_watcher.py` |

---

## 1. 需求映射表

### 1.1 功能需求（IDEA §3）

| 需求 | 出处 | 摘要 | 实现载体（模块 / 函数） | 验收 |
|---|---|---|---|---|
| R1 | §3.1 | QQ→MC 转发：`@机器人` + `#` 开头 | `bridge.Bridge.handle_group_message()` | S2 |
| R2 | §3.1 | QQ→MC 指令：`@机器人` + `/` 开头 | `commands.registry.CommandRegistry.dispatch()` | S5-4/5/6 |
| R3 | §3.1 | MC→QQ 转发：游戏内聊天以 `#` 开头 | `bridge.Bridge.handle_log_event()` | S3 |
| R4 | §3.1 | MC→QQ 进出通知 | `bridge.Bridge.handle_log_event()` | S4 |
| R5 | §3.1 | 其它情况一律忽略，不互通 | `bridge.Bridge.handle_group_message()` / `handle_log_event()`（返回 None） | S3 |
| R6 | §3.2 | 分流：`/` 走指令、`#` 走聊天，互不干扰 | `bridge.Bridge.handle_group_message()` | S2 + S5-4 |
| R7 | §3.2 | 未绑定发送 `#` 消息 → 回复 `请先使用 /bind <游戏ID> 绑定` | `bridge.Bridge.handle_group_message()` | S2 |
| R8 | §3.2 | 转发格式 `[QQ] Steve: 你好` | `bridge.Bridge._format_to_mc()` | S2 |
| R9 | §3.2 | 忽略图片/附件、换行截断为单行 | `bridge.Bridge._extract_text()` / `_single_line()` | S2（A6/A7） |
| R10 | §3.3 | 进服 → 群内 `Steve进入了main`；退服 → `Steve退出了main`（服名来自 `[[mc_servers]].name`，A4/§7） | `bridge.Bridge.handle_log_event()` | S4 |
| R11 | §3.3 | 游戏内 `#` 聊天 → 群内 `Steve@main: 你好`（去 `#`，前缀为来源服名）；**不再**往游戏内回显（§7） | `bridge.Bridge.handle_log_event()` | S3 |
| R12 | §3.3 | 非 `#` 聊天不转发 | `bridge.Bridge.handle_log_event()` | S3 |
| R13 | §3.4 | 装饰器式指令注册框架（名称/别名/描述） | `commands.registry.CommandRegistry.register()` | `test_commands.py` |
| R14 | §3.4 | 触发格式 `/status`（无空格） | `commands.registry.CommandRegistry.dispatch()` | S5-4 |
| R15 | §3.4 | `/status`：在线人数 + 在线玩家（来自 RCON `/list`） | `commands.builtin.cmd_status()`、`rcon.pool.parse_list_response()` | S5-4 |
| R16 | §3.4 | `/bind <游戏ID>`：写 TOML | `commands.builtin.cmd_bind()`、`binding.BindingStore.bind()` | S5-5 |
| R17 | §3.4 | 未注册指令 → `未知指令` | `CommandRegistry.dispatch()` | S5-6 |
| R18 | §3.5 | `/status` 返回格式（三行）+ 离线格式 | `bridge.Bridge.format_status()` | S5-4 |
| R19 | §3.5 | 离线提示：状态**变化**时提示一次 | `bridge.Bridge.poll_health()` + `state.StateStore` | S4-健康翻转 |
| R20 | §3.6 | 一对一绑定，覆盖写入，无解绑确认 | `binding.BindingStore.bind()` | S5-5 |
| R21 | §3.6 | 绑定跨所有 MC 服通用 | `binding.BindingStore`（与服务器无关的全局表） | S2 |
| R22 | §3.6 | 绑定以 TOML 持久化（`[[bindings]] qq_openid/game_id`） | `binding.BindingStore.save()` | S2 |
| R23 | §3.6 | `OpenID` 取事件中的 `member_openid`，不是 QQ 号 | `qq.gateway.MCGroupMessage.member_openid` | S5-5 |
| R24 | §3.7 | 日志按**字节偏移**增量读取并持久化 | `mclog.watcher.LogWatcher` + `state.StateStore` | S6 |
| R25 | §3.7 | 日志轮转：大小 < 偏移 → 重置为 0 重读 | `mclog.watcher.LogWatcher.poll_new_events()` | S6 |
| R26 | §3.7 | 进程重启加载持久化偏移；文件大小 < 偏移则从 0 开始 | `state.StateStore.load()` + `LogWatcher` | S6 |
| R27 | §3.7 | 日志格式模板化（TOML 可改，不改代码） | `mclog.patterns.compile_patterns()` + `config.LogPatterns` | `test_mclog_patterns.py` |
| R28 | §3.8 | MC→QQ 都发到同一个群，但消息文案带来源服名以便区分（v0.2：§7 记录了对「不区分来源服」的偏离） | `bridge.Bridge.handle_log_event()` | S3/S4 |
| R29 | §3.8 | QQ→MC 全局广播到所有 RCON 连接的 MC 服 | `rcon.pool.RconPool.broadcast_tellraw()` | S2 |

### 1.2 非功能需求（IDEA §4）

| 需求 | 摘要 | 实现 / 保障 | 验收 |
|---|---|---|---|
| N1 | 语言 Python | `pyproject.toml` `requires-python = ">=3.11,<3.14"` | S1 |
| N2 | 独立服务端进程、跨平台、不干预 MC 实例 | `y33bot run` 单进程、不与 MC 同目录、只经 RCON + 只读日志 | S5 |
| N3 | 配置 TOML；AppID/Secret 走环境变量 | `config.py` + `.env.example`（仓内不存密钥） | S1 + CI 无密钥检查 |
| N4 | 不需要热重载 | 不做配置监听（`config.load_config()` 仅启动时调用一次） | 代码评审项 |
| N5 | 日志用标准库 `logging` | 全项目统一 `logging.getLogger("y33bot.<模块>")`，`run` 打印到 stderr | S1/S3 |
| N6 | 无延迟要求 | 轮询间隔可配（默认日志 0.5s、健康 30s），不做低延迟优化 | `config.Behavior` |
| N7 | 不重试 | QQ 发送、RCON 注入失败只记日志；不引入重试框架 | S5-7/A12/A14 |
| N8 | 无敏感词/黑名单/频率限制 | 不做（A17） | §1.4 |
| N9 | 权限 = 指定 QQID-游戏ID 绑定 | 仅绑定用户能转发（`BindingStore.lookup()`） | S2 |
| N10 | 仅文字/Emoji | `msg_type=0`；`_extract_text()` 保留 Emoji、剔除 `<...>` 标记 | S2 |
| N11 | 只提取文字、忽略图片/附件 | A6 | S2 |
| N12 | 换行截断为单行 | A7 | S2 |
| N13 | 回环过滤 | A8（默认忽略 `[QQ]` 前缀聊天，`ignored_chat_prefixes` 可覆盖） | S3 |
| N14 | 后期功能不预留数据结构 | 不引入插件接口、不引入投票/热重载相关字段 | §1.4 |

### 1.3 技术调研结论落地（IDEA §6）

| 结论 | 落地 |
|---|---|
| RCON 库：推荐 `mcnexus`，备选 `aio-mc-rcon` | **两者均不采用**，改为自研（证据见 §2.8），统一挂在 `rcon.protocol.RconTransport` 接口下，日后可无痛替换 |
| QQ Bot：被动回复 5 分钟窗口、主动消息有频控 | 被动回复带 `msg_id`+`msg_seq=1`；主动消息 `msg_seq` 递增（A12） |
| Vanilla 无 `/tps` | `/status` 不含 TPS（A15） |
| 日志轮转：字节偏移 + 缩小即重置 | `LogWatcher`（A10） |
| OpenID 非 QQ 号、跨应用不通用、必须从事件提取 | `MCGroupMessage.member_openid` 是唯一身份来源（R23） |

### 1.4 明确不做（IDEA §5 后期规划 + §4 负向项）

| 项 | 处理 | 说明 |
|---|---|---|
| 投票重启服务器 | 不做，不预留 | 只记录在 IDEA §5 |
| 插件式通信 | 不做，不预留接口 | 抽象仅止于 `RconTransport`，不引入插件加载器 |
| 热重载配置 | 不做 | 改配置需重启进程 |
| 自定义触发字符 | 不做（`/` 与 `#` 写在配置里但仅作常量读取，不做多字符扩展） | `QQConfig.command_prefix/chat_prefix` |
| 解绑/二次确认 | 不做，`/bind` 覆盖即解绑 | R20 |
| TPS | 不做 | A15 |
| 权限审批、敏感词、黑名单、频率限制 | 不做 | N8 |
| 图片/附件处理 | 不做（剔除标记即忽略） | N11 |

---

## 2. 技术选型

### 2.1 语言与运行时

| 项 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.11+（开发/CI 固定 3.12） | IDEA 冻结 Python；`tomllib` 自 3.11 起为标准库，读 TOML 零依赖；本机 `python3`=3.12.10 |
| 上限 | `<3.14` | 本机另有 3.14.7，但 `aiohttp`/`APScheduler` 在 3.14 的 wheel 覆盖不稳定，写死上限可避免“安装期才炸” |
| 并发模型 | 单进程 `asyncio` + 三个常驻任务（QQ 网关、日志轮询、健康轮询） | 每台 MC 服的日志文件必须用一个字节偏移串行推进，单事件循环最省事；规格明确「独立服务端进程」 |
| 包管理 | `pyproject.toml`（setuptools，`src/` 布局）+ `requirements.txt`（锁定直接依赖）+ `requirements-dev.txt` | 只装运行时需要的两三个包，避免整仓依赖锁污染 |

### 2.2 依赖矩阵（已核验，2026-10-13）

| 用途 | 依赖 | 版本 | 核验事实 |
|---|---|---|---|
| QQ 官方机器人接入 | `qq-botpy` | `==1.2.1` | 腾讯官方 SDK，仓库 `tencent-connect/botpy`（MIT，918★，2024-09 最后提交，未归档）；自带 WebSocket 网关、token 刷新、心跳、重连，直接支持 `on_group_at_message_create` 与 `post_group_message` |
| 写 TOML（读用标准库 `tomllib`） | `tomli-w` | `==1.2.0` | 纯 Python、无依赖、MIT，`<3.9` 以上全平台 |
| 测试 | `pytest` `pytest-asyncio` `pytest-cov` `ruff` | 见 `requirements-dev.txt` | 仅开发期依赖，CI 与本地一致 |
| RCON | 无第三方依赖（标准库 `asyncio` 自研） | — | 见 §2.4 / §2.8 |

运行时第三方依赖总计 **2 个**（`qq-botpy` 会带入 `aiohttp`/`PyYAML`/`APScheduler`，属其自身依赖）。

### 2.3 QQ 接入方式

- 使用 `qq-botpy` 的 `botpy.Client` 子类，`intents = botpy.Intents(public_messages=True)`；`appid/secret` 从 `QQ_BOT_APP_ID` / `QQ_BOT_APP_SECRET` 读取（`client.run(appid=..., secret=...)`，见官方示例 `examples/demo_group_reply_text.py`）。
- 事件：`async def on_group_at_message_create(self, message: botpy.message.GroupMessage)`；取 `message.content`、`message.author.member_openid`、`message.group_openid`、`message.id`。
- 发送：`await self.api.post_group_message(group_openid=..., msg_type=0, content=..., msg_id=..., msg_seq=...)`。被动回复（5 分钟窗口内）带 `message.id`；主动消息不带 `msg_id`，`msg_seq` 用全局递增序号（A12）。
- 生命周期：`botpy.Client.start(appid, secret, ret_coro=True)` 会返回网关协程（已核验 `botpy/client.py:139-223`），因此可以在自己的事件循环里 `asyncio.create_task()` 与日志/健康轮询并发跑，退出时 `await client.close()`。

### 2.4 RCON 接入方式

- 自研 `rcon/client.py`：Valve RCON 二进制协议（`<i` 长度 + `<ii` req_id/type + UTF-8 body + `\x00\x00`），实现
  - `LOGIN(3)` 鉴权（响应 id `-1` → `RconAuthError`）；
  - **多包响应**：读完首个 `RESPONSE(0)` 包后，在 `drain_timeout`（默认 0.1s）内继续读后续包并拼接（Vanilla 长输出会分多个 4KB 包）；
  - `asyncio.Lock` 串行化同一条连接上的命令（多任务并发调用必须配对请求/响应）；
  - 命令体 > 1446 字节直接拒绝（协议硬限，`aio-mc-rcon` 同样限制）；
  - 断连自动重连（下次调用时），不重发（A14）；
  - `connect_timeout` / `command_timeout` 可配，超时抛 `RconTimeoutError`。
- `rcon/pool.py`：多服管理，`broadcast_tellraw()` 广播全部服，`status()` 聚合 `/list`，`parse_list_response()` 解析 `There are 3 of a max of 20 players online: Steve, Alex`。
- 注入格式：`tellraw @a {"text":"..."}`，JSON 由 `json.dumps(..., ensure_ascii=False)` 生成，命令整体先做 1446 字节校验。

### 2.5 日志监听方式

同步实现（`Path.open` + `seek(offset)` + 正则），由 `service` 用 `asyncio.to_thread()` 调度，保证：单测无需事件循环即可覆盖偏移/轮转/半行；事件循环不被文件 IO 阻塞（文件小、0.5s 一次）。

### 2.6 持久化

| 数据 | 介质 | 写入方式 |
|---|---|---|
| 配置 | `config.toml`（`tomllib` 读） | 人工维护 |
| 绑定 | `data/bindings.toml`（`tomllib` 读 + `tomli-w` 写） | 临时文件 + `os.replace()` 原子替换 |
| 运行状态（日志偏移、健康状态、`msg_seq`） | `data/state.json` | 同上；每次事件推进后与优雅退出时各写一次 |

### 2.7 运行方式

- 主入口：`python -m y33bot run --config config.toml`，控制台脚本 `y33bot`（`pyproject.toml` `[project.scripts]`）。
- 部署形态：普通常驻进程，不要求容器。跨平台启动方式在 README 给出：Linux `systemd` 单元示例、Windows「任务计划/`nssm`」或直接前台运行（实施任务的文档部分产出，本计划只要求 README 含 Linux `systemd` 示例）。
- 一键开发：`scripts/dev_setup.sh`（建 `.venv` → 装依赖 → 打印下一步），`Makefile` 提供 `setup/run/check/lint/test`。

### 2.8 被否决方案及证据

| 方案 | 否决理由（核验于 2026-10-13） |
|---|---|
| `mcnexus`（IDEA §6 首推） | PyPI 上声明的仓库 `github.com/Bogdan11212/mcnexus` **返回 404**，文档站 `bogdan11212.github.io/mcnexus` 同样 404；依赖清单含 `asyncpg`/`motor`/`aiomysql` 等数据库驱动，与 RCON 无关。来源不可核查 + 依赖畸重，不引入生产 |
| `aio-mc-rcon` 3.5.0（IDEA §6 备选） | 仓库真实且活跃（`Iapetus-11/aio-mc-rcon`，MIT，53★，2026-09-18 推送），但源码 `aiomcrcon/client.py` **只读一个响应包**（`send_cmd` 读 `in_len` 即返回），未处理 Vanilla 多包响应，也无并发锁，不满足 IDEA 对 RCON 库的能力要求 |
| 自己手写 QQ 网关（aiohttp + WebSocket） | 需要自行实现 AccessToken、网关分片、心跳、断线 resume、`msg_seq` 语义，约 200+ 行且易踩官方频控坑；官方 SDK 已覆盖，收益为负 |
| 引入数据库/Redis | 单机私服、数据量级为「几十条绑定 + 几 KB 状态」，文件即可；规格也要求不预留 |

---

## 3. 模块与目录结构

### 3.1 目录结构树

```
.
├── IDEA.md                     # 既有需求书（本次不修改）
├── PLAN.md                     # 本文件
├── README.md                   # 使用/部署文档（由 t_bcf892eb 重写）
├── LICENSE
├── pyproject.toml              # 包元数据、依赖、pytest/ruff 配置
├── requirements.txt            # 运行时直接依赖（== 锁定）
├── requirements-dev.txt        # 测试/检查依赖（== 锁定）
├── Makefile                    # setup / run / check / lint / test
├── .gitignore                  # .venv、data/、__pycache__、.env、*.log、.worktrees/（看板工作树不得入库）
├── .env.example                # 环境变量清单（不含真实值）
├── config.example.toml         # 配置样板（可直接复制为 config.toml）
├── .github/workflows/ci.yml    # push/PR：装依赖 → ruff → pytest(+覆盖率门槛)
├── scripts/dev_setup.sh        # 一条命令准备好环境
├── docs/
│   ├── smoke.md                # 手工自测命令（t_68925b93 产出）
│   └── acceptance.md           # 端到端验收记录（t_7b86eb6b 产出）
├── src/y33bot/
│   ├── __init__.py             # __version__ = "0.1.0"
│   ├── __main__.py             # python -m y33bot → cli.main()
│   ├── cli.py                  # 子命令：run / check / bind / simulate
│   ├── config.py               # 配置加载与校验、密钥解析
│   ├── models.py               # 全部 dataclass（事件、消息、结果、健康）
│   ├── binding.py              # BindingStore（TOML 读写，原子落盘）
│   ├── state.py                # StateStore（偏移/健康/msg_seq，JSON）
│   ├── bridge.py               # 事件路由与文案渲染（核心业务）
│   ├── service.py              # 组件装配、常驻任务、优雅退出、启动自检
│   ├── rcon/
│   │   ├── __init__.py
│   │   ├── protocol.py         # RconTransport 协议 + 异常类型
│   │   ├── client.py           # AsyncRconClient（多包/锁/重连）
│   │   ├── pool.py             # RconPool（多服广播、status、/list 解析）
│   │   └── fakes.py            # FakeRconTransport（dry-run / 测试）
│   ├── mclog/
│   │   ├── __init__.py
│   │   ├── patterns.py         # 模板编译、单行解析
│   │   └── watcher.py          # LogWatcher（偏移轮询、轮转重置、残行缓冲）
│   ├── qq/
│   │   ├── __init__.py
│   │   ├── gateway.py          # QQGateway 协议 + BotpyGateway
│   │   ├── probe.py            # 凭据探活（check 取一次 access_token）
│   │   └── fakes.py            # FakeQQGateway（模拟/测试）
│   └── commands/
│       ├── __init__.py
│       ├── registry.py         # CommandRegistry / CommandContext / CommandSpec
│       └── builtin.py          # /status、/bind
└── tests/
    ├── conftest.py             # 临时 config/state/日志夹具
    ├── test_config.py
    ├── test_binding.py
    ├── test_state.py
    ├── test_mclog_patterns.py
    ├── test_mclog_watcher.py
    ├── test_rcon_client.py     # 内存假 RCON 服务器（asyncio 本地 socket）
    ├── test_commands.py
    ├── test_bridge.py
    ├── test_cli.py
    └── e2e/
        └── test_acceptance.py  # S1–S4 的可重复端到端（无网络）
```

### 3.2 模块清单

| 模块 | 职责 | 对外接口 | 依赖 |
|---|---|---|---|
| `config` | 读 `config.toml`、校验、解析密钥 | `load_config(path, env=None) -> AppConfig`；`ConfigError` | `tomllib` |
| `models` | 数据结构定义 | 全部 dataclass（见 §4.4） | 无 |
| `binding` | 绑定表读写（覆盖语义、原子落盘） | `BindingStore.load/lookup/bind/unbind/items/save` | `tomllib`、`tomli-w` |
| `state` | 运行状态读写 | `StateStore.load/save`，`RuntimeState`/`ServerState` | `json` |
| `mclog.patterns` | 模板编译 + 单行解析 | `compile_patterns(LogPatterns) -> CompiledPatterns`；`parse_line(cp, line) -> MCLogEvent \| None` | `re` |
| `mclog.watcher` | 偏移推进、轮转重置、残行缓冲 | `LogWatcher.poll_new_events() -> list[MCLogEvent]` | `mclog.patterns`、`state` |
| `rcon.protocol` | 接口与异常 | `RconTransport`(Protocol)、`RconError/RconAuthError/RconConnectError/RconDisconnectedError/RconTimeoutError` | 无 |
| `rcon.client` | 单连接 RCON 客户端 | `AsyncRconClient.connect/command/close/connected` | `asyncio` |
| `rcon.pool` | 多服编排、广播、`/list` 解析 | `RconPool.start/close/broadcast/broadcast_tellraw/query/status`；`parse_list_response()` | `rcon.client` |
| `qq.gateway` | QQ 接入 | `QQGateway`(Protocol)：`start/send_group_message/close/wait_closed`；`BotpyGateway` | `qq-botpy` |
| `qq.probe` | 凭据探活（`check` 的 QQ 项） | `probe_access_token(app_id, secret, *, timeout) -> int`；`QQProbeError` | 标准库 `urllib` |
| `commands.registry` | 指令注册与分发 | `CommandRegistry.register/get/names/dispatch`；`CommandContext` | `models` |
| `commands.builtin` | `/status`、`/bind` | `cmd_status(ctx, args) -> str`、`cmd_bind(ctx, args) -> str`；`build_registry()` | `rcon.pool`、`binding` |
| `bridge` | 触发规则、文案渲染、健康翻转 | `Bridge.handle_group_message/handle_log_event/poll_health/format_status` | 以上全部 |
| `service` | 装配 + 常驻循环 + 退出 | `Service.run()/startup_checks()/shutdown()` | `bridge`、`qq.gateway`、`mclog.watcher`、`rcon.pool` |
| `cli` | 命令行入口 | `main(argv=None) -> int` | `service`、`config`、`binding` |
| `qq.fakes`/`rcon.fakes` | 离线替身 | `FakeQQGateway`、`FakeRconTransport` | 无 |

### 3.3 关键接口签名（实现者按此填写函数体，不得改签名）

```python
# models.py
@dataclass(frozen=True)
class MCGroupMessage:
    group_openid: str
    member_openid: str
    message_id: str
    content: str              # 已剥离 @机器人 前缀
    received_at: float

@dataclass(frozen=True)
class OutgoingGroupMessage:
    group_openid: str
    text: str
    reply_to_message_id: str | None = None   # None → 主动消息

@dataclass(frozen=True)
class MCLogEvent:
    server: str
    kind: Literal["join", "quit", "chat"]
    player: str | None
    message: str | None
    raw: str
    occurred_at: float

@dataclass(frozen=True)
class PlayerList:
    online: int
    max_players: int
    players: list[str]
    raw: str

@dataclass(frozen=True)
class CommandResult:
    server: str
    ok: bool
    response: str
    error: str | None

@dataclass(frozen=True)
class ServerStatusReport:
    per_server: dict[str, PlayerList | None]
    offline: list[str]
    total_online: int

# config.py
@dataclass(frozen=True)
class MCServerConfig:
    name: str; host: str; port: int; password_env: str; log_path: Path
    connect_timeout: float = 5.0; command_timeout: float = 5.0

@dataclass(frozen=True)
class QQConfig:
    group_openid: str = ""
    app_id_env: str = "QQ_BOT_APP_ID"
    app_secret_env: str = "QQ_BOT_APP_SECRET"
    command_prefix: str = "/"
    chat_prefix: str = "#"

@dataclass(frozen=True)
class LogPatterns:
    join: str; quit: str; chat: str; encoding: str = "utf-8"

@dataclass(frozen=True)
class Behavior:
    log_poll_interval: float = 0.5
    health_poll_interval: float = 30.0
    max_line_length: int = 200
    ignored_chat_prefixes: tuple[str, ...] = ("[QQ]",)

@dataclass(frozen=True)
class AppConfig:
    qq: QQConfig; servers: list[MCServerConfig]; patterns: LogPatterns; behavior: Behavior
    bindings_path: Path; state_path: Path
    def rcon_password(self, server: MCServerConfig, env: Mapping[str, str]) -> str: ...
    def app_credentials(self, env: Mapping[str, str]) -> tuple[str, str]: ...

def load_config(path: Path, env: Mapping[str, str] | None = None) -> AppConfig: ...   # 失败抛 ConfigError

# rcon/client.py
class AsyncRconClient:
    MAX_PAYLOAD_BYTES = 1446
    def __init__(self, host: str, port: int, password: str, *,
                 connect_timeout: float = 5.0, command_timeout: float = 5.0,
                 drain_timeout: float = 0.1) -> None: ...
    async def connect(self) -> None: ...
    async def command(self, cmd: str) -> str: ...
    async def close(self) -> None: ...
    @property
    def connected(self) -> bool: ...

# rcon/pool.py
class RconPool:
    def __init__(self, servers: Sequence[MCServerConfig], passwords: Mapping[str, str],
                 *, factory: Callable[..., RconTransport] = AsyncRconClient) -> None: ...
    async def start(self) -> None: ...        # 单服连不上只告警，不阻塞启动
    async def close(self) -> None: ...
    async def broadcast(self, cmd: str) -> dict[str, CommandResult]: ...
    async def broadcast_tellraw(self, text: str) -> dict[str, CommandResult]: ...
    async def query(self, server: str, cmd: str) -> CommandResult: ...
    async def status(self) -> ServerStatusReport: ...
    def server_names(self) -> list[str]: ...

# mclog/watcher.py
class LogWatcher:
    def __init__(self, server: MCServerConfig, patterns: LogPatterns,
                 store: StateStore) -> None: ...
    def poll_new_events(self) -> list[MCLogEvent]: ...   # 同步，service 用 to_thread 调用

# qq/gateway.py
class QQGateway(Protocol):
    async def start(self) -> None: ...
    async def send_group_message(self, message: OutgoingGroupMessage) -> None: ...
    async def close(self) -> None: ...
    async def wait_closed(self) -> None: ...   # 网关任务自己结束（BUG-001：作为运行期失效信号，§7.2）

# qq/probe.py
class QQProbeError(RuntimeError): ...
def parse_token(payload: object) -> int: ...            # 纯函数：取 expires_in 或抛 QQProbeError
async def probe_access_token(app_id: str, app_secret: str, *, timeout: float = 5.0) -> int: ...  # 真取一次 token

# commands/registry.py
@dataclass
class CommandContext:
    config: AppConfig; bindings: BindingStore; rcon: RconPool
    state: StateStore; message: MCGroupMessage; logger: logging.Logger

Handler = Callable[[CommandContext, list[str]], Awaitable[str]]

class CommandRegistry:
    def register(self, name: str, *, aliases: Sequence[str] = (), desc: str = "") -> Callable[[Handler], Handler]: ...
    def get(self, name: str) -> CommandSpec | None: ...
    def names(self) -> list[str]: ...
    async def dispatch(self, ctx: CommandContext, line: str) -> str: ...   # line 含前缀，如 "/status 1"

# bridge.py
class Bridge:
    def __init__(self, config: AppConfig, bindings: BindingStore, state: StateStore,
                 rcon: RconPool, registry: CommandRegistry, gateway: QQGateway,
                 *, clock: Callable[[], float] = time.time, logger: logging.Logger | None = None) -> None: ...
    async def handle_group_message(self, message: MCGroupMessage) -> str | None: ...
    async def handle_log_event(self, event: MCLogEvent) -> None: ...
    async def poll_health(self) -> list[tuple[str, bool]]: ...   # 返回发生翻转的 (server, online)
    def format_status(self, report: ServerStatusReport) -> str: ...
```

### 3.4 CLI 契约（stdout 文案即验收断言对象）

```
python -m y33bot --version                     # 打印 y33bot 0.1.0
python -m y33bot run    --config config.toml   # 常驻服务（QQ 网关 + 日志轮询 + 健康轮询）
python -m y33bot check  --config config.toml [--no-probe]   # 启动自检，退出码 0 通过 / 1 失败
python -m y33bot bind list | bind set <openid> <game_id> | bind remove <openid>
python -m y33bot commands --config config.toml   # 打印 QQ 管理端指令面板要配置的「指令名 + 指令介绍」
python -m y33bot simulate group-message --openid <id> --content '<文本>' [--group-openid <gid>] [--dry-run]
python -m y33bot simulate log-event --server <name> --line '<一行日志>' [--dry-run]
python -m y33bot simulate log-event --server <name> --kind join|quit --player <name> [--dry-run]
python -m y33bot simulate health --server <name> --online|--offline
```

- 输出行前缀固定：`[群消息] `（要发到 QQ 群的文本）、`[RCON <server>] `（实际执行的命令）、`[指令] `（`commands` 输出的管理端清单）、`[忽略] `（未触发规则的原因）、`[警告] `/`[错误] `。
- `simulate` 默认使用**真实 RCON 连接**（验收要看游戏内注入）；`--dry-run` 用 `rcon.fakes.FakeRconTransport`，只打印 `[RCON <server>] <命令>`，不做任何网络 IO（CI 用）。
- `simulate` 的 QQ 侧统一使用 `qq.fakes.FakeQQGateway`，绝不连 QQ。
- `check` 输出逐项结果行：`[配置] OK …`、`[QQ] OK|FAIL …`、`[RCON <name>] OK|FAIL …`、`[日志 <name>] OK|FAIL …`、`[绑定] OK N 条`，最后一行 `OK`（退出码 0）或 `FAIL`（退出码 1）。
- `check` 的 **QQ 项默认真探活**（§7.2）：向 `https://bots.qq.com/app/getAppAccessToken` 取一次 `access_token`——
  - 成功 → `[QQ] OK access_token 获取成功（有效期 <N>s），app_id 已设置 (env <变量名>)，group_openid 已配置`；
  - 失败（凭据无效 / 平台报错 / 网络不可达）→ `[QQ] FAIL access_token 获取失败: <原因>`，末行随之 `FAIL`；
  - `--no-probe` 跳过探活（**给离线环境/CI 用**）→ `[QQ] OK app_id 已设置 (env <变量名>)，未探活（--no-probe），group_openid 已配置`；
  - 凭据**缺失**（变量没设）时与旧行为一致：`[QQ] FAIL 环境变量 <名> 未设置`，不联网。
  默认探活是刻意的：`[QQ] OK` 的语义必须是「凭据可用」，而不是「变量填了」（BUG-001 的 F4/R5）。
- 用法错误（缺少子命令/参数）由 `argparse` 处理，退出码 2。

### 3.5 配置文件示例（`config.example.toml` 内容以此为准）

```toml
[qq]
group_openid = "填写目标群的 group_openid"   # MC→QQ 方向的发送目标；留空则该方向禁用并告警
app_id_env = "QQ_BOT_APP_ID"
app_secret_env = "QQ_BOT_APP_SECRET"
command_prefix = "/"
chat_prefix = "#"

[behavior]
log_poll_interval = 0.5       # 秒
health_poll_interval = 30.0   # 秒
max_line_length = 200         # 单行转发长度上限（字符）
ignored_chat_prefixes = ["[QQ]"]

[paths]
bindings = "data/bindings.toml"
state = "data/state.json"

[[mc_servers]]
name = "main"                           # 唯一，用于日志与状态文件名
host = "127.0.0.1"
port = 25575
password_env = "MC_RCON_PASSWORD_MAIN"  # 变量不存在时回退 MC_RCON_PASSWORD
log_path = "D:/mc/server/logs/latest.log"
connect_timeout = 5.0
command_timeout = 5.0

[log_patterns]
join = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?P<player>\w+) joined the game'
quit = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?P<player>\w+) left the game'
chat = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)'
encoding = "utf-8"
```

`.env.example`：

```
QQ_BOT_APP_ID=
QQ_BOT_APP_SECRET=
MC_RCON_PASSWORD_MAIN=
```

### 3.6 日志与错误处理约定

- 统一 `logging`，logger 名 `y33bot.<模块>`；`run` 默认 `INFO` 到 stderr；`--verbose` 提升为 `DEBUG`。
- 失败分层：配置/模板错误 → 启动即 `ConfigError` 退出码 1（`check` 打印 `FAIL`）；单服 RCON 故障 → `[警告]` 并继续服务（故障服在 `/status` 显示离线）；QQ 发送失败 → `[错误]` 日志，不重试；日志文件缺失 → `[警告]`，下一轮继续尝试（文件出现后从 0 开始）。
- 失败分层（QQ 网关，§7.2）：**启动期**失败 → `[错误] QQ 网关启动失败: <原因>` + 退出码 1（原有行为）；**运行期**网关任务结束（长连接断了且 SDK 不会自己重连）→ `[错误] QQ 网关已断开（收不到群消息），进程退出等待重启` + 退出码 1，随后走正常 `shutdown()`。口径：**网关任务结束即视为故障**，一次失败就退出，交给 `systemd`/`nssm` 拉起；**不做退避重启**（用户 2026-10-15 拍板）。收到停止信号时的正常关闭不算故障：退出码仍为 0、不打印 `[错误]`。
- 所有写盘（bindings/state）用「临时文件 + `os.replace()`」原子替换，避免半截文件。

---

## 4. 数据模型

### 4.1 `config.toml`（§3.5 完整示例即模型定义）

| 键 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `qq.group_openid` | str | 否（空则 MC→QQ 禁用） | 非空时用于主动消息 |
| `qq.app_id_env` / `qq.app_secret_env` | str | 是 | 指向环境变量名 |
| `qq.command_prefix` / `qq.chat_prefix` | str | 是 | 单字符，默认 `/` `#` |
| `behavior.log_poll_interval` | float | 是 | > 0 |
| `behavior.health_poll_interval` | float | 是 | > 0 |
| `behavior.max_line_length` | int | 是 | 1..1446 |
| `behavior.ignored_chat_prefixes` | list[str] | 是 | 可空数组；样板值为 `["[QQ]"]`（服务只注入这一个标记，§7） |
| `paths.bindings` / `paths.state` | str | 是 | 相对路径按配置文件所在目录解析 |
| `mc_servers[].name` | str | 是 | `^[A-Za-z0-9_-]{1,32}$`，同一文件内唯一 |
| `mc_servers[].host/port` | str/int | 是 | port 1..65535 |
| `mc_servers[].password_env` | str | 是 | 环境变量名；缺失回退 `MC_RCON_PASSWORD` |
| `mc_servers[].log_path` | str | 是 | 绝对或相对路径；不存在不报错，只告警 |
| `mc_servers[].connect_timeout/command_timeout` | float | 否 | 默认 5.0，> 0 |
| `log_patterns.join/quit/chat` | str | 是 | 可编译正则；`chat` 必须含命名组 `player`、`message`；`join`/`quit` 必须含 `player` |
| `log_patterns.encoding` | str | 否 | 默认 `utf-8` |

### 4.2 `data/bindings.toml`

```toml
[[bindings]]
qq_openid = "1A2B3C4D"
game_id = "Steve"

[[bindings]]
qq_openid = "5E6F7890"
game_id = "Alex"
```

不变量：`qq_openid` 唯一（`bind()` 覆盖写，等价于“解绑后再绑定”）；`game_id` 允许重复（同一玩家可被多个 QQ 绑定，规范未禁止）。

### 4.3 `data/state.json`

```json
{
  "version": 1,
  "qq": { "msg_seq": 37 },
  "servers": {
    "main": {
      "log_offset": 184320,
      "log_size": 184320,
      "log_inode": "281474976711234",
      "health_online": true,
      "health_changed_at": 1791824536.0
    }
  }
}
```

字段语义：`log_offset` 已读字节数；`log_size`/`log_inode` 仅诊断用（A10）；`health_online` 为 `null` 表示尚未探测；`health_changed_at` 用于「变化时提示一次」（R19）。

### 4.4 运行时数据结构

见 §3.3 的 dataclass 定义（`MCGroupMessage`、`OutgoingGroupMessage`、`MCLogEvent`、`PlayerList`、`CommandResult`、`ServerStatusReport`、`CommandContext`、`ServerState`、`RuntimeState`）。

### 4.5 不变量与校验规则

1. 事件载荷 `member_openid`、`group_openid` 非空，否则丢弃并 `[警告]`。
2. 转发文本先做单行化（A7）再做 1446 字节命令上限校验；超限时按字符截断以保证命令可发送。
3. `game_id` 校验正则 `^[A-Za-z0-9_]{3,16}$`。
4. `state.json` 版本号不匹配（`version != 1`）→ 备份为 `state.json.bak` 后重置（不静默丢数据）。
5. `bindings.toml` 解析失败 → 抛 `BindingError`，**不覆盖**原文件（保护人工数据）。
6. 每个 MC 服恰好一个 `LogWatcher` 实例，一个事件循环内串行推进偏移。

---

## 5. 验收场景

以下 5 个场景可人工完整复现。S1–S4 不依赖 QQ、不依赖真实 MC（`--dry-run` 分支），S5 是真实端到端。所有命令以 git-bash（Windows）为例，Linux 把 `.venv/Scripts` 换成 `.venv/bin` 即可。

**S1 环境与配置自检**

前置：`git clone` 仓库 → `bash scripts/dev_setup.sh`（或 `make setup`）；把 `config.example.toml` 复制为 `config.toml`，设置 `MC_RCON_PASSWORD_MAIN`（可填任意值）。

步骤与期望：
```
$ python -m y33bot check --config config.toml
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] OK access_token 获取成功（有效期 7200s），app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON main] FAIL 无法连接 127.0.0.1:25575: ...
[日志 main] OK D:/mc/.../latest.log 可读，偏移 0 字节
[绑定] OK 0 条
FAIL
$ echo $?
1
```
把 MC 服起起来（或把 `host/port` 指向可达 RCON）后，`[RCON main] OK /list -> ...` 且末行为 `OK`、退出码 0。缺失 `QQ_BOT_APP_SECRET` 时 `[QQ] FAIL 环境变量 QQ_BOT_APP_SECRET 未设置`。

QQ 项自 §7.2 起默认**真探活**（真取一次 `access_token`，需要能访问 `bots.qq.com`），因此：
- 凭据无效/网络不通 → `[QQ] FAIL access_token 获取失败: <原因>`，末行 `FAIL`、退出码 1（实测样例见 `docs/acceptance.md` §9.1）；
- 完全离线的机器（或 CI）用 `--no-probe`：`[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，未探活（--no-probe），group_openid 已配置`，此时 `[QQ] OK` 只代表「变量填了」。

**S2 QQ→MC（指令与转发）**

```
$ python -m y33bot bind set 1A2B3C4D Steve
[绑定] 已写入 1A2B3C4D -> Steve (data/bindings.toml)
$ python -m y33bot simulate group-message --openid 1A2B3C4D --content '#你好
世界' --dry-run
[RCON main] tellraw @a {"text":"[QQ] Steve: 你好"}
```
（第二行 `世界` 演示 A7 换行截断：只转发第一行）
- 未绑定：`--openid UNKNOWN --content '#hi'` → 输出 `[群消息] 请先使用 /bind <游戏ID> 绑定`，**无** `[RCON …]` 行。
- 非触发前缀：`--content '普通消息'` → `[忽略] 非触发前缀`，无任何发送。
- 缺参数：`--content '/bind'` → `[群消息] 用法: /bind <游戏ID>`。
- 真实 MC（去掉 `--dry-run`）：游戏内所有在线玩家看到 `[QQ] Steve: 你好`；日志出现 `[RCON main] tellraw …`。

**S3 MC→QQ（聊天转发与回环防护）**

```
$ python -m y33bot simulate log-event --server main --line '[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好' --dry-run
[群消息] Steve@main: 大家好
$ python -m y33bot simulate log-event --server main --line '[12:00:02] [Async Chat Thread - #0/INFO]: <Steve> 普通聊天' --dry-run
[忽略] 聊天非 # 开头，不转发
$ python -m y33bot simulate log-event --server main --line '[12:00:03] [Async Chat Thread - #0/INFO]: <Steve> [QQ] Steve: 大家好' --dry-run
[忽略] 回环防护：命中 ignored_chat_prefixes
```
（`#` 聊天只在群里出现一行，**没有** `[RCON …]` 回显行；群消息带来源服名 —— §7 的 v0.2 变更）

**S4 进出通知与健康翻转（只提示一次）**

```
$ python -m y33bot simulate log-event --server main --line '[12:00:04] [Server thread/INFO]: Steve joined the game' --dry-run
[群消息] Steve进入了main
$ python -m y33bot simulate log-event --server main --line '[12:00:05] [Server thread/INFO]: Steve left the game' --dry-run
[群消息] Steve退出了main
$ python -m y33bot simulate health --server main --offline --dry-run
[群消息] [服务器状态] main 离线
$ python -m y33bot simulate health --server main --offline --dry-run     # 再执行一次
[忽略] 状态未变化，不重复提示
```

**S5 真实端到端（QQ 群 + MC 服）**

前置：`QQ_BOT_APP_ID`、`QQ_BOT_APP_SECRET`、`MC_RCON_PASSWORD_MAIN` 已设置；MC `server.properties` 打开 `enable-rcon=true`；`config.toml` 填好 `[qq] group_openid`。

1. `python -m y33bot run --config config.toml` → 日志出现 `[启动] QQ 网关已连接` 与 `[启动] 日志监听已启动: main`。
2. 群里 `@机器人 #测试消息` → **期望**：MC 内所有玩家看到 `[QQ] Steve: 测试消息`；群里**不**回消息。
3. MC 内输入 `#大家好啊` → **期望**：群里出现 `Steve@main: 大家好啊`；**MC 内不再多出任何行**（v0.2 起取消游戏内回显，§7）。
4. 群里 `@机器人 /status` → **期望**：群内回
   ```
   [服务器状态]
   在线: 1/20
   玩家: Steve
   ```
   （多服时逐服一行 + `总计: N 人在线`；全离线时为 `[服务器状态] 服务器离线`）
5. 群里 `@机器人 /bind Alex` → **期望**：群内回 `绑定成功: Alex`；`data/bindings.toml` 新增该条；同一 openid 再 `/bind Notch` 覆盖成功。
6. 群里 `@机器人 /unknowncmd` → **期望**：群内回 `未知指令`。
7. `Ctrl+C` → 进程退出；`data/state.json` 的 `log_offset` 等于 `latest.log` 当前大小；重新 `run` 后**不重复**推送历史事件（偏移续读）。
8. 玩家进服/退服 → 群里出现 `Steve进入了main` / `Steve退出了main`（带服名，§7 V1）；手动停掉 MC 进程 → 30s 内（`health_poll_interval`）群里出现一次 `[服务器状态] main 离线`；恢复后出现一次上线提示。

**新增观察点（§7.2，BUG-001 修复后）**：运行期把 QQ 侧弄断（断网 10s / 重置 AppSecret / 踢下线），**期望**日志出现

```
[错误] QQ 网关已断开（收不到群消息），进程退出等待重启
[停止] 正在关闭…
[停止] 已退出
```

且进程退出码为 1（`systemd`/`nssm` 据此拉起）——**不再**是「进程常驻、群里没反应、日志干净」。
反向对照：`Ctrl+C`（步骤 7）时不应出现该 `[错误]` 行、退出码仍为 0。

**S6 日志轮转**

前置：S5 步骤 7 之后（`log_offset` 非 0）。

1. 手动清空/重命名 `latest.log`，再写入一行进服日志。
2. `python -m y33bot run --config config.toml` → **期望**：日志出现 `[警告] 日志文件缩小（size=... < offset=...），偏移重置为 0`，且新写入的进服日志被解析为 `Steve进入了main` 推送到群。

---

## 6. 任务清单

依赖列中的 `T#` 为本清单内任务；`看板卡` 列给出该任务由哪张已存在的卡片承接（卡内步骤按本表执行）。

| T | 任务 | 内容摘要 | 依赖 | 交付物 | 看板卡 |
|---|---|---|---|---|---|
| T1 | 骨架与依赖 | 建 §3.1 目录树与空模块（仅签名 + docstring）、`pyproject.toml`、`requirements*.txt`（`qq-botpy==1.2.1`、`tomli-w==1.2.0`）、`.gitignore`（必须含 `.worktrees/`、`.venv/`、`data/`、`.env`、`*.log`）、`.env.example`、`config.example.toml`、`scripts/dev_setup.sh`、`Makefile`、`.github/workflows/ci.yml`（3.12：装依赖 → `ruff check` → `pytest`） | — | 可 `pip install -e .` 的空骨架 | `t_8442a7d5` |
| T2 | 配置与模型 | `config.py`、`models.py` 全量实现 + 校验（§4.1 规则、A18 环境变量） | T1 | `test_config.py` 全绿 | `t_68925b93` |
| T3 | 持久化层 | `binding.py`（TOML 读写、覆盖语义、原子替换）、`state.py`（JSON、版本迁移、偏移/健康/msg_seq） | T2 | `test_binding.py`、`test_state.py` 全绿 | `t_68925b93` |
| T4 | RCON 层 | `rcon/protocol.py`、`rcon/client.py`（多包/锁/重连/超时/1446 限制）、`rcon/pool.py`（广播、status、`/list` 解析）、`rcon/fakes.py` | T2 | `test_rcon_client.py`（内存假 RCON 服）全绿 | `t_68925b93` |
| T5 | 日志层 | `mclog/patterns.py`（模板补锚点、命名组校验）、`mclog/watcher.py`（偏移、轮转、残行缓冲、编码兜底） | T2, T3 | `test_mclog_patterns.py`、`test_mclog_watcher.py` 全绿 | `t_68925b93` |
| T6 | 指令层 | `commands/registry.py`（装饰器、别名、参数解析、`未知指令`）、`commands/builtin.py`（`/status`、`/bind` + A2 文案） | T3, T4 | `test_commands.py` 全绿 | `t_68925b93` |
| T7 | 业务桥与 QQ 适配 | `bridge.py`（R1–R12、R19、A1/A4/A6/A7/A8 文案与规则）、`qq/gateway.py`（BotpyGateway + 主动/被动发送 + A12）、`qq/fakes.py` | T4, T5, T6 | `test_bridge.py` 全绿 | `t_68925b93` |
| T8 | 服务与 CLI | `service.py`（三任务并发、启动自检、优雅退出、配置与状态落盘）、`cli.py`（`run/check/bind/simulate` + §3.4 输出契约）、`__main__.py` | T7 | 手工跑通 S1–S4；`docs/smoke.md` | `t_68925b93` |
| T9 | 单元测试补全 | 逐模块补边界用例（空输入、超长、类型错误、失败分支），核心函数行覆盖 ≥70%，`make test` 离线一键通过 | T8 | 覆盖率报告 + CI 绿 | `t_7b86eb6b` |
| T10 | 端到端测试与验收记录 | `tests/e2e/test_acceptance.py` 覆盖 S1–S4、S6（假 RCON + FakeQQGateway + 临时日志），按本文件 §5 逐条真实执行并写入 `docs/acceptance.md` | T9 | `docs/acceptance.md`（每条含命令/实际输出/结论） | `t_7b86eb6b` |
| T11 | 文档与发布 | 重写 `README.md`（简介、功能、环境要求、安装、启动、配置说明、最小示例、目录说明、常见问题、systemd 部署、状态重置方法），核对文档中每条命令可复制执行，打 `v0.1.0` tag 并推送 | T10 | 可用 README + `v0.1.0` | `t_bcf892eb` |
| T12 | 汇总复验 | 按 `docs/acceptance.md` 与 §5 全量复跑，确认 S1–S6 结论、CI 绿、无硬编码密钥 | T11 | 根卡 `t_c3a76c90` 的完成结论 | `t_c3a76c90` |

并行建议：T2 完成后 T3/T4/T5 可并行；T6 依赖 T3+T4；T7 依赖 T4+T5+T6；T9/T10 不得早于 T8；T11 不得早于 T10。

---

## 7. 变更记录

### 7.1 v0.2（2026-10-13，真机反馈驱动）

来源：`需求1.txt` 第 53–55 行（用户在真机试跑后的三条反馈）。三项均已落地；其中 V1、V2 **偏离了 IDEA.md 的冻结表述**——按本文件开头的效力条款在此登记，IDEA.md 与 `需求1.txt` 按仓库规则不修改。三条反馈与实现的对应关系如下。

> 命名说明：本节用「v0.2」指代**这批变更**；包版本号仍是 `0.1.0`（`pyproject.toml` / `__version__`），
> 发版时再统一 bump —— 本次没有做发布，所以文档里的 `y33bot 0.1.0` 输出保持原样。

| # | 变更 | 原状（IDEA / 原 PLAN） | 现行为 | 涉及位置 |
|---|---|---|---|---|
| V1 | MC→QQ 的消息带来源服名 | 进出通知为 `Steve进入游戏` / `Steve退出游戏`，且明确「不加服务器名前缀」（IDEA §3.3/§3.8、原 A4） | 进出通知 `Steve进入了main` / `Steve退出了main`；游戏内 `#` 聊天转发 `Steve@main: 你好`（`main` 取 `[[mc_servers]].name`，不加 `【】`） | `bridge.py`；PLAN A4 / R10 / R11 / R28 / S3-S6；README；`docs/smoke.md`；`docs/acceptance.md`；5 个测试文件 |
| V2 | 取消游戏内回显 | 玩家在游戏内发 `#大家好` 后，服务再 RCON 注入一行 `[→QQ] Steve: 大家好`（IDEA §3.3、原 R11/A8），造成游戏内聊天刷屏 | 只在 QQ 群出现一行；游戏内不再注入任何回显（玩家自己那行 `#大家好` 本来就可见） | `bridge.py`；PLAN R11 / A8 / N13 / S3 / S5-3；`config.example.toml` 的 `ignored_chat_prefixes` 收窄为 `["[QQ]"]`；README；`docs/smoke.md`；`docs/acceptance.md`；测试 |
| V3 | QQ 管理端指令面板配套 | 仓库文档只描述了进程内的装饰器式 `CommandRegistry`，没有说明 C 端「@机器人 输入框 `/` 指令面板」由**管理端手工配置**，也没有面向该面板的清单 | 新增 `y33bot commands` 子命令，打印「指令名（带 `command_prefix`）+ 指令介绍」；`status`/`bind` 的描述压到面板限制内（≤15 中文字符） | `cli.py`；`commands/builtin.py`；PLAN §3.4；README §5.3 / §8；`tests/test_cli.py`；`tests/e2e/test_entrypoint.py` |

平台事实依据（本次现查 QQ 官方文档，非推测）：

- 「介绍与接入指南」§9.1.2 指令配置：群聊/频道/单聊的「/」指令面板条目「**开发者需在管理端配置**」，上限 24 条；每条字段为「指令名（≤8 中文字符或 16 英文字符）」「指令介绍（≤15 中文字符或 30 英文字符）」「权限菜单」「使用场景」；「指令、服务和快捷菜单模块**暂不需要单独提审**」。
- API v2 文档（API 调用指南 / 消息收发概述）**没有**群聊指令注册接口 —— 所以不存在"代码层主动注册指令"，能做的是「管理端手填 + 代码侧保证指令名与 `dispatch()` 一致 + 把清单沉淀进文档」。
- 群聊只订阅 `public_messages`（即 `GROUP_AT_MESSAGE_CREATE`）。用户已在真机确认面板发出的是 @消息，因此无需改 intent；若日后出现不带 @ 的面板消息，需要另行申请全量消息 `GROUP_MESSAGE_CREATE`。

回环防护的连带结论（A8）：服务现在只注入 `[QQ] …` 一种标记，故样板 `ignored_chat_prefixes` 收窄为 `["[QQ]"]`；旧配置保留 `[→QQ]` 不影响运行（配置只做前缀匹配）。回环判断在 `#` 判断**之前**执行，并由 `test_bridge.py::test_chat_loop_protection_is_config_driven` 锁住「前缀可配置」这一行为。

明确不做：`/list`（或 `/help`）这类**群内列举指令**不做 —— 可发现性交给 QQ 客户端的指令面板（用户 2026-10-13 决定）。

### 7.2 BUG-001 修复：运行期网关失效报警退出 + `check` 真探活（2026-10-15）

来源：`BUGS.md` 的 **BUG-001「回复」**（调查卡 `t_6cc56405` 离线复刻结论：真缺陷，推荐 R2+R5），
加上用户 2026-10-15 拍板的口径：

> **网关任务结束即视为故障：打 `[错误]`，并立即以非 0 退出**，交给 `systemd`/`nssm` 拉起。
> **不做退避重启**（一次失败就退出）；`check` 的 QQ 项改为真实探活。

| # | 变更 | 原状 | 现行为 | 涉及位置 |
|---|---|---|---|---|
| B1 | 运行期网关失效 → 报警 + 非 0 退出（R2-lite） | `Service.run()` 在 `start()` 之后只 `await _wait_for_stop()`，**不监视网关任务**；而 `ret_coro=True` 下 SDK 自带的重连驱动不执行（`botpy/client.py:217-223`）→ 会话被回填后没人启动（`botpy/connection.py:57-67`）→ 网关协程**正常返回**（无异常 ⇒ 原实现一行日志都不打）⇒ 进程常驻、群里永久无反应、日志干净 | `QQGateway` 协议**新增**成员 `wait_closed()`（`BotpyGateway` 用 done-callback 观测自己的网关任务；`FakeQQGateway` 等到 `close()`）；`Service.run()` 同时等「停止信号」与「网关任务结束」：**网关先结束** → `[错误] QQ 网关已断开（收不到群消息），进程退出等待重启` + 走既有 `shutdown()` + 返回 **1**；**收到停止信号** → 仍返回 **0**、不打印 `[错误]`（区分「我们主动关」与「网关死了」）。**不重试、不退避重启**（一次失败就退出） | `src/y33bot/qq/gateway.py`、`src/y33bot/qq/fakes.py`、`src/y33bot/service.py`；PLAN §3.2/§3.3/§3.6/§5 S5；README §7/§8/§13；`docs/smoke.md`；`docs/acceptance.md` §9；`BUGS.md`；`tests/test_service.py`、`tests/test_gateway.py`、`tests/test_bug001_reconnect.py`、`tests/test_failures.py` |
| B2 | `check` 的 QQ 项真探活（R5） | `[QQ] OK app_id 已设置 …` 只证明**环境变量非空**：凭据完全是伪造/过期值也照样 OK（BUGS.md 的 F4，附实测输出） | 默认向 `https://bots.qq.com/app/getAppAccessToken` 取一次 `access_token`：成功 → `[QQ] OK access_token 获取成功（有效期 <N>s），app_id 已设置 (env …)，group_openid 已配置`；失败 → `[QQ] FAIL access_token 获取失败: <原因>`（末行 `FAIL`、退出码 1）。新增 `check --no-probe` 给离线环境/CI：`[QQ] OK app_id 已设置 (env …)，未探活（--no-probe），group_openid 已配置`，文案里明说「未探活」，不再冒充「凭据可用」 | 新增 `src/y33bot/qq/probe.py`；`src/y33bot/service.py`（`startup_checks` + 可注入 `qq_probe`/`probe_qq`）；`src/y33bot/cli.py`（`--no-probe`）；PLAN §3.1/§3.2/§3.3/§3.4/§5 S1；README §8/§13/§14；`docs/smoke.md` S1；`docs/acceptance.md` §9；`tests/test_qq_probe.py`、`tests/test_cli.py`、`tests/test_smoke.py`、`tests/e2e/*` |

**对 IDEA 的偏离**：无。IDEA §4「重试：不重试」只约束**单条消息**，没有约束「发现通道死了要报出来」；
B1 也**没有**新增重试（明确不重启）。`IDEA.md`、`需求1.txt` 未改。

**签名冻结条款核对**：本次只**新增** `QQGateway.wait_closed()` 与 `qq.probe` 的新函数，
`PLAN.md` §3.3 里既有签名一行未改。

**验证与边界**：修复落地时做了**离线前后对照**（同一脚本、同一配置，指向 `757db31` 的 `src` 为「修复前」）——
修复前 `run()` 在网关结束后 3s 内仍不返回（看门狗判超时、无 `[错误]`），修复后同一场景打印
`[错误] QQ 网关已断开…` 并 `exit=1`；`check` 也在真网络下实测（假凭据 → `[QQ] FAIL access_token 获取失败: 平台返回错误: code=10004 message=机器人不存在`）。
原始输出见 `docs/acceptance.md` §9。**真机触发链路（Q1 静默时的日志尾部 / Q3 QQ 侧关码）仍未验证** ——
本机没有真实 QQ 凭据与真 MC 服，按仓库规则「未执行就如实写未执行」，不用推断代替证据。
