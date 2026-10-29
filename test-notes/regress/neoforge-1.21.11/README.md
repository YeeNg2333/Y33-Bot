# NeoForge 1.21.11 真机回归（离线安装器恢复 / 新出厂模板 / `check` 判定 / 看门狗）

看板卡 `t_0ee0c2ff`，2026-10-29 20:39–20:53 +0800。**本目录只记录本卡的实机证据**，
不放别族（vanilla / Fabric / Forge）的记录 —— 那几族各写各的目录，避免抢同一追加点。

**一句话结论**：在 **NeoForge 21.11.48 / MC 1.21.11**（BUG-003 的另一半场景）上，用**离线打补丁的安装器**
把被删掉的运行环境恢复起来后，main `8996a1d` 的**新出厂模板**把真机 **14 条事件行全部命中**；
同一批真行换旧模板 **全部未命中**且 `check` 判 `FAIL`/`exit=1`；真客户端 E2E 的三类出站
（进服 / `#` 聊天 / 退服）都打到 `api.sgroup.qq.com` 并被 404 `请求Query参数group_id无效` 拒绝（预期成功信号）；
旧模板下看门狗「连续 3 条未命中」**每段只报 1 次**，并用**段间重新武装实验**补上了 Forge 卡留的边界
（2 段 ⇒ 2 次，不是 1 次也不是 4 次）。**产品代码零改动** —— 本卡只做验证与文档。

## 0. 环境与前置

| 项 | 值 |
|---|---|
| 测试主机 | `hermes@10.1.1.4`（Rocky Linux 9，2.6 GB 内存 / 磁盘 95%） |
| 本机驱动方式 | Windows + git-bash，paramiko harness `rsh.py`（本机无 `sshpass`/`plink`） |
| 服务端 | NeoForge **21.11.48** / MC **1.21.11**（FancyModLoader 10.0.36，日志自证），目录 `~/mc-test/neoforge/1.21.11`，tmux `mc-neoforge-1_21_11` |
| 端口 | 游戏 `25634` / RCON `25734` |
| 日志 | `~/mc-test/neoforge/1.21.11/logs/latest.log` |
| Java | `~/jdk-21`（Temurin 21.0.12.1+1-LTS，`java -version` 实跑自证） |
| 被测副本 | `~/Y33-Bot`＝main `8996a1d` 的归档副本（**非 git 仓库**：`git log` 报「不是 git 仓库」，符合预期），`.venv` 可用 |
| 副本一致性 | `config.example.toml` / `src/y33bot/{service.py,mclog/watcher.py,mclog/patterns.py}` / `tests/test_log_patterns_real_lines.py` 的 sha256 与本机 main 工作树**逐一相等**（见 §2） |
| 真客户端 | mineflayer（`~/mc-test/client/client.js`、`client3.js`），Node v24.1.0，协议协商实测 `1.21.11` |
| QQ 侧 | 真 `app_id`/`app_secret`（`~/y33-env.sh` 载入 `~/.env`），**假** `group_openid = E2E_DUMMY_GROUP_OPENID` —— 故意打真平台换 404 |
| 回归脚本 | 服务器上的 `~/mc-test/harness/{regress_start.sh,e2e_family.sh,e2e_neg.sh,old-config.example.toml}`（**直接用，未重写**；md5 见 §7） |

### 0.1 恢复运行环境：离线打补丁安装器（本卡第一件事）

`maven.neoforged.net` 不可达，NeoForge 的 `libraries/` 在上次清理时被删（实例目录只剩 844 KB）。
按卡片给的路径走「复用原版 jar + 离线补丁安装器」，**一次成功**，全程真实输出见 `artifacts/install.txt`：

```bash
# 1) 复用已核的原版 jar（免 54 MB 下载；sha1 两边一致）
$ sha1sum ~/mc-test/vanilla/1.21.11/server.jar ~/mc-test/neoforge/1.21.11/minecraft_server.1.21.11.jar
64bb6d763bed0a9f1d632ec347938594144943ed  /home/hermes/mc-test/vanilla/1.21.11/server.jar
64bb6d763bed0a9f1d632ec347938594144943ed  /home/hermes/mc-test/neoforge/1.21.11/minecraft_server.1.21.11.jar

# 2) 离线补丁安装器（--installServer）
$ JAVA_HOME=$HOME/jdk-21 ~/jdk-21/bin/java -jar ~/mc-test/neoforge/tools/nf-21.11.48-installer-patched.jar \
    --installServer ~/mc-test/neoforge/1.21.11
...
Processing 14729 entries
deobfuscate jar [10766ms]
applying patches [244ms]
write output file [1226ms]
overall work [14662ms]
The server installed successfully

# 3) 成功标志
$ ls -la ~/mc-test/neoforge/1.21.11/libraries/net/neoforged/neoforge/21.11.48/
-rw-r--r-- 1 hermes hermes 3833335 10月 29 20:42 neoforge-21.11.48-universal.jar
-rw-r--r-- 1 hermes hermes    5244 10月 29 20:42 unix_args.txt      ← 卡片要求的存在性标志
-rw-r--r-- 1 hermes hermes    5244 10月 29 20:42 win_args.txt
```

- **没有**出现 `zip END header not found`，所以卡片里那条「python `zipfile.testzip()` 扫坏包」的兜底**未触发**（如实登记）。
- 安装耗时数十秒（其中 `PROCESS_MINECRAFT_JAR` 反混淆 14.7 s）；磁盘余量 1.1 GB → 安装完成时 892 MB（本卡结束时 884 MB）。
- 安装产物体量：`libraries` **134 MB**，实例其余约 **65 MB**（`du -sh $D` 因跳过已访问目录只算非 libraries 部分）。
- **产物保留**：这是本卡恢复出来的运行环境，后续 NeoForge 回归还要用，未删除；`rm` 只清掉了本卡自己的 `/tmp` 临时文件。

### 0.2 复现命令（本机逐条实跑）

```bash
SSHKIT=C:/Users/Lenovo/AppData/Local/hermes/cache/scratch/sshkit
PY=$SSHKIT/.venv/Scripts/python.exe

# 0) 恢复环境（见 §0.1，仅第一次需要）

# 1) 起服 + 用「新出厂默认模板」生成配置 + check（日志新鲜时该项应为「跳过」）
$PY $SSHKIT/rsh.py -r '~/mc-test/harness/regress_start.sh neoforge 1.21.11 new'

# 2) 主回归：旧配置生成 → E2E 真客户端 → 真行判读 → 新/旧 check → 看门狗
$PY $SSHKIT/rsh.py -r '~/mc-test/harness/e2e_family.sh neoforge 1.21.11'

# 3) 负向：旧模板逐行重放 + 旧模板 check + 看门狗（换 Zoe 再造 3 条未命中）
$PY $SSHKIT/rsh.py -r '~/mc-test/harness/e2e_neg.sh neoforge 1.21.11'

# 4) 归因实验：空日志 + 全新 state ⇒ 发送 1 次（证明「4 次」= 3 事件 + 1 启动健康翻转）
$PY $SSHKIT/rsh.py -f $SSHKIT/nf_health_only.sh

# 5) 段间重新武装实验：2 段未命中 ⇒ 2 次告警（Forge 卡未覆盖的边界）
$PY $SSHKIT/rsh.py -f $SSHKIT/nf_wd_rearm.sh

# 6) 收尾停服
$PY $SSHKIT/rsh.py 'tmux send-keys -t mc-neoforge-1_21_11 "stop" Enter; ...'
```

产物目录（服务器）`~/mc-test/regress/neoforge-1_21_11/`，本目录 `artifacts/` 是其**逐字副本**（2026-10-29 20:51 回读，
另加本卡补的三份终端转录：`start-and-check-skip.txt`、`cleanup.txt`、`install.txt` 的生成命令见 §0.1）。

## 1. BUG-003 布局取证：NeoForge 与 Forge **同族但不同加载器段**

起服完成行（20:43，`regress_start.sh`）：

```
[2910月2026 20:43:20.142] [Server thread/INFO] [net.minecraft.server.dedicated.DedicatedServer/]: Done (7.286s)! For help, type "help"
```

起服头 3 行（**加载器自己的日志**，线程名是 `main`）：

```
[2910月2026 20:43:02.175] [main/INFO] [net.neoforged.fml.startup.Entrypoint/]: JVM Uptime at startup: 67ms
[2910月2026 20:43:02.184] [main/INFO] [net.neoforged.fml.loading.FMLLoader/]: Starting FancyModLoader version 10.0.36 (DEDICATED_SERVER in PROD)
[2910月2026 20:43:02.184] [main/INFO] [net.neoforged.fml.loading.FMLLoader/]: Game directory: /home/hermes/mc-test/neoforge/1.21.11
```

**14 条事件真行全文**（`artifacts/real-lines-all.txt` 前 14 行；聊天行统一带 `[Not Secure] `）：

```
56:[2910月2026 20:43:46.412] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve joined the game
57:[2910月2026 20:43:48.311] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Steve> 大家好，这是普通聊天（不该被转发）
58:[2910月2026 20:43:49.498] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
60:[2910月2026 20:43:51.053] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve left the game
68:[2910月2026 20:44:13.317] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Alex joined the game
69:[2910月2026 20:44:14.852] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Alex> 普通聊天第 1 条（旧模板下应未命中）
70:[2910月2026 20:44:15.748] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Alex> 普通聊天第 2 条（旧模板下应未命中）
71:[2910月2026 20:44:16.650] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Alex> 普通聊天第 3 条（旧模板下应未命中）
73:[2910月2026 20:44:18.358] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Alex left the game
80:[2910月2026 20:44:47.179] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Zoe joined the game
81:[2910月2026 20:44:48.622] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Zoe> 普通聊天第 1 条（旧模板下应未命中）
82:[2910月2026 20:44:49.523] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Zoe> 普通聊天第 2 条（旧模板下应未命中）
83:[2910月2026 20:44:50.424] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Zoe> 普通聊天第 3 条（旧模板下应未命中）
85:[2910月2026 20:44:52.132] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Zoe left the game
```

`artifacts/real-lines-all.txt` 后 10 行是 §6.2 段间重新武装实验里 Rex / Nia 两轮的真行（同样是真客户端产生），
`artifacts/lines-92-105.txt` 是这两轮的原始 14 行（含 `logged in with entity id …` 与 `lost connection: Disconnected` 这类**非事件行**）。

### 1.1 与 Forge 61.2.0 的同与异（本卡实测对照，不假定完全相同）

| 维度 | Forge 61.2.0（`t_f4d69bba`） | NeoForge 21.11.48（本卡） | 是否影响模板 |
|---|---|---|---|
| 时间戳段 | `[2910月2026 20:28:31.611]` | `[2910月2026 20:43:46.412]` | 同形，`\[[^\]]+\]` 吃 |
| 线程/级别段 | `[Server thread/INFO]` | `[Server thread/INFO]` | 完全一致 |
| logger 段 | `[net.minecraft.server.MinecraftServer/]`、`[cpw.mods.modlauncher.Launcher/MODLAUNCHER]`、`[net.minecraftforge.fml.VersionChecker/]`、`[net.minecraftforge.common.ForgeMod/FORGEMOD]` | `[net.minecraft.server.MinecraftServer/]`、`[net.neoforged.fml.loading.FMLLoader/]`、`[net.neoforged.neoforge.common.NeoForgeMod/NEOFORGE-MOD]`、`[net.neoforged.neoforge.server.permission.PermissionAPI/]`、`[MixinExtras\|Service/]`、`[mixin/]` —— **没有** modlauncher 段 | 同形不同名，`(?: \[[^\]]+\])?` 吃 |
| `+` 前缀段（卡片正文提到的形态） | 0 命中 | **0 命中**（`grep -acE '\[[^]]*\+[^]]*\]'`） | 不是稳定形态 |
| 事件行本体 | `… [MinecraftServer/]: Steve joined the game` | 逐字同形 | 一致 |
| `[Not Secure]` 聊天前缀 | 有（`online-mode=false`） | 有（`online-mode=false`），本卡日志 14 条 | 一致 |

⇒ **结论**：NeoForge 与 Forge 属**同一日志布局族**（`[时间戳] [线程/级别] [logger/]: 载荷`），
差异只在**加载器自己的 logger 段名**（`net.neoforged.*` vs `cpw.mods.modlauncher` / `net.minecraftforge.*`），
而事件行（join / left / chat）的形态**逐字相同**。出厂模板的可选 logger 段 `(?: \[[^\]]+\])?`
两种都吃，所以 Forge 的修复对 NeoForge 同样成立 —— 但这是**实测得出**的，不是从 Forge 外推的。

logger 段分布（`artifacts/layout.txt`，106 行日志，`grep -aoE '\] \[[^]]*\]:' | sort | uniq -c` 节选）：

```
     25 ] [net.minecraft.server.MinecraftServer/]:
     11 ] [net.minecraft.server.rcon.thread.GenericThread/]:
     11 ] [net.minecraft.server.dedicated.DedicatedServer/]:
     10 ] [net.minecraft.server.rcon.thread.RconClient/]:
      9 ] [net.neoforged.fml.loading.FMLLoader/]:
      5 ] [net.minecraft.server.players.PlayerList/]:
      5 ] [net.minecraft.server.network.ServerGamePacketListenerImpl/]:
      4 ] [net.minecraft.server.level.progress.LoggingLevelLoadListener/]:
      1 ] [net.neoforged.neoforge.common.NeoForgeMod/NEOFORGE-MOD]:
      1 ] [net.neoforged.neoforge.server.permission.PermissionAPI/]:
      1 ] [MixinExtras|Service/]:
      1 ] [mixin/]:
```

## 2. 副本一致性（证明跑的是 main 的代码，不是旧拷贝）

```
本机 main 8996a1d                                    ~/Y33-Bot（服务器）
46ee24f07ca65f9b6bd7024888aff35a713bc43f9613da102fef5762abc770e5  config.example.toml            ==  同值
a67c4c45bfd43c98e6b578b1bdece65b21d4be50ecdba864c7536a04e24df8a2  src/y33bot/mclog/patterns.py  ==  同值
478b11f98ecaf7e4bec0d79e7dabb9bd33fabd6324e71e0d26f3151ac83b9fb4  src/y33bot/mclog/watcher.py   ==  同值
9971d87bf1e42da4495dcb984b1f0d9effde341ef6a75a5b3a34a9c35fe847b7  src/y33bot/service.py         ==  同值
39ad5d305faed1e13c38deee232c1b2f2f7697c382eea9d9c9b388808bebaf16  tests/test_log_patterns_real_lines.py == 同值
```

（与 Forge 卡记录的五条 sha256 完全一致 —— 同一份 main `8996a1d` 归档副本。）

## 3. `check` 的三态真判定（跳过 ≠ 通过 ≠ 失败）

**(a) 刚重启、日志里还没有事件行 → 「跳过」**（`regress_start.sh neoforge 1.21.11 new`，20:43；
`artifacts/start-and-check-skip.txt`）

```
[日志 neoforge] OK /home/hermes/mc-test/neoforge/1.21.11/logs/latest.log 可读，偏移 0 字节
[日志模板 neoforge] OK 未找到可判定的样例行，跳过
[绑定] OK 0 条
OK
check exit=0
```

这条**不算通过**：日志里只有起服噪声，模板再坏也是这个输出。本卡把它当「前置未满足」的证据留着
（Forge 卡已证明这一点，本卡在同一机制上复现）。

**(b) 真客户端跑过一次之后 → 新出厂模板全命中**（`e2e_family.sh` 第 5 步，20:43；`artifacts/check-new.txt`）

```
[日志模板 neoforge] OK 样例行 4 条全部命中（join 1 / quit 1 / chat 2）
[绑定] OK 0 条
OK
check(new) exit=0
```

日志更长之后（`e2e_neg.sh` 第 5 步，20:45；`artifacts/check-new-latest.txt`）：
`[日志模板 neoforge] OK 样例行 14 条全部命中（join 3 / quit 3 / chat 8）`、`exit=0`。

**(c) 同一份真行、旧模板 → FAIL 且 exit=1**（`artifacts/check-old.txt`）

```
[日志 neoforge] OK /home/hermes/mc-test/neoforge/1.21.11/logs/latest.log 可读，偏移 10022 字节
[日志模板 neoforge] FAIL 9 条样例行全部未命中：请按 README §13 调整 [log_patterns]
[绑定] OK 0 条
FAIL
check(old) exit=1
```

同一脚本前一步（4 条真行时）为 `FAIL 4 条样例行全部未命中：请按 README §13 调整 [log_patterns]`、`check(old) exit=1`
（`artifacts/summary.txt`）。旧模板的 `[log_patterns]` 逐字（`e2e_family.sh` 第 1 步输出，与 Forge 卡同一份）：

```toml
join = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) joined the game'
quit = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) left the game'
chat = '\[\d{2}:\d{2}:\d{2}\] \[Async Chat Thread - #\d+/INFO\]: <(?P<player>\w+)> (?P<message>.+)'
```

## 4. `simulate log-event --dry-run` 四类真行的判读

命令（`e2e_family.sh` 第 4 步，配置＝新出厂模板；`artifacts/parse.txt` 是原始记录）：

```bash
cd ~/Y33-Bot && .venv/bin/python -m y33bot simulate log-event --server neoforge --line "<真行>" --dry-run \
  --config config-regress-neoforge-1_21_11-new.toml
```

| 类别 | 真行（`artifacts/real-lines.txt`） | 输出 |
|---|---|---|
| join | `… [MinecraftServer/]: Steve joined the game` | `[群消息] Steve进入了neoforge` |
| `#` 聊天（`[Not Secure]`） | `… [MinecraftServer/]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）` | `[群消息] Steve@neoforge: 大家好，这是带井号的聊天（应被转发）` |
| 普通聊天（非 `#`） | `… [MinecraftServer/]: [Not Secure] <Steve> 大家好，这是普通聊天（不该被转发）` | `[忽略] 聊天非 # 开头，不转发` |
| quit | `… [MinecraftServer/]: Steve left the game` | `[群消息] Steve退出了neoforge` |

`[Not Secure]` 前缀被模板里的 `(?:\[Not Secure\] )?` 吃掉，转发正文里**没有**残留前缀 ——
BUG-003 的两半（加载器 logger 段 + `[Not Secure]`）在 NeoForge 上同时生效时仍然正确。

## 5. E2E：真客户端进服 → 三类出站真打 `api.sgroup.qq.com`

`artifacts/client.txt`（mineflayer，协议协商 `1.21.11`）：

```
[client] 连接 127.0.0.1:25634 用户名 Steve
[client] 已 spawn（进服成功），版本协商: 1.21.11
[client] 已发送普通聊天
[client] 已发送 # 聊天
[client] 主动退出
[client] 连接结束
```

机器人侧（`artifacts/run-e2e.txt`，去掉 `^[botpy]` 噪声后）：

```
[启动] y33bot 0.1.0（1 个 MC 服）
[启动] 日志监听已启动: neoforge
[启动] QQ 网关已连接
[启动] QQ 网关就绪
[RCON neoforge] /list
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效
[忽略] 聊天非 # 开头，不转发
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效
[RCON neoforge] /list
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效
[停止] 收到退出信号
[停止] 正在关闭…
[停止] 已退出
--- 计数 ---
QQ 发送调用次数: 4
忽略(非#)次数  : 1
警告次数       : 0
```

原始 botpy 行（4 条，各带独立 `trace_id`，逐字一条）：

```
[botpy] 接口请求异常，请求连接: https://api.sgroup.qq.com/v2/groups/E2E_DUMMY_GROUP_OPENID/messages, 错误代码: 404, 返回内容: {'message': '请求Query参数group_id无效', 'code': 11321, 'err_code': 40011036, 'trace_id': 'bdacbe398a469cbeb67552f11e1992d6'}, trace_id:bdacbe398a469cbeb67552f11e1992d6
```

（另三条 `trace_id`：`cc82e32e99f9860eb6202ef0d082cbd3`、`12efd968cf28845279b27510173394d3`、`0f016a40cd9dd94f23ab65b07366608a`）

**「4 次」的归因（自查过，不是拍的）**：3 类事件 = join 1 + `#` 聊天 1 + quit 1，另有 **1 条启动健康翻转**
（`state` 文件在脚本里被删过 ⇒ 首轮健康轮询必然翻转）。归因实验 `artifacts/run-healthonly.txt`
（`nf_health_only.sh`：`log_path` 指向**空文件** + 全新 `state`，跑 12 s）：

```
[启动] 日志监听已启动: neoforge
[启动] QQ 网关就绪
[RCON neoforge] /list
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效
[停止] 收到退出信号
--- 计数 ---
QQ 发送调用次数(空日志/全新 state): 1
健康轮询 /list 次数             : 1
```

⇒ 1（健康翻转）+ 3（事件）= 4，实测吻合；普通聊天那 1 条在发送前就被 `[忽略]` 掉了，没有打平台。

## 6. 看门狗：连续 3 条未命中 → 每段只报 1 次

### 6.1 单段（真实回归跑出来的那段）

旧模板 + 全新 `state` + `client3.js`（Alex：进服 + 3 条普通聊天 + 退服），`artifacts/run-wd.txt`
（节选，已去掉 `^[botpy]` 噪声）：

```
[启动] 日志监听已启动: neoforge
[启动] QQ 网关就绪
[RCON neoforge] /list
[警告] 疑似事件行连续 3 条未匹配 [log_patterns]（neoforge）：MC→QQ 方向可能失效，请按 README §13 调整模板
[RCON neoforge] /list
[停止] 收到退出信号
警告次数: 1
```

- 这一段实际有 **5 条**候选事件行（join + 3 条普通聊天 + quit，见 `artifacts/real-lines-all.txt` 第 5–9 行），
  第 3 条触发告警后，第 4、5 条**没有**再刷 —— 一段只报 1 次。
- `e2e_neg.sh` 第 4 步（Zoe 那一轮，同样 5 条未命中）也是 `警告次数: 1`。
- 反证：模板正确的那一轮（§5）有 4 条事件行 + 1 条被忽略的普通聊天，`警告次数: 0` —— 命中即不武装，
  没有被聊天的「未匹配」误伤。

### 6.2 段间重新武装（Forge 卡留的边界，本卡补上）

Forge 卡的 README §6 末条写的是「本轮**没有**在同一次运行里造出『命中 → 重新武装 → 再连续 3 条未命中 → 第二次告警』，
该行为只由单测覆盖」。本卡用 `nf_wd_rearm.sh` 把它做成了真机实验：

- 用**副本**日志 `/tmp/nf-rearm.log`（先清空），**不污染真实 `latest.log`**；
- 段 1：真客户端 `client3.js Rex`（join + 3 普通聊天 + quit），把 `latest.log` 的新增行**原样复制**进副本
  ⇒ 旧模板全部未命中 ⇒ 第 3 条触发告警 #1；
- 命中行：**合成**一条匹配旧模板的行 `[20:45:00] [Server thread/INFO]: Tester joined the game`
  ⇒ 解析成功 ⇒ 看门狗重新武装（**此行是合成行，只用于行为验证，不作为真机模板证据**，也没有写进 `latest.log`）；
- 段 2：真客户端 `client3.js Nia` 再来一轮，同样把新增行复制进副本 ⇒ 告警 #2。

`artifacts/run-rearm.txt`（节选，已去掉 botpy 噪声；右侧 `←` 注释为本卡所加，原文件里没有）：

```
[启动] 日志监听已启动: neoforge
[启动] QQ 网关就绪
[RCON neoforge] /list
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效          ← 启动健康翻转
[警告] 疑似事件行连续 3 条未匹配 [log_patterns]（neoforge）：…    ← 段 1（Rex）
[RCON neoforge] /list
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效          ← 合成命中行被正常转发
[RCON neoforge] /list
[警告] 疑似事件行连续 3 条未匹配 [log_patterns]（neoforge）：…    ← 段 2（Nia）
[RCON neoforge] /list
[停止] 收到退出信号
--- 计数 ---
警告次数: 2
发送次数: 2
```

⇒ **2 段 ⇒ 2 次**：既不是「只报 1 次」（说明确实重新武装了），也不是「每段里每条都报」（说明段内仍然只报 1 次）。
两段各自 5 条未命中，输出里各只有 1 行 `[警告]`。

## 7. harness 脚本的版本与已知缺陷（脚本，非产品代码）

| 脚本 | 服务器 md5 | 说明 |
|---|---|---|
| `e2e_family.sh` | `af9735069940504913d9b7cbbda0add6` | 已含 Forge 卡修好的 `make_old_cfg`（函数式 `re.sub` 替换），本机副本同 md5 |
| `e2e_neg.sh` | `ed186db19f30780015bfead1b65c848a` | 服务器版第 64–65 行多了 `tee check-new-latest.txt`（本机副本同 md5，本轮确实跑出 `check-new-latest.txt`） |
| `regress_start.sh` | `bf755ec773bda1b082a52a72fb4a62df` | 服务器版把 `old` 模式的 `/tmp/old-config.example.toml` 改成 `$HOME/mc-test/harness/old-config.example.toml`（本卡用 `new` 模式，未走该分支）；起服判定缺陷仍在，见下 |

**起服判定缺陷（Forge 卡登记、未修，本卡复现但结论不同）**：`regress_start.sh` 第 79/85 行的
`DONE_BEFORE=$(grep -ac 'Done (' … || echo 0)` 在日志为空时会得到 `"0\n0"`，本轮仍打印了 6 次：

```
/home/hermes/mc-test/harness/regress_start.sh: 第 85 行：[: 0
0：需要整数表达式
```

但这次**判定行输出的是「启动结果: 成功 耗时 21s」**（Forge 卡那轮是「失败 210s」）。
⇒ 同一缺陷既能误报失败、也能恰好报成功，**两个方向的判定都不可作为证据**；真证据是
`Done (7.286s)` 行与 `*:25634` / `*:25734` 两个监听端口（`artifacts/start-and-check-skip.txt`）。
建议修法仍是 `|| true` + `${VAR:-0}`（或改用 `grep -a … | wc -l`）。

## 8. 收尾停服（硬要求）

`artifacts/cleanup.txt` 逐字：

```
端口已消失（第 1 次检查，约 1s）
--- 端口 ---
(无监听)
--- tmux ---
no server running on /tmp/tmux-1002/default
--- free ---
               total        used        free      shared  buff/cache   available
Mem:            2679        1114        1020          11         733        1564
--- df ---
/dev/mapper/rlm-root   17G   17G  884M   95% /
```

- 停服前日志尾部（世界已存盘、RCON 已停、FML 已收尾）：
  `ThreadedAnvilChunkStorage: All dimensions are saved` / `Thread RCON Listener stopped` /
  `Closing FML Loader 7150f3ad` / `Clearing ModLoader`。
- 可用内存：起服前 **1577 MB** → 停服后 **1564 MB**（服务端已完全退出）。
- 磁盘：起服前 1.1 GB 余量 → 恢复 NeoForge 环境后 **884 MB**（libraries 134 MB + 实例其余约 65 MB，属本卡必需产物），
  停服后**未继续缩水**；本轮新增文本产物 ≈ 15 KB。
- 没有删除任何他人产物（`rm` 只清了本卡自己的 `/tmp/nf-rearm.log`、`/tmp/y33-empty-nf.log`、两个临时配置）。

## 9. 产物清单（`artifacts/`，逐字副本）

| 文件 | 内容 | 取自 |
|---|---|---|
| `install.txt` | 原版 jar sha1（两边一致）/ 安装器命令行 / 安装器日志尾部 / `unix_args.txt` 存在性 / 体量 / 磁盘 | 本卡 §0.1 |
| `start-and-check-skip.txt` | 起服输出 + `Done` 行 + 端口 + `check` 的「跳过」态（终端逐字转录） | `regress_start.sh` |
| `real-lines.txt` | JOIN / CHAT / PLAIN / QUIT 四条真行原文 | `e2e_family.sh` 第 3 步 |
| `parse.txt` | `simulate --dry-run` 判读（4 行） | 第 4 步 |
| `check-new.txt` | 新出厂模板 `check` = `OK 样例行 4 条全部命中` + `exit=0` | 第 5 步 |
| `check-old.txt` | 旧模板 `check` = `FAIL 9 条样例行全部未命中` + `exit=1` | `e2e_neg.sh` 第 3 步 |
| `check-new-latest.txt` | 日志变长后新模板 `OK 样例行 14 条全部命中（join 3 / quit 3 / chat 8）` | `e2e_neg.sh` 第 5 步 |
| `summary.txt` | `e2e_family.sh` 汇总（新 4 条 OK / 旧 4 条 FAIL / 发送 4 / 看门狗 1） | 第 7 步 |
| `run-e2e.txt` | E2E 机器人全量输出（含 4 条 botpy 404 原文与 trace_id） | 第 2 步 |
| `run-wd.txt` | 看门狗单段输出（`[警告]` ×1） | 第 6 步 |
| `run-healthonly.txt` | 归因实验：空日志 + 全新 state ⇒ 发送 1 次 | `nf_health_only.sh` |
| `run-rearm.txt` | 段间重新武装实验：2 段 ⇒ `[警告]` ×2 | `nf_wd_rearm.sh` |
| `client.txt` / `client3.txt` | mineflayer 客户端输出（Steve / Alex） | 第 2 / 6 步 |
| `real-lines-all.txt` | 日志里 24 条事件真行（前 14 = E2E 轮，后 10 = Rex/Nia 轮）带行号 | 本卡 §1 |
| `lines-92-105.txt` | Rex/Nia 两轮原始 14 行（含非事件行） | 本卡 §6.2 |
| `layout.txt` | 总行数 / logger 段分布 / `+` 前缀计数 / `[Not Secure]` 计数 | 本卡 §1 |
| `cleanup.txt` | 停服输出（端口、tmux、free、df、日志尾部） | 本卡 §8 |

## 10. 未覆盖的边界（不下结论）

1. **原版 / Fabric**：不在本卡范围（原版与 Fabric 各有独立记录）。
2. **`online-mode=true` 的签名聊天行**：本实例 `online-mode=false`，`[Not Secure]` 是这一前提下的形态；
   正版服是否另有前缀未验。
3. **只测了 NeoForge 21.11.48 / MC 1.21.11 一个点**：`test-notes/04-neoforge.md` 里的其它版本仍只有格式取样。
4. **QQ 侧真实投递**：`group_openid` 是假的，404 是**预期**结果；真群能不能收到消息属 S5。
5. **段间重新武装的「命中行」是合成的**（§6.2）：该实验证明的是**行为**（命中 ⇒ 重新武装 ⇒ 第二段再报一次），
   不是「真机日志里存在这样一行」。真机场景下旧模板不会有命中行，所以这个实验只能用合成行做。

## 11. 验收清单逐条对照（卡片要求 → 本目录证据）

| 卡片验收项 | 结果 | 证据 |
|---|---|---|
| 记录 NeoForge 真行原样，确认与 Forge 同族但不假定完全相同 | ✅ 14 条真行逐字 + 同异对照表 | §1、`real-lines-all.txt`、`layout.txt` |
| 新出厂模板下 `[日志模板 neoforge]` = `OK 样例行 N 条全部命中`（跳过不算通过） | ✅ 先「跳过」（登记为不算通过），造真行后 `4 条全部命中`、再 `14 条全部命中` | §3(a)(b)、`start-and-check-skip.txt`、`check-new.txt`、`check-new-latest.txt` |
| 旧模板下该项 = `FAIL` 且整体 `exit=1` | ✅ `FAIL 4 条全部未命中` / `FAIL 9 条全部未命中`，均 `exit=1` | §3(c)、`check-old.txt`、`summary.txt` |
| `simulate log-event` 对 join / quit / `[Not Secure] <玩家> #…` 输出 `[群消息] …`；普通聊天输出 `[忽略] 聊天非 # 开头，不转发` | ✅ 四类逐一命中 | §4、`parse.txt` |
| E2E 三类出站走到 `api.sgroup.qq.com` 并被 404 `请求Query参数group_id无效` 拒（预期成功信号） | ✅ 4 次发送全部 404，归因闭合（3 事件 + 1 健康翻转） | §5、`run-e2e.txt`、`run-healthonly.txt` |
| 旧模板 + 连续 3 条未命中 → `[警告] …（neoforge）…`，且能说明几段、每段是否只报一次 | ✅ 单段 1 次（5 条未命中仍 1 次）；段间实验 2 段 2 次 | §6、`run-wd.txt`、`run-rearm.txt` |
| 离线安装器若也起不来要如实登记 | ✅ 不需要：离线补丁安装器一次成功，`unix_args.txt` 存在、`Done` 行与端口都在 | §0.1、`install.txt`、`start-and-check-skip.txt` |
