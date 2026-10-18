# 02 · Fabric 加载器实机测试矩阵（卡 t_5bccfcd8）

> 本文件是 **Fabric 族的实机测试记录**：近两年（2024-10-18 之后）发布的每个「版本线首版」上，
> 用官方 fabric-installer 装出可玩的 Fabric 服务端（Loader + fabric-api），再按项目文档的测试流程
> （`docs/smoke.md` 的 S1–S6 / `PLAN.md` §5）逐条跑完整用例。
> 文中每条输出都是在这台测试机上真实执行后粘贴的，原始制品在 `test-notes/artifacts/fabric/<版本>/`。
>
> 卡内约束：**只测试与记录，不修改项目代码，不做代码级根因分析**（根因与登记由汇总卡 `t_1c0e88a4` 负责）。
> 环境基座（JDK / 端口表 / 脚本模板）见 `test-notes/00-env.md`，本卡复用、不重复搭环境。

---

## 0. 验收对照（卡 t_5bccfcd8）

| 验收项 | 要求 | 实测结果 | 证据 |
|---|---|---|---|
| 版本清单与理由 | 明确列出要覆盖的版本 + 依据 | ✅ §1（近两年 9 个版本线首版，含 1.21.11 对照版） | §1 表格 |
| 每版本都有明确结论 | 清单内每个版本跑完并给出通过/失败 | ✅ 9/9：**7 个通过**、**2 个部分通过**（26.2 / 26.3，原因见 F-2） | §3 总表 + `results-<版本>.txt` |
| 失败项可复现 + 原始日志 | 失败要有复现步骤与原始制品 | ✅ F-1（聊天模板不匹配）逐版本给真日志行与命令；F-2 给客户端探测原文 | §4、`artifacts/fabric/<版本>/` |
| 按文档测试流程跑完整用例 | 覆盖 S1–S6 | ✅ T1–T8 逐条（含真 RCON、真玩家、常驻 run、日志轮转） | §2 用例映射表、§3 逐版本详情 |
| 关注加载器/API 不匹配等异常 | 记录 ClassLoader/ASM/依赖/协议差异 | ✅ 均未复现（§4 F-4），另加 loader 0.20.0 变体用例 | §3.10 |
| 未修改项目代码 | 只新增 `test-notes/` | ✅ 本卡改动仅 `test-notes/02-fabric.md` + `test-notes/artifacts/fabric/` | git 提交 |

---

## 1. 版本清单与理由

### 1.1 口径

- **时间窗口**：`2024-10-18`（测试日 2026-10-18 往前两年）之后发布的正式版。
  窗口外的前一个正式版是 `1.21.1`（2024-08-08），**不测**。
- **「x.xx.0」的解读**：只看**每个版本线的首个正式版**，不细化到补丁版。
  依据两类事实定稿：
  1. 任务描述「只要 x.xx.0，不需要细化到 x.xx.xx」；
  2. `00-env.md` §3 已把 26.x 明确为「x.xx.0 形态」（26.1 / 26.2 / 26.3）。
  于是窗口内的线首版 = `1.21.2`、`1.21.4`、`1.21.5`、`1.21.6`、`1.21.9`、`26.1`、`26.2`、`26.3`
  （`1.21.3`/`1.21.7`/`1.21.8`/`1.21.10`/`1.21.11` 是各自线的补丁版；`26.1.1`/`26.1.2` 是 26.1 的补丁版）。
- **额外加的对照版 `1.21.11`**：`00-env.md` §7-10 在现场发现「聊天日志行与项目默认模板不匹配」，
  该现象最早是在 1.21.11 上抓到的；把它加进矩阵，用来判断这个现象是新版本才有，还是整窗口都有。
  （结论：整窗口都有，见 F-1。）
- **Fabric 官方支持性**：`meta.fabricmc.net/v2/versions/game` 里上述 9 个版本全部 `stable=true` 且都在
  Fabric 的 game 版本列表内（清单共 531 条），fabric-api 也都有对应构建（§1.2），故全部纳入。

### 1.2 逐版本实测配置（脚本自动选 JDK、分配端口，实际值）

| slot | 版本 | 发布日 | Java | 端口（游戏/RCON） | 服名 | Loader | fabric-api | 启动 `Done(...)` |
|---|---|---|---|---|---|---|---|---|
| 0 | 1.21.2 | 2024-10-22 | 21 | 25610 / 25710 | `fab1212` | 0.19.5 | 0.106.1+1.21.2 | 22.228s |
| 1 | 1.21.4 | 2024-12-03 | 21 | 25611 / 25711 | `fab1214` | 0.19.5 | 0.119.4+1.21.4 | 14.891s |
| 2 | 1.21.5 | 2025-03-25 | 21 | 25612 / 25712 | `fab1215` | 0.19.5 | 0.128.2+1.21.5 | 24.758s |
| 3 | 1.21.6 | 2025-06-17 | 21 | 25613 / 25713 | `fab1216` | 0.19.5 | 0.128.2+1.21.6 | 15.512s |
| 4 | 1.21.9 | 2025-09-30 | 21 | 25614 / 25714 | `fab1219` | 0.19.5 | 0.134.1+1.21.9 | 7.833s |
| 5 | 1.21.11 | 2025-12-09 | 21 | 25615 / 25715 | `fab12111` | 0.19.5 | 0.141.6+1.21.11 | 10.441s |
| 6 | 26.1 | 2026-03-24 | 25 | 25616 / 25716 | `fab261` | 0.19.5 | 0.145.1+26.1 | 7.180s |
| 7 | 26.2 | 2026-06-16 | 25 | 25617 / 25717 | `fab262` | 0.19.5 | 0.161.0+26.2 | 12.183s |
| 8 | 26.3 | 2026-09-15 | 25 | 25618 / 25718 | `fab263` | 0.19.5 | 0.163.0+26.3 | 9.175s |
| 附加 | 26.3（变体） | — | 25 | 25619 / 25719 | `fab263l020` | **0.20.0** | 0.163.0+26.3 | 3.401s |

- **Loader 固定用最新「标记为 stable」的 `0.19.5`**（`meta.fabricmc.net/v2/versions/loader` 里
  `stable:true` 的最新一条；`0.20.0` 已发布但 `stable:false`）。把 loader 当常量，
  矩阵才是「MC 版本」的对照；loader 的版本差异另用 §3.10 的变体用例覆盖。
- **fabric-api 取 maven 上该 MC 版本的最新构建**（`+<MC版本>` 后缀），例如 26.3 → `0.163.0+26.3`。
  在 9 个版本上，这个「最新 API + 稳定 loader」组合**全部一次装成、全部能起**（无分辨率错误）。
- 启动耗时含首次解压/下载 `libraries/`；1.21.2 的 22.2s 与 1.21.5 的 24.8s 是当时机器被其他矩阵卡挤占
  （日志里有 `Can't keep up!`），不是 Fabric 的问题。

---

## 2. 测试方法（可复现）

### 2.1 实例怎么装（服务器上一条命令）

```bash
. ~/y33-env.sh                                  # JAVA_HOME/PATH + ~/.env（含 MC_RCON_PASSWORD）
bash ~/mc-test/new-fabric.sh 1.21.2 0           # 版本 + slot；自动选 JDK、分配端口、下依赖
# 结果：~/mc-test/fabric/1.21.2/{server.jar,fabric-server-launch.jar,libraries/,mods/,start.sh,instance.env}
```

`new-fabric.sh` 依次做四件事（脚本在 `~/mc-test/new-fabric.sh`，本卡新增；模板抄自基座卡的 `new-vanilla.sh`）：

1. 从 `versions.tsv` 拿 Mojang 官方 `server.jar` 的 URL + sha1，下载并**校验 sha1**；
2. 跑官方安装器 `fabric-installer-1.1.2.jar server -dir <实例目录> -mcversion <版本> -loader 0.19.5`
   （复用它自己下 ASM / mixin / intermediary / fabric-loader 等库）；
3. 从 `maven.fabricmc.net` 的 `fabric-api` maven-metadata 里挑 `+<版本>` 的最新构建，放进 `mods/`；
4. 写 `server.properties`（`enable-rcon=true`、RCON 端口、`online-mode=false`、`pause-when-empty-seconds=0`）、
   `eula.txt`、`start.sh`（`-Xms512M -Xmx1024M -jar fabric-server-launch.jar nogui`）、`instance.env`。

### 2.2 机器人配置（**故意用项目默认日志模板**）

每个版本一份 `~/Y33-Bot/config-fabric-<版本>.toml`（由 `~/mc-test/gen-config-fabric.sh` 生成）：
`port` = 该版本 **RCON 端口**；`[paths] state/bindings` 各自独立（避免多配置互相污染偏移，见 00-env.md §4）；
`group_openid` 填**假群** `E2E_DUMMY_GROUP_OPENID`（本环境拿不到真群 openid，见 §5），
好处是 MC→QQ 方向真的走到平台（预期被拒），能看到完整链路；
`[log_patterns]` **原样复制 `config.example.toml` 的默认模板**，不放宽 —— 本卡的目标之一就是检验默认模板
对真机日志是否匹配。

### 2.3 用例与文档的对应关系

| 本卡用例 | 文档出处 | 做什么 |
|---|---|---|
| T0 | `PLAN.md` §5 前置 | tmux 起服务端，等 `Done (` + RCON 端口在听 |
| T1 | S1 环境与配置自检 | `y33bot check`（**真 QQ 探活** + 真 RCON `/list` + 日志可读 + 绑定表） |
| T2 | S2 QQ→MC | `bind set` + `simulate group-message '#你好'`（**真 RCON**，无 `--dry-run`），并用**真客户端**核对游戏内可见 |
| T3 | S2 QQ→MC | `simulate group-message '/status'` → 回复内容来自服务端**真实 `/list` 响应** |
| T4 | S3 MC→QQ | 无头客户端真进服 → 发普通聊天 + `#` 聊天 → 退服，抓**真实日志行**，再用默认模板逐行解析 |
| T5 | S3 回环防护 | 用真行格式的 `[QQ] …` 文本验证 `ignored_chat_prefixes` |
| T6 | S4 健康翻转 | `simulate health --offline` ×2 + `--online`（离线只提示一次） |
| T7 | S5 常驻运行 | `y33bot run --verbose` 真连 QQ 网关；运行期真玩家进服/聊天 → MC→QQ 真链路；`SIGTERM` 看退出码 |
| T8 | S6 日志轮转 | 运行中清空 `latest.log` → 期望「日志文件缩小…偏移重置为 0」+ 新行被解析转发 |
| T9 | — | 优雅停服 + 制品归档 + 清理可再生目录 |

### 2.4 脚本与制品

```bash
# 一键跑完 9 个版本（服务器上，约 40 分钟，含资源门控等待）
nohup setsid bash ~/mc-test/fabric_drive.sh > ~/mc-test/fabric-drive.out 2>&1 &
# 单版本重跑（需 new-fabric.sh 先重建 libraries/，见 F-3）
bash ~/mc-test/new-fabric.sh <版本> <slot> && bash ~/mc-test/fabric_smoke_one.sh <版本> <slot>
# 补测（1.21.11 注入可见性 + 26.3 客户端能力）
bash ~/mc-test/fabric_retests.sh
# 附加用例（26.3 + loader 0.20.0）
bash ~/mc-test/fabric_loader_variant.sh
```

本卡新增脚本（服务器 `~/mc-test/` 与本地 `test-notes/artifacts/fabric/scripts/` 各一份）：

| 脚本 | 用途 |
|---|---|
| `new-fabric.sh` | 建/复用 Fabric 实例：下 vanilla jar（sha1 校验）→ 跑 fabric-installer → 装 fabric-api → 写 `server.properties`/`start.sh`/`instance.env` |
| `gen-config-fabric.sh` | 按版本生成 `config-fabric-<版本>.toml`（默认日志模板 + 独立 state/bindings + 假群 openid） |
| `fabric_smoke_one.sh` | 单版本 T0–T9 全流程（启动 → check → 注入 → `/status` → 真玩家 → 健康 → run → 轮转 → 停服 → 归档） |
| `fabric_drive.sh` | 9 版本串行驱动（含资源门控、逐版本 tee 出 `test-<版本>.txt`） |
| `fabric_retests.sh` | 补测：1.21.11 注入可见性（等 spawn 再注入）+ 26.3 客户端能力探测 |
| `fabric_loader_variant.sh` | 附加用例：26.3 + loader 0.20.0 |
| `client_hold.js` | 保持在线版无头客户端：打印收到的每条聊天/系统消息（注入可见性证据） |

### 2.5 环境限制（本卡遇到的）

| 限制 | 影响 | 本卡怎么处理 |
|---|---|---|
| 测试机 2.6G 内存 / 2 vCPU，四张矩阵卡共用 | 同跑多个服务端会 OOM | 脚本里有**资源门控**：等无其他实例且可用内存 ≥900M 再启动（最长等 30 分钟）；磁盘 <700M 时看门狗删掉**已跑完版本**可再生的 `server.jar` |
| 磁盘总可用 2.5G | 9 个实例的 `libraries/` 会吃掉全部空间 | 每个版本测完删 `libraries/ world/ logs/`，只留 `server.jar` + 制品 |
| 无头客户端（mineflayer + minecraft-data）最高支持 **26.1** | 26.2/26.3 造不出真玩家日志行 | 见 F-2，如实标注「未验证」而不是编造 |
| `group_openid` 未知（botpy 无列群 API） | 真群收发无法自证 | MC→QQ 用假群打到平台，看真实 400 响应（§3.1 的 T7 证据） |
| 资料中未含的真实 QQ 群 | 同上 | 同上 |

---

## 3. 逐版本结果

### 3.1 总表

`✅` 通过 / `❌` 失败 / `—` 该版本不适用或未验证。T4 的「模板」列指**项目默认模板**对**真机日志行**的匹配。

| 版本 | T0 启动 | T1 check | T2 真注入（客户端可见） | T3 `/status` 真往返 | T4 join/quit/chat 模板 | T6 健康翻转 | T7 run 退出码 | T8 轮转 | 结论 |
|---|---|---|---|---|---|---|---|---|---|
| 1.21.2 | ✅ | ✅ exit 0 | ✅（✅ 客户端收到） | ✅ `1/20 … Watcher` | ✅/✅/**❌** | ✅ | ✅ 0 | ✅ | **通过**（除 F-1） |
| 1.21.4 | ✅ | ✅ exit 0 | ✅（✅） | ✅ | ✅/✅/**❌** | ✅ | ✅ 0 | ✅ | **通过**（除 F-1） |
| 1.21.5 | ✅ | ✅ exit 0 | ✅（✅） | ✅ | ✅/✅/**❌** | ✅ | ✅ 0 | ✅ | **通过**（除 F-1） |
| 1.21.6 | ✅ | ✅ exit 0 | ✅（✅） | ✅ | ✅/✅/**❌** | ✅ | ✅ 0 | ✅ | **通过**（除 F-1） |
| 1.21.9 | ✅ | ✅ exit 0 | ✅（✅） | ✅ | ✅/✅/**❌** | ✅ | ✅ 0 | ✅ | **通过**（除 F-1） |
| 1.21.11 | ✅ | ✅ exit 0 | ✅（补测 ✅） | ✅ | ✅/✅/**❌** | ✅ | ✅ 0 | ✅ | **通过**（除 F-1） |
| 26.1 | ✅ | ✅ exit 0 | ✅（✅） | ✅ | ✅/✅/**❌** | ✅ | ✅ 0 | ✅ | **通过**（除 F-1） |
| 26.2 | ✅ | ✅ exit 0 | ✅（无客户端核对） | ✅ | **未验证** / **未验证** / **未验证** | ✅ | ✅ 0 | ✅（合成行） | **部分通过**（F-2） |
| 26.3 | ✅ | ✅ exit 0 | ✅（无客户端核对） | ✅ | **未验证** / **未验证** / **未验证** | ✅ | ✅ 0 | ✅（合成行） | **部分通过**（F-2） |
| 26.3 + loader 0.20.0 | ✅ | ✅ exit 0 | —（未 bind，见 §3.10） | ✅ | — | — | — | — | **通过**（变体用例） |

每个版本完整结果行（机器可读）在 `test-notes/artifacts/fabric/results-<版本>.txt`，全流程输出在同目录
`test-<版本>.txt`（服务器上还有一份 `~/mc-test/fabric/<版本>/test-<版本>.txt`）。

### 3.2 服务端启动 + 依赖装载（每个版本都一致）

```text
[15:21:50] [main/INFO]: Loading Minecraft 26.1 with Fabric Loader 0.19.5
[15:21:50] [main/INFO]: Mappings not present!
[15:21:50] [main/INFO]: Loading 40 mods:
    - fabric-api 0.145.1+26.1
       |-- fabric-api-base 2.0.3+ece0632347
       |-- fabric-api-lookup-api-v1 2.0.10+d5a053b647
       |-- fabric-biome-api-v1 18.0.4+35c80edc47
       |-- fabric-block-api-v1 3.0.2+ec56b60147
...
[15:22:08] [Server thread/INFO]: Done (7.180s)! For help, type "help"
[15:22:08] [Server thread/INFO]: RCON running on 0.0.0.0:25716
```

（原始输出：`26.1/console-26.1.txt`；各版本的 `Loading N mods`：1.21.2→41、1.21.4→42、1.21.5→42、
1.21.6→39、1.21.9→41、1.21.11→41、26.1→40、26.2→42、26.3→42。日志里的 `Mappings not present!`
是 Fabric 在正式版上的正常提示，不是错误。）

### 3.3 T1 `check`（真 QQ 探活 + 真 RCON）—— 全部 exit 0

以 1.21.2 为例（`1.21.2/test-1.21.2.txt`）：

```text
[配置] OK config-fabric-1.21.2.toml 解析成功，1 个 MC 服
[QQ] OK access_token 获取成功（有效期 1517s），app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON fab1212] OK /list -> There are 0 of a max of 20 players online:
[日志 fab1212] OK /home/hermes/mc-test/fabric/1.21.2/logs/latest.log 可读，偏移 55 字节
[绑定] OK 1 条
OK
```

9 个版本全部 `OK / check_exit=0`；26.x（JDK25 路径）同样通过，例如 26.3：

```text
[RCON fab263] OK /list -> There are 0 of a max of 20 players online:
[日志 fab263] OK /home/hermes/mc-test/fabric/26.3/logs/latest.log 可读，偏移 0 字节
OK
```

### 3.4 T2 QQ→MC 真注 + 真客户端可见（7 个版本有客户端核对）

```text
[绑定] 已写入 1A2B3C4D -> Steve (data/bindings-fabric-1.21.2.toml)
[hold] 连接 127.0.0.1:25610 用户名 Watcher 保持 30s
[hold] 已 spawn（进服成功），版本协商: 1.21.3
[RCON fab1212] tellraw @a {"text":"[QQ] Steve: 你好"}
>>> [RESULT] tellraw_exit=0
>>> [RESULT] client_saw_tellraw=yes
3:[hold 06:57:13] 收到: [QQ] Steve: 你好
```

客户端真的在游戏内收到了机器人注入的消息（这条「游戏内可见」是基座卡不能自证的，因为注入命令的回显只能说明 RCON 调用成功）：
1.21.2 / 1.21.4 / 1.21.5 / 1.21.6 / 1.21.9 / 26.1 都是 `client_saw_tellraw=yes`；
1.21.11 首轮因为**客户端 spawn 慢于注入**（`Preparing spawn area` 期间机器被其他矩阵卡挤占）漏测，
补测（等客户端打印「已 spawn」后再注入）通过：

```text
[补测] 1.21.11 启动等待轮次=8 端口 1
[补测A] 客户端 spawn 等待轮次=6 spawned=yes
[RCON fab12111] tellraw @a {"text":"[QQ] Steve: 你好"}
[补测A] 客户端收到注入消息: yes
[hold 07:43:48] 收到: [QQ] Steve: 你好
```

（原始：`1.21.11/client-hold-1.21.11-retest.txt`、`1.21.11/results-1.21.11-retest.txt`、
`fabric-retests.out`。）

### 3.5 T3 `/status` 真往返

```text
[RCON fab1212] /list
[群消息] [服务器状态]
[群消息] 在线: 1/20
[群消息] 玩家: Watcher
>>> [RESULT] status_exit=0
```

`1/20` 和玩家名 `Watcher` 都来自服务端真实 `/list` 响应（当时保持在线客户端在服里），不是模拟数据。
26.1 上的输出同样是 `在线: 1/20 / 玩家: Watcher`；其余版本 `在线: 0/20 / 玩家: 无`（T2 的客户端已退出）。

### 3.6 T4 进出通知 ✅ / 聊天模板 ❌（**本卡主要发现**，见 §4 F-1）

1.21.2 的真实日志行（无头客户端真进服/真聊天/真退服产出）：

```text
[14:57:17] [Server thread/INFO]: Steve joined the game
[14:57:19] [Server thread/INFO]: [Not Secure] <Steve> 大家好，这是普通聊天（不该被转发）
[14:57:20] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
[14:57:22] [Server thread/INFO]: Steve left the game
```

用**项目默认模板**逐行解析：

```text
T4a 默认 join 模板对真进服行 → [群消息] Steve进入了fab1212          （join_template_match=yes）
T4b 默认 quit 模板对真退服行 → [群消息] Steve退出了fab1212          （quit_template_match=yes）
T4c 默认 chat 模板对真 # 聊天行 → [警告] 日志行未匹配任何模板        （chat_template_match=no）
T4d 默认 chat 模板对真普通聊天行 → [警告] 日志行未匹配任何模板        （chatplain_template_match=no）
```

注意：**匹配不上时连「非 # 开头，不转发」都走不到** —— 整行在进入 `Bridge` 之前就被日志解析器丢掉了。
`simulate log-event --line …` 此时退出码为 1（`cli.py` 的 `[警告] 日志行未匹配任何模板` 分支）。

### 3.7 T6 健康翻转（26.3 为例，其余版本一致）

```text
[RCON fab263] /list
[警告] RCON fab263 命令失败: 假 RCON 服务器离线: 127.0.0.1:25718
[群消息] [服务器状态] fab263 离线
[RCON fab263] /list
[警告] RCON fab263 命令失败: 假 RCON 服务器离线: 127.0.0.1:25718
[忽略] 状态未变化，不重复提示
[RCON fab263] /list
[群消息] [服务器状态] fab263 上线
```

### 3.8 T7 常驻 `run` + MC→QQ 真链路（26.1 为例）

```text
[启动] y33bot 0.1.0（1 个 MC 服）
[启动] 日志监听已启动: fab261
[启动] QQ 网关已连接
[启动] QQ 网关就绪
[错误] QQ 发送失败（不重试）: 请求的资源不存在(用户/群已注销)      ← 进服/退服/聊天事件真的发到了平台
...
[停止] 收到退出信号
[停止] 正在关闭…
[停止] 已退出
>>> [RESULT] run_exit=0
```

`[错误] QQ 发送失败` 后面紧跟 botpy 的原始报文，证明**真的走了生产 `BotpyGateway` + 真 HTTP**：

```text
[botpy] 接口请求异常，请求连接: https://api.sgroup.qq.com/v2/groups/E2E_DUMMY_GROUP_OPENID/messages,
错误代码: 400, 返回内容: {'message': '请求的资源不存在(用户/群已注销)', 'code': 11255,
'err_code': 40011028, 'trace_id': '…'}
```

400 是**预期的**（群 openid 是假的，见 §5）；9 个版本的 `run_exit` 全是 0（收到 `SIGTERM` 优雅退出，
没有出现 BUG-001 那种网关静默失效）。26.2/26.3 没有真客户端，运行期只有 1 次平台发送（来自 T8 追加的行）。

### 3.9 T8 日志轮转（S6）

1.21.2（运行中清空 `latest.log` 再追加**该版本自己的真实进服行**）：

```text
日志已清空（清空前大小 7085 字节），当前大小 0
145:[警告] 日志文件缩小（size=0 < offset=7085），偏移重置为 0
148:[错误] QQ 发送失败（不重试）: 请求的资源不存在(用户/群已注销)   ← 追加的行被解析成事件并尝试发送
```

即：偏移重置告警 + 新行被正确解析（26.1 同样：`size=0 < offset=6679`）。
**26.2/26.3 这一条用的是同格式合成行**（`[12:00:04] [Server thread/INFO]: Steve joined the game`，
因为这两个版本造不出真玩家行）——它只证明「轮转 + 模板逻辑」没问题，**不能**用来推断 26.2/26.3 真机日志格式。

### 3.10 附加用例：26.3 + loader 0.20.0

```text
[15:53:12] [main/INFO]: Loading Minecraft 26.3 with Fabric Loader 0.20.0
[15:53:12] [main/INFO]: Loading 42 mods:
    - fabric-api 0.163.0+26.3
[15:53:27] [Server thread/INFO]: Done (3.401s)! For help, type "help"
[配置] OK config-fabric-26.3-loader0.20.0.toml 解析成功，1 个 MC 服
[RCON fab263l020] OK /list -> There are 0 of a max of 20 players online:
OK
[RCON fab263l020] /list
[群消息] [服务器状态] / 在线: 0/20 / 玩家: 无
```

**结论**：`0.20.0`（最新、但 `stable:false`）在 26.3 上同样可用，机器人侧 check 与 `/status` 真往返都通过；
未出现 ClassLoader / mixin / API 分辨率错误。注意本变体**没有**做 bind，所以 `#你好` 走的是「未绑定」回复
（未真正注入），注入项由主矩阵 26.3 用例覆盖。原始：`26.3-loader0.20.0/results-loader-variant.txt`。

---

## 4. 发现（只记录症状与复现，不做代码级根因）

### F-1 ⚠️ 默认 `chat` 模板与真机聊天行不匹配 → 游戏内 `#` 聊天不会被转发到群

**影响版本**：本卡验证到的 **1.21.2 / 1.21.4 / 1.21.5 / 1.21.6 / 1.21.9 / 1.21.11 / 26.1 全部命中**
（26.2/26.3 未能验证，见 F-2）。加载器无关：同样的行在 `00-env.md` §7-10 的原版 1.21.11 上也出现。

**症状**：玩家在游戏内发 `#…`，群里收不到；工程侧只有一条 `[警告] 日志行未匹配任何模板`
（在 `y33bot run` 里是 DEBUG 级，默认看不见；用 `simulate log-event` 时更直接，退出码 1）。
进出服通知、`/status`、QQ→MC 注入都不受影响。

**真机日志行（各版本格式完全一致，`[Not Secure] ` 前缀 + `Server thread` 线程名）**：

```text
1.21.2  [14:57:20] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
1.21.4  [15:01:33] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
1.21.5  [15:05:36] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
1.21.6  [15:08:42] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
1.21.9  [15:12:19] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
1.21.11 [15:14:55] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
26.1    [15:22:31] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
```

而 `config.example.toml`（=`config.toml` 默认值）里是：

```toml
chat = '\[\d{2}:\d{2}:\d{2}\] \[Async Chat Thread - #\d+/INFO\]: <(?P<player>\w+)> (?P<message>.+)'
```

**复现步骤**（任一版本，示例用 1.21.2；不需要重跑服务端，只要有一行真机日志文本）：

```bash
cd ~/Y33-Bot && . ~/y33-env.sh
LINE=$(cat ~/mc-test/fabric/1.21.2/artifacts/real-chat-line-1.21.2.txt)   # 上面那条真行
.venv/bin/python -m y33bot simulate log-event --server fab1212 --line "$LINE" --dry-run --config config-fabric-1.21.2.toml
# → [警告] 日志行未匹配任何模板   （stderr；退出码 1）
```

**对照（证明是模板而不是链路的问题）**：同一条真行，只把配置里的 `chat` 放宽成
`\[\d{2}:\d{2}:\d{2}\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\]: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)`
（**只改配置、不改代码**，基座卡已用 `config-fix.toml` 验证过）就能正常转发。
本卡另外验证：`simulate log-event --kind join --player Steve` 这种不经模板的路径正常。

**证据文件**：每个版本 `test-notes/artifacts/fabric/<版本>/real-chat-line-<版本>.txt`（真行）、
`test-<版本>.txt`（T4c/T4d 的输出与 `>>> [RESULT] chat_template_match=no`）、
`latest-log-<版本>.txt` / `console-<版本>.txt`（服务端原始日志）。

> 根因分析（代码位置、为什么线程名/前缀变了）属于汇总卡 `t_1c0e88a4`；本卡不做结论。

### F-2 26.2 / 26.3 的真玩家日志格式**无法**在本环境验证（信息不足，非产品缺陷）

- `mineflayer` + `minecraft-data` 支持的最高版本是 **26.1**（实测输出：
  `minecraft-data 支持的版本尾部: 1.21.1 1.21.3 1.21.4 1.21.5 1.21.6 1.21.8 1.21.9 1.21.10 1.21.11 26.1`）。
- 直接拿它连 26.3 服务端（25618）的实测原文：

```text
Error: No data available for version 26.3
    at createProtocol (/home/hermes/mc-test/client/node_modules/minecraft-protocol/src/transforms/serializer.js:21:11)
    ...
[client] 出错: No data available for version 26.3
```

- 因此 26.2/26.3 上：`join/quit/chat` 三个默认模板**未验证**（F-1 的结论无法外推到这两个版本）；
  `T8` 轮转用例用的是同格式合成行，只覆盖逻辑不覆盖格式。
- **补齐方式**（后续卡）：等 `minecraft-data` 支持 26.2+，或用一个真 26.2/26.3 客户端手工在服内发一条
  `#…` 并把 `logs/latest.log` 的原始行贴回来。
- 证据：`26.3/client-26.3-probe.txt`、`26.3/minecraft-data-versions.txt`、`fabric-retests.out`。
- （这两版的其它用例都通过：启服、check、真注入 exit 0、`/status` 真往返、健康翻转、run 退出码 0、轮转。）

### F-3 环境/流程坑（**不是产品缺陷**）：清理 `libraries/` 后实例不能再直接启动

本卡为省磁盘在每个版本测完删掉 `libraries/ world/ logs/`。之后若直接 `./start.sh`：

```text
错误: 找不到或无法加载主类 net.fabricmc.loader.impl.launch.server.FabricServerLauncher
原因: java.lang.ClassNotFoundException: net.fabricmc.loader.impl.launch.server.FabricServerLauncher
```

**复现**：`bash ~/mc-test/fabric_smoke_one.sh <版本> <slot>`（末尾会清目录）→ 直接 `cd <实例目录> && ./start.sh`。
**解决**：先 `bash ~/mc-test/new-fabric.sh <版本> <slot>` 重装 loader（会重新拉 `libraries/`）再启动 ——
本卡补测 A 第一轮就踩了这个坑（客户端 `ECONNREFUSED`），改脚本后重跑通过。
仅影响测试流程，不影响项目代码。

### F-4 未复现：加载器/API 版本不匹配、依赖缺失、ClassLoader/ASM 异常、机器人协议差异

任务点名要关注的几类问题，在 9 个版本 + 1 个 loader 变体上**都没有出现**：

- 装载：9 个版本全部用「最新稳定 loader 0.19.5 + 该版本最新 fabric-api」一次装成并启动成功，
  日志中没有 `Incompatible mod set` / `requires fabricloader >= …` / `Mixin` / `ASM` / `ClassLoader` 报错。
- 依赖：`fabric-installer 1.1.2` 自动解析并下载了 `asm 9.10.1`、`sponge-mixin 0.17.4`、
  `intermediary <版本>`、`fabric-loader 0.19.5`（26.3 变体是 `sponge-mixin 0.17.5` + `fabric-loader 0.20.0`），
  没有出现缺库或 sha1 不匹配。
- 机器人侧：RCON 是 MC 自己的协议，Fabric 不改它 —— 9 个版本上 `check`（真 `/list`）、`tellraw` 注入、
  `/status` 往返、健康翻转、日志监听的表现与 `00-env.md` 的原版实例**完全一致**，没有握手/协议差异。
- 唯一「跨版本差异」是 F-1 的日志行格式，而它在本卡覆盖的**整个窗口内都是同一种**（1.21.2 → 26.1 行格式一致），
  所以它不是「新版本才有」，而是**项目默认模板对近两年全部正式版都不匹配**。

### F-5 观测到但不算缺陷的现象（记录备查）

| 现象 | 说明 |
|---|---|
| 运行期日志里大量 `[忽略] 日志行未匹配任何模板: …` | `run --verbose` 下的 DEBUG 级输出，把启动信息、mod 列表、RCON 线程行等全部打出来（属正常解析行为，只是噪声大） |
| `Fabric is preparing JARs on first launch…` / `Mappings not present!` | Fabric 在正式版服务端的正常提示 |
| `[警告] 日志文件已轮转（inode … -> …），偏移重置为 0` | 服务端启动时重建 `latest.log` 触发，属预期（S6 的姊妹分支） |
| `Can't keep up! Is the server overloaded?` | 2 vCPU 上四张矩阵卡并行时的机器负载，不是服务端/项目问题 |

---

## 5. 未验证 / 信息不足清单

| 项 | 为什么没做 | 怎么补 |
|---|---|---|
| 26.2 / 26.3 的 `join/quit/chat` 真机日志行 | 无头客户端不支持这两个协议（F-2） | 换支持 26.2+ 的客户端，或人工在服里发一条 `#…` 并回贴原始行 |
| 1.21.3 / 1.21.7 / 1.21.8 / 1.21.10 / 26.1.1 / 26.1.2 | 按「x.xx.0 不细化到 x.xx.xx」的口径排除（§1.1） | 若需要，用同一套脚本加版本即可（Fabric 段 10 个 slot 本卡已用满 0–9，再多要按 `00-env.md` §5.2 扩段） |
| loader 0.19.x 其它版本、其它 loader/API 组合 | 固定 0.19.5 当常量，另测了 0.20.0 变体（§3.10） | 需要时用 `new-fabric.sh <版本> <slot> <loader>` 换版本重跑 |
| **真** QQ 群的收发（S5 群侧步骤） | 环境里没有真群 openid（botpy 无「列群」API），只能用假群验证链路 | 人给一个真实 `group_openid`，或去群里 `@机器人` 抓一次事件 |
| 多人/高负载下的表现 | 机器只有 2 vCPU / 2.6G，且四张矩阵卡共用 | 单独在闲机上跑压力场景 |
| 1.21.2 上的客户端精确性 | mineflayer 自动协商到 `1.21.3`（同协议），日志行格式一致 | 用真 1.21.2 客户端复核（本卡认为影响可忽略） |

---

## 6. 制品清单（`test-notes/artifacts/fabric/`）

每个版本一个目录，文件名带版本号；`results-<版本>.txt` 是机器可读结果，`test-<版本>.txt` 是**全流程原始输出**。

| 文件（每版本各一份） | 内容 |
|---|---|
| `results-<版本>.txt` | 该版本所有 `>>> [RESULT]` 标记（start/check/tellraw/status/模板匹配/run/轮转） |
| `test-<版本>.txt` | T0–T9 的完整 stdout/stderr（含 check 六行、注入回显、`/status` 回复、健康翻转等） |
| `console-<版本>.txt` | 服务端控制台原始输出（启动全过程、`Loading N mods`、`Done (...)`、`RCON running on …`） |
| `latest-log-<版本>.txt` | 服务端真实 `logs/latest.log`（含真玩家进服/聊天/退服行；因 `.gitignore` 有 `*.log`，统一改名 `.txt`） |
| `latest-log-before-rotate-<版本>.txt` | 轮转用例清空前的日志快照 |
| `real-join-line-<版本>.txt` / `real-quit-line-<版本>.txt` | 从真机日志里抠出的进服/退服行（用于默认模板比对） |
| `real-chat-line-<版本>.txt` / `real-chatplain-line-<版本>.txt` | 真机 `#` 聊天行 / 普通聊天行（F-1 的直接证据） |
| `real-chat-lines-raw-<版本>.txt` | 该版本日志里所有 `<Steve>` 行原文 |
| `client-<版本>.txt` | 无头客户端（进服→普通聊天→`#` 聊天→退服）的输出 |
| `client-hold-<版本>.txt` | 保持在线版客户端输出（含「收到: [QQ] Steve: 你好」= 注入可见性证据） |
| `client-run-<版本>.txt` | `run` 期间第二个真客户端（Steve2）的输出 |
| `run-<版本>.txt` | `y33bot run --verbose` 的完整输出（QQ 网关、MC→QQ 真实发送、轮转告警、退出码） |
| `bindings-<版本>.txt` / `state-<版本>.txt` | 该版本落盘的绑定表 / 状态文件（`log_offset`、`msg_seq`、`health_online`） |
| `1.21.11/…-retest.txt` | 1.21.11 注入可见性补测（等 spawn 后注入） |
| `26.3/client-26.3-probe.txt`、`26.3/minecraft-data-versions.txt` | 26.3 客户端能力探测与 mineflayer 支持版本（F-2 证据） |
| `26.3-loader0.20.0/` | 附加用例（loader 0.20.0）的结果与日志 |
| `results-*.txt`（顶层） | 9 个版本的 `results-*.txt` 汇总副本，方便一眼对比 |
| `fabric-drive.out` / `fabric-retests.out` | 矩阵驱动脚本与补测脚本的完整输出（含资源门控等待、时间戳） |
| `digest.txt` / `digest2.txt` / `digest3.txt` / `digest4.txt` | 本卡整理证据时从上面这些原始文件里抽取的汇总（各版本 loader/API/启动耗时/真行/结果），方便比对，**非原始输出** |

---

## 7. 资源与清理

| 项 | 数值 |
|---|---|
| 单个 Fabric 实例 | 服务端 jar ≈ 53.6–59.4M（按版本）+ `libraries/` ≈ 100M（含 Fabric）+ world ≈ 5M |
| 单实例内存 | `-Xms512M -Xmx1024M`；Fabric 安装器 1.1.x 的启动器会再拉一个子 JVM，实测两个 java 进程 RSS 合计 ≈ 1.4G |
| 测试机 | 2 vCPU / 2.6G 内存 / `/` 可用 2.5G（与另外三张矩阵卡共用，故脚本有资源门控） |
| 清理策略 | 每版本测完删 `libraries/ world/ logs/ console.out.log`（可再生），保留 `server.jar` + `artifacts/`；磁盘告警时看门狗再删已测版本的 `server.jar`（可由 `versions.tsv` 的 URL 重新下载） |

收尾时（本卡结束）实测状态：本卡启动的 MC 实例、驱动脚本、补测脚本、磁盘看门狗全部退出
（`pgrep` 无匹配；Fabric 段 25610–25619 / 25710–25719 无端口在听）；跑一遍收尾清理
（`~/mc-test/fabric_cleanup.sh`，与本文档同批）后，10 个实例目录各 ≈ 87–99M，只剩
`server.jar` + `mods/` + 配置 + 制品（`libraries/ world/ logs/ console.out.log` 已删，可再生），
`~/mc-test/fabric/` 下仍有 158 个 `.txt` 制品；测试机 `/` 可用空间从 895M 回升到 1.1G。
同一份文档、制品与脚本也放在 `~/Y33-Bot/test-notes/`（`02-fabric.md` + `artifacts/fabric/scripts/`）。
