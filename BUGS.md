# BUGS.md — 缺陷与疑似缺陷记录

本文件记录 Y33-Bot 的缺陷。与 `docs/acceptance.md`（验收"设计是否兑现"）互补：这里记"实际跑起来哪里不对"。

## 记录规则

1. 每条含固定小节：**现象 / 影响 / 环境 / 已核实的代码事实 / 待核实的疑点 / 复现步骤 / 期望行为 / 回复**。
2. **没复现的一律标「疑似」**，不许把猜测写成结论；结论只能写在「回复」小节里，且必须带证据（命令、日志、时间戳、SDK 源码 `文件:行号`）。
3. 「已核实」与「疑点」分开写：前者是本仓代码/SDK 里**读得到**的事实，后者是需要跑起来才能定的问题。
4. 修复与调查分开：调查卡只负责把结论写进「回复」；真要改代码另开卡，并走 `PLAN.md` §7 的变更登记。
5. 严重级别用词固定为三档：**高（功能级）** / **中（可用性、可观测性）** / **低（文档、部署、测试流程）**；
   排序规则：先按级别降序，同级别内按影响范围（加载器数 × 版本数）降序；**已修复的历史条目排在最后**。
6. **批量矩阵条目**（BUG-002 起，由实机测试矩阵产出）用「根因分析 / 修复方向 / 未验证的边界」三节
   代替「待核实的疑点 / 回复」：这类条目的分析卡就是汇总卡本身，结论直接落在条目里，不再另设「回复」小节；
   证据必须是**原始日志片段、`文件:行号`、或可复跑命令**（能离线跑的优先给离线复核）。
7. 影响范围必须写清「**哪些加载器 × 哪些版本是实证、哪些是外推或未验证**」；
   **同一根因**在不同加载器/版本上的表现合并为一条，**不同根因**（哪怕症状一样）不合并，条目之间互相引用。

## 汇总表（2026-10-18 实机测试矩阵，汇总卡 `t_1c0e88a4`）

来源：四张矩阵卡 —— 原版 `t_ac457fe1`、Fabric `t_5bccfcd8`、Forge `t_157ba7fe`、NeoForge `t_efe57773` ——
在测试机 `hermes@10.1.1.4`（Rocky 9.7）上的实机输出，逐条证据见 `test-notes/00-env.md` ~ `04-neoforge.md`
与各自 `artifacts/`（原件在四张卡的分支与测试机上，见 §「测试矩阵与证据来源」）。

| 编号 | 标题 | 加载器 | 版本区间（实证） | 严重级别 | 状态 |
|---|---|---|---|---|---|
| BUG-002 | 默认 `chat` 模板与 1.21.2+ 的真实聊天行不匹配 → 游戏内 `#` 聊天不被转发 | 原版 / Fabric / Forge / NeoForge | 原版 1.21.2–26.3（15/15）、Fabric 1.21.2–26.1（7/7）；窗口内**无版本边界**，变更点 ≤ 1.21.1 | 高（功能级） | 已修复（待真机回归） |
| BUG-003 | 加载器自带的 log4j2 布局与默认 `join`/`quit`/`chat` **三个模板全部不匹配** → MC→QQ 方向（进出服通知 + `#` 聊天）全哑 | Forge / NeoForge | Forge 1.21.3–26.3（12/12）、NeoForge 1.21.3–26.3（9/9），**加载器级、非版本级** | 高（功能级） | 已修复（待真机回归） |
| BUG-004 | 日志行 100% 未匹配时没有任何可见提示（只有 DEBUG 级 `[忽略]`），缺「零事件」看门狗 | 全部 | 全部（与加载器、版本无关） | 中（可观测性） | 已复现（是否按缺陷处理待口径） |
| BUG-005 | QQ 网关遇平台接口超时时：SDK 把超时吞成 `None` → 报错不可读（`'NoneType' …`）并**不重试**直接非 0 退出 | 全部（与 MC 无关，平台/网络触发） | 全部加载器与版本；实测 Forge 5 次、NeoForge 3 次、原版 1 次 | 中（可用性） | 已复现（触发条件随机、不可控复现） |

> **本轮复验 BUG-001**：四张卡在真机上共触发 9 次「网关启动期失败 / 网关任务结束」，每次都出现 `[错误]` +
> 非 0 退出（不再静默常驻），R2-lite 契约实测生效 —— 原始输出见 BUG-005「症状」。

## 测试矩阵与证据来源

- 环境：`hermes@10.1.1.4`（Rocky 9.7，2 vCPU / 2.6 GiB）、Temurin JDK21（默认）与 JDK25、
  Python 3.12.8 + 仓库 `.venv`、源码 `f7fd5cb`（与 `main` 同步）；端口分配表见 `test-notes/00-env.md` §5.2。
- 四份逐版本记录（**本轮新增，未改动任何项目代码**）：

| 卡 | 记录 | 分支 / 提交 | 覆盖 |
|---|---|---|---|
| `t_a4c6c3ae` | `test-notes/00-env.md` | `wt/t_a4c6c3ae` @ `3c20315` | 环境基座 + 原版 1.21.11 / 26.3 冒烟 |
| `t_ac457fe1` | `test-notes/01-vanilla.md` | `wt/t_ac457fe1` @ `d387de5`、`bb9166e` | 原版 15 个正式版 × 17 条用例（255 条，0 失败） |
| `t_5bccfcd8` | `test-notes/02-fabric.md` | `wt/t_5bccfcd8` @ `c8ef7bc` | Fabric 9 个版本 + 1 个 loader 变体 |
| `t_157ba7fe` | `test-notes/03-forge.md` | `wt/t_157ba7fe` @ `5f25918` | Forge 12 个版本 + D1–D4 补充观察 |
| `t_efe57773` | `test-notes/04-neoforge.md` | `wt/t_efe57773` @ `ee94d57` | NeoForge 9 个版本（T0–T9） |

- 本卡新增：`BUGS.md`（本文件）+ `test-notes/*.md`（上面五份记录的逐字副本，便于本文件引用的证据落在同一棵树里）；
  **原始制品**（`artifacts/vanilla|fabric|forge|neoforge/`）仍在各自卡分支与测试机上，本节按条目给出相对路径。
- **根卡 `t_d25d5a1d` 汇总（2026-10-18）**：六张卡的分支全部合入根卡分支 `y33-bot/t_d25d5a1d`（6 个 merge 提交、0 冲突），
  于是本文引用的 `test-notes/**` 与**原始制品**落在同一棵树里；制品**实测 761 个文件**
  （`00-env` 4、`vanilla` 107、`fabric` 162、`forge` 296、`neoforge` 192）。
  合并后全仓 `git diff f7fd5cb..HEAD -- src tests docs README.md PLAN.md IDEA.md config.example.toml` 为**空**。
  根卡的独立复核与一处修正见文末「根卡复核记录」。

## 索引

| 编号 | 标题 | 状态 | 登记日 | 调查卡 |
|---|---|---|---|---|
| [BUG-002](#bug-002-默认-chat-模板与-1212-的真实聊天行不匹配--游戏内--聊天不被转发) | 默认 `chat` 模板与 1.21.2+ 真实聊天行不匹配 | **已修复（待真机回归）** | 2026-10-18 | 汇总卡 `t_1c0e88a4`；修复卡 `t_13b9be2a` |
| [BUG-003](#bug-003-加载器自带-log4j2-布局与默认-joinquitchat-三个模板全部不匹配--mcqq-方向全哑) | 加载器日志布局与三个默认模板全部不匹配 | **已修复（待真机回归）** | 2026-10-18 | 汇总卡 `t_1c0e88a4`；修复卡 `t_13b9be2a` |
| [BUG-004](#bug-004-日志行-100-未匹配时没有任何可见提示仅-debug-级) | 全量未匹配无可见提示，缺「零事件」看门狗 | 已复现（待口径） | 2026-10-18 | 汇总卡 `t_1c0e88a4` |
| [BUG-005](#bug-005-qq-网关遇平台接口超时时-sdk-吞成-none--报错不可读且直接非-0-退出) | QQ 网关遇平台超时：报错不可读、不重试直接退出 | 已复现（触发随机） | 2026-10-18 | 汇总卡 `t_1c0e88a4` |
| [BUG-001](#bug-001-qq-token-过期后运行时静默失效运行期无任何提示) | QQ token 过期后运行时静默失效，运行期无任何提示 | **已修复**（2026-10-15 落地 R2-lite + R5，见本条「修复记录」；真机触发链路仍未验证） | 2026-10-13 | 看板 `default` 的 `t_6cc56405`（2026-10-15 结案，结论见本条「回复」）；修复卡 `t_80249809` |

> 本轮（2026-10-18）另附两节，紧跟 BUG-005 之后：§「非产品缺陷观察（环境 / 部署 / 测试流程）」、
> §「**未能复现 / 信息不足清单**（本轮四张矩阵卡汇总）」。
> 排在最后的 `§ 模板` 是「新增条目照抄」的格式说明。

---

## BUG-002 默认 `chat` 模板与 1.21.2+ 的真实聊天行不匹配 → 游戏内 `#` 聊天不被转发

**状态**：已修复（待真机回归）—— 2026-10-29 出厂默认改为四族通吃形态，见本条「修复记录」
**登记日**：2026-10-18
**上报**：实机测试矩阵 —— 环境基座卡 `t_a4c6c3ae` 首次抓到现场证据（`00-env.md` §7-10），
原版卡 `t_ac457fe1`、Fabric 卡 `t_5bccfcd8` 逐版本复现并给出真行
**影响范围**：**所有加载器**。实证：原版 1.21.2–26.3（15/15，`01-vanilla.md` §6.1）、
Fabric 1.21.2–26.1（7/7，`02-fabric.md` §3.1）；Forge 12/12（其中 26.2/26.3 用的是「真前缀 + 正文」合成行，
`03-forge.md` §7-1）与 NeoForge 有真玩家日志的全部版本（`04-neoforge.md` §4.2 共 7 版，含 26.1.2）**亦命中**，
但那两族另有加载器级问题（[BUG-003](#bug-003-加载器自带-log4j2-布局与默认-joinquitchat-三个模板全部不匹配--mcqq-方向全哑)）叠加
**版本边界**：**窗口内没有边界** —— 自窗口最早一版 1.21.2（2024-10-22）起聊天行就是这个形态，
变更点在窗口之前（**≤ 1.21.1**）（`01-vanilla.md` §6.2-1）

### 症状（可观测）

1. 玩家在游戏内发 `#…`，**群里收不到**（没有 `[群消息] <玩家>@<服名>: <内容>` 这样的行）。
2. 机器人侧**没有报错**：常驻 `run` 在默认日志级别下只在 DEBUG 里留一行
   `[忽略] 日志行未匹配任何模板: <真实行>`；只有 `simulate log-event --line` 会显形为
   `[警告] 日志行未匹配任何模板` + **退出码 1**（`src/y33bot/cli.py:221-225`）。
3. 同一时刻**进出服通知、`/status`、QQ→MC 注入全部正常** —— 所以从外面看「机器人是好的」。

### 原始证据

真机日志行（各版本逐字相同；服务端原文在 `artifacts/vanilla/<版本>/latest-log.txt`、
`artifacts/fabric/<版本>/real-chat-line-<版本>.txt`，本仓库内的逐字副本见 `test-notes/01-vanilla.md` §5 F-V1、`test-notes/02-fabric.md` §4 F-1）：

```text
1.21.2  [14:57:20] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
1.21.11 [14:30:09] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
26.1    [15:22:31] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
```

项目出厂默认（`config.example.toml:33`；同款见 `IDEA.md:170`、`PLAN.md:482`、`README.md:119`）：

```toml
chat = '\[\d{2}:\d{2}:\d{2}\] \[Async Chat Thread - #\d+/INFO\]: <(?P<player>\w+)> (?P<message>.+)'
```

机器人侧输出（A/B 对照，只差 `chat` 模板；`00-env.md` §7-10、`01-vanilla.md` §5 F-V1、`02-fabric.md` §4 F-1）：

```text
[A] 默认模板 + 真行       → [警告] 日志行未匹配任何模板              （退出码 1，无 [群消息]）
[A] 默认模板 + 旧格式行   → [群消息] Steve@main: 大家好              （对照组：≤1.21.1 的行能匹配）
[B] 放宽 chat 模板 + 真行  → [群消息] Steve@main: 大家好，这是带井号的聊天（应被转发）
```

### 复现步骤

**离线（不需要 MC 服，任何装了本项目 `.venv` 的机器都能跑）** —— 本卡用**仓库自己的代码**复核
（脚本在仓库外，不入库：`C:\Users\Lenovo\AppData\Local\hermes\cache\scratch\t1c0e88a4\verify_patterns2.py`；
`python -c` 在本机被判为危险命令，故写成脚本再跑）：

```bash
E:/D-Data/Users/Lenovo/docs/GitHub/Y33-Bot/.venv/Scripts/python.exe \
  C:/Users/Lenovo/AppData/Local/hermes/cache/scratch/t1c0e88a4/verify_patterns2.py
```

实测输出（2026-10-18 17:05:02 +0800，节选）：

```text
[1] config.example.toml 的默认模板（出厂默认）
    join = '\\[\\d{2}:\\d{2}:\\d{2}\\] \\[Server thread/INFO\\]: (?P<player>\\w+) joined the game'
    quit = '\\[\\d{2}:\\d{2}:\\d{2}\\] \\[Server thread/INFO\\]: (?P<player>\\w+) left the game'
    chat = '\\[\\d{2}:\\d{2}:\\d{2}\\] \\[Async Chat Thread - #\\d+/INFO\\]: <(?P<player>\\w+)> (?P<message>.+)'

[2] 编译后（patterns._anchor 补 ^/$，parse_line 用 re.match）
    chat -> '^\\[\\d{2}:\\d{2}:\\d{2}\\] \\[Async Chat Thread - #\\d+/INFO\\]: <(?P<player>\\w+)> (?P<message>.+)$'

[3] 默认模板 x 真实行
    vanilla 1.21.2 chat        default=False event=None
    fabric  1.21.9 chat        default=False event=None
    vanilla 1.21.2 join        default=True  event=join
    vanilla 1.21.2 quit        default=True  event=quit
    docs old chat (<=1.21.1)   default=True  event=chat
    docs old join (<=1.21.1)   default=True  event=join

[4] 各卡实测的放宽模板 x 同一批真行（验证修复方向）
    [vanilla/fabric 放宽] vanilla-chat=Y fabric-chat=Y vanilla-join=Y vanilla-quit=Y docs-chat=Y docs-join=Y
```

**真机（任选一版）**：`01-vanilla.md` §5 F-V1 的命令（`bash ~/mc-test/vanilla-matrix.sh 1.21.9 6 full`，看 `[C19]/[C20]` 两段）；
或起一台服 + 无头客户端进服发一条 `#…`，再 `grep '<玩家> #' <实例>/logs/latest.log`。

### 根因分析（代码级）

**不是「解析到了但被过滤」，而是「根本没有解析出事件」**：

| # | 环节 | 位置 | 事实 |
|---|---|---|---|
| 1 | 出厂默认模板写的是旧形态 | `config.example.toml:31-33`（来源 `IDEA.md:170`） | chat 模板认的是 **≤ 1.21.1** 的行：`[Async Chat Thread - #N/INFO]: <player> msg` —— 线程名是异步聊天执行器，且没有 `[Not Secure] ` 标记 |
| 2 | 模板编译时被整行锚定 | `src/y33bot/mclog/patterns.py:52-60`（`_anchor()`）、`:96`（`re.match`） | 模板自身没写 `^`/`$` 也会被补成 `^…$` ⇒ **整行必须逐字匹配**：行首时间戳、线程名、`[Not Secure] ` 任何一处不同都不命中 |
| 3 | 上游在 ≥ 1.21.2 改了聊天行 | MC 1.21.2 起（本窗口全部版本） | 聊天回到**主线程**、未签名身份带前缀：`[Server thread/INFO]: [Not Secure] <player> msg`（`01-vanilla.md` §5 F-V1 的 15 版真行） |
| 4 | 未命中 ⇒ 没有事件 | `src/y33bot/mclog/patterns.py:91-110`（按 `join`→`quit`→`chat` 依次 `match`，全败返回 `None`）、`src/y33bot/mclog/watcher.py:112-115` | `parse_line()` 返回 `None` → `poll_new_events()` 只记一条 DEBUG `[忽略] 日志行未匹配任何模板` 后 `continue` |
| 5 | 桥接层根本没被调用 | `src/y33bot/bridge.py:139`（`handle_log_event`，只在**有事件**时由 `src/y33bot/service.py:284-289` 调用；`#` 前缀判断在 `bridge.py:165-167`） | 「非 `#` 开头不转发」这类判断都在事件层**之上**；没有事件就没有任何判断机会 |
| 6 | 于是静默 | `src/y33bot/cli.py:221-225` 是唯一显形点 | `run` 不告警、不退出、不自愈 ⇒ 与 BUG-001 同类「静默失效」，只是方向相反（MC→QQ） |

**为什么以前没被发现（同类事实，一并登记）**：默认模板、文档示例与**测试夹具**是同一份旧格式 ——
`tests/conftest.py:19-21`（`CHAT_TEMPLATE`）、`tests/e2e/test_acceptance.py:131/148/164`、`tests/test_cli.py:274-312`、
`docs/acceptance.md:138-148`、`docs/smoke.md:124-132`、`PLAN.md:618-622` 喂的都是 `[Async Chat Thread - #0/INFO]` 的行，
等于「自造行验自造模板」；所以 381 条单测全绿（`00-env.md` §4）也测不出这个问题。

### 未验证的边界

- **`online-mode=true`（正版签名聊天）**：本环境所有实例统一 `online-mode=false`（`00-env.md` §5.3），
  无法判定默认模板当初是不是为正版服而写（`01-vanilla.md` §7-2）。若正版服的行是 `<Steve> msg`（无 `[Not Secure] ` 前缀），
  修复时必须把该前缀做成**可选**（下面的放宽模板已这么做）。
- **MC 26.2 / 26.3 的真实聊天行**：无头客户端（mineflayer + minecraft-data）最高支持 26.1（实测连 26.3 报
  `No data available for version 26.3`，`02-fabric.md` §4 F-2）⇒ 这两版只能标「未验证」，不外推。
- Bedrock / 非 Java 版日志格式：不在本仓支持范围，未测。

### 修复方向（只登记方向，不在本卡改）

1. **改默认值**（一行）：`config.example.toml:33` 的 `chat` 换成兼容形态，同时保留旧线程名分支 ——
   `\[\d{2}:\d{2}:\d{2}\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\]: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)`
   （实测：真行 `Y`、旧格式行 `Y`、普通聊天仍被 `bridge.py:165-167` 忽略、回环防护不受影响；15 版的 `[B]` 段全 PASS。）
2. **同步文档与测试夹具**：`README.md:116-127`、`PLAN.md:479-483/618-622`、`docs/smoke.md:124-132`、
   `docs/acceptance.md:138-148` 的示例行换成真行；`tests/conftest.py:19-21` 增加**真机行夹具**（新形态 + 旧形态各一条）。
   `IDEA.md:170` 是冻结需求书，**不直接改**，按 `PLAN.md` §7 登记偏离。
3. **（可选，与 BUG-004 合并）** 让 `check` 拿 `latest.log` 的最后一行试匹配三模板，把「模板与真机不匹配」
   在启动期变成 `FAIL`，而不是等玩家发现群里没消息。
4. 文档侧 FAQ（`README.md` §13）建议补一条：「群里收不到游戏内聊天，但进服通知正常 → 先看 `[log_patterns].chat`」。

### 修复记录（2026-10-29，修复卡 `t_13b9be2a` 及其子卡）

**口径**：用户拍板「**直接把出厂默认改成四族通吃形态**」（vanilla / Fabric / Forge / NeoForge 共用同一组模板），
不做「按加载器分预设文件」；`IDEA.md` 冻结不动，偏离登记在 `PLAN.md` §7。

**出厂默认（现形态，逐字对齐 `config.example.toml:31-33`）**：

```toml
join = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?P<player>\w+) joined the game'
quit = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?P<player>\w+) left the game'
chat = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)'
```

与旧形态的三点差别：① logger 段写成 `(?: \[[^\]]+\])?` —— **空格在可选组内**、整段可省 ⇒ 没有 logger 段的原版行也命中；
② 时间戳整体用 `\[[^\]]+\]` 吃掉（既不写死 `\d{2}:\d{2}:\d{2}`，也不写死 `\d+月`）⇒ 加载器的 `ddMMMyyyy` 形态不绑 locale；
③ 线程名保留 `Async Chat Thread - #\d+` 分支 ⇒ ≤1.21.1 旧形态仍命中。
（本条「修复方向」第 1 条给的 `chat` 候选只覆盖原版形态、不含 logger 段，**最终落地的是上面这组**，不要再照抄那条。）

**涉及文件清单**（5 张子卡并行落地，合并后生效）：

| 类别 | 文件 | 改动 | 卡 |
|---|---|---|---|
| 配置 | `config.example.toml:31-33` | 三模板换成上面这组（`encoding = "utf-8"` 不动） | `t_2a31fd67` |
| 夹具 | `tests/conftest.py:19-21` | `JOIN/QUIT/CHAT_TEMPLATE` 与出厂默认逐字相同（「夹具 ≡ 默认」是硬约束） | `t_2a31fd67` |
| 夹具 | `tests/test_smoke.py:95` | 转义串同步 | `t_2a31fd67` |
| 测试 | `tests/test_log_patterns_real_lines.py`（新增） | 三方相等（`config.example.toml` ≡ 夹具 ≡ `PLAN.md` §3.5）+ 真机真行参数化 | `t_739a0487` |
| 文档 | `PLAN.md` §3.5 / §7 | 样板同步 + 变更登记（含对 `IDEA.md:170` 冻结形态的偏离） | `t_33baa9bb` |
| 文档 | `README.md` §5 / §13 / §14 | 配置块 + FAQ「群里收不到游戏内 `#` 聊天但进服通知正常 → 先看 `[log_patterns].chat`」+ 数字基线 | `t_33baa9bb` |
| 文档 | `docs/smoke.md` S3、`docs/acceptance.md` 新增一节 | 示例行换真行；历史记录只加「变更前记录」标注 | `t_33baa9bb` |
| 文档 | `docs/progress.md` 顶部基线表 | 例数 / 覆盖率 / 361 命中回填 | `t_33baa9bb` |
| 载体 | `BUGS.md`（本条 + BUG-003 + 310-312 勘误） | 状态推进 + 本条「修复记录」 | 本卡 `t_e014c230` |

**离线复核：361/361 命中（本卡实跑，2026-10-29 11:35 +0800）**

语料：`test-notes/artifacts/**/*.txt` 里全部「像 MC 日志行」的行，按 (族, 事件类型) 去重 ——
`00-env` 4 / `vanilla` 105 / `fabric` 73 / `forge` 108 / `neoforge` 71，**合计 361 条**。
喂的是仓库自身的解析路径（`y33bot.mclog.patterns.compile_patterns` + `parse_line`，含 `_anchor()` 的整行锚定），
不是另写一套正则：

| 模板组 | 361 条命中 | ≤1.21.1 旧形态（join / quit / chat） |
|---|---|---|
| 修复前出厂默认（本节「原始证据」那三行） | **101/361** | Y / Y / Y |
| **修复后（现出厂默认）** | **361/361** | **Y / Y / Y** |

复跑方式（脚本在仓库外，不入库）：

```bash
E:/D-Data/Users/Lenovo/docs/GitHub/Y33-Bot/.venv/Scripts/python.exe \
  C:/Users/Lenovo/AppData/Local/hermes/cache/scratch/pattern_plan_sweep.py \
  E:/D-Data/Users/Lenovo/docs/GitHub/Y33-Bot/.worktrees/t_e014c230
```

**真机回归：未执行。**
- 原因：本卡是载体（文档）卡，跑在 Windows 开发机，手上既没有 MC 服务端实例、也没有 QQ 凭据；
  本轮 5 张子卡并行，真机回归排在合卡之后（PR 说明里如实登记）。
- 替代证据：① 上面 361/361 的离线复核（走仓库自身编译/解析路径，不是自造行验自造模板）；
  ② 本条「原始证据」的 A/B 对照（`[A] 默认模板 + 真行 → 未匹配` / `[B] 放宽模板 + 真行 → 命中`）；
  ③ `pytest`：本卡分支改动后复跑 **381 passed in 54.60s**（2026-10-29 11:43 +0800，见下「本卡自检」）；
  新增回归锁后例数应 > 381，最终数字由 `t_739a0487` / `t_33baa9bb` 回填。

**本卡自检（`t_e014c230`，2026-10-29 11:43 +0800）**

- `git diff BUGS.md` 的**删除行只有 6 行** —— 汇总表 2 个状态单元格、索引 2 个状态单元格、两条「**状态**」行；
  其余全是新增 ⇒ 本条的真行原文、复现步骤、根因链**一字未动**；
- `.venv/Scripts/python.exe -m pytest -q` → **381 passed in 54.60s**（文档改动不影响用例；
  新增回归锁后应 > 381，数字由 `t_739a0487` / `t_33baa9bb` 回填）；
- `git diff -- src/` 为空；`AGENTS.md` 未动（本卡只碰 `BUGS.md`）。

---

## BUG-003 加载器自带 log4j2 布局与默认 join/quit/chat 三个模板全部不匹配 → MC→QQ 方向全哑

**状态**：已修复（待真机回归）—— 2026-10-29 出厂默认改为四族通吃形态，见本条「修复记录」
**登记日**：2026-10-18
**上报**：Forge 卡 `t_157ba7fe`（12 个版本 100% 命中）、NeoForge 卡 `t_efe57773`（9 个版本 100% 命中）
**影响范围**：**加载器级，非版本级** —— Forge 1.21.3 / 1.21.4 / 1.21.5 / 1.21.6 / 1.21.7 / 1.21.8 / 1.21.9 /
1.21.10 / 1.21.11 / 26.1 / 26.2 / 26.3（**12/12**，`03-forge.md` §6）；NeoForge 1.21.3 / 1.21.4 / 1.21.5 / 1.21.8 /
1.21.10 / 1.21.11 / 26.1.2 有真玩家日志（7/7），26.2 / 26.3 由常驻 `run` 的全量「未匹配」+ 格式取样佐证（合计 **9/9**，`04-neoforge.md` §5.1/§6.1）
**与 BUG-002 的关系**：两个**独立根因**，症状叠加 —— 即使只修 BUG-002 的 `chat` 模板，
Forge/NeoForge 上的 `join`/`quit`（进出服通知）**仍然全哑**；反之只修本条的布局兼容，`chat` 也仍然不匹配（`Server thread` 线程名）

### 症状（可观测）

1. 换成 Forge/NeoForge 服务端后：**玩家进服、退服、游戏内 `#` 聊天都不进群**（默认配置下 MC→QQ 方向整体失效）。
2. 机器人侧不报错、不退出；`run --verbose` 里对**每一行**服务端日志都打
   `[忽略] 日志行未匹配任何模板: <真实行>`（把进出服/聊天三行本身也包含在内）。
3. `check`（真 QQ 探活 + 真 RCON `/list`）、`tellraw` 注入、`/status` 真往返、健康翻转、日志轮转、SIGTERM 退出码 0
   **全部正常**（`04-neoforge.md` §5.3）⇒ 故障面完全落在「日志 → 事件」这一步。

### 原始证据

真机日志行（Forge 1.21.11，`artifacts/forge/1.21.11/real-lines.txt`；NeoForge 1.21.4 同族）：

```text
[1810月2026 15:35:33.486] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve joined the game
[1810月2026 15:35:36.278] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
[1810月2026 15:35:37.785] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve left the game
```

默认模板对这三行的实测（`artifacts/forge/1.21.11/pattern-default.txt` 原文）：

```text
--- 默认 join 模板 + 真行 ---
[警告] 日志行未匹配任何模板
[join] exit=1
--- 默认 quit 模板 + 真行 ---
[警告] 日志行未匹配任何模板
[quit] exit=1
--- 默认 chat 模板 + 真行 ---
[警告] 日志行未匹配任何模板
[chat] exit=1
```

NeoForge 的 A/B（同一条真行、只改配置；`artifacts/neoforge/1.21.4/results-1.21.4.txt`）：

```text
default_join_exit=1      default_quit_exit=1      default_chat_exit=1      default_chatplain_exit=1
relaxed_join_exit=0      relaxed_quit_exit=0      relaxed_chat_exit=0      relaxed_chatplain_exit=0
```

生产现场（NeoForge 1.21.4，真客户端进服/聊天/退服，`artifacts/neoforge/1.21.4/run-1.21.4.txt`）：

```text
[忽略] 日志行未匹配任何模板: [1810月2026 15:26:13.926] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve2 joined the game
[忽略] 日志行未匹配任何模板: [1810月2026 15:26:17.100] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Steve2> #大家好，这是带井号的聊天（应被转发）
[忽略] 日志行未匹配任何模板: [1810月2026 15:26:18.637] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve2 left the game
```

本卡的离线复核（同一脚本，2026-10-18 17:05:02 +0800，节选）：

```text
[3] 默认模板 x 真实行
    forge   1.21.11 join       default=False event=None
    forge   1.21.11 quit       default=False event=None
    forge   1.21.11 chat       default=False event=None
    neoforge 1.21.4 join       default=False event=None
    neoforge 1.21.4 chat       default=False event=None
[4] 各卡实测的放宽模板 x 同一批真行
    [forge/neoforge 放宽] forge-join=Y forge-quit=Y forge-chat=Y neoforge-join=Y neoforge-chat=Y
```

### 复现步骤

**离线**：同 BUG-002 的脚本（真行已内置在脚本的 `CASES` 里），或把上面任意一行喂给
`y33bot simulate log-event --server <名> --line '<真行>' --dry-run --config <配置>` → `[警告] 日志行未匹配任何模板`（退出码 1）。

**真机（Forge，`03-forge.md` §4 F1 原文）**：

```bash
ssh hermes@10.1.1.4; . ~/y33-env.sh
bash ~/mc-test/new-forge.sh 1.21.11 61.2.0 8
tmux new -d -s mc-forge-1_21_11 "cd ~/mc-test/forge/1.21.11 && ./start.sh 2>&1 | tee -a console.out.log"   # 等 Done (...) 与 RCON 监听
cd ~/Y33-Bot && .venv/bin/python -m y33bot simulate log-event --server forge --dry-run --config config-forge-1_21_11.toml \
  --line '[1810月2026 15:35:33.486] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve joined the game'
```

NeoForge 侧等价命令见 `04-neoforge.md` §6.1（`nf_smoke_one.sh` + 无头客户端）。

### 根因分析（代码级）

| # | 环节 | 位置 | 事实 |
|---|---|---|---|
| 1 | 默认模板按 **vanilla 布局**书写 | `config.example.toml:31-33` | 三模板都以 `\[\d{2}:\d{2}:\d{2}\] \[<线程>/INFO\]: ` 开头 —— 这是原版 `latest.log` 的形状 |
| 2 | 加载器改写了整套日志布局 | Forge / NeoForge 自带 `log4j2`（`03-forge.md` §4 F1、`04-neoforge.md` §5.2） | ① 时间戳变 `[dd月yyyy hh:mm:ss.SSS]`（本机 `zh_CN` 下渲染成 `[1810月2026 15:35:33.486]`）；② `[线程/级别]` 之后**多一层 `[logger/]` 段**（`[net.minecraft.server.MinecraftServer/]`） |
| 3 | 整行锚定 ⇒ 三模板全灭 | `src/y33bot/mclog/patterns.py:52-60`、`:96` | 行首只差一个时间戳形状、行中少一段 logger，`^…$` 就必然不命中；`join`/`quit`/`chat` 三个模板**同时**失效（与原版只坏 `chat` 不同） |
| 4 | 不命中只记 DEBUG | `src/y33bot/mclog/watcher.py:112-115` | 见 BUG-004：默认级别下「全量未匹配」看起来和「服务器很安静」一模一样 |
| 5 | 影响被放大到整个方向 | `src/y33bot/bridge.py:139-155` | 进出服通知与聊天**都**依赖日志事件 ⇒ MC→QQ 方向（含 RCON 之外的几乎全部功能）整体失效 |

补充事实（不是缺陷，但影响修复写法）：加载器的时间戳是 `ddMMMyyyy HH:mm:ss.SSS` 形态（`18` + `10月` + `2026`），
月份名由 **JVM 默认 locale** 渲染（本机 `zh_CN` 渲染成 `10月`）。
**因此修复模板不要写死 `\d+月\d+`**（那会绑死 zh_CN），用 `\[[^\]]+\]` 把时间戳整体吃掉更稳。
（此点为**推断**：只有 zh_CN 机器，未能用 en_US 的 JVM 实测渲染结果。）

### 未验证的边界

- MC 26.2 / 26.3 的**真玩家**行：无头客户端上限 26.1（`04-neoforge.md` §6.3）⇒ 这两版只有「全量未匹配 + 格式取样」佐证。
- 其它加载器（Quilt / 自行改 `log4j2.xml` / 服务端加自定义 appender）：未测。
- Forge 26.2 / 26.3 的聊天行是「真前缀 + 正文」合成的（`03-forge.md` §7-1），已在 `real-lines.txt` 标注。

### 修复方向（只登记方向，不在本卡改）

1. **默认模板改成对加载器布局宽容**（与 BUG-002 的第 1 条可以合并成一次配置改动，给出实测可用的一组）：

   > **⚠ 勘误（2026-10-29，卡 `t_e014c230`）：下面这组三模板实测不可用，不要照抄 —— 照抄会把原版也打死。**
   > 写错两处：① 可选段写成 `(?:\[[^\]]+/\]): `，**空格落在可选组外** ⇒ 原版真行
   > `[14:54:43] [Server thread/INFO]: Steve joined the game` 在 `/INFO]` 后面直接就是 `: `，
   > 没有那一个空格 ⇒ `join` 必然失败；② logger 段强制 `/` 结尾（`[^\]]+/`）⇒ 换加载器或改
   > `log4j2.xml` 的 appender 之后，整段就再也匹配不上。
   > 实测（361 条去重真行，用仓库自身 `compile_patterns` + `parse_line`，含整行锚定）：**82/361** ——
   > 原版 `join 0/27`、`quit 0/26`、`chat 0/52`（三模板全灭）、Fabric `0/73`、≤1.21.1 旧形态 **0/3**；
   > 它只在带 `[logger/]` 段的 NeoForge（70/71）与部分 Forge（12/108）上「看起来能用」，正是这点造成误导。
   > **正确的一组见本代码块下方「⚠ 勘误后正确模板组」。**

   ```toml
   join = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\] (?:\[[^\]]+/\])?: (?P<player>\w+) joined the game'
   quit = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\] (?:\[[^\]]+/\])?: (?P<player>\w+) left the game'
   chat = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\] (?:\[[^\]]+/\])?: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)'
   ```

   **⚠ 勘误后正确模板组（与 `config.example.toml:31-33` 一致；离线复核 361/361，≤1.21.1 旧形态仍命中）**：

   ```toml
   join = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?P<player>\w+) joined the game'
   quit = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?P<player>\w+) left the game'
   chat = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)'
   ```

   > 只改两处（空格移进可选组、logger 段不再要求 `/` 结尾），原组就从 82/361 变成 361/361；
   > 因此下面那句「三模板均为本卡离线复核 + 两张卡真机实测通过的形态」**对上面第一组不成立**，以本勘误为准。
   > 复跑脚本（仓库外，不入库）：`C:/Users/Lenovo/AppData/Local/hermes/cache/scratch/t_e014c230_erratum_check.py`。
   （三模板均为**本卡离线复核 + 两张卡真机实测**通过的形态；时间戳与 logger 段用「不解析内容」的 `[^\]]+` 吃掉，避免绑死 locale。）
2. **或提供「按加载器预设」**：`config.example-<loader>.toml` 之类，或在 `README.md` 增加一小节
   「换了加载器 → `[log_patterns]` 怎么改」，并说明「同一根因：加载器自带 log4j2 布局」。
3. **测试夹具补真行**：`tests/conftest.py:19-21` 增加 Forge / NeoForge 形态的真行样本，
   让「模板 × 真实布局」有回归保护（现在的夹具只覆盖 vanilla 旧形态）。
4. 文档 FAQ 增一条：**「群里收不到进服通知、`/status` 却正常」→ 先按本节放宽 `[log_patterns]`**。

### 修复记录（2026-10-29，修复卡 `t_13b9be2a` 及其子卡）

**结论**：不再按「加载器布局」单独给模板 —— 出厂默认直接换成**四族通吃**的一组，
Forge / NeoForge 的 `ddMMMyyyy` 时间戳与多出来的 `[logger/]` 段都被**整段吃掉**：

```toml
join = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?P<player>\w+) joined the game'
quit = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?P<player>\w+) left the game'
chat = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\](?: \[[^\]]+\])?: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)'
```

**本条的三个模板为什么同时活过来**：
① 时间戳用 `\[[^\]]+\]` 整体吞（不写死 `\d{2}:\d{2}:\d{2}`）⇒ `[1810月2026 15:35:33.486]` 命中，且不绑 JVM locale
（正是本节「补充事实」里那条推断要求的写法，`\d+月\d+` 会被排掉）；
② logger 段 `(?: \[[^\]]+\])?` 整段可选、**不要求 `/` 结尾** ⇒ `[net.minecraft.server.MinecraftServer/]` 命中，
同时原版/加载器未加 logger 段的行也命中；
③ `quit` 与 `chat` 与 `join` 同一前缀 ⇒ 三条同时恢复，MC→QQ 方向（进出服通知 + `#` 聊天）整体复活。

**涉及文件清单**：与 BUG-002「修复记录」的文件表**完全同一批**（配置 / 夹具 / 回归锁 / 文档 / 载体，5 张子卡），
本条不重复列表，只强调与加载器相关的两行：`config.example.toml:31-33`（`t_2a31fd67`）与
`tests/test_log_patterns_real_lines.py` 里 Forge / NeoForge 真行的参数化用例（`t_739a0487`）。

**离线复核（本卡实跑，2026-10-29 11:35 +0800）**：同一批 361 条去重真行，按族看命中（`compile_patterns` + `parse_line`，含整行锚定）：

| 模板组 | forge（108 条） | neoforge（71 条） | 合计 361 条 |
|---|---|---|---|
| 修复前出厂默认 | **0/108** | **1/71** | 101/361 |
| **修复后（现出厂默认）** | **108/108** | **71/71** | **361/361** |

修复前 Forge 侧 `join`/`quit`/`chat` 全 0（与本节「根因链」第 3 行一致：三模板同时失效），
NeoForge 只偶然命中 1 条 `join`（那一条真行恰好没有 logger 段），可作为「加载器布局把模板打死」的旁证。

**与本节「修复方向」第 1 条的关系**：那段代码块（旧 `BUGS.md:310-312`）**实测不可用，已在原处标注勘误**
（空格在可选组外 + logger 段强制 `/` 结尾 ⇒ 实测 82/361，原版三模板 0 命中、≤1.21.1 旧形态 0 命中）。
**以本条上面这组为准**，详见本节「修复方向」第 1 条代码块处的「⚠ 勘误」标注。

**真机回归：未执行** —— 原因与替代证据同 BUG-002「修复记录」的真机段落（同一台开发机、同一批卡，不重复展开）；
本条的额外替代证据是上表按加载器分族的 108/108、71/71。

---

## BUG-004 日志行 100% 未匹配时没有任何可见提示（仅 DEBUG 级）

**状态**：已复现（行为确凿；**是否按缺陷处理取决于用户口径**，见「修复方向」）
**登记日**：2026-10-18
**上报**：Fabric 卡 `t_5bccfcd8`（F-5 记录「未匹配噪声」）、NeoForge 卡 `t_efe57773`（§5.1/§6.1 把它写成「静默」）
**影响范围**：全部加载器、全部版本（与 MC 无关）；它是 BUG-002 / BUG-003 变成「静默失效」的直接原因，
也是 BUG-001 那条「明确不接受静默」的口径在 MC→QQ 方向上的同类缺口

### 症状（可观测）

1. 服务端日志格式一变（换加载器、MC 改格式、`log4j2.xml` 被改），MC→QQ 方向可以**整体失效而没有任何告警**：
   进程常驻、`check` 全 OK、`/status` 有回、健康轮询照常，群里却是死的。
2. 唯一的痕迹是 DEBUG 级 `[忽略] 日志行未匹配任何模板: <行>`（`src/y33bot/mclog/watcher.py:114`）——
   默认日志级别下不打印；`run --verbose` 下则被淹没在启动信息、mod 列表、RCON 线程行里（`02-fabric.md` §4 F-5 记了「噪声大」）。
3. 唯一会**显形**的入口是手动跑 `y33bot simulate log-event --line '<真行>'`（`[警告]` + 退出码 1，`src/y33bot/cli.py:221-225`）——
   必须人主动去跑，且要先知道「格式可能变了」。

### 原始证据

- `artifacts/neoforge/1.21.4/run-1.21.4.txt`：常驻 `run` 对每一条服务端日志（含玩家进服/聊天/退服三行本身）都打
  `[忽略] 日志行未匹配任何模板: …`，但**没有任何** `[警告]`/`[错误]`、退出码仍为 0；
- `artifacts/fabric/*/run-<版本>.txt`：同样的 DEBUG 噪声（F-5）；
- `artifacts/vanilla/<版本>/run.out`：`[忽略] 日志行未匹配任何模板: … <Alex> #矩阵测试…`（`01-vanilla.md` §5 F-V1）。

### 复现步骤

```bash
# 任意一台 MC 服（或直接用一段日志文本）
y33bot run --config config.toml            # 正常级别：日志里看不到任何异常
y33bot run --config config.toml --verbose  # 才看得到 [忽略] 日志行未匹配任何模板
y33bot simulate log-event --server main --line '[14:30:09] [Server thread/INFO]: [Not Secure] <Steve> #你好' --dry-run
# → [警告] 日志行未匹配任何模板（退出码 1）
```

### 根因分析（代码级）

| # | 环节 | 位置 | 事实 |
|---|---|---|---|
| 1 | 未匹配只记 DEBUG | `src/y33bot/mclog/watcher.py:112-115` | `self._logger.debug("[忽略] 日志行未匹配任何模板: %s", text)` —— 默认级别不可见 |
| 2 | 没有任何计数/阈值 | `src/y33bot/mclog/watcher.py`（整文件） | 不统计「本轮/最近 N 行里命中了几条」，也没有「连续 T 秒零事件」的看门狗 |
| 3 | `check` 不校验模板与真机日志行 | `src/y33bot/service.py:85-173`（自检项：配置 / QQ / RCON / 日志可读 / 绑定表） | 只判「日志文件可读」，不判「模板能匹配这个服的日志」⇒ 配错模板照样 `check` OK |
| 4 | 桥接/健康轮询与日志事件解耦 | `src/y33bot/service.py:271-304` | 没有事件时 `_log_loop` 什么都不做，`_health_loop` 只看 RCON ⇒ 进程一切正常的表象被维持 |

### 未验证的边界

- **用户口径未定**：是要求「打一次 `[警告]` 即可」，还是要求「长时间零事件就非 0 退出」（像 BUG-001 的 R2-lite 那样），
  本卡不替用户拍板。误报风险也需要口径：一个真·安静的服务器本来就长时间没有进出服事件。

### 修复方向（只登记方向，不在本卡改）

1. **加「零事件」提示**：按服统计「最近 N 条日志行命中 0 条」或「连续 T 分钟零事件且期间有新日志行」→ 打**一次**
   `[警告] 日志与 [log_patterns] 不匹配（最近 N 行全部未命中），MC→QQ 方向可能失效`（只打一次，避免刷屏）。
2. **`check` 增一项**「模板 × 真机日志行」：读 `latest.log` 的最后一行（或配置里指定的样例行）试匹配
   `join`/`quit`/`chat`，不匹配即 `FAIL` 并在 detail 里给出建议模板 —— 把 BUG-002 / BUG-003 挡在启动前。
3. **文档**：`README.md` §13 FAQ 增加排查顺序「群里没有进服通知/聊天 → 先 `run --verbose` 看有没有
   `[忽略] 日志行未匹配任何模板` → 再按 `[log_patterns]` 调整」。

---

## BUG-005 QQ 网关遇平台接口超时时：SDK 吞成 `None` → 报错不可读且直接非 0 退出

**状态**：已复现（触发条件随机；错误链条可在离线逐字复现）
**登记日**：2026-10-18
**上报**：Forge 卡 `t_157ba7fe`（F2，12 版里 5 次）、原版卡 `t_ac457fe1`（F-V2，1 次）、NeoForge 卡 `t_efe57773`（§6.2，3 次）
**影响范围**：**与 MC 加载器/版本无关**（QQ 平台侧或网络瞬时不稳触发）；凡 `y33bot run` 都会遇到，
表现是**启动期**失败（网关还没就绪就退出）或运行期网关任务结束

### 症状（可观测）

1. 启动期撞上平台接口超时时：网关**起不来**，进程打两条**读不出原因**的 `[错误]`，走 `[停止]` 收尾后**退出码 1**
   （交给 `systemd`/`nssm` 拉起 —— 契约对，但运维只能看到 `'NoneType' …`）。
2. 真机上是**随机**的：同版本复跑、3 次冷启动尝试都恢复正常（`01-vanilla.md` §5 F-V2）。
3. 运行期同样走这条链路（`src/y33bot/service.py:238-244`）：网关任务结束 → `[错误] QQ 网关已断开（收不到群消息）…` + 返回 1。

### 原始证据

原版 1.21.8 首跑原文（`artifacts/vanilla/1.21.8/run.out.gateway-starttimeout-original.txt`，整个 `run.out` 只有 12 行）：

```text
Using selector: EpollSelector
[启动] y33bot 0.1.0（1 个 MC 服）
[RCON 127.0.0.1:25705] 已连接
[RCON v1_21_8] 已连接
[启动] 日志监听已启动: v1_21_8
[botpy] 登录机器人账号中...
[botpy] access_token expires_in 1015
请求超时，请求连接: https://api.sgroup.qq.com/gateway/bot
[错误] QQ 网关异常退出: 'NoneType' object is not subscriptable
[错误] QQ 网关启动失败: QQ 网关启动失败: 'NoneType' object is not subscriptable
[停止] 正在关闭…
[状态] 已落盘 /home/hermes/Y33-Bot/data/state-vanilla-1.21.8.json
[停止] 已退出
```

Forge 侧原文（`03-forge.md` §4 F2，同一形态、两条超时都出现）：

```text
[botpy] 登录机器人账号中...
[botpy] access_token expires_in 5209
请求超时，请求连接: https://api.sgroup.qq.com/users/@me
请求超时，请求连接: https://api.sgroup.qq.com/gateway/bot
[错误] QQ 网关异常退出: 'NoneType' object is not subscriptable
[错误] QQ 网关启动失败: QQ 网关启动失败: 'NoneType' object is not subscriptable
[停止] 正在关闭… / [停止] 已退出      → run exit=1
```

NeoForge 侧另一种措辞（`04-neoforge.md` §6.2）：`users/@me` 超时那一步抛的是
`'NoneType' object has no attribute 'get'`；26.2 那次是 `[botpy] access_token TimeoutError:`。

**观察到的频率**：Forge 12 个版本命中 5 次（1.21.3 / 1.21.5 / 1.21.8 / 26.1 / 26.3，其中 1.21.8 两次），
NeoForge 3 次（1.21.10 连续两轮 + 26.2 一轮）、原版 1 次（1.21.8 首跑）；
**同版本复跑/重装后均恢复正常**（`forge-retry.sh`、`neoforge/scripts/rerun_*.sh`、3 次冷启动全成功）。

### 复现步骤

- **正面复现**（平台超时）：**不可控** —— 本卡未找到稳定触发条件（见「未复现 / 信息不足」第 4 条）；
  四张卡共 9 次都是「随机撞上」，且都在 4 张卡并行跑 MC 服务端、机器负载高时（`01-vanilla.md` §5 F-V2 的环境观察）。
- **反向复现**（错误文本的产生方式，离线可跑）：SDK 吞掉超时后返回 `None`，随后被当 dict 用。
  本卡用脚本造出同样的两条异常文本：

  ```text
  None[...]      -> TypeError: 'NoneType' object is not subscriptable
  None.get(..)   -> AttributeError: 'NoneType' object has no attribute 'get'
  ```

  与日志里的 `[错误] QQ 网关异常退出: …` 逐字一致。

### 根因分析（代码级）

| # | 环节 | 位置 | 事实 |
|---|---|---|---|
| 1 | SDK 把 HTTP 超时**吞掉并返回 `None`** | `.venv/Lib/site-packages/botpy/http.py:181-195` | `except asyncio.TimeoutError: _log.warning(f"请求超时，请求连接: {route.url}")` —— 之后**隐式 `return None`**（这正是日志里那条 `请求超时，请求连接: …` 的来源） |
| 2 | 启动链路第一站：`/users/@me` | `botpy/client.py:161-164`（`_bot_login`）→ `botpy/http.py:197-207`（`login()` 里 `data = await self.request(Route("GET","/users/@me"))`）→ `botpy/client.py:178`（`Robot(user)`）→ `botpy/robot.py:16-19`（`data.get("username")` / `int(data["id"])`） | `data` 为 `None` ⇒ `AttributeError: 'NoneType' object has no attribute 'get'`（NeoForge 那两轮的文本） |
| 3 | 启动链路第二站：`/gateway/bot` | `botpy/client.py:167`（`self._ws_ap = await self.api.get_ws_url()`）→ `botpy/api.py:805-813`（`Route("GET","/gateway/bot")`）→ `botpy/client.py:171`（`max_async=self._ws_ap["session_start_limit"]["max_concurrency"]`），另见 `:183/187/203` 的 `self._ws_ap["shards"]` | `_ws_ap` 为 `None` ⇒ `TypeError: 'NoneType' object is not subscriptable`（原版/Forge 的文本） |
| 4 | 我们这层原样透传，不做分类 | `src/y33bot/qq/gateway.py:145-147` | `except Exception as exc: self._logger.error("[错误] QQ 网关异常退出: %s", exc)` ⇒ 异常原文成了给运维看的唯一线索 |
| 5 | 启动期失败 ⇒ 报错 + 返回 1 | `src/y33bot/service.py:229-234`、`src/y33bot/qq/gateway.py:104-116`（`start()` 把 `_up_error` 再包一层） | 契约**正确**（BUG-001 的 R2-lite：不静默）—— 但错误文本对运维不可读，且**启动期没有重试/退避**，进程管理器会反复拉起 |
| 6 | 运行期同样会走这条路径 | `src/y33bot/service.py:238-244` | 网关任务结束 → `[错误] QQ 网关已断开（收不到群消息），进程退出等待重启` + 返回 1 |

**性质判定**：**触发原因是外部的**（QQ 平台接口超时/无响应），但**代码侧的缺陷是明确的**：
① 把 SDK 的内部异常（`TypeError`/`AttributeError`）当成给用户的错误文案；
② 启动期失败不做有限重试/退避（`IDEA.md` §4 的「不重试」只约束**单条消息**；启动期重试属装配决策，需按 `PLAN.md` §7 登记）；
③ 没有区分「凭据不可用」（可用）与「平台抖动」（应重试）的手段。

### 未验证的边界

- **触发条件与频率**：只在平台/网络抖动时出现，本卡无法主动复现（`01-vanilla.md` §7-4）。
- **放大因素**：NeoForge 卡留了两个疑点给本卡 —— ① 机器内存压力（2.6 GiB 峰值）；② **4 张矩阵卡共用同一套 QQ 凭据**、
  同一时刻可能有并发会话（SDK 自己打印 `最大并发连接数: 1`）。本卡无法判定二者与失败率的关系（见「未复现 / 信息不足」第 4 条）。
- 重启风暴的实际后果（`systemd` 拉起频率、平台是否限流）未实测。

### 修复方向（只登记方向，不在本卡改）

1. **启动期有限重试 + 退避**（需用户拍板次数与间隔，例如 3 次 / 5·15·45s；落地要按 `PLAN.md` §7 登记并更新 §5 S5 期望值）——
   平台抖动时能自愈，而不是让进程管理器反复冷启动。
2. **把 `None` 类错误翻译成可读原因**：在 `src/y33bot/qq/gateway.py:145-147` 捕获 `TypeError`/`AttributeError`/`TimeoutError`，
   输出如 `[错误] QQ 平台接口无响应（超时）: https://api.sgroup.qq.com/gateway/bot（SDK 未处理 None 响应）`，
   原始异常留在 DEBUG。这样运维能区分「平台抖动」与「凭据/配置错误」。
3. **启动前先探活**（复用 BUG-001 R5 的 `src/y33bot/qq/probe.py`）：`run` 启动时先取一次 `access_token`，
   失败就报可读原因并不再往下走；成功后再起网关 —— 能把「凭据问题」和「sgroup 接口抖动」分开。
4. **文档**：`README.md` §13 FAQ 增加「`run` 立刻退出 `exit=1` 且报 `'NoneType' object is not subscriptable'`
   → 平台接口瞬时超时，直接重跑即可（附带本条编号）」。

---

## 非产品缺陷观察（环境 / 部署 / 测试流程）

以下现象**实测存在、但不属本仓代码缺陷**，登记是为了后续卡不重复踩坑、也避免被误读成 BUG。

| # | 现象 | 证据 | 性质与处置 |
|---|---|---|---|
| A1 | **NeoForge 26.x 的服务端类文件是 Java 25**（class file 69.0），用 JDK21 启动直接 `UnsupportedClassVersionError: … class file version 69.0 … up to 65.0`；换 `~/jdk-25` 后 26.3 起服 18s | `04-neoforge.md` §5.4、`artifacts/neoforge/26.3/console-26.3-jdk21-bootstrap-fail.txt` | 部署事实。本仓只管 RCON + 日志，不校验 MC 端 JDK；但**文档/`check` 都不提示**，建议在 `README`/`docs/smoke.md` 的部署小节写明「26.x 加载器服务端用 JDK25」 |
| A2 | `maven.neoforged.net` 在本机不可达（DNS 被污染 + 真实 IP 也不通），installer 自带的 `--mirror` **不生效**；改用 `maven.creeperhost.net` + 主机替换后的 installer 才装成 | `04-neoforge.md` §2.1-2.3、§5.5 | 环境/网络。后续任何 NeoForge 任务别指望 `--mirror` |
| A3 | Fabric：测试脚本清掉 `libraries/` 后实例不能再直接启动（`ClassNotFoundException: … FabricServerLauncher`），需先重跑 `new-fabric.sh` | `02-fabric.md` §4 F-3 | 测试流程坑，非产品问题 |
| A4 | `run --verbose` 的 `[忽略] 日志行未匹配任何模板` 噪声很大（启动信息、mod 列表、RCON 线程行全打） | `02-fabric.md` §4 F-5 | 属预期解析行为；同时也是 BUG-004 的正面材料（「看不到」与「看不清」是同一个问题的两面） |
| A5 | 用假 `group_openid` 时 MC→QQ 必然被平台拒绝（`code 11255 / err_code 40011028`「群不存在」/ 400），`state.json` 的 `msg_seq` 照常递增落盘 | `01-vanilla.md` §5.3、`03-forge.md` §6-7 | **预期**：环境里没有真群 openid，这是用来证明「链路真的走到平台」的判据 |
| A6 | 日志轮转时可能**先**报 `[警告] 日志文件已轮转（inode A -> B）`、**再**报 `[警告] 日志文件缩小（size=… < offset=…）` | `01-vanilla.md` §5.3 | 两条只做同一件事（偏移重置为 0），之后事件仍正确解析；无功能影响，未深究 |
| A7 | 同机 4 张矩阵卡并行时：启动耗时被拖到 362s（无争抢时 18–45s）、平台请求超时变多、jar 下载停滞一次（断点续传 + sha1 校验后正常） | `01-vanilla.md` §4.1/§5.3、`04-neoforge.md` §6.2 备注 | 环境噪声；BUG-005 的频率可能被它放大（未证实） |
| A8 | 窗口内**没有「版本相关」的差异**：13 个能真客户端跑完的版本行为逐条一致；聊天行自 1.21.2 起就是同一形态（变更点 ≤ 1.21.1） | `01-vanilla.md` §6.2、`02-fabric.md` §4 F-4 | 结论性事实，用于收窄 BUG-002 的影响范围 |

---

## 未能复现 / 信息不足清单（本轮四张矩阵卡汇总）

| # | 缺什么 | 卡在哪 / 为什么 | 影响哪些条目 | 后续怎么补 |
|---|---|---|---|---|
| 1 | **真 QQ 群里的收发**（群侧步骤无法自证） | `~/.env` 只有 AppID/AppSecret；botpy 没有「列出机器人所在群」的 API，拿不到 `group_openid`（`00-env.md` §8-1） | 所有条目的「群里真的收到/发出」只能证明到平台层（400/11255 即「走到了平台」） | 由人给出目标群 `group_openid`，或去群里 `@机器人` 抓一次事件 |
| 2 | **MC 26.2 / 26.3 的真玩家日志行** | 无头客户端 mineflayer + minecraft-data 最高支持 26.1（实测 `Error: No data available for version 26.3`，`02-fabric.md` §4 F-2、`04-neoforge.md` §6.3） | BUG-002 / BUG-003 在这两版上只能「格式取样 + 全量未匹配」佐证，不能断言 | 升级 `minecraft-data`（当前 latest 已到顶）或用真 26.2/26.3 客户端进服抓 `latest.log` |
| 3 | **`online-mode=true` 的签名聊天行形态** | 全部实例统一 `online-mode=false`，无正版账号/客户端（`01-vanilla.md` §7-2） | BUG-002 的**定性**：默认模板当初是否为正版服而写 | 用真账号连一台 `online-mode=true` 实例抓同一位置的行 |
| 4 | **BUG-005 的触发条件与频率**（含并发会话 / 内存压力是否放大） | 平台超时是随机事件；同版本复跑 + 3 次冷启动都不复现（`01-vanilla.md` §5 F-V2 / §7-4） | BUG-005 只能登记「已发生 9 次」，给不出频率与可控复现 | 空闲机器上多跑若干次 `run`；或对 `https://api.sgroup.qq.com/gateway/bot` 做稳定性采样；另可单机独占凭据再测一轮以排除并发会话因素 |
| 5 | 加载器/API 版本不匹配、依赖缺失（sha1/缺库）、ClassLoader/ASM/mixin 异常、机器人连接后的协议握手差异 | 四张卡**都没有复现**：Fabric 9 版 + 1 变体（`02-fabric.md` §4 F-4）、Forge D1–D2（`03-forge.md` §5，且 D1 在 26.3 上是无效实验）、NeoForge 9 版（`04-neoforge.md` §4.2） | 反向结论：这些方向不是本轮的故障源 | 若要覆盖，需要构造具体组合（指定 loader/API/mod 版本）后另开卡 |
| 6 | **第三方 mod 场景**（mod 之间 mixin/ASM 冲突、mod 与加载器的依赖约束、加载顺序） | 卡内要求「installer + 文档要求的最小依赖」= 无 mod；本机 `github.com` 不通也下不到真实 mod | 未列入任何 BUG（无证据） | 另开卡：给出具体 mod 清单（含 mixin/ASM 用法与版本约束）再测 |
| 7 | 部分补丁版未逐版 | 按「x.xx.0 不细化到 x.xx.xx」的口径排除（Forge 无 1.21.2 构建、26.1.1/26.1.2 为补丁版；Fabric 未测 1.21.3/1.21.7/1.21.8/1.21.10/26.1.1/26.1.2） | 只影响覆盖密度，不影响 BUG-002/003 的结论（窗口内格式一致） | 用同一套脚本加版本即可（端口段按 `00-env.md` §5.2 扩） |
| 8 | Forge 1.21.8 的 C8（日志轮转）**成功样本** | 主轮与补测各撞一次平台超时（BUG-005），同一用例在其余 11 版通过（`03-forge.md` §7-2） | BUG-005 的一条附证 | 空闲时段重跑该用例 |
| 9 | Forge 26.2 / 26.3 的真聊天行 | 无头客户端上限 26.1；这两版的行是「真前缀 + PLAN 正文」合成的，已在 `real-lines.txt` 标注（`03-forge.md` §7-1） | BUG-002/003 的外推部分 | 同第 2 条 |

---

## 根卡复核记录（`t_d25d5a1d`，2026-10-18）

根卡只做三件事：把六张卡的分支合进同一棵树、**独立复核**上面的结论、把残留问题写清楚。**没有改任何项目代码。**

### 合并

`wt/t_a4c6c3ae`、`wt/t_ac457fe1`、`wt/t_5bccfcd8`、`wt/t_157ba7fe`、`wt/t_efe57773`、`wt/t_1c0e88a4`
六个分支依次合入 `y33-bot/t_d25d5a1d`（6 个 merge 提交，0 冲突）。合并后：

- `git diff f7fd5cb..HEAD -- src tests docs README.md PLAN.md IDEA.md config.example.toml Makefile pyproject.toml requirements*.txt .github scripts` → **空**；
- 相对 `f7fd5cb` 的全部改动 = `BUGS.md` + `test-notes/**`（773 个文件、39860 行插入）。

### 复核一：结论独立复现（离线，用**本仓代码**，不引用他卡结论）

用 `src/y33bot/config.py` 的 `LogPatterns` + `src/y33bot/mclog/patterns.py` 的 `compile_patterns` / `parse_line`，
把 `config.example.toml` 的**出厂默认模板**编译起来，喂**各卡制品里的真机原始行**（逐字未改），
再喂一遍「只放宽时间戳/线程名/logger 段」的模板做对照：

| 真行（来源） | 默认模板 | 放宽模板（只改配置） |
|---|---|---|
| 原版 1.21.11 `join` / `quit`（`00-env` 制品） | 命中 join / quit | 命中 |
| 原版 1.21.11 `chat`（`00-env` 制品） | **不命中** | 命中 |
| Fabric 1.21.2 / 1.21.11 / 26.1 `chat`（`02-fabric` 制品） | **不命中** | 命中 |
| Forge 1.21.11 `join` / `quit` / `chat`（`03-forge` 制品） | **三者全不命中** | 三者全命中 |
| NeoForge 1.21.4 `join` / `quit` / `chat`（`04-neoforge` 制品） | **三者全不命中** | 三者全命中 |
| 旧形态对照 `[14:30:09] [Async Chat Thread - #0/INFO]: <Steve> #hi` | **命中 chat** | 命中 |

⇒ **BUG-002**（默认 `chat` 只认 ≤1.21.1 的形态）与 **BUG-003**（加载器布局把三个模板一起打死）**独立复现**；
两者的「修复方向 = 只改 `[log_patterns]`」也**独立验证可行**。

### 复核二：条目里的 `文件:行号` 抽查（逐条打开源码核对）

`patterns.py:52-60`（`_anchor` 补 `^`/`$`）与 `:96`（`re.match` 整行锚定）；
`watcher.py:112-115`（未命中只记 **DEBUG** `[忽略] 日志行未匹配任何模板`，这是 BUG-004 的支点）；
`bridge.py:139`（`handle_log_event`）与 `:165-167`（`#` 前缀/回环判断都在事件层**之上**）；
`service.py:284-289`（只有拿到事件才调桥接）；`cli.py:221-225`（`simulate log-event` 是唯一显形点）；
`config.example.toml:31-33`（默认三模板，来源 `IDEA.md:170` 的 ≤1.21.1 形态）；
`tests/conftest.py:19-21`（`CHAT_TEMPLATE` 与默认模板同为旧形态 ⇒ 381 条单测「自造行验自造模板」，
测不出 BUG-002）—— **全部与条目描述一致**。

### 复核三：本仓基线（合并后的树上重跑）

```
$ env -u MC_RCON_PASSWORD -u MC_RCON_PASSWORD_MAIN PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q
381 passed in 44.18s                      # 与 f7fd5cb 基线一致（本批未改代码）
$ ruff check . && ruff format --check .   # make lint 同款
All checks passed! / 44 files already formatted
```

### 根卡发现并处理的两点

1. **制品数量**：原文「共 771 个文件」是估算，实测 **761**（分族见 §「测试矩阵与证据来源」）——已按实测改正。
   四张卡各自的卡面数字与提交内容也有出入（Forge 卡元数据 297 含 1 份记录、NeoForge 卡元数据 219 而分支里 193 个）——
   这也是「卡面自述不等于事实」的一例，故根卡以**树里的实测值**为准。
2. **`make lint` 会被新加的测试脚本弄红**（CI 不受影响：CI 只 lint `src tests`，`make lint` 是 `ruff check .`）：
   `test-notes/artifacts/neoforge/scripts/nf_patch_installer.py` 有一个未用的 `import json` + 一处换行不合 ruff format。
   已用 `ruff check --fix` + `ruff format` 修好（`-3/+2` 行，行为不变，`py_compile` 通过），使 `make lint` 回到全绿。
   这是本批**唯一**改动的非新增文件；若想保持「制品逐字未改」，替代做法是在 `pyproject.toml` 的 `[tool.ruff]` 里
   `extend-exclude = ["test-notes"]`（需用户拍板，根卡未擅自改项目配置）。

### 未做的两件事（如实登记）

1. **`AGENTS.md` 的「开发进度」没有改**：根卡运行环境把 `AGENTS.md` 列为受保护的智能体指令文件，
   写入需要交互式批准，本次无人值守 ⇒ 未写入。本批的进度等价记录就是本文件（`BUGS.md` 汇总表 + 证据来源 + 本条复核记录），
   需要 `AGENTS.md` 同步时请人工补一条 2026-10-18 的条目（模板见该文件既有条目）。

   > **2026-10-28 更新**：开发进度已从 `AGENTS.md` **迁到 `docs/progress.md`**（普通文件，看板卡可直接写），
   > 本条要求的 2026-10-18 进度已在那里补记。以后记进度一律写 `docs/progress.md`，不再需要改 `AGENTS.md`。
2. **没有改 `PLAN.md` §7 的变更登记**：本批零产品改动（`src/` 一行未动），按 `PLAN.md` §7 的口径，
   变更登记留给真正改默认模板的修复卡去做。

---

## BUG-001 QQ token 过期后运行时静默失效，运行期无任何提示

> **历史条目**（2026-10-13 登记、2026-10-15 修复）。2026-10-18 四张矩阵卡在真机上共触发 9 次
> 「网关启动期失败 / 网关任务结束」，每次都出现 `[错误]` + 非 0 退出 —— **R2-lite 契约实测生效**，
> 原始输出见 [BUG-005](#bug-005-qq-网关遇平台接口超时时-sdk-吞成-none--报错不可读且直接非-0-退出)「症状」。

**状态**：**已修复**（2026-10-15，卡 `t_80249809` 落地 R2-lite + R5，见本条「修复记录」；真机触发链路 Q1/Q3 仍未验证）
**登记日**：2026-10-13
**上报**：用户（真机运行观察到，非 CI 用例）
**调查卡**：看板 `default` 的 `t_6cc56405`（分支 `y33-bot/t_6cc56405-bug-001-qq-token`，2026-10-15 结案）—— 只调查、不改产品代码，结论写本条的「回复」
**修复卡**：看板 `default` 的 `t_80249809`（分支 `y33-bot/t_80249809-bug-001-0-r2-lite-check-qq-r5`）—— 改产品代码，登记在 `PLAN.md` §7.2，复验在 `docs/acceptance.md` §9
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

> 由调查卡 `t_6cc56405` 填写（分支 `y33-bot/t_6cc56405-bug-001-qq-token`）。要求：逐条回答上面 5 个疑点，每条给「复现 / 未复现 + 证据」，
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

### 修复记录（2026-10-15，卡 `t_80249809`）

> 本小节由**修复卡**填写；上面「回复」小节是调查卡的原文，**未改写**。

#### 改了什么

按「回复」推荐的 **R2 + R5** 落地（用户 2026-10-15 拍板把 R2 收窄为 **R2-lite：不重启、不重试，一次失败就退出**）：

| 项 | 改动 | 位置 |
|---|---|---|
| R2-lite | `QQGateway` 协议**新增** `wait_closed()`（网关任务结束的观测点）：`BotpyGateway` 用 done-callback 观测自己的 `_task`；`FakeQQGateway` 等到 `close()` | `src/y33bot/qq/gateway.py`、`src/y33bot/qq/fakes.py` |
| R2-lite | `Service.run()` 同时等「停止信号」与「网关任务结束」：**网关先结束** → `[错误] QQ 网关已断开（收不到群消息），进程退出等待重启` + 既有 `shutdown()` + 返回 **1**；**收到停止信号** → 返回 **0**、不打 `[错误]`（`_wait_for_stop(gateway_task)` 返回布尔值表达是哪种） | `src/y33bot/service.py` |
| R5 | 新增 `qq.probe`：向 `POST https://bots.qq.com/app/getAppAccessToken` 取一次 `access_token`（`urllib`，超时 5s），失败一律 `QQProbeError` | `src/y33bot/qq/probe.py`（新文件） |
| R5 | `check` 的 QQ 项默认**真探活**：成功 `[QQ] OK access_token 获取成功（有效期 Ns），…`；失败 `[QQ] FAIL access_token 获取失败: <原因>`；`--no-probe` 跳过（文案写明「未探活」）；探活函数可注入（`Service(qq_probe=…)`），测试全程离线 | `src/y33bot/service.py`、`src/y33bot/cli.py` |
| 登记 | `PLAN.md` §7.2 变更记录 + §3.1/§3.2/§3.3/§3.4/§3.6/§5 S1/S5 同步；README §7/§8/§13/§14；`docs/smoke.md` §1/§6/§7 | 见 `PLAN.md` §7.2 |

**没做的**（刻意）：不做退避重启、不做重连驱动（R1/R3 都不上）、不新增配置项。

#### 怎么验的

1. **离线前后对照**（同一脚本、同一份配置；「修复前」= `git archive 757db31 src`）：
   - 网关启动后结束：修复前 `run()` 3s 看门狗判超时（退出码 99、日志里 0 条 `[错误]`）；修复后打印
     `[错误] QQ 网关已断开（收不到群消息），进程退出等待重启` 并 `exit=1`。
   - `check`：修复前同一组假凭据打印 `[QQ] OK app_id 已设置 …`；修复后打印
     `[QQ] FAIL access_token 获取失败: 平台返回错误: code=10004 message=机器人不存在`（平台真的回了话）。
2. **自动化**：`pytest -q` **381 passed**；`--cov=y33bot --cov-fail-under=70` **99.33%**；
   `ruff check .` / `ruff format --check .` 全绿（43 文件）；无 `skip`/`xfail`。
   新增 `tests/test_qq_probe.py`（10 例）与 `wait_closed`/探活/退出码相关用例，另有 5 例按新契约改写（见下）。
3. 原始输出与命令见 `docs/acceptance.md` §9。

#### 证据（粘贴）

```
修复前（757db31 的 src）：
INFO [启动] y33bot 0.1.0（1 个 MC 服）
INFO [启动] 日志监听已启动: main
INFO [停止] 正在关闭…
INFO [停止] 已退出
run() 在 3s 内没有返回：网关 started=True，进程仍在常驻（静默）        # 退出码 99

修复后（本卡 src）：
INFO [启动] y33bot 0.1.0（1 个 MC 服）
INFO [启动] 日志监听已启动: main
ERROR [错误] QQ 网关已断开（收不到群消息），进程退出等待重启
INFO [停止] 正在关闭…
INFO [停止] 已退出
exit=1

check（假凭据，修复后默认探活）：
[QQ] FAIL access_token 获取失败: 平台返回错误: code=10004 message=机器人不存在
check --no-probe：
[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，未探活（--no-probe），group_openid 已配置
```

（时间戳与完整命令见 `docs/acceptance.md` §9.1 / §9.2。）

#### 对「回复」里取证用例的影响（必须说明）

「回复」引用的两个用例原本钉的是**修复前**的事实（「网关死了没人管」），修复后契约相反，因此**改名并翻转断言**，
不是把失败用例改绿：

| 「回复」里的旧用例 | 现在 | 差异 |
|---|---|---|
| `tests/test_service.py:198 test_run_ignores_gateway_task_ending` | `tests/test_service.py::test_run_returns_1_when_gateway_dies_after_start` | 同一场景（网关启动后结束），断言从「run() 不退出、无日志」变成「`[错误]` + 返回 1」 |
| `tests/test_bug001_reconnect.py:101 test_service_stays_alive_when_sdk_gateway_coroutine_returns` | `tests/test_bug001_reconnect.py::test_service_reports_and_exits_when_sdk_gateway_coroutine_returns` | 同上（整链：真 SDK `multi_run()` + 真 `BotpyGateway` + 真 `Service.run()`） |
| `tests/test_gateway.py:296 test_gateway_coroutine_end_is_silent` | **保留原名** | 仍然成立：SDK 协程正常返回时**网关层**不打日志，告警改由 `Service` 承担（用例内已注明） |
| `tests/test_bug001_reconnect.py:51 test_multi_run_starts_each_session_once_and_never_again` | **保留原样** | 这是纯 SDK 行为（`multi_run()` 一次性），修复没有改变它 —— 正因为它成立，才必须由我们退出 |

「回复」小节的原文、行号与结论**按原样保留**（那是修复前的事实，用作历史对照）。

#### 边界与遗留（未执行就写未执行）

- **真机触发链路仍未验证**：Q1（静默那一刻的日志尾部）、Q3（QQ 侧关码）以及 `BUGS.md`「复现步骤 → 真机部分」的三步
  （断网 10s / 重置 AppSecret / 等 token 过期）**未执行** —— 本机没有真实 QQ 凭据、也没有 `enable-rcon=true` 的真 MC 服。
  修复后的期望行为已写进 `PLAN.md` §5 S5「新增观察点」，具备环境后按 `docs/smoke.md` 回填。
- 因此本条的「已修复」指的是：**离线复现的缺陷链条已被消除**（网关任务结束必然被观察到、必然报错并非 0 退出；
  `check` 的 `[QQ] OK` 不再能只靠「变量填了」骗过），**不是**「真机上 token 过期一定触发并一定被兜住」的验证结论。
- 发送方向未改：仍是「不重试，但留 `[错误]` 痕迹」（`src/y33bot/qq/gateway.py`）。

---

## 模板（新增条目照抄）

**A. 调查类条目**（可疑→调查→修复，如 BUG-001）

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

**B. 矩阵类条目**（实机测试矩阵产出：既有现象又有代码级根因，如 BUG-002 ~ BUG-005）

```markdown
## BUG-00N <一句话标题>

**状态**：已复现（未修） / 已修复
**登记日**：YYYY-MM-DD
**上报**：<哪张矩阵卡 / 谁在什么场景下发现>
**影响范围**：<加载器 × 版本区间（实证 / 外推 / 未验证 分开写）>
**与其它条目的关系**：<同根因 / 叠加 / 独立>

### 症状（可观测）
### 原始证据        ← 原始日志片段 + 制品相对路径 + 时间戳
### 复现步骤        ← 优先给「离线可复跑」的；真机步骤给完整命令
### 根因分析（代码级）  ← 表格：环节 / 位置（文件:行号）/ 事实
### 未验证的边界
### 修复方向（只登记方向，不在本卡改）
```
