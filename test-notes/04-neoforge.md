# 04 · NeoForge 加载器实机测试矩阵（卡 t_efe57773）

> 目标：按项目文档（`docs/smoke.md` S1–S6 / `PLAN.md` §5）的测试流程，对近两年发布的 NeoForge 服务端
> 在「官方支持且属于 x.xx.0 形态」的 MC 版本上逐个做完整实机测试。
> 前置环境复用 `test-notes/00-env.md`（JDK21/JDK25、端口分配表、脚本模板）；本卡**只新增 `test-notes/`**。
> 全部结论均来自测试机（`ssh hermes@10.1.1.4`，Rocky 9.7）上的真实执行，原始制品见
> `test-notes/artifacts/neoforge/<版本>/`。

---

## 0. 验收对照（卡 t_efe57773）

| 验收项 | 要求 | 实测结果 | 证据 |
|---|---|---|---|
| 版本清单与理由 | 列出「近两年 x.xx.0 中 NeoForge 官方支持」的版本 | ✅ §1（9 个入列版本 + 5 类被排除版本及理由） | §1、`artifacts/neoforge/version-matrix.tsv` |
| 每版本独立目录与端口部署 | 按 `00-env.md` 端口表，installer + 文档要求的最小依赖 | ✅ §3（9 个实例：`~/mc-test/neoforge/<MC>`，端口 25630+slot / 25730+slot，逐版本 JDK） | §3、§4 |
| 完整用例逐版本跑完并有结论 | 连接/登录/指令/交互/退出 | ✅ §4 逐版本结论矩阵（9/9 有结论） | §4、`artifacts/neoforge/*/results-*.txt` |
| 失败项有原始日志与复现步骤 | 服务端日志 + crash-report + 脚本输出落盘 | ✅ §6（`latest.log`、console、格式取样、run 输出、首轮失败归档） | §6、§8 |
| 未修改项目代码 | 只新增 `test-notes/` | ✅ 未改 `src/`、`tests/`、`config.example.toml`、`docs/` | §9 |

---

## 1. 版本清单与理由

### 1.1 筛选口径

1. **近两年**：`00-env.md` §3 已定稿为 `2024-10-18` 之后发布的正式版（发布日期取自 `~/mc-test/versions.tsv`）。
2. **x.xx.0 形态 /「版本线首个正式版」**：与原版 / Fabric / Forge 三个矩阵卡保持同一口径——
   只看每条「版本线」的首个正式版，不细化到补丁版（Fabric 卡 `fabric_drive.sh` 头部写明的清单是
   `1.21.2 / 1.21.4 / 1.21.5 / 1.21.6 / 1.21.9 / 26.1 / 26.2 / 26.3`，外加 `1.21.11` 作对照）。
3. **NeoForge 官方是否支持**：以官方 maven 的 `maven-metadata.xml` 为准，**只承认 `stable`**
   （版本号无 `-alpha` / `-beta` / `+snapshot` 后缀者）。元数据共 1838 个版本，逐族统计见
   `artifacts/neoforge/version-matrix.tsv`：

   | NeoForge 族 | 对应 MC | stable 数 | 该族首个 → 末个 stable | alpha / beta / snapshot |
   |---|---|---|---|---|
   | 21.2 | 1.21.2 | **0** | — | 0 / 2 / 0 |
   | 21.3 | 1.21.3 | 43 | 21.3.56 → 21.3.100 | 0 / 56 / 0 |
   | 21.4 | 1.21.4 | 39 | 21.4.121 → 21.4.161 | 0 / 119 / 0 |
   | 21.5 | 1.21.5 | 26 | 21.5.74 → 21.5.101 | 0 / 73 / 0 |
   | 21.6 | 1.21.6 | **0** | — | 0 / 21 / 0 |
   | 21.7 | 1.21.7 | **0** | — | 0 / 26 / 0 |
   | 21.8 | 1.21.8 | 47 | 21.8.9 → 21.8.57 | 0 / 9 / 0 |
   | 21.9 | 1.21.9 | **0** | — | 0 / 17 / 0 |
   | 21.10 | 1.21.10 | 2 | 21.10.63 → 21.10.64 | 0 / 61 / 0 |
   | 21.11 | 1.21.11 | 4 | 21.11.42 → 21.11.48 | 0 / 42 / 0 |
   | 26.1.0 / 26.1.1 | 26.1 / 26.1.1 | **0** | — | 15 / 102 / 14（含 26.1.2 的 alpha/beta） |
   | 26.1.2 | 26.1.2 | 50 | 26.1.2.71 → 26.1.2.122 | — |
   | 26.2.0 | 26.2 | 35 | 26.2.0.57 → 26.2.0.93 | 0 / 57 / 0 |
   | 26.3.0 | 26.3 | 12 | 26.3.0.76 → 26.3.0.89 | 0 / 74 / 0 |

### 1.2 本卡实际覆盖的 9 个版本

| slot | MC | NeoForge | Java | 端口（游戏 / RCON） | 入列理由 |
|---|---|---|---|---|---|
| 0 | **1.21.4** | 21.4.161 | 21 | 25630 / 25730 | 1.21.4 线首版，NeoForge 有 stable |
| 1 | **1.21.11** | 21.11.48 | 21 | 25634 / 25734 | 1.21.x 线末；也是原版矩阵已确认「默认 chat 模板不匹配」的对照版本 |
| 2 | **26.3** | 26.3.0.89 | 25 | 25638 / 25738 | 新版本号体系（年份.序号）下当前最新的正式版 |
| 3 | **26.2** | 26.2.0.93 | 25 | 25637 / 25737 | 26.2 线首版 |
| 4 | **26.1.2** | 26.1.2.122 | 25 | 25636 / 25736 | 26.1 线**唯一**有 NeoForge stable 的版本（26.1 / 26.1.1 无 stable） |
| 5 | **1.21.3** | 21.3.100 | 21 | 25635 / 25735 | 1.21.2 只有 `21.2.0-beta*`，该线首个 stable 落在 1.21.3 |
| 6 | **1.21.5** | 21.5.101 | 21 | 25631 / 25731 | 1.21.5 线首版 |
| 7 | **1.21.8** | 21.8.57 | 21 | 25632 / 25732 | 1.21.6 / 1.21.7 只有 beta，该线首个 stable 落在 1.21.8 |
| 8 | **1.21.10** | 21.10.64 | 21 | 25633 / 25733 | 1.21.9 只有 beta，该线首个 stable 落在 1.21.10 |

### 1.3 明确排除的版本（附理由，避免被误判为「漏测」）

| MC 版本 | 排除理由 |
|---|---|
| 1.21.2 | NeoForge 只发过 `21.2.0-beta*`（2 个），**无 stable** |
| 1.21.6 / 1.21.7 | 只有 `21.6.*-beta`（21 个）/ `21.7.*-beta`（26 个），无 stable |
| 1.21.9 | 只有 `21.9.*-beta`（17 个），无 stable |
| 26.1 / 26.1.1 | 只有 `26.1.0.0-alpha*` 与 snapshot，`26.1.1.*` 无 stable；该线 stable 从 26.1.2 起 |
| 1.21.0 / 1.21.1 | 发布时间（2024-06 / 2024-08）在「近两年」窗口之外（`00-env.md` §3 已判定） |

---

## 2. 下载通道（本卡第一道坎，先解决再排矩阵）

`00-env.md` §2/§8 已记录 **`maven.neoforged.net:443` 在这台机器上不通**。本卡先做最小验证：

### 2.1 实测：DNS 被污染 + 真实 IP 同样不可达

```
$ getent ahostsv4 maven.neoforged.net
159.106.121.75  STREAM maven.neoforged.net        ← 污染答案（非 NeoForged 的地址段）
$ getent ahostsv6 maven.neoforged.net
2001::45ab:e549 STREAM maven.neoforged.net        ← 同样是污染答案
$ curl -sS --max-time 20 https://maven.neoforged.net/releases/.../maven-metadata.xml
curl: (28) Failed to connect to maven.neoforged.net port 443: 连接超时
$ curl -4 -sS --max-time 25 https://maven.neoforged.net/...
curl: (7) Failed to connect to maven.neoforged.net port 443: 拒绝连接
# 用 DoH（dns.alidns.com）拿到真实 IP 后仍不可达：
$ curl -4 -sS --resolve maven.neoforged.net:443:173.244.209.150 .../maven-metadata.xml
curl: (7) Failed to connect to maven.neoforged.net port 443: 拒绝连接
```

⇒ **不是「改 hosts 就行」**：污染 IP 与 DoH 返回的真实 IP 都连不上，必须换源。

### 2.2 可用替代源：`maven.creeperhost.net`（公共 maven 镜像，代理了 neoforged 仓库）

```
$ curl -4 -sSI https://maven.creeperhost.net/net/neoforged/neoforge/maven-metadata.xml
http=200  content-type: application/xml  bytes=68224          # 完整元数据（1838 个版本，latest=26.3.0.89）
$ curl -4 -sSI https://maven.creeperhost.net/net/neoforged/neoforge/21.4.161/neoforge-21.4.161-installer.jar
http=200  content-type: application/java-archive  content-length: 7224094
$ curl -4 -sSI https://maven.creeperhost.net/net/neoforged/mergetool/2.0.0/mergetool-2.0.0-api.jar
http=200  content-length: 2550
$ curl -4 -sSI https://maven.creeperhost.net/cpw/mods/modlauncher/11.0.4/modlauncher-11.0.4.jar
http=200  content-length: 116200
```

同批实测**不可用**的候选（记为排除项）：`repo1.maven.org` / `maven.aliyun.com`（central、public）/
`repo.huaweicloud.com` / `mirrors.cloud.tencent.com` 对 `net/neoforged/**` 一律 404（不代理该仓库）；
`repo.codemc.io/repository/maven-public`、`maven.blamejared.com` 404；`maven.mcmoddev.com`、
`mirrors.neoforged.net` DNS 解析失败；`api.allorigins.win`、`api.codetabs.com`、`r.jina.ai`、
`cdn.jsdelivr.net` 连接超时。
另外：`libraries.minecraft.net`、`piston-data.mojang.com`（installer 需要的原版依赖与 `server.jar`）**可直连**。

### 2.3 installer 的下载 URL 写死在 jar 里 ⇒ 用「替换主机后重打包」的 installer

* NeoForge installer 的下载 URL 全部写在 `install_profile.json`（52 处指向 `maven.neoforged.net`）与
  `version.json`（32 处）里；**自带 `--mirror` 在本机不生效**，实测：

  ```
  $ java -Xmx1200M -jar nf-21.4.161-installer.jar --installServer --mirror https://maven.creeperhost.net
  Considering library net.neoforged.installertools:cli-utils:2.1.2
  Downloading library from https://maven.neoforged.net/releases/net/neoforged/installertools/cli-utils/2.1.2/cli-utils-2.1.2.jar
  java.net.SocketTimeoutException: Connect timed out     ← 仍走原主机；每个库 5s 超时后继续下一个
  ```
* 可用做法：`nf_patch_installer.py` 解包 installer → 把 `https://maven.neoforged.net/releases` 整体替换为
  `https://maven.creeperhost.net`（路径原样、sha1 校验值不动）→ 顺带把 `mirrorList`（原本指向被墙的
  `mirrors.neoforged.net`）改成不可路由地址避免卡住 → 重新打包。实测输出：

  ```
  patched nf-21.4.161-installer.jar -> nf-21.4.161-installer-patched.jar (mirror=https://maven.creeperhost.net)
    install_profile.json: 52 x https://maven.neoforged.net/releases -> 0 x https://maven.neoforged.net/
    version.json: 32 x https://maven.neoforged.net/releases -> 0 x https://maven.neoforged.net/
  $ java -Xmx1200M -jar nf-21.4.161-installer-patched.jar --installServer
  ...
  The server installed successfully
  ```
* **9/9 个版本安装成功**：每个版本 `The server installed successfully` ×1、下载类异常
  （`SocketTimeoutException` / `UnknownHostException`）**0 次**（逐版本计数见
  `artifacts/neoforge/<版本>/install-success-count.txt` 与 `install-download-errors.txt`）。
* installer 侧声明的 sha1 与本地实测值逐版本核对无差异（`installer.sha1.remote` / `installer.sha1.local`）。

> 结论：NeoForge 的下载通道已打通（`maven.creeperhost.net` + 主机替换 installer），下面 9 个版本都走这条路。

---

## 3. 部署方式（每版本独立目录 / 端口 / JDK）

沿用 `00-env.md` §5 的约定，新建 `~/mc-test/neoforge/<MC版本>/`：

* 端口：**游戏 `25630+slot`，RCON `25730+slot`**（NeoForge 族专用段，与其它三族不重叠）。
* JDK：`1.21.x → ~/jdk-21`；`26.x → ~/jdk-25`（与 `versions.tsv` 的 `javaVersion` 一致，理由见 §5.4）。
* `server.properties`：`enable-rcon=true`、`rcon.port=25730+slot`、`rcon.password=$MC_RCON_PASSWORD`（取自 `~/.env`）、
  `online-mode=false`、`pause-when-empty-seconds=0`、`view-distance=4`、`simulation-distance=4`、`spawn-protection=0`。
* `user_jvm_args.txt`：`-Xms512M -Xmx1024M`（机器仅 2.6Gi 内存且四个矩阵卡共用，必须收敛）。
* `start.sh`：先 `. ./instance.env` 选对 `JAVA_HOME`/`PATH`，再 `exec ./run.sh nogui`
  （installer 生成的 NeoForge 启动脚本，参数在 `libraries/net/neoforged/neoforge/<NF>/unix_args.txt`）。
* 每版本跑完清理 `libraries/`、`world/`、`logs/`（可再生）以腾磁盘（`/` 仅剩约 1.0–1.5G）。

实例规模（1.21.4 实测）：`libraries/` **189MB**；installer 的输出里 15 个 `Processor:` 段 / 6 个 `Task:` 段
全部执行完成（`grep -c '^Processor:' install.out` = 15、`grep -c '^Task:'` = 6），末尾
`The server installed successfully`；每版本产物 = `run.sh` + `user_jvm_args.txt` + `libraries/` + `world/` + `logs/latest.log`。

本卡新增脚本（测试机 `~/mc-test/neoforge/scripts/`，同时入库到 `artifacts/neoforge/scripts/`）：

| 脚本 | 作用 |
|---|---|
| `nf_patch_installer.py` | 把 installer 里的 maven 主机替换为可达镜像并重打包（含 `mirrorList` 处置） |
| `nf_install.sh <MC> <NF> <slot>` | 下载 installer（镜像）→ 打补丁 → `--installServer` → 落安装日志与 sha1 对照 |
| `nf_setup.sh <MC> <NF> <slot>` | 写 `eula/server.properties/user_jvm_args/start.sh/instance.env` + 生成 `config-neoforge-<MC>.toml` |
| `nf_smoke_one.sh <MC> <NF> <slot>` | 该版本的完整用例（T0–T9）+ `config-neoforge-<MC>-fix.toml`，产出 artifacts |
| `nf_drive.sh` | 按 §1.2 清单逐版本 安装→配置→用例→清理（已完成版本自动跳过） |
| `gen_matrix.sh` | 由镜像元数据生成 `version-matrix.tsv`（§1.1 的统计来源） |

---

## 4. 测试用例与逐版本结果

### 4.1 用例清单（与文档的对应关系）

| 编号 | 对应文档 | 内容 |
|---|---|---|
| T0 | `PLAN.md` §5 启动 | 起服（tmux）→ 等 `Done (` + RCON 端口就绪 → 记录启动耗时 → 扫装载期告警（FML/Mixin/ASM）+ `latest.log` 格式取样 |
| T1 | `smoke.md` S1 | `check`：真 QQ 探活 + 真 RCON `/list` + 日志可读 + 绑定表 |
| T2 | `smoke.md` S2 | `bind set` + `simulate group-message '#你好'`（真 RCON `tellraw` 注入），并用无头客户端核对游戏内可见性 |
| T3 | `smoke.md` S2 | `simulate group-message '/status'`：真往返（服务端真 `/list` 响应解析） |
| T4 | `smoke.md` S3 | 真玩家进服 / 普通聊天 / `#` 聊天 / 退服 → 真实日志行 → **默认模板 vs 放宽模板 A/B** + 回环防护 |
| T5 | `smoke.md` S4 | `simulate health --offline` ×2 + `--online`：健康翻转与去重 |
| T6 | `smoke.md` S5（离线可复现部分） | 常驻 `run`（真 QQ 网关）+ 运行期真玩家 → MC→QQ 真链路 |
| T7 | `smoke.md` S6 | 日志轮转：运行中清空 `latest.log` 再写入 → 观察 `偏移重置` |
| T8 | `00-env.md` §6 | `run` SIGTERM 退出码（0 = 正常停止） |
| T9 | `00-env.md` §6 | 优雅停服（`stop`）→ 端口释放 |

### 4.2 逐版本结论矩阵（9/9 跑完）

标记含义：`0` = 命令退出码 0（成功）；`1` = 非 0（未匹配/失败）；`—` = 该版本无头客户端不支持，用例跳过。

| MC | NeoForge | JDK | 启动 | T1 check | T2 注入 / 客户端可见 | T3 `/status` | T4 真玩家日志 | 默认模板 join/quit/chat | 放宽模板 | T6 run 退出 | T7 轮转 | 结论 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.21.3 | 21.3.100 | 21 | 39s | 0 | 0 / 是 | 0 | 有 | **1 / 1 / 1** | 0 / 0 / 0 | 0 | ✅ | 通过（含 §5.1 格式分歧） |
| 1.21.4 | 21.4.161 | 21 | 21s | 0 | 0 / 是 | 0 | 有 | **1 / 1 / 1** | 0 / 0 / 0 | 0 | ✅ | 通过（含 §5.1） |
| 1.21.5 | 21.5.101 | 21 | 30s | 0 | 0 / 是 | 0 | 有 | **1 / 1 / 1** | 0 / 0 / 0 | 0 | ✅ | 通过（含 §5.1） |
| 1.21.8 | 21.8.57 | 21 | 33s | 0 | 0 / 是 | 0 | 有 | **1 / 1 / 1** | 0 / 0 / 0 | 0 | ✅ | 通过（含 §5.1） |
| 1.21.10 | 21.10.64 | 21 | 21s | 0 | 0 / 是 | 0 | 有 | **1 / 1 / 1** | 0 / 0 / 0 | **1 → 1 → 0（三轮，§6.2）** | ✅ | 通过（含 §5.1；T6 前两轮 QQ 侧失败，见 §6.2） |
| 1.21.11 | 21.11.48 | 21 | 34s | 0 | 0 / 是 | 0 | 有 | **1 / 1 / 1** | 0 / 0 / 0 | 0 | ✅ | 通过（含 §5.1） |
| 26.1.2 | 26.1.2.122 | 25 | 27s | 0 | 0 / 是 | 0 | 有 | **1 / 1 / 1** | 0 / 0 / 0 | 0 | ✅ | 通过（含 §5.1） |
| 26.2 | 26.2.0.93 | 25 | 24s | 0 | 0 / — | 0 | 无（客户端不支持） | — | — | 1 → 复跑 0（§6.2） | ✅ | 通过（含 §5.1、§6.2、§6.3） |
| 26.3 | 26.3.0.89 | 25 | 18s | 0 | 0 / — | 0 | 无（客户端不支持） | — | — | 0 | ✅ | 通过（含 §5.1、§6.3） |

补充：`default_chatplain_exit=1` / `relaxed_chatplain_exit=0`（普通聊天在放宽模板下正确输出
`[忽略] 聊天非 # 开头，不转发`）；`loop_guard_tested=yes`（回环防护用真行格式的 `[QQ]` 文本验证）；
`health_flip_tested=yes`；`server_stopped=yes`（9/9 端口均能释放）。

**逐版本结论**：9 个版本的 NeoForge 服务端都能正常部署、启动、接受机器人的 RCON 与游戏内连接；
**没有任何版本出现启动失败、crash-report、mixin/ASM 异常或依赖版本约束问题**；
唯一的系统性分歧是 §5.1 的日志格式问题（只影响 MC→QQ 方向）。

---

## 5. 发现（症状级；根因分析与 `BUGS.md` 登记留给汇总卡 `t_1c0e88a4`）

### 5.1 ★核心发现：NeoForge 的 `latest.log` 行格式与项目默认 `[log_patterns]` **三个模板全部不兼容**

真机日志行（1.21.4 / 21.4.161，取自 `artifacts/neoforge/1.21.4/real-*-line-1.21.4.txt`）：

```
join: [1810月2026 15:25:45.610] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve joined the game
quit: [1810月2026 15:25:50.263] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve left the game
chat: [1810月2026 15:25:48.701] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
```

而项目默认模板（`config.example.toml`）要求形如 `[15:25:45] [Server thread/INFO]: …` 的行。
A/B 实测（同一条真行、只改配置）：

```
===================== T4 [default] chat 模板用例 =====================
[警告] 日志行未匹配任何模板
>>> [RESULT] default_chat_exit=1
===================== T4 [relaxed] join 模板用例 =====================
[群消息] Steve进入了nf1214
>>> [RESULT] relaxed_join_exit=0
===================== T4 [relaxed] quit 模板用例 =====================
[群消息] Steve退出了nf1214
>>> [RESULT] relaxed_quit_exit=0
===================== T4 [relaxed] chat 模板用例 =====================
[群消息] Steve@nf1214: 大家好，这是带井号的聊天（应被转发）
>>> [RESULT] relaxed_chat_exit=0
===================== T4 [relaxed] chatplain 模板用例 =====================
[忽略] 聊天非 # 开头，不转发
>>> [RESULT] relaxed_chatplain_exit=0
```

**生产现场**（T6 常驻 `run` + 无头客户端真进服/聊天/退服，1.21.4）：bot 对**每一行**日志都打
`[忽略] 日志行未匹配任何模板`，包括进服/聊天/退服三行本身：

```
[忽略] 日志行未匹配任何模板: [1810月2026 15:26:13.926] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve2 joined the game
[忽略] 日志行未匹配任何模板: [1810月2026 15:26:17.100] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Steve2> #大家好，这是带井号的聊天（应被转发）
[忽略] 日志行未匹配任何模板: [1810月2026 15:26:18.637] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve2 left the game
[警告] 日志文件缩小（size=0 < offset=9377），偏移重置为 0
```

⇒ **症状**：在 NeoForge 服务端上，群里既收不到进出服通知，也收不到游戏内 `#` 聊天
（8 个有真玩家日志的版本 100% 复现；`check` / RCON / QQ→MC 方向正常，见 §5.3）。
`26.2 / 26.3` 无真玩家日志（§6.3），但它们的常驻 `run` 同样对每一行打印「未匹配」，且
`log-format-sample-26.3.txt` 显示文件格式与 1.21.x 同族（`[1810月2026 15:42:49.485] [main/INFO] [记录器/]:`）。

**可用绕法（只改配置，与 `00-env.md` §7-10 同一手法）**：放宽 `[log_patterns]` 三个模板后
四类用例全部通过（`artifacts/neoforge/<版本>/results-*.txt` 里的 `relaxed_*_exit=0`）：

```toml
[log_patterns]
join = '\[\d+月\d+ \d{2}:\d{2}:\d{2}\.\d{3}\] \[Server thread/INFO\] \[[^\]]*\]: (?P<player>\w+) joined the game'
quit = '\[\d+月\d+ \d{2}:\d{2}:\d{2}\.\d{3}\] \[Server thread/INFO\] \[[^\]]*\]: (?P<player>\w+) left the game'
chat = '\[\d+月\d+ \d{2}:\d{2}:\d{2}\.\d{3}\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\] \[[^\]]*\]: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)'
encoding = "utf-8"
```

（生成物：`~/Y33-Bot/config-neoforge-<MC>-fix.toml`，由 `nf_smoke_one.sh` 自动写出。）

### 5.2 与原版的差异：NeoForge 比原版多「坏一个键」

| 场景 | join / quit 模板 | chat 模板 |
|---|---|---|
| 原版 1.21.11（`00-env.md` §7-10） | 匹配 | 不匹配（`[Not Secure] ` 前缀 + `Server thread` 线程名） |
| **NeoForge（本卡：1.21.3 / 1.21.4 / 1.21.5 / 1.21.8 / 1.21.10 / 1.21.11 / 26.1.2）** | **不匹配** | 不匹配 |

原因（症状层）：NeoForge 的 log4j 布局把时间戳写成 `DDMM月YYYY HH:MM:SS.mmm`，并在 `[线程/级别]`
之后**多插一段 `[记录器名/]`**。也就是说：Vanilla/Fabric 上只有 `chat` 模板需要放宽，
NeoForge 上 `join / quit / chat` 三个都要放宽。

### 5.3 不受影响的链路（同样有实测证据，避免被误读成「全坏」）

| 链路 | 结果 | 证据 |
|---|---|---|
| `check`（真 QQ 探活 + 真 RCON `/list`） | 9/9 `check_exit=0` | `results-*.txt` |
| QQ→MC 真注入（`tellraw`） | 9/9 `tellraw_exit=0`；7 个有客户端的版本在游戏内看到 `[QQ] Steve: 你好` | `client-hold-*.txt` |
| `/status` 真往返 | 9/9 `status_exit=0`（NeoForge 的 `/list` 响应与原版同格式，解析出 `在线: 0/20`） | `results-*.txt`、`run-*.txt` |
| 健康翻转 | 9/9 `health_flip_tested=yes`，重复离线被去重（`[忽略] 状态未变化，不重复提示`） | `run-*.txt` |
| 常驻 `run` + SIGTERM | 启动/关闭正常（两例因 QQ 侧超时非 0，见 §6.2） | `run-*.txt` |
| S6 日志轮转 | 9/9 检测到 `[警告] 日志文件缩小（size=0 < offset=N），偏移重置为 0` | `run-*.txt` |
| 加载器装载 | 无 mixin/ASM/依赖异常、无 crash-report（无第三方 mod，符合卡内「文档要求的最小依赖」） | `loader-notes-*.txt`、`console-*.txt` |

NeoForge 装载实测（1.21.4，`loader-notes-1.21.4.txt`）：`ModLauncher 11.0.4` + `MIXIN 0.8.7` +
`MixinExtras 0.5.3` + `NeoForge 21.4.161`；26.3 为 `FancyModLoader 12.0.12` + `MixinExtras 0.5.5`
（26.x 换了新的 FML 启动器体系）。

### 5.4 加载器要求：NeoForge 26.x 的类文件是 **Java 25**（class file 69.0）

首轮 26.3 用机器默认的 JDK21 启动直接失败（原文见
`artifacts/neoforge/26.3/console-26.3-jdk21-bootstrap-fail.txt`）：

```
错误: 加载主类 net.neoforged.fml.startup.Server 时出现 LinkageError
	java.lang.UnsupportedClassVersionError: net/neoforged/fml/startup/Server has been compiled by a more recent
	version of the Java Runtime (class file version 69.0), this version of the Java Runtime only recognizes
	class file versions up to 65.0
```

⇒ 26.x 的 NeoForge 实例**必须**用 `~/jdk-25` 启动（`00-env.md` §3 的 `y33java 25`）。
复现：`cd ~/mc-test/neoforge/26.3 && PATH=$HOME/jdk-21/bin:$PATH ./run.sh nogui`（必现）；
`JAVA_HOME` 指向 `~/jdk-25` 后 26.3 起服成功（18s）。

### 5.5 环境侧发现：installer 自带 `--mirror` 在本机不生效

见 §2.3。对后续卡的意义：**NeoForge 相关任务别指望 `--mirror`，要替换 installer 内嵌 URL（或本地代理）**。

---

## 6. 失败项 / 未通过项（含复现步骤与原始日志）

### 6.1 MC→QQ 方向静默（8 个有真玩家日志的版本全部复现）

* 症状：机器人常驻运行时，游戏内玩家进服/退服/`#` 聊天都不进群；bot 日志里对应行是
  `[忽略] 日志行未匹配任何模板`（不是报错、也不退出）。
* 复现（以 1.21.4 为例）：
  ```bash
  . ~/y33-env.sh; cd ~/Y33-Bot
  tmux new -d -s nf "cd ~/mc-test/neoforge/1.21.4 && ./start.sh 2>&1 | tee -a console.out.log"
  # 等 `Done (` 出现且 RCON 25730 就绪
  .venv/bin/python -m y33bot run --config config-neoforge-1.21.4.toml --verbose > /tmp/run.out 2>&1 &
  cd ~/mc-test/client && node client.js 127.0.0.1 25630 Steve     # 真进服 + 普通聊天 + # 聊天 + 退服
  grep -n '未匹配\|进入了\|退出\|群消息' /tmp/run.out
  ```
* 原始日志：`artifacts/neoforge/<版本>/run-<版本>.txt`（bot 侧）、`latest-log-<版本>.txt`（服务端侧）、
  `real-*-line-<版本>.txt`（真日志行）。
* 结论：**服务端日志格式问题**（§5.1），不是 RCON / QQ / 桥接逻辑问题——同一台服务器上 `check`、
  `tellraw` 注入、`/status` 往返全部正常。

### 6.2 两例常驻 `run` 非 0 退出：QQ 侧 HTTP 失败（环境侧，非 NeoForge 侧）

| 版本 | 症状（bot 输出原文） | 判定 |
|---|---|---|
| 1.21.10（第 1 轮） | `[botpy] access_token expires_in 4553` → `[错误] QQ 网关异常退出: 'NoneType' object has no attribute 'get'` → `[错误] QQ 网关启动失败: …` → `run_exit=1` | QQ 平台网关接口返回空（机器当时在跑 4 个卡的服务端，2.6Gi 内存接近打满） |
| 1.21.10（第 2 轮） | 同上（`expires_in 4138` 后同一条 `'NoneType' object has no attribute 'get'`） | 同上；同一版本连续两轮复现 |
| 1.21.10（第 3 轮） | `[botpy] access_token expires_in 3750` → `[启动] QQ 网关已连接` → `[启动] QQ 网关就绪` → `run_exit=0` | 恢复正常 |
| 26.2（第 1 轮） | `[botpy] access_token TimeoutError:` → `[错误] QQ 网关异常退出: ` → `[错误] QQ 网关启动失败: …` → `run_exit=1` | access_token 请求超时（同环境条件） |
| 26.2（第 2 轮） | 正常：网关连接/就绪 → `run_exit=0` | 恢复正常 |

* 判定：**QQ 平台侧 / 环境侧的瞬时不稳**，与 NeoForge 无关——同一失败在其它 7 个版本上完全没出现，
  而失败的两个版本在机器空闲下来后复跑即恢复（1.21.10 三轮：失败、失败、成功）。
  可疑放大因素有两个，留给汇总卡判断：① 机器内存压力（2.6Gi 峰值）；② **四张矩阵卡共用同一套 QQ 凭据**，
  同一时刻可能有并发会话（botpy 自己打印 `最大并发连接数: 1`）。
* 这两例还**顺带验证了 BUG-001 修复后的契约**：网关任务结束即打 `[错误]` 并以非 0 退出（不再静默常驻）。
* 原始证据（全部入库）：`artifacts/neoforge/1.21.10/results-1.21.10-run1-gwtimeout.txt`、
  `results-1.21.10-run2-gwtimeout.txt`、`artifacts/neoforge/26.2/results-26.2-run1-gwtimeout.txt`，
  以及两版本各自 `run-*.txt`（最终一轮）里的原文。
* 复现命令（本轮的实际复跑脚本）：`bash ~/mc-test/neoforge/scripts/rerun_two.sh`
  与 `rerun_12110.sh`（= `nf_install.sh` + `nf_setup.sh` + `nf_smoke_one.sh` 三段串起来跑）。

### 6.3 26.2 / 26.3 无法做「真玩家」用例（客户端能力天花板）

```
$ node -e "…minecraft-data.supportedVersions.pc…"
supported tail: 1.21.4 1.21.5 1.21.6 1.21.8 1.21.9 1.21.10 1.21.11 26.1
26.x supported: 26.1
```

* 无头客户端（mineflayer 4.39.0 + minecraft-data 3.117.0，`~/mc-test/client`）**支持到 26.1**；
  MC 26.1.2 能连（`client_saw_tellraw=yes`），26.2 / 26.3 不行。
* 因此这两个版本的「真玩家进服/聊天/退服」缺失，`join/quit/chat` 模板 A/B 未跑；
  它们的格式结论来自常驻 `run` 对全量日志行的「未匹配」输出 + `log-format-sample-*.txt` 的格式取样。
* 可补路径（留给后续卡）：升级 `minecraft-data` 到支持 26.2/26.3 的版本（本机实测 npm 上
  `minecraft-data@3.117.0` / `mineflayer@4.39.0` 已是 latest，暂无可用升级）、或接一个真 26.2/26.3 客户端。

### 6.4 首轮 26.3「启动失败」（已定位为本卡脚本问题，非产品问题）

* 症状：`start_ok=0`，`startup_seconds=361`，console 里只有 §5.4 的 `UnsupportedClassVersionError`。
* 原因：当时 `start.sh` 没有载入 `instance.env`，26.x 实例在默认 JDK21 下启动。
* 处理：修 `start.sh`（`. ./instance.env; export JAVA_HOME PATH`）后复跑成功（18s）。
* 原始证据：`artifacts/neoforge/26.3/results-26.3-failed-jdk21-bootstrap.txt` +
  `console-26.3-jdk21-bootstrap-fail.txt`。

---

## 7. 未能测试 / 信息不足

| 项 | 原因 | 后续怎么补 |
|---|---|---|
| 真 QQ 群里的收发（S5 群侧步骤） | `~/.env` 只有 AppID/AppSecret，SDK 没有「列出机器人所在群」的 API，拿不到 `group_openid`（同 `00-env.md` §8-1） | 由人给出一个群 `group_openid`，或去群里 `@机器人` 抓一次事件 |
| 26.2 / 26.3 的真玩家日志行与模板 A/B | 无头客户端不支持（§6.3） | 升级 minecraft-data 或接真客户端 |
| 第三方 mod 场景（mod 之间 mixin/ASM 冲突、mod 与加载器的依赖版本约束、加载顺序） | 卡内要求「installer + 文档要求的最小依赖」，即**无 mod**；覆盖 mod 冲突需要具体 mod 清单 | 另开卡：给定 mod 清单（含 mixin/ASM 用法与版本约束）后再测 |
| NeoForge 客户端侧行为 | 本卡目标是**服务端** | 不需要 |
| 根因分析与 `BUGS.md` 登记 | 属汇总卡 `t_1c0e88a4` 的职责（本卡只给症状 + 原始证据） | 汇总卡按 §5.1/§5.2 的证据链分析 |

---

## 8. 原始制品索引（`test-notes/artifacts/neoforge/`）

```
version-matrix.tsv                     # §1.1 的版本统计（由 maven-metadata 生成）
nf-metadata.xml                        # 镜像 maven-metadata.xml 原文（1838 个版本，可复核 §1.1）
scripts/                               # 本卡脚本（nf_patch_installer.py / nf_install.sh / nf_setup.sh /
                                       #   nf_smoke_one.sh / nf_drive.sh / gen_matrix.sh）
<MC版本>/                              # 1.21.3 1.21.4 1.21.5 1.21.8 1.21.10 1.21.11 26.1.2 26.2 26.3
  results-<MC>.txt                     # 结构化结论行（§4.2 的来源）
  latest-log-boot-<MC>.txt             # 启动完成后的 latest.log 快照
  latest-log-<MC>.txt                  # 收尾快照
  latest-log-before-rotate-<MC>.txt    # S6 轮转前快照
  log-format-sample-<MC>.txt           # latest.log 头 4 行（格式取样，§5.1/§5.2 依据）
  real-join-line-<MC>.txt              # 真进服行
  real-quit-line-<MC>.txt              # 真退服行
  real-chat-line-<MC>.txt              # 真 # 聊天行
  real-chatplain-line-<MC>.txt         # 真普通聊天行
  real-chat-lines-raw-<MC>.txt         # 真聊天行（原始多条）
  client-<MC>.txt / client-hold-<MC>.txt / client-run-<MC>.txt   # 无头客户端输出（进服/收消息/退出）
  console-<MC>.txt                     # 服务端控制台输出（含装载全过程）
  loader-notes-<MC>.txt                # FML/ModLauncher/Mixin/ASM 摘录
  run-<MC>.txt                         # 常驻 run 的真实输出（真 QQ 网关 + MC→QQ 链路 + 轮转 + SIGTERM）
  state-<MC>.txt / bindings-<MC>.txt   # 落盘的 state（偏移 / msg_seq）与绑定表
  install-tail.txt                     # installer 输出尾部（The server installed successfully）
  install-success-count.txt            # 「installed successfully」出现次数
  install-download-errors.txt          # 下载类异常计数（全为 0）
  installer.sha1.remote / .local       # 镜像声明的 sha1 vs 本地实测
  results-1.21.10-run1-gwtimeout.txt / -run2-gwtimeout.txt / results-26.2-run1-gwtimeout.txt   # §6.2 归档
  results-1.21.10-archived.txt / -archived2.txt（被归档的中间轮结论）
  results-26.3-failed-jdk21-bootstrap.txt / console-26.3-jdk21-bootstrap-fail.txt   # §6.4 归档
```

> 命名沿用 `00-env.md` §7：原始日志制品一律 `.txt`（仓库 `.gitignore` 忽略 `*.log` 与 `logs/`）。

---

## 9. 本卡对项目文件的改动

**零改动**：只新增 `test-notes/04-neoforge.md` 与 `test-notes/artifacts/neoforge/**`；
`src/`、`tests/`、`config.example.toml`、`docs/`、`README.md`、`AGENTS.md`、`BUGS.md` 均未触碰
（`git status` 可见改动范围）。NeoForge 侧的全部结论都落在本文件里，供汇总卡 `t_1c0e88a4`
与后续修复卡引用。
