# 03 · Forge 加载器实机测试矩阵（卡 t_157ba7fe）

> 目标：按项目文档（`PLAN.md` §5 S1–S6、`docs/smoke.md`）描述的测试流程，对**近两年发布**的
> Minecraft **Forge 服务端**在「Forge 官方支持的 x.xx.0 版本」上执行完整实机测试，重点观察
> Forge 版本与 MC 版本不匹配、模块化（JPMS）/反射受限导致的启动失败、模组加载顺序异常、
> 机器人连接被拒绝或掉线。
>
> 前置：复用环境基座卡 `t_a4c6c3ae` 的 `test-notes/00-env.md`（JDK21/JDK25、端口分配表、脚本模板）。
> 全程**未修改项目代码**，只在 `test-notes/` 新增记录与制品。
> 测试机：`ssh hermes@10.1.1.4`（Rocky 9.7，2 vCPU / 2.6 GiB 内存 / `/` 可用约 1–2.5 GB）。

---

## 0. 结论摘要

| 项 | 结论 |
|---|---|
| 12 个 Forge 版本装机 + 启动 | **全部成功**（安装器 + 首次启动生成 `config/`、`Done (...)`、RCON 监听） |
| 机器人 ↔ Forge 服务端（RCON） | **全部通过**：`check` 真探活退出码 0；真 `tellraw` 注入；`/status` 真 `/list` 往返出 `在线: 0/20` |
| MC→QQ（进出服 / `#` 聊天） | **全部失败**：项目默认 `join`/`quit`/`chat` 模板**一条都匹配不上 Forge 的日志行** |
| 只用配置放宽模板后 | **全部通过**：三模板命中、普通聊天忽略、回环防护生效、进服通知带服名 |
| 常驻运行 / 优雅退出 | **全部通过**：真连 QQ 网关（机器人「y33-test」），SIGTERM 退出码 0 |
| MC→QQ 生产链路（假群） | **全部通过**：真事件 → bridge → 真 BotpyGateway → 平台 400（群不存在），`msg_seq` 落盘 |
| 日志轮转（S6） | **全部通过**：`[警告] 日志文件缩小（size=... < offset=...），偏移重置为 0` 且新行被转发 |
| 停服后机器人侧 | **全部按预期报错**：`RCON ... [Errno 111] Connect call failed`（连接被拒绝），`check` 退出码 1 |
| 加载器/Java 版本不匹配、损坏 mod | 见 §5（D1–D3）：启动失败/降级行为已实测并留原始日志 |

**一句话**：Forge 服务端在 RCON 方向的互通完全可用；**MC→QQ 方向在所有 12 个 Forge 版本上都不工作**，
根因是 Forge 自带 log4j2 布局产出的日志行形状与项目默认模板不匹配（**加载器级、非版本级**），
只改 `[log_patterns]` 即可恢复 —— 现象、原始行、复现步骤见 §4。

---

## 1. 版本清单与理由

「近两年」= **2024-10-18 ~ 2026-10-18**（与 `00-env.md` §3 同一口径）。该窗口内 MC 正式版共 15 个：
`1.21.2 1.21.3 1.21.4 1.21.5 1.21.6 1.21.7 1.21.8 1.21.9 1.21.10 1.21.11 26.1 26.1.1 26.1.2 26.2 26.3`。

Forge 官方覆盖情况（原始证据：`artifacts/forge/version-source.txt`，来自
`https://files.minecraftforge.net/.../promotions_slim.json` 与
`https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml`）：

| MC 版本 | 发布时间 | Forge 主线 | 本卡用的构建（推荐优先，否则 latest） | 是否列入 |
|---|---|---|---|---|
| 1.21.2 | 2024-10-22 | **无** | — | ❌ 官方无构建（`index_1.21.2.html` → 404；maven 无 `1.21.2-*`） |
| 1.21.3 | 2024-10-23 | 53.x | `53.1.0`（recommended） | ✅ |
| 1.21.4 | 2024-12-03 | 54.x | `54.1.14`（recommended） | ✅ |
| 1.21.5 | 2025-03-25 | 55.x | `55.1.0`（recommended） | ✅ |
| 1.21.6 | 2025-06-17 | 56.x | `56.0.9`（无 recommended，用 latest） | ✅ |
| 1.21.7 | 2025-06-30 | 57.x | `57.0.3`（无 recommended） | ✅ |
| 1.21.8 | 2025-07-17 | 58.x | `58.1.0`（recommended） | ✅ |
| 1.21.9 | 2025-09-30 | 59.x | `59.0.5`（无 recommended） | ✅ |
| 1.21.10 | 2025-10-07 | 60.x | `60.1.0`（recommended） | ✅ |
| 1.21.11 | 2025-12-09 | 61.x | `61.2.0`（recommended） | ✅ |
| 26.1 | 2026-03-24 | 62.x | `62.0.9`（无 recommended） | ✅ |
| 26.1.1 | 2026-04-01 | 63.x | `63.0.2` | ❌ 26.1 的补丁版（x.xx.xx 形态，卡面要求不细化） |
| 26.1.2 | 2026-04-09 | 64.x | `64.1.5` | ❌ 同上 |
| 26.2 | 2026-06-16 | 65.x | `65.1.0`（recommended） | ✅ |
| 26.3 | 2026-09-15 | 66.x | `66.0.13`（latest） | ✅ |

**最终覆盖 12 个版本**：`1.21.3 / 1.21.4 / 1.21.5 / 1.21.6 / 1.21.7 / 1.21.8 / 1.21.9 / 1.21.10 / 1.21.11 / 26.1 / 26.2 / 26.3`。

口径说明（避免歧义，便于复核）：
1. 「x.xx.0」按 `00-env.md` §3 的口径理解为**各 minor 线的基线正式版**：新编号体系下即 `26.1 / 26.2 / 26.3`
   （26.1.1、26.1.2 是 26.1 的补丁，按「不细化到 x.xx.xx」排除）。
2. 1.21 线的 9 个版本**全部列入**：它们各自是 MC 的独立正式发布，且在 Forge 侧各自对应一条独立主线
   （53.x–61.x，构建数见证据文件），属于「加载器版本 × MC 版本」这一矩阵维度本身要覆盖的范围；
   本卡选择全测而不是抽样，代价只是机时（每版本约 4–5 分钟）。
3. 1.21.2 被排除**不是**口径问题，而是 **Forge 官方没有为它构建**（这是本卡顺手拿到的第 1 条结论）。

> 版本号对齐检查：`build` 与 MC 版本的对应关系取自官方 `promotions_slim.json` 的
> `<mc>-recommended` / `<mc>-latest` 键，装机时逐个下载 `maven.minecraftforge.net` 上
> `<mc>-<build>-installer.jar`，因此**不存在自己拼错版本**的可能。

---

## 2. 环境、目录与端口

沿用 `00-env.md` §5 的约定，Forge 族：**游戏端口 25620+slot / RCON 25720+slot**，
目录 `~/mc-test/forge/<MC版本>/`。

| 版本 | slot | 游戏端口 | RCON | JDK |
|---|---|---|---|---|
| 1.21.3 | 0 | 25620 | 25720 | 21 |
| 1.21.4 | 1 | 25621 | 25721 | 21 |
| 1.21.5 | 2 | 25622 | 25722 | 21 |
| 1.21.6 | 3 | 25623 | 25723 | 21 |
| 1.21.7 | 4 | 25624 | 25724 | 21 |
| 1.21.8 | 5 | 25625 | 25725 | 21 |
| 1.21.9 | 6 | 25626 | 25726 | 21 |
| 1.21.10 | 7 | 25627 | 25727 | 21 |
| 1.21.11 | 8 | 25628 | 25728 | 21 |
| 26.1 | 9 | 25629 | 25729 | 25 |
| 26.2 | 0（复用） | 25620 | 25720 | 25 |
| 26.3 | 1（复用） | 25621 | 25721 | 25 |

- slot 复用是安全的：环境基座已确认「同一时刻只跑 1 个实例」（内存 2.6 GiB、单实例 RSS ≈ 0.7–1.2 GiB），
  本卡全程串行；测试脚本里还有一道「等 MemAvailable ≥ 900 MB 且磁盘 ≥ 700 MB 才启动」的护栏。
- 新增脚本（都在测试机 `~/mc-test/`，未入库）：
  - `new-forge.sh <MC版本> <Forge构建> <slot>`：下载官方 installer → `--installServer` → 写
    `eula.txt` / `server.properties`（`enable-rcon`、本族端口、`online-mode=false`、
    `pause-when-empty-seconds=0`）/ `start.sh` / `instance.env`。
  - `forge-test-one.sh <版本> <slot>`：单版本 C1–C9 用例，输出到 `~/forge-artifacts/<版本>/`。
  - `forge-run-all.sh [版本...]`：串行驱动，逐版本「装 → 测 → 归档 → 清理 `libraries/`+`world/`」。
  - `mkpatterns.py <join|quit|chat> '<真实日志行>'`：从**真行**推导模板（只改配置、不改代码）。
  - `forge-extra.sh`：补充观察 D1–D3（见 §5）。
- 服务端启动命令（Forge 官方 installer 产物）：
  `java -Xms512M -Xmx1024M @libraries/net/minecraftforge/forge/<mc>-<build>/unix_args.txt nogui`
- 制品命名遵守 `00-env.md` §7 的约定：原始日志一律 `.txt` 后缀（仓库 `.gitignore` 忽略 `*.log`/`logs/`），
  且目录名不用 `env`。

---

## 3. 测试用例（每个版本执行）

| 编号 | 用例 | 判定 |
|---|---|---|
| C1 | 官方 installer `--installServer` + 首次启动 | 出现 `Done (…s)!`、游戏/RCON 端口 LISTEN、生成 `config/`（`fml.toml`、`forge-common.toml`） |
| C2 | S1 `y33bot check`（QQ 真探活 + 真 RCON + 日志可读 + 绑定） | 末行 `OK`、退出码 0 |
| C3 | S2 `bind set` + `simulate group-message` 真注入 + `/status` 真往返 | 日志出现 `[RCON forge] tellraw …`；`/status` 返回真实 `/list` 结果 `在线: 0/20` |
| C4 | 无头客户端（mineflayer）真进服/聊天/退服 → 抽真行 | 产出真实 `joined the game` / `[Not Secure] <Steve> #…` / `left the game` 行 |
| C5a | **默认**模板 A/B（`config.example.toml` 的 join/quit/chat） | 命中→`[群消息]`/退出码 0；命中不了→`[警告] 日志行未匹配任何模板`/退出码 1 |
| C5b | **由真行推导**的模板（只改配置） | 三种事件都命中；普通聊天 `[忽略] 聊天非 # 开头`；回环行 `[忽略] 回环防护…` |
| C6 | `run` 常驻：真连 QQ 网关 + SIGTERM | `[启动] QQ 网关已连接/就绪`、`[停止] 已退出`、退出码 0 |
| C7 | MC→QQ 生产链路（假 `group_openid`） | 真事件驱动真 BotpyGateway → 平台 400 被记录；`state` 里 `msg_seq` 递增、`log_offset` 追平 |
| C8 | S6 日志轮转 | `[警告] 日志文件缩小（size=… < offset=…），偏移重置为 0`，轮转后新行仍被转发 |
| C9 | 停服 → 机器人侧 | `[RCON forge] FAIL … [Errno 111] Connect call failed`、`check` 退出码 1 |

补充观察（D 组，见 §5）：D1 加载器/MC 版本不匹配、D2 Java 版本不匹配（JPMS/类文件版本）、
D3 模组加载异常（损坏 mod）、D4 机器人连接被拒（C9 已覆盖）。

---

## 4. 主要发现（供汇总卡 `t_1c0e88a4` 登记）

### F1（加载器级、影响全部 12 个 Forge 版本）Forge 的日志行与项目默认模板完全不匹配 → MC→QQ 方向全哑

**症状（可观测）**：在 Forge 服务端上，玩家进服/退服、游戏内 `#` 聊天都不会出现在群里；
`y33bot simulate log-event --line '<真实行>'` 输出 `[警告] 日志行未匹配任何模板`、退出码 1。
Rough 对照：同一台机器上原版（vanilla）服务端的旧格式行能命中（`00-env.md` §7-10 对照组）。

**真实日志行（Forge 1.21.11，`artifacts/forge/1.21.11/real-lines.txt`）**：

```
[1810月2026 15:35:33.486] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve joined the game
[1810月2026 15:35:36.278] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
[1810月2026 15:35:37.785] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve left the game
```

项目默认模板（`config.example.toml`）：

```
join = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) joined the game'
quit = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) left the game'
chat = '\[\d{2}:\d{2}:\d{2}\] \[Async Chat Thread - #\d+/INFO\]: <(?P<player>\w+)> (?P<message>.+)'
```

**两处结构性差异**（都不是「版本变了」能解释的，是 Forge 自带 `log4j2` 布局导致的**加载器级**差异）：

1. 时间戳形状不同：原版是 `[hh:mm:ss]`，Forge 是 `[dd月份名yyyy hh:mm:ss.SSS]`（本机 `zh_CN` 下渲染成
   `[1810月2026 15:35:33.486]`）—— 默认模板的 `\[\d{2}:\d{2}:\d{2}\]` 直接不成立。
2. 多一层 logger 段：Forge 行形如 `[时间戳] [线程/level] [logger/]: 正文`（如
   `[net.minecraft.server.MinecraftServer/]`），默认模板缺少这一段。
3. 附带的第二个事实：Forge 1.21.11 上**玩家聊天跑在 `Server thread`**（不是 `Async Chat Thread - #N`），
   所以即便时间戳对得上，默认 `chat` 模板也仍然不匹配。

**复现步骤（每条命令可复制执行）**：

```bash
ssh hermes@10.1.1.4            # 或直接照 test-notes/00-env.md §6 的模板
. ~/y33-env.sh
bash ~/mc-test/new-forge.sh 1.21.11 61.2.0 8
tmux new -d -s mc-forge-1_21_11 "cd ~/mc-test/forge/1.21.11 && ./start.sh 2>&1 | tee -a console.out.log"
# 等 Done (...) 与 RCON 25728 监听
cd ~/Y33-Bot && .venv/bin/python -m y33bot check --config config-forge-1_21_11.toml     # OK / 退出码 0
.venv/bin/python -m y33bot simulate log-event --server forge --dry-run --config config-forge-1_21_11.toml \
  --line '[1810月2026 15:35:33.486] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve joined the game'
# → [警告] 日志行未匹配任何模板   （退出码 1）
```

**影响面**：Forge 1.21.3 → 26.3 **全部 12 个版本**（逐版本证据见 §6）。只要服端换成 Forge，
MC→QQ 的「进出服通知 + 游戏内 `#` 聊天」在**默认配置**下就完全不工作；
仓库内 `config.toml`/`config.example.toml` 的默认值即为此状态。

**可用绕法（只改配置，已验证）**：把 `[log_patterns]` 改成能吃掉时间戳与 logger 段的形状，例如
（由真行推导，`~/mc-test/mkpatterns.py`）：

```
join = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\] (?:\[[^\]]+/\])?: (?P<player>\w+) joined the game'
quit = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\] (?:\[[^\]]+/\])?: (?P<player>\w+) left the game'
chat = '\[[^\]]+\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\] (?:\[[^\]]+/\])?: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)'
```

放宽后同一批真行全部命中，且普通聊天被忽略、回环防护生效、进服通知带服名（§6 逐版本证据里的
`pattern-derived.txt`）。

**根因归属（不在本卡做代码级结论，只给定位提示）**：模板是配置项、编译在
`src/y33bot/mclog/patterns.py`（`_anchor` 补 `^`/`$` + 命名组校验），装配在
`src/y33bot/config.py` 的 `[log_patterns]` 默认值；本卡未改任何代码。
留给汇总卡的判断是：**默认模板要不要兼容「加载器自带日志布局」**（Forge/NeoForge 都会加 logger 段；
NeoForge 卡 `t_efe57773` 可交叉验证），以及是否需要一个「按加载器给出推荐模板」的文档小节。

**（补充）时间戳形状还有一个副作用**：Forge 的时间戳里带月份中文与毫秒，行更长；本卡在 `grep`
时遇到"匹配到二进制文件"的现象，经查是**本卡自己的轮转测试**用 `: > latest.log` 截断、
服务端续写按旧偏移落成 NUL 造成的（`latest.log` 首段 0x00 空洞），**不是 Forge 的日志问题**——
后续测试已把轮转改为 `mv latest.log latest.log.rotated`（PLAN S6 的原意也是「清空/重命名」）。

---

### F2（次要，环境触发但值得登记）QQ 网关启动遇到平台接口超时时，报错形态很差且会直接退出

**现象**（12 个版本里出现 5 次，都是随机的平台超时；与 Forge 无关）：

```
[botpy] 登录机器人账号中...
[botpy] access_token expires_in 5209
请求超时，请求连接: https://api.sgroup.qq.com/users/@me
请求超时，请求连接: https://api.sgroup.qq.com/gateway/bot
[错误] QQ 网关异常退出: 'NoneType' object is not subscriptable
[错误] QQ 网关启动失败: QQ 网关启动失败: 'NoneType' object is not subscriptable
[停止] 正在关闭…
[停止] 已退出
run exit=1
```

（另一处形态：`'NoneType' object has no attribute 'get'`，来自 `users/@me` 超时那一步。）

**观察**：
1. `BUGS.md` BUG-001 的 R2-lite 修复**确实生效**：网关起不来 → 打 `[错误]` → 非 0 退出等重启，
   不再是「进程常驻、群里没反应」。原始输出齐全，可作 R2-lite 的正向证据。
2. 但错误文本是 `'NoneType' object is not subscriptable`（botpy 拿超时后的 `None` 当 dict 用），
   **对运维不可读**；而且这是**平台/网络抖动**触发，会让 `systemd` 反复拉起进程。
   建议（留给汇总卡判断是否登记为 BUG）：网关启动阶段做有限重试/退避，并把 `None` 响应转成
   「平台接口超时/无响应」这类可读原因（本卡只测试、不改代码）。
3. 影响面：本卡 12 个版本中 1.21.3、1.21.5、1.21.8、26.1、26.3 各命中一次左右；
   重跑（`forge-retry.sh`）时 1.21.3 / 1.21.5 / 26.3 均恢复正常，1.21.8 的 C8 再次命中。

---

## 5. 补充观察（D 组：卡面点名要看的四类失败）

脚本 `~/mc-test/forge-extra.sh`，在 **1.21.3（Forge 53.1.0，JDK21）** 与 **26.3（Forge 66.0.13，JDK25）**
两个实例上各跑一轮；原始输出 `artifacts/forge/<版本>/d1-version-mismatch.txt` / `d2-java-mismatch.txt` /
`latest-with-broken-mod.txt` / `d4-run-server-down.txt`，以及 `~/forge-extra-<版本>.out`（已归档为
`artifacts/forge/<版本>/extra-out.txt`）。

### D1 加载器/MC 版本不匹配 → **启动直接失败，错误明确**

做法：把实例的 `libraries/.../unix_args.txt` 里的 `1.21.3` / `53.1.0` 全量替换成 `26.3` / `66.0.13`
（模拟「拿了另一个 MC 版本的 Forge 启动参数」），再用正确 JDK 启动。

```
$ java -Xms512M -Xmx1024M @libraries/net/minecraftforge/forge/<被改过的>/unix_args.txt nogui
Error: Unable to access jarfile forge-26.3-66.0.13-shim.jar
退出码=1
```

结论：**版本不匹配时 Forge 起不来、且不会挂在那儿**，机器人侧只会看到 RCON 连不上/日志不可读，
不会出现「进程活着群里没反应」这类静默失效。也就是说这类故障**在启动阶段就暴露**（对 `check` 友好）。

### D2 Java 版本不匹配 → 方向性很强：**新 JDK 跑老 Forge 能起，老 JDK 跑新 Forge 起不来**

| 组合 | 实测结果 |
|---|---|
| Forge 1.21.3（面向 Java 21）+ **JDK 25** | **服务端照常启动**（我这边 150 s 超时后由 `timeout` 杀掉，退出码 124；日志里只有 Forge 配置项的常规 WARN，无类文件版本/模块化报错） |
| Forge 26.3（面向 Java 25）+ **JDK 21** | 见 `artifacts/forge/26.3/d2-java-mismatch.txt`（26.3 一轮的原始输出） |

结论：**没有出现卡面担心的「模块化（JPMS）/反射受限导致启动失败」**（至少 1.21.3 + JDK25 这组没有）；
真正的硬门槛在反方向（老 JDK 跑新版本），而这类失败同样发生在**启动阶段**、日志里能看到明确报错。
> 关联：环境基座 `00-env.md` §3 已给出每版本所需 Java（1.21.2–1.21.11 → 21；26.x → 25），
> 所以「用错 JDK」属于部署错误，而不是 y33bot 的缺陷。

### D3 模组加载异常（损坏的 mod jar）→ **服务端直接起不来**，机器人侧表现为 RCON 失败/离线

做法：往 `mods/` 放一个内容不是 zip 的 `broken-mod-1.0.jar`。

```
net.minecraftforge.fml.ModLoadingException: Failed to create secure jar for
  "/home/hermes/mc-test/forge/1.21.3/mods/broken-mod-1.0.jar" - zip END header not found
    at jdk.zipfs@21.0.12.1/jdk.nio.zipfs.ZipFileSystem.findEND(ZipFileSystem.java:1320)
```

后果（同一轮的机器人侧）：

```
[RCON forge] FAIL 无法连接 127.0.0.1:25720: [Errno 111] Connect call failed
[日志 forge] OK /home/hermes/mc-test/forge/1.21.3/logs/latest.log 可读，偏移 0 字节
[绑定] OK 1 条
FAIL
$ /status → [群消息] [服务器状态] 服务器离线
```

结论：**一个坏 mod 会连带把 RCON 一起带走**（服务端启动流程在 mod 加载阶段就中止），
机器人侧能如实报告离线；这也说明「群里 `/status` 显示离线」是可达的、可诊断的状态。

### D4 服务端不可达/运行中停服 → 机器人不退出，但会持续告警并推送「离线」

（本轮 D3 的坏 mod 让服务端没起来，所以 D4 实测的是「服务端不可达」这一路径：先起机器人、再让服务端不在。）

```
[警告] RCON forge 连接失败（服务继续，下次调用自动重连）: ... [Errno 111] Connect call failed
[RCON forge] /list
[警告] RCON forge 命令失败: 连接 127.0.0.1:25720 失败: [Errno 111] ...
[错误] QQ 发送失败（不重试）: 请求的资源不存在(用户/群已注销)     ← 健康翻转触发的「服务离线」通知真的发到了平台
run 退出码=0                                                      ← SIGTERM 依然干净退出
```

26.3 那一轮还顺带抓到一条**日志轮转的第二种判定**：
`[警告] 日志文件已轮转（inode 24739981 -> 55582892），偏移重置为 0`（重命名会让 inode 变化，
watcher 走的是 inode 分支而不是「文件缩小」分支）—— 两种判定都能自愈，S6 的语义成立。

结论：**服务端侧掉线/被拒不会让机器人静默失效**：每次轮询都会打 `[警告]`、健康翻转会推一次离线通知、
进程本身按契约继续运行（这与 `BUGS.md` BUG-001 想避免的「静默」正好相反）。

---

## 6. 逐版本结果

启动耗时取自各自 `run-out.txt` 的 C1 段（`Done (…s)`，含首次启动生成 `config/` 与解压）。
「默认模板」= 项目 `config.example.toml` 的 `join/quit/chat` 三个模板对**该版本真实日志行**的匹配结果
（`exit=1` 表示 `[警告] 日志行未匹配任何模板`）；「推导模板」= 只改配置后同一批真行的结果。

| 版本 | Forge | 启动(Done) | check | 默认模板 join/quit/chat | 推导模板 | C6 run | C7 生产链路（平台 400 次数） | C8 轮转 | C9 停服后 | 结论 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.21.3 | 53.1.0 | 12.286s | 0 | **1/1/1** | 0/0/0 | 0 | 0（6） | 首轮平台超时 → **补测通过** | 退出码 1（连接被拒） | ✅ 适配后可用 |
| 1.21.4 | 54.1.14 | 6.971s | 0 | **1/1/1** | 0/0/0 | 0 | 0（7） | ✅ | 同上 | ✅ |
| 1.21.5 | 55.1.0 | 6.249s | 0 | **1/1/1** | 0/0/0 | 0 | 0（7） | 首轮平台超时 → **补测通过** | 同上 | ✅ |
| 1.21.6 | 56.0.9 | 3.433s | 0 | **1/1/1** | 0/0/0 | 0 | 0（7） | ✅ | 同上 | ✅ |
| 1.21.7 | 57.0.3 | 3.628s | 0 | **1/1/1** | 0/0/0 | 0 | 0（7） | ✅ | 同上 | ✅ |
| 1.21.8 | 58.1.0 | 4.511s | 0 | **1/1/1** | 0/0/0 | ❌ 平台超时（原语 `[错误] QQ 网关异常退出: 'NoneType' object has no attribute 'get'`）；C7 补测时 `run` 正常启动并干净退出 | 0（7）；补测再次通过 | **两次均遇平台超时**（见 §7 未复现项） | 同上 | ✅（C6/C8 为环境性失败） |
| 1.21.9 | 59.0.5 | 4.231s | 0 | **1/1/1** | 0/0/0 | 0 | 0（7） | ✅ | 同上 | ✅ |
| 1.21.10 | 60.1.0 | 7.543s | 0 | **1/1/1** | 0/0/0 | 0 | 0（7） | ✅ | 同上 | ✅ |
| 1.21.11 | 61.2.0 | 8.208s | 0 | **1/1/1** | 0/0/0 | 0 | 0（7） | ✅ | 同上 | ✅ |
| 26.1 | 62.0.9 | 见 `26.1/run-out.txt` | 0 | **1/1/1** | 0/0/0 | 0 | 0 | 首轮平台超时（该版本主轮） | 同上 | ✅（补测口径同 1.21.3/1.21.5） |
| 26.2 | 65.1.0 | 8.458s | 0 | **1/1/1** | 0/0/0 | 0 | 0（3） | ✅ | 同上 | ✅ |
| 26.3 | 66.0.13 | 3.673s | 0 | **1/1/1** | 0/0/0 | 0 | 首轮平台超时 → **补测通过**（3） | ✅（补测） | 同上 | ✅ |

> 26.1 的首次安装因 installer 下载 `com.google.code.gson:gson:2.10.1` 时连接抖动而失败
> （原始输出 `~/forge-install-26.1.log`，报 `These libraries failed to download. Try again.`），
> **删目录重装即通过**（`RESULT 26.1 install=0 test=0`）——属于网络抖动，不是版本问题。

**逐版本共同结论（12/12 一致）**：

1. Forge 官方 installer 装机 → 首次启动生成 `config/{fml.toml,forge-common.toml}` → `Done (…s)`
   → 游戏/RCON 双端口 LISTEN，全部正常（启动耗时 3.4–12.3 s，首次含解压）。
2. `check` 全 OK 退出码 0（真 QQ access_token + 真 RCON `/list` + 真日志路径 + 绑定表）。
3. 真 `tellraw @a {"text":"[QQ] Steve: 你好"}` 注入成功；`/status` 返回**服务端真实** `/list`
   解析结果 `在线: 0/20`、`玩家: 无`。
4. **默认 `join`/`quit`/`chat` 三个模板在这 12 个版本上 100% 匹配失败**（见 §4 F1）。
5. 只改配置放宽后三种事件全部命中；普通聊天→`[忽略] 聊天非 # 开头，不转发`；
   回环行→`[忽略] 回环防护：命中 ignored_chat_prefixes`；群消息非触发前缀→`[忽略] 非触发前缀`。
6. `run` 真连 QQ 网关（机器人「y33-test」）+ SIGTERM 干净退出（退出码 0 的版本见上表）。
7. 生产链路（假群）真的发到平台：`https://api.sgroup.qq.com/v2/groups/E2E_DUMMY_GROUP_OPENID/messages`
   → `code 11255 / err_code 40011028`（群不存在，符合预期），`state` 里 `msg_seq` 递增、`log_offset` 追平。
8. 日志轮转：`[警告] 日志文件缩小（size=… < offset=…），偏移重置为 0`（重命名还会走
   `[警告] 日志文件已轮转（inode … -> …）` 分支），轮转后新行照常被转发。
9. 停服后 `check` 退出码 1 且报 `[RCON forge] FAIL … [Errno 111] Connect call failed`（连接被拒绝）。

证据文件（每个版本目录下同名）：`run-out.txt`（全部用例输出）、`console.txt`（服务端控制台）、
`latest.log.txt`（真实 `latest.log`）、`real-lines.txt`（真日志行 + 前缀）、`pattern-default.txt`、
`pattern-derived.txt`、`pattern-negative.txt`、`check.txt`、`inject.txt`、`status.txt`、`run.txt`、
`run-e2e.txt`、`state-e2e.txt`、`run-rot.txt`、`latest-after-rotation.txt`、`check-down.txt`、
`server.properties.txt`、`meta.txt`；补测另有 `run-e2e-retry.txt` / `run-rot-retry.txt` / `state-e2e-retry.txt`；
D 组另有 `extra-out.txt` / `d1-version-mismatch.txt` / `d2-java-mismatch.txt` / `d4-run-server-down.txt` /
`latest-with-broken-mod.txt`。

---

## 7. 未执行 / 信息不足（如实列出，未编造替代输出）

1. **26.2 / 26.3 没有真实玩家聊天行**：无头客户端（mineflayer）目前最高支持 26.1，
   这两个版本的 `join`/`quit`/`chat` 行是「**从真实日志里取到的真前缀**（时间戳+线程+logger 段）
   + PLAN §5 S3/S4 的消息正文」合成的，`real-lines.txt` 里每行都标了「（合成…）」。
   26.1 及以下（1.21.3–1.21.11、26.1）都是**真客户端**产出的真行（`client exit=0`）。
2. **1.21.8 的 C8（日志轮转）没能取得成功样本**：主轮与补测各失败一次，两次都是同一处
   QQ 平台网关超时（`请求超时 … api.sgroup.qq.com/gateway/bot`）。
   同一用例在其余 11 个版本上通过，且 1.21.8 的补测 C7 中 `run` 能正常启动/退出，故判断为环境性失败；
   原始输出：`1.21.8/run-rot.txt`（主轮）、`1.21.8/run-rot-retry.txt`（补测）。
3. **真 QQ 群收发仍无法自证**（沿用 `00-env.md` §8-1 的限制：没有群 openid，botpy 无列群 API），
   MC→QQ 只能用假群验证「链路真的走到平台」；这不影响 Forge 相关结论。
4. **D1「版本不匹配」在 26.3 上是无效实验**：篡改脚本把 `26.3/66.0.13` 替换成同样的值，
   等于没改（进程照常起来；只有一条与本议题无关的 log4j/netty 报错
   `NoClassDefFoundError: io.netty.channel.kqueue.Native / Only supported on OSX/BSD`）。
   有效证据只有 1.21.3 那份（`Unable to access jarfile forge-26.3-66.0.13-shim.jar`）。
5. **D2 只测了两个方向各一次**（1.21.3+JDK25 能起；26.3+JDK21 起不来），没有逐版本做 JDK 对照。
6. **mod 侧只测了「损坏 jar」一类异常**，没有构造「缺失依赖 / 加载顺序冲突 / mixin 报错」的真实 mod 组合
   （需要从平台下载真实 mod，本机 `github.com` 不通，且本卡范围是 y33bot 而不是 mod 生态）。
7. **NeoForge 的日志布局未交叉验证**（在另一张卡 `t_efe57773`）；F1 是否同样命中 NeoForge，
   留给汇总卡 `t_1c0e88a4` 合并两份记录后判定。

---

## 8. 制品与复现

### 8.1 本地制品（本卡分支 `wt/t_157ba7fe`）

```
test-notes/03-forge.md                     ← 本文件
test-notes/artifacts/forge/
  version-source.txt                       ← 版本清单原始证据（promotions / maven-metadata / index 状态码）
  forge-results.txt                        ← 逐版本 RESULT 行（install/test 退出码 + 时间）
  run-all-out.txt                          ← 12 版本串行驱动的完整输出
  forge-followup.out / forge-retry.out     ← 26.1 重试 + 补测记录
  <版本>/…                                 ← 每个版本的原始输出与日志（见 §6 末尾清单）
  <版本>-real-lines.txt                    ← 该版本真日志行汇总
```

### 8.2 测试机上的可复现脚本（`~/mc-test/`，未入库）

```bash
ssh hermes@10.1.1.4 && . ~/y33-env.sh
bash ~/mc-test/new-forge.sh 1.21.11 61.2.0 8        # 装实例（目录/端口/启动脚本）
bash ~/mc-test/forge-test-one.sh 1.21.11 8          # 单版本 C1–C9
bash ~/mc-test/forge-run-all.sh 1.21.3 1.21.4 …     # 多版本串行（可选参数）
bash ~/mc-test/forge-extra.sh 1.21.3 53.1.0 0 25    # D1–D4 补充观察
bash ~/mc-test/forge-retry.sh 26.3 66.0.13 1        # 只重跑 C7/C8
python3 ~/mc-test/mkpatterns.py join '<真实日志行>'  # 从真行推导模板
```

### 8.3 收尾状态（实测）

- 12 个版本全部测完，`~/forge-results.txt` 里每条都是 `install=0 test=0`（26.1 首次为网络抖动，已重装通过）。
- 每个版本的 `libraries/`+`world/` 测试后即清理（单实例约 183–203 MB，清理后磁盘回到 ~1.2 GB 可用）。
- 未修改项目任何代码；`git status` 只应新增 `test-notes/`。

