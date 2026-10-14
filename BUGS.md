# BUGS.md — 缺陷与疑似缺陷记录

本文件记录 Y33-Bot 的缺陷。与 `docs/acceptance.md`（验收"设计是否兑现"）互补：这里记"实际跑起来哪里不对"。

## 记录规则

1. 每条含固定小节：**现象 / 影响 / 环境 / 已核实的代码事实 / 待核实的疑点 / 复现步骤 / 期望行为 / 回复**。
2. **没复现的一律标「疑似」**，不许把猜测写成结论；结论只能写在「回复」小节里，且必须带证据（命令、日志、时间戳、SDK 源码 `文件:行号`）。
3. 「已核实」与「疑点」分开写：前者是本仓代码/SDK 里**读得到**的事实，后者是需要跑起来才能定的问题。
4. 修复与调查分开：调查卡只负责把结论写进「回复」；真要改代码另开卡，并走 `PLAN.md` §7 的变更登记。

## 索引

| 编号 | 标题 | 状态 | 登记日 | 调查卡 |
|---|---|---|---|---|
| [BUG-001](#bug-001-qq-token-过期后运行时静默失效运行期无任何提示) | QQ token 过期后运行时静默失效，运行期无任何提示 | **已复现**（离线复刻，真机未验证） | 2026-10-13 | 看板 `default` 的 `t_6cc56405`（2026-10-15 结案，结论见本条「回复」） |

---

## BUG-001 QQ token 过期后运行时静默失效，运行期无任何提示

**状态**：已复现（2026-10-15 离线复刻「静默失效」整条链条；真机触发链路 Q1/Q3 未执行 —— 见「回复」）
**登记日**：2026-10-13
**上报**：用户（真机运行观察到，非 CI 用例）
**调查卡**：看板 `default` 的 `t_6cc56405`（分支 `y33-bot/t_6cc56405-bug-001-qq-token`，2026-10-15 结案）—— 只调查、不改产品代码，结论写本条的「回复」
**涉及方向**：QQ 侧（`src/y33bot/qq/gateway.py`、`src/y33bot/service.py`），依赖 `qq-botpy==1.2.1`

### 现象

真机运行期间，怀疑 QQ 凭据/token 过期后**没有自动获取、或者获取失败**，而且**运行期没有任何提示**：
进程看起来还在跑，但群里 @机器人 不再有反应，日志里也没看到明显的报错。用户无法判断是"机器人挂了"
还是"消息没发出去"。

### 影响

- 静默失效：QQ 方向不通时进程仍在常驻，日志轮询/健康轮询照旧工作，看起来"服务是好的"。
- 只能靠人发现（群里没人应答才知道），没有自愈、没有告警、没有退出码让 `systemd`/`nssm` 拉起。
- 与 `IDEA.md` §4「重试：不重试」不冲突：规格说不重试**单条消息**，但没说不许"发现通道死了要报出来"。

### 环境

| 项 | 值 |
|---|---|
| 仓库 | `Y33-Bot`（本机 Windows 11 + git-bash，Python 3.12.10） |
| 依赖 | `qq-botpy==1.2.1`（装在仓库 `.venv`，`botpy` 无 `__version__` 属性，按 `requirements.txt` 锁定） |
| 配置 | `[qq] app_id_env / app_secret_env` 走环境变量，`group_openid` 指向目标群 |
| 触发条件（待确认） | 真机长时间运行、或 AppSecret 被重置、或 `bots.qq.com` 一时不可达 |

### 已核实的代码事实（本轮只读核对，未改动任何文件）

| # | 事实 | 位置 |
|---|---|---|
| F1 | 服务启动时**只等一次**网关就绪（`asyncio.wait_for(self._up_event.wait(), 30s)`）；就绪之后再发生什么都不再有人看这个 event | `src/y33bot/qq/gateway.py:102-107` |
| F2 | `_run_client()` 里，SDK 网关协程**正常返回**时什么都不做（不抛异常 → **一行日志都不会有**）；只有抛异常才记 `[错误] QQ 网关异常退出: %s`，随后 `_signal_up(exc)` —— 而 event 早已 set，等于**没有接收方** | `src/y33bot/qq/gateway.py:123-144` |
| F3 | `Service.run()` 在 `await gateway.start()` 之后只 `await self._wait_for_stop()`：**没有监视网关任务**，也没有"网关死了就退出/重启"的分支；日志与健康轮询继续跑 | `src/y33bot/service.py:205-221` |
| F4 | `check` 只校验凭据**存在**（`config.app_credentials()`），不校验**可用**；配了过期/失效的凭据照样打印 `[QQ] OK app_id 已设置 …` | `src/y33bot/service.py:86-93` |
| F5 | 我们用 `ret_coro=True` 启动 SDK（这是 `PLAN.md` §2.3 的既有决定：为了把网关塞进自己的事件循环，与日志/健康轮询并发跑） | `src/y33bot/qq/gateway.py:129`；`PLAN.md:145` |
| F6 | 发送路径**有痕**：`send_group_message()` 失败会记 `[错误] QQ 发送失败（不重试）: %s` | `src/y33bot/qq/gateway.py:215-226` |
| F7 | 我们关掉了 botpy 自己的日志文件（`bot_log=None, ext_handlers=False`），但 SDK 的 logger 仍会传播到 root —— 真机记录里确实出现过 `[botpy] 登录机器人账号中...`，说明 SDK 的日志是**能**看到的 | `src/y33bot/qq/gateway.py:119-121`；`README.md` §7 |

**`qq-botpy==1.2.1` 源码**（`.venv/Lib/site-packages/botpy/`）

| # | 事实 | 位置 |
|---|---|---|
| S1 | **"自动更新凭据"确实存在**：`check_token()` 在 `access_token is None` 或 `now >= expires_in` 时调 `update_access_token()` 重新取 token；成功后打印 `[botpy] access_token expires_in <秒>` | `botpy/robot.py:39-41`、`botpy/robot.py:43-67` |
| S2 | 刷新是**按需触发**：每次 HTTP 调用前 `check_token()`；WS 侧在建连 / 重连前也各调一次 | `botpy/http.py:145`、`botpy/gateway.py:143`（identify）、`botpy/gateway.py:176`（resume） |
| S3 | 刷新失败（响应缺 `access_token`/`expires_in`，例如 secret 失效）会 `_log.error("[botpy] 获取token失败，请检查appid和secret填写是否正确！")` 并 **raise RuntimeError**；网络超时先 `_log.info("[botpy] access_token TimeoutError: …")` 再 raise | `botpy/robot.py:44-67` |
| S4 | 断线处理：close code 4004 → `[botpy] 鉴权失败，重置token...` 并把 `access_token` 置 None；9001/9005 → 清 `session_id`/`last_seq`；随后**一律** `self._connection.add(self._session)` 把会话放回队列等重连 | `botpy/gateway.py:52-65` |
| S5 | **SDK 自带的重连驱动是 `while not self._closed: await self._connection.multi_run(...)`** —— 但 `ret_coro=True` 时 `_pool_init` **直接 return 协程对象**，这个 while 循环根本不执行 | `botpy/client.py:217-231`、`botpy/client.py:222-223` |
| S6 | 少了 S5 的驱动后，重连只剩 `multi_run()` 自己：它先**排空**会话列表（`while len(session_list) > 0`）再 `await asyncio.wait(tasks)`；而 `on_closed` 的 `add()` 发生在 `await` 之后 —— **排空已经结束，没人再启动这个新会话** | `botpy/connection.py:48-75`（尤其 57-67）、`botpy/gateway.py:65` |
| S7 | 于是断线链路是：`ws_connect` 任务结束 → `asyncio.wait` 返回 → `multi_run()` 返回 → 我们那层 `_run_client` **正常结束（无异常、无日志）** | `botpy/gateway.py:110-135`、`botpy/connection.py:67`、`src/y33bot/qq/gateway.py:123-138` |

### 假设 H1（待验证，置信度中等偏上）

**"凭据没有自动获取"大概率不成立**（S1/S2：SDK 确实按需自动刷新，真失败时还会打 `[botpy] 获取token失败…`）。
更可能的链条是：

> token 自然过期 / secret 失效 / 网络瞬断 → QQ 侧断开长连接（或 4004 鉴权失败）→ SDK 把会话放回队列，
> 但**重连驱动在 `ret_coro=True` 下不存在**（S5/S6）→ 网关协程**正常返回** → 我们既不监视也不退出
> （F1–F3）→ 进程常驻、群里永久无反应、日志可能一行都不多。

这条链条能同时解释用户看到的三个现象（收不到消息、没有提示、进程还在）。**但它需要真机断线实验确认**
（疑点 Q1/Q3），也要先排除"日志里其实有 `[botpy]` 行、只是没被注意到"（Q1）。

### 为什么会这样（背景知识）

QQ 官方机器人有**两条链路**，用的是同一个 `access_token`，但刷新时机不同：

- **收（WebSocket 长连接）**：token 只在建连/重连的握手时用；连上之后事件靠长连接推送。所以"token 过期"本身**不会**立刻掐断一个已经建立的连接。
- **发（HTTPS OpenAPI）**：每次请求都会 `check_token()`，过期就现刷。所以发送方向对 token 过期更敏感，但恰好也是**唯一会留下 `[错误]` 痕迹**的路径。

这就解释了一个反直觉的现象：**"机器人不回话"可能来自收方向（长连接悄悄断了/SDK 重连驱动失效），而不是发方向** —— 收方向没有任何主动探测，进程也不会因此退出，
于是"服务活着但群里没反应，日志还干净"这种状态是**代码结构上允许发生**的（F1–F3 + S5–S7）。

### 待核实的疑点（调查卡逐条作答）

1. **真机日志**：静默发生时最后几行 `[botpy]` 是什么？重点找 `[botpy] ws关闭，停止接收消息!`、
   `[botpy] 鉴权失败，重置token...`、`[botpy] 获取token失败…`、`[botpy] 最大并发连接数…`；
   并确认日志里**到底有没有**任何 `[错误]`/`[警告]`（用户说的"没有提示"要落成日志片段）。
2. **离线复刻 H1**（不连 QQ；允许新增测试，**不许改产品代码**）：
   (a) `ret_coro=True` 下 `multi_run()` 是否真是一次性的（会话被 `add()` 回来也不会再启动）；
   (b) 我们这层对"网关协程结束"是否真无感知（`Service.run()` 不退出、不打日志）。
3. **QQ 侧断连码**：token 自然过期（7200s）时 QQ 是否主动关 WS、关闭码是多少（4004 还是别的）？
   若关 → 与 H1 合成完整链条；若不关 → "过期"只是背景，真正的触发是其它断线原因。
4. **期望口径（需用户拍板）**：网关不可用时想"自愈重连"，还是"报警并非 0 退出交给进程管理器拉起"，或两者都要（先自愈，多次失败后退出）？
5. **`check` 语义**：是否补一条"凭据可用性"探活（取一次 token / 发一条测试消息），
   避免 `[QQ] OK` 只证明"变量填了"（F4）。

### 复现步骤

**离线部分（不需要凭据）**

```bash
cd "E:/D-Data/Users/Lenovo/docs/GitHub/Y33-Bot"
PY=.venv/Scripts/python.exe

# 1) 复核本文件 S1–S7 的源码坐标
$PY -c "import inspect,botpy.connection as c,botpy.robot as r; print(inspect.getsource(c.ConnectionSession.multi_run)); print(inspect.getsource(r.Token.check_token))"

# 2) 网关在"启动成功后"结束，服务是否察觉？（预期：不察觉 —— 进程继续常驻、无日志）
#    调查卡需新增用例：桩网关 start() 成功、之后内部任务结束，
#    断言 Service.run() 仍在 _wait_for_stop()（不退出、不打日志）
$PY -m pytest tests/test_service.py -q -k gateway

# 3) token 刷新失败时发送路径是否留痕（S2/S3 的验证）
#    monkeypatch botpy.robot.Token.update_access_token 抛 RuntimeError，
#    断言日志出现 "[错误] QQ 发送失败（不重试）"
$PY -m pytest tests/test_gateway.py -q -k send
```

**真机部分（需要真实凭据，不改服务端代码）**

1. `python -m y33bot run --config config.toml --verbose`（要 DEBUG 级 `[botpy]` 行），
   确认群里 `@机器人 /status` 有回；
2. 制造断线，**逐个单独做**便于归因：
   (a) 断网 10 秒（拔网线 / 关 Wi-Fi / 屏蔽 `api.sgroup.qq.com`）；
   (b) 在开放平台**重置 AppSecret**（旧 secret 立刻失效，下一次刷新必失败）；
   (c) 等 token 自然过期（约 2 小时）；
3. 断线后 5–10 分钟反复 `@机器人 /status`，同时盯日志：
   - 是否出现 `[botpy] ws关闭，停止接收消息!` / `[botpy] 鉴权失败，重置token...` / 任何 `[错误]`？
   - 之后是否**再无任何行**、而进程仍活着（`data/state.json` 的 `log_offset` 仍在推进可证）？
   - 进程退出码是否变化（`echo $?`）？
4. 把日志片段、时间点、动作时间、`echo $?` 贴进「回复」。

### 期望行为（需与用户确认口径）

- **要么自愈**：SDK 重连成功后自动恢复收消息；发送失败按规格不重试但要有痕。
- **要么显式报警**：网关不可用时打 `[错误]` 并以非 0 退出（交给 `systemd`/`nssm` 拉起），或至少能通过 `check`/日志看出"QQ 侧不可用"。
- **明确不接受的**：进程常驻、无日志、无退出、群里没反应 —— 即"静默失效"。

### 结论与修复方向

**见下方「回复」**（调查卡 `t_6cc56405` 已给出结论与推荐方向；修复**另开卡**并走 `PLAN.md` §7 登记）

候选修复方向（**仅供调查卡评估，不要现在动手**）：

| 方向 | 做法 | 代价 / 风险 |
|---|---|---|
| R1 | 改回 `ret_coro=False`，让 SDK 的 `while not self._closed` 驱动重连 | 与 `PLAN.md` §2.3 的并发装配冲突，需确认 SDK 的 while 不会阻塞日志/健康轮询 |
| R2 | 保留 `ret_coro=True`，但**自己监视网关任务**：任务结束 → `[错误]` + 有限次重启或非 0 退出 | 改动小、语义清晰；等于部分接管 SDK 的重连职责 |
| R3 | 自己补重连驱动（断线后重新 `create_task(client.start())`，或在 SDK 外层再包一层 `multi_run` 循环） | 与 R1 同类风险，必须真机验证 |
| R4 | 增加"QQ 通道探活"：`check` 取一次 token；运行时定期打点/日志心跳 | 不解决自愈，但能把"静默"变成"有痕" |
| R5 | 修正 `check` 的 `[QQ] OK` 语义为"凭据可用"（F4） | 小改动，独立于重连问题 |

---

### 回复

> 由 BUG-001 调查卡填写（id 见看板 `default`）。要求：逐条回答上面 5 个疑点，每条给「复现 / 未复现 + 证据」，
> 证据里带命令、真实输出、时间戳、`文件:行号`；最后给出结论（真缺陷 / 设计如此 / 环境问题）、
> 影响面、以及在上表 R1–R5 里推荐哪一条（含理由）。无法复现就写「未复现 + 已排除的原因」，
> 不要写"大概"。**不要在这里改产品代码**。

**调查卡**：看板 `default` 的 `t_6cc56405`，分支 `y33-bot/t_6cc56405-bug-001-qq-token`，工作树 `.worktrees/t_6cc56405`
**取证时间**：2026-10-15 00:36–00:49（+0800；每条命令前都跑了 `date`，时间戳随证据贴在下面）
**取证环境**：Windows 11 + git-bash；`python -m venv .venv`（Python 3.12.10）；依赖走清华镜像安装：
`qq-botpy 1.2.1`、`tomli-w 1.2.0`、`pytest 9.1.1`、`pytest-asyncio 1.4.0`、`pytest-cov 7.1.0`、`ruff 0.17.0`。
**本轮改动**：`src/y33bot/**` **一行未改**，`tests/**` 既有用例与断言**一行未改**；只**新增**取证用例与本记录：
`tests/test_bug001_reconnect.py`（新文件，2 例）、`tests/test_gateway.py`（+2 例）、`tests/test_service.py`（+1 例）、`BUGS.md`（本回复）。
**未执行的部分**：真机断线实验（Q1、Q3）—— 原因见疑点 1，不做任何替代性推测。

#### 0. 源码坐标复核（F1–F7 / S1–S7 逐条核对）

本机单次运行模式会把 `python -c`（`-c` 脚本执行）判为危险命令并拒绝执行（需人工批准），所以把 BUGS.md 复现步骤里那条
`python -c "import inspect,botpy.connection as c,botpy.robot as r; ..."` 的原样逻辑写成脚本文件（落在仓库外
`%LOCALAPPDATA%\hermes\cache\scratch\dump_botpy*.py`）再跑，输出等价：

```bash
$ .venv/Scripts/python.exe C:/Users/Lenovo/AppData/Local/hermes/cache/scratch/dump_botpy.py      # 2026-10-15 00:37:46 +0800
botpy package: ...\.venv\Lib\site-packages\botpy
```

**复核结论**：F1–F7、S1–S3、S5、S7 与描述**逐行一致**（引用见下）。两处坐标需微调，**都不改变结论**：

- **S4**：断线处理代码实际在 `botpy/gateway.py:55-66`（`on_closed`）。原文写 `52-65`；其中 `52-53` 属 `on_error`（`traceback.print_exc()` + `add()`），两处都会回填会话，所以「一律 add」的结论不变。
- **S6** 引用的 `botpy/gateway.py:65` 应为 `:66`（65 是注释行，66 才是 `self._connection.add(self._session)`）。

关键片段（原文粘贴，行号即文件真实行号）：

**S5 —— `ret_coro=True` 让重连驱动不执行**（`botpy/client.py:217-227`）

```python
217|         while not self._closed:
218|             _log.debug("[botpy] 会话循环检查...")
219|             try:
220|                 # 返回协程对象，交由开发者自行调控
221|                 coroutine = self._connection.multi_run(session_interval)
222|                 if self.ret_coro:
223|                     return coroutine
224|                 elif coroutine:
225|                     await coroutine
226|                 else:
227|                     await self.close()
```

**S6 —— 先排空、后 await，回填的会话再也不会被启动**（`botpy/connection.py:48-67`）

```python
48|     async def multi_run(self, session_interval=5):
49|         if len(self._session_list) == 0:
50|             return
...
57|         while len(session_list) > 0:
58|             _log.debug("[botpy] 会话列表循环运行")
59|             time_interval = session_interval * (index + 1)
60|             _log.info("[botpy] 最大并发连接数: %s, 启动会话数: %s" % (self._max_async, len(session_list)))
61|             for i in range(self._max_async):
62|                 if len(session_list) == 0:
63|                     break
64|                 tasks.append(asyncio.ensure_future(self._runner(session_list.pop(i), time_interval), loop=self.loop))
65|             index += self._max_async
66| 
67|         await asyncio.wait(tasks)
```

**S4 —— 断线回填**（`botpy/gateway.py:55-66`）

```python
55|     async def on_closed(self, close_status_code, close_msg):
56|         _log.info("[botpy] 关闭, 返回码: %s" % close_status_code + ", 返回信息: %s" % close_msg)
57|         if close_status_code in self._AUTH_FAIL_CODE:
58|             _log.info("[botpy] 鉴权失败，重置token...")
59|             self._session["token"].access_token = None
60|         # 这种不能重新链接
61|         if close_status_code in self._INVALID_RECONNECT_CODE or not self._can_reconnect:
62|             _log.info("[botpy] 无法重连，创建新连接!")
63|             self._session["session_id"] = ""
64|             self._session["last_seq"] = 0
65|         # 断连后启动一个新的链接并透传当前的session，不使用内部重连的方式，避免死循环
66|         self._connection.add(self._session)
```

**S1 / S3 —— token 是自动刷新、失败会抛错**（`botpy/robot.py:39-41`、`43-67`）

```python
39|     async def check_token(self):
40|         if self.access_token is None or int(time.time()) >= self.expires_in:
41|             await self.update_access_token()
...
62|         if "access_token" not in data or "expires_in" not in data:
63|             _log.error("[botpy] 获取token失败，请检查appid和secret填写是否正确！")
64|             raise RuntimeError(str(data))
65|         _log.info("[botpy] access_token expires_in " + data["expires_in"])
```

**S2 —— 刷新是按需触发**（`botpy/http.py:145`；`botpy/gateway.py:143` identify 前、`:176` resume 前）

```python
145|         await self._token.check_token()      # botpy/http.py（check_session）
143|         await self._session["token"].check_token()   # botpy/gateway.py（ws_identify）
176|         await self._session["token"].check_token()   # botpy/gateway.py（ws_resume）
```

**S7 的补充（本轮新读到，对结论有用）**：`botpy/client.py:233-248` 的 `bot_connect()` 里 `await client.ws_connect()` 在
「连接被关闭」时**正常返回**（`botpy/gateway.py:135` 的 `break`）→ `botpy/connection.py:69-72` 的 `_runner()` 里
`await asyncio.sleep(time_interval)` 结束 → 任务完成 → `asyncio.wait(tasks)` 返回 → `multi_run()` 返回。**只有异常路径**
才走 `client.on_error(e)`（`botpy/client.py:247-248`）。

**我们这层（F1/F2/F3/F5/F6）的坐标同样逐条核对无误**：`src/y33bot/qq/gateway.py:103`（只等一次就绪）、
`:129`（`ret_coro=True`）、`:131`（`_signal_up()`）、`:132-133`（`await coroutine`）、`:136-138`（只有异常才 `[错误] QQ 网关异常退出`）、
`:140-144`（`_signal_up` 对已 set 的 event 无接收方）、`:224`（`[错误] QQ 发送失败（不重试）: %s`）；
`src/y33bot/service.py:87-93`（QQ 自检只查凭据存在）、`:207-210`（启动期失败 → `[错误]` + 返回 1）、`:215`（之后只 `_wait_for_stop()`）；
`PLAN.md:145`（`ret_coro=True` 的装配决定，原文只写了"返回网关协程…可以并发跑"，**没有**写"因此不补重连驱动"）。

#### 疑点 1：真机日志（静默时最后几行 `[botpy]` / 有没有 `[错误]`）—— **未执行**

**原因（不编造）**：本机**没有真实 QQ 凭据** —— 实测 `env | grep -c '^QQ_BOT_'` → `0`（环境里没有这两个变量），
仓库/工作树里也没有 `.env`（`ls .env` → `No such file or directory`），只有 `.env.example` 的空值模板
（`QQ_BOT_APP_ID=` / `QQ_BOT_APP_SECRET=`，`README` 注明服务本身不解析 `.env`）；同时本机也没有
`enable-rcon=true` 的真 MC 服（`check` 里 `127.0.0.1:25575` 直接超时，见疑点 5）。所以"静默发生那一刻的日志尾部"拿不到，
Q1 保持未执行。

已做/可用的**替代证据**（都不等于 Q1，因此不写结论）：

- 同一条 `[botpy]` → 项目 logging 的通道**是通的**（不是"日志被吞了"）：真机记录见 `README.md:279-281`
  —— `[botpy] 登录机器人账号中...`、`[botpy] 获取token失败，请检查appid和secret填写是否正确！`、
  `[错误] QQ 网关异常退出: {'code': 10004, 'message': '机器人不存在'}`。
- **启动期**失败一定留痕且有退出码：`tests/test_gateway.py:200`（启动失败 → `QQGatewayError`）、
  `tests/test_service.py:124`（`run()` 返回 1）。本缺陷的缺口恰好在"启动之后"。
- 真机 3 步（断网 10s / 重置 AppSecret / 等 token 过期）与观察点（`[botpy]` 行、后续是否再无日志、
  `data/state.json` 的 `log_offset` 是否仍推进、`echo $?`）**原样留在**"复现步骤 → 真机部分"，未执行、未编造输出。

#### 疑点 2：离线复刻 H1 —— **(a) 复现、(b) 复现**

**(a) `ret_coro=True` 下 `multi_run()` 是一次性的（会话被 `add()` 回填后不会再启动）—— 复现**

- 用例：`tests/test_bug001_reconnect.py:51` `test_multi_run_starts_each_session_once_and_never_again`（`tests/test_bug001_reconnect.py:27` 的
  `_make_connection()` 用**真 SDK 的 `ConnectionSession`** + 假 connect：假 connect 里"建连 → 0.02s → `connection.add(session)`"，
  后者就是 `botpy/gateway.py:66` 的等价动作）。
- 命令与真实输出：

```bash
$ date '+%Y-%m-%d %H:%M:%S %z'
2026-10-15 00:49:24 +0800
$ .venv/Scripts/python.exe -m pytest tests/test_bug001_reconnect.py \
    "tests/test_gateway.py::test_gateway_coroutine_end_is_silent" \
    "tests/test_gateway.py::test_send_token_refresh_failure_is_logged" \
    "tests/test_service.py::test_run_ignores_gateway_task_ending" -v
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
plugins: asyncio-1.4.0, cov-7.1.0
collecting ... collected 5 items

tests/test_bug001_reconnect.py::test_multi_run_starts_each_session_once_and_never_again PASSED [ 20%]
tests/test_bug001_reconnect.py::test_service_stays_alive_when_sdk_gateway_coroutine_returns PASSED [ 40%]
tests/test_gateway.py::test_gateway_coroutine_end_is_silent PASSED       [ 60%]
tests/test_gateway.py::test_send_token_refresh_failure_is_logged PASSED  [ 80%]
tests/test_service.py::test_run_ignores_gateway_task_ending PASSED       [100%]

============================== 5 passed in 1.78s ==============================
```

- 断言逐条（`tests/test_bug001_reconnect.py:59-67`）：
  1. `await multi_run()` 返回后 `calls == [session]` —— 只建连一次；
  2. `connection._session_list == [session]` —— 会话**确实被回填**，队列非空（不是"会话丢了"）；
  3. 再等 0.1s，`calls` 仍只有一次 —— **没有任何人再启动它**，即不复连；
  4. **正向对照**：紧接着再调一次 `multi_run()`，`calls == [session, session]` —— 会话本身没坏，缺的只是"驱动"
     （也就是 `botpy/client.py:217` 那层 `while not self._closed`）。
- **证明**：`multi_run()` 的一次性语义 + 回填会话不会被自动重启，即 S6 成立、S5 的"驱动缺失"是真缺口。
- **没证明**：真机上 QQ 断线时一定走到这条路径（关码/触发原因属 Q1/Q3）；也未覆盖 `_max_async > 1` 与多分片。

**(b) 我们的 `Service.run()` 对"网关协程在启动后结束"确实毫无感知 —— 复现（3 个用例，从桩到整链）**

1. 服务侧（桩网关）：`tests/test_service.py:198` `test_run_ignores_gateway_task_ending`
   —— 桩网关 `start()` 成功、内部任务 20ms 后结束；断言 `gateway.ended is True` 的同时
   `run_task.done() is False`（仍在 `src/y33bot/service.py:215` 的 `_wait_for_stop()`），
   且 `[r for r in caplog.records if r.levelno >= logging.WARNING] == []`（**一条 `[警告]`/`[错误]` 都没有**），
   而 `[启动] 日志监听已启动: main` 照旧出现（日志轮询/健康轮询不受影响）。
2. 我们真实的适配层（假 SDK `botpy.Client`，照抄 `ret_coro` 语义）：`tests/test_gateway.py:296` `test_gateway_coroutine_end_is_silent`
   —— 断言 `task.exception() is None`（**走不到** `src/y33bot/qq/gateway.py:136` 的 `except`）、`gateway._up_error is None`、
   0.05s 内没有任何 `[警告]`/`[错误]`，而 `[启动] QQ 网关已连接`（`gateway.py:130`）在。
3. 整链复刻（真 SDK 的 `multi_run()` + 我们真实的 `BotpyGateway` + 真实的 `Service.run()`）：
   `tests/test_bug001_reconnect.py:101` `test_service_stays_alive_when_sdk_gateway_coroutine_returns`
   —— 断言：网关协程已返回（`gateway._task.done() is True`）；**没有第二次建连**（`len(connect_calls) == 1`）；
   **会话还躺在队列里**（`len(_connection._session_list) == 1`，永远等不到启动）；`Service.run()` **仍在跑**
   （`task.done() is False`）；日志里 0 条 `[警告]`/`[错误]`。

对照（说明不是"我们什么都不管"）：`tests/test_service.py:124` 证明**启动期**网关失败会被发现并返回 1 —— 差别正在"启动后"。

**(4) 顺带核到 F6（发送路径有痕）**：`tests/test_gateway.py:330` `test_send_token_refresh_failure_is_logged`
—— 用**真 SDK** 的 `BotAPI`/`BotHttp`（`botpy/api.py:1423-1424` → `botpy/http.py:156`、`:177` `await self.check_session()`
→ `botpy/robot.py:39-41`），monkeypatch `botpy.robot.Token.update_access_token` 抛
`RuntimeError("获取token失败，请检查appid和secret填写是否正确！")`；断言日志里**同时**出现
`[错误] QQ 发送失败（不重试）` 与 SDK 的原因串。一条网络请求都没发出去（不需要凭据、不需要网络）。

#### 疑点 3：QQ 侧断连码（token 自然过期时 QQ 是否主动关 WS、关码是多少）—— **未执行（真机）**；源码层能定的边界如下

- **未执行原因**同 Q1（无真实凭据，无法让平台真的断开我们）。**不猜关码**：`4004`（`_AUTH_FAIL_CODE`）与
  `9001`/`9005`（`_INVALID_RECONNECT_CODE`）在 `botpy/gateway.py:47-48` 只是 SDK 的分支常量，成立的前提是"QQ 真的发了那个码"。
- 源码层**可确定**（因此 Q3 未执行也不影响"失败了会静默"这个结论）：
  1. token 只在**握手**时用（`botpy/gateway.py:143` identify、`:176` resume）；连上之后的收包循环（`botpy/gateway.py:123-135`）
     **不看 token** ⇒ "token 自然过期"本身不会掐断一条已经建立的连接（它只影响后续重连的握手与发送方向的现刷）。
  2. 无论关码是什么，`on_closed` 最后都会 `add()` 回填（`botpy/gateway.py:66`），而回填后没人启动（S6）
     ⇒ **静默链条对关码不敏感**；4004 只是多做一件事：把 `access_token` 置 None（`botpy/gateway.py:59`），下次发送才现刷。
- 所以 Q3 只影响"**触发前提**是不是 token 过期"，不影响"一旦网关结束就静默失守"这个结论。

#### 疑点 4：期望口径（自愈 or 报警 or 两者）—— **需用户拍板；这不是可复现的技术疑点**

给出我的建议（供拍板，落地方式可以不同）：

- **主选 R2 + R5**：
  - **R2**（监视网关任务）：`Service.run()` 在 `start()` 之后把"网关任务结束"也当成一个唤醒源（例如
    `asyncio.wait([gw_task, stop_signal], return_when=FIRST_COMPLETED)`）；网关任务结束就 `[错误] QQ 网关已断开（收不到群消息）`，
    **先自愈**（有限次重启 + 退避，例如 3 次 / 5·15·45s），仍失败再**非 0 退出**交给 `systemd`/`nssm`。
  - **R5**（修 `check` 语义）：一行探活就能把"变量填了"变成"凭据可用"（见 Q5）。
- **可选增强 R4**（探活/心跳日志）：只在"连自愈都做不到"时兜底；**不建议只做 R4** —— 那只是让死得更明显，用户仍要人工重启。
- **不建议第一轮做 R1**：它确实能恢复 SDK 的 `while not self._closed` 驱动，但（a）与 `PLAN.md:145` 的并发装配冲突、要重跑真机验收；
  （b）SDK 那层在会话列表空时会自己 `await self.close()` 并打 `[botpy] 服务意外停止!`（`botpy/client.py:226-228`），
  而**我们这层依然不会退出**（`src/y33bot/qq/gateway.py:132-133` 之后 `_run_client` 正常结束），所以 R1 单独治不了"不退出/不报警"。
- **R3** 与 R1 同类风险（等于自己实现重连、与 SDK 内部状态打架），不值得在第一轮就上。

#### 疑点 5：`check` 语义（`[QQ] OK` 是否只证明"变量填了"）—— **复现**

命令与真实输出（配置在仓库外，凭据故意用"格式像真的、但从未签发"的假值）：

```bash
$ date '+=== check @ %Y-%m-%d %H:%M:%S %z ==='
=== check @ 2026-10-15 00:41:09 +0800 ===
$ PYTHONPATH=src QQ_BOT_APP_ID=102000000 QQ_BOT_APP_SECRET=this-secret-is-bogus-and-never-issued \
  MC_RCON_PASSWORD_MAIN=bogus-rcon \
  .venv/Scripts/python.exe -m y33bot check --config C:/Users/Lenovo/AppData/Local/hermes/cache/scratch/bug001-run/config.toml
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON main] FAIL 无法连接 127.0.0.1:25575: 连接 127.0.0.1:25575 超时（1.0s）
[日志 main] OK C:\Users\Lenovo\AppData\Local\hermes\cache\scratch\bug001-run\logs\latest.log 可读，偏移 0 字节
[绑定] OK 0 条
FAIL
exit=1
```

（`FAIL` / `exit=1` 来自 RCON 项——本机没有 MC 服，与本缺陷无关；关键是**凭据完全无效时 `[QQ] OK` 照样通过**。）

- 代码依据：`src/y33bot/service.py:87-93` 只调 `config.app_credentials()`；`src/y33bot/config.py:121-130` 只判"非空字符串"，
  **没有任何一次取 token / 探活**。
- 对照事实：同一份 `check` 的 **RCON 项是真连一次 `/list`**（`src/y33bot/service.py:115-119`）—— 也就是"部分项真探活、
  QQ 项不探活"这个不对称是实测出来的，不是推测。

#### 结论：**真缺陷**（代码结构上允许"静默失效"）

1. **离线把整条链条复现了**（不是推断）：`ret_coro=True` → SDK 自带的重连驱动不执行（`botpy/client.py:217-223`）→
   会话被回填后无人启动（`botpy/connection.py:57-67`）→ 网关协程**正常返回**（`src/y33bot/qq/gateway.py:132-138`：
   无异常 ⇒ 无日志）→ `Service.run()` 只等停止信号（`src/y33bot/service.py:205-221`）→ 进程常驻、日志干净。
   三个现象（群里无反应 / 无提示 / 进程还活着）**同时**被解释，且由 5 个新用例钉死。
2. **排除"设计如此"**：`IDEA.md` §4 的"不重试"只约束**单条消息**，并且已经被落实成"不重试但有 `[错误]` 痕迹"
   （`src/y33bot/qq/gateway.py:223-224`，用例 `tests/test_gateway.py:330`）；本条目「期望行为」里"**明确不接受**：进程常驻、
   无日志、无退出"在 `PLAN.md` 里找不到相反条款；`PLAN.md:145` 只说了"用 `ret_coro=True` 并发跑"，
   **没有**说明"因此放弃 SDK 的重连驱动、也不自己补" —— 属实现未覆盖的边界，不是有意的设计。
3. **排除"环境问题"**：token 刷新失败与发送失败都有痕（S1/S2/S3 + F6，用例 `tests/test_gateway.py:330`）；
   剩下的缺口全在我们自己的进程装配（F1–F3）上，与凭据是否有效、网络是否可达无关。

**边界（必须写在结论里）**：Q1、Q3 的**真机触发链路未验证**。本卡证明的是"**一旦网关协程结束（或从未真正在跑），
我们必然静默失守**"，没有证明"真机上 token 过期就一定触发它"。

#### 影响面

- **会中招**：任何让 SDK 网关协程结束或从未真正在跑的场景 —— 网络瞬断（`botpy/gateway.py:128-130` 的 `on_error` 路径）、
  QQ 主动关闭长连接（`:132` `on_closed`）、平台判鉴权失败（4004）、被踢下线/并发连接数超限、`bots.qq.com` 不可达，
  以及启动之后 SDK 自身异常退出的任何情况。中招后 **QQ→MC 方向永久失效**：收不到群消息，且不自愈、不告警、不退出。
- **不会中招**：启动阶段失败（`start()` 抛错 → `[错误] QQ 网关启动失败` + 返回 1，`src/y33bot/service.py:206-210`；
  真机样例 `README.md:281`）；发送方向的单条失败（每次都有 `[错误] QQ 发送失败（不重试）`，`src/y33bot/qq/gateway.py:223-224`）；
  日志轮询 / 健康轮询 / RCON 各自的故障（各有日志与状态翻转）。
- **"日志一行都不多"的确切条件（重要）**：发送方向**有痕**，所以最极端的"日志干净"版本要求静默期内**没有任何**
  MC→QQ 主动消息（MC 侧无进出、无聊天）。若静默期间 MC 侧有动静，会看到
  `[错误] QQ 发送失败（不重试）: …`，但用户看到的症状仍是"群里没反应 + 进程没退出"，因为不重试、不重启、不退出。
- **MC→QQ 方向同样不可靠**：SDK 自己的接口文档写明"发送消息接口要求机器人接口需要链接到 websocket gateway 上保持在线状态"
  （`botpy/api.py:1402`），所以网关死了以后 MC→QQ 大多也会失败（只是**有痕**）。

#### 推荐方向：**R2 + R5**（R4 作为可选增强；理由见疑点 4）

#### 本卡未做 / 留给下一张卡

- 真机三连（断网 10s / 重置 AppSecret / 等 token 过期）**未执行**，Q1、Q3 保持未执行；**建议修复卡落地后先真机复现一次再验证修复**
  （否则无法区分"修好了"与"没触发"）。
- `src/y33bot/**` 未改一行（`git diff --stat -- src` 为空），`IDEA.md`/`需求1.txt`/`PLAN.md` 未改；修复要另开卡并走 `PLAN.md` §7 登记。
- 用例数/覆盖率：本卡新增 5 例后 **357 passed、总覆盖率 99.30%**（门槛 70%），`ruff check .` 全过、`ruff format --check .`
  41 文件合规，`tests/` 无 skip/xfail（原为 352 passed；覆盖率不变）。
  `README.md:576`、`docs/smoke.md:250`、`docs/acceptance.md:38` 记的是 v0.2 轮次的 `352 passed`，**本卡未改**（它们是那一轮的实测记录）：
  若本卡的取证用例合入 `main`，需要一次文档同步 —— 建议由修复卡或后续文档卡一并做。

---

## 模板（新增条目照抄）

```markdown
## BUG-00N <一句话标题>

**状态**：疑似 / 已复现 / 已修复 / 设计如此
**登记日**：YYYY-MM-DD
**上报**：<谁在什么场景下发现>
**调查卡**：<看板 slug> / <task id>

### 现象
### 影响
### 环境
### 已核实的代码事实
| # | 事实 | 位置 |
### 待核实的疑点
### 复现步骤
### 期望行为
### 回复
```
