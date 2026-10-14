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
| [BUG-001](#bug-001-qq-token-过期后运行时静默失效运行期无任何提示) | QQ token 过期后运行时静默失效，运行期无任何提示 | **疑似**（调查中） | 2026-10-13 | 看板 `default` 的 BUG-001 调查卡（id 建卡后回填） |

---

## BUG-001 QQ token 过期后运行时静默失效，运行期无任何提示

**状态**：疑似（未复现，调查中）
**登记日**：2026-10-13
**上报**：用户（真机运行观察到，非 CI 用例）
**调查卡**：看板 `default` 的 BUG-001 调查卡（id 建卡后回填）—— 只调查、不改产品代码，结论写本条的「回复」
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

**待填**（由 BUG-001 调查卡写在下面「回复」小节；若确认是缺陷，修复**另开卡**并走 `PLAN.md` §7 登记）

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

（待填）

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
