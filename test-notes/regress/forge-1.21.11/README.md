# Forge 1.21.11 真机回归（新出厂模板 / `check` 判定 / 看门狗）

看板卡 `t_f4d69bba`，2026-10-29 20:15–20:31 +0800。**本目录只记录本卡的实机证据**，
不放别族（vanilla / Fabric / NeoForge）的记录 —— 那几族各写各的目录，避免抢同一追加点。

**一句话结论**：在 **Forge 61.2.0 / MC 1.21.11**（BUG-003 的核心场景：加载器日志布局 + `[Not Secure]` 前缀）上，
main `8996a1d` 的**新出厂模板**把真机 14 条事件行**全部命中**，旧模板**全部未命中**且 `check` 判 `FAIL`/`exit=1`；
真客户端 E2E 的三类出站（进服通知 / `#` 聊天 / 退服通知）都走到了 `api.sgroup.qq.com` 并被 404
`请求Query参数group_id无效` 拒绝（预期成功信号）；旧模板下看门狗按「连续 3 条未命中」**只报一次**。
**产品代码零改动** —— 本卡只做验证与文档。

## 0. 环境与前置（可复现）

| 项 | 值 |
|---|---|
| 测试主机 | `hermes@10.1.1.4`（Rocky Linux 9，2.6 GB 内存 / 磁盘 95%） |
| 本机驱动方式 | Windows + git-bash，paramiko harness `rsh.py`（本机无 `sshpass`/`plink`） |
| 服务端 | Forge **61.2.0** / MC **1.21.11**，目录 `~/mc-test/forge/1.21.11`，tmux `mc-forge-1_21_11` |
| 端口 | 游戏 `25628` / RCON `25728` |
| 日志 | `~/mc-test/forge/1.21.11/logs/latest.log` |
| Java | `~/jdk-21`（Eclipse Adoptium 21.0.12.1+1-LTS，日志首行自证） |
| 被测副本 | `~/Y33-Bot`＝main `8996a1d` 的归档副本（**非 git 仓库**），`.venv` 可用 |
| 副本一致性 | `config.example.toml` / `src/y33bot/{service.py,mclog/watcher.py,mclog/patterns.py}` / `tests/test_log_patterns_real_lines.py` 的 sha256 与本机 main 工作树**逐一相等**（见 §2），所以「模板/看门狗/自检」跑的确实是合并后 main 的代码 |
| 真客户端 | mineflayer（`~/mc-test/client/client.js`、`client3.js`），Node v24.1.0，协议协商实测 `1.21.11` |
| QQ 侧 | 真 `app_id`/`app_secret`（`~/y33-env.sh` 载入 `~/.env`），**假** `group_openid = E2E_DUMMY_GROUP_OPENID` —— 故意打真平台换 404，用来证明「解析→格式化→发送」链路通 |

### 复现命令（本机逐条实跑）

```bash
SSHKIT=C:/Users/Lenovo/AppData/Local/hermes/cache/scratch/sshkit
PY=$SSHKIT/.venv/Scripts/python.exe

# 0) 服务端在跑：端口 + Done 行
$PY $SSHKIT/rsh.py 'ss -tln | grep -E ":25628|:25728"; grep -m1 "Done (" ~/mc-test/forge/1.21.11/logs/latest.log'

# 1) 起服 + 用「新出厂默认模板」生成配置 + check（日志新鲜时该项应为「跳过」）
$PY $SSHKIT/rsh.py -r '~/mc-test/harness/regress_start.sh forge 1.21.11 new'

# 2) 主回归：旧配置生成 → E2E 真客户端 → 真行判读 → 新/旧 check → 看门狗
$PY $SSHKIT/rsh.py -r '~/mc-test/harness/e2e_family.sh forge 1.21.11'

# 3) 负向：旧模板逐行重放 + 旧模板 check + 看门狗（换 Zoe 再造 3 条未命中）
$PY $SSHKIT/rsh.py -r '~/mc-test/harness/e2e_neg.sh forge 1.21.11'

# 4) 补一次归因实验：空日志 + 全新 state，验证「启动健康翻转」恰好发 1 条
$PY $SSHKIT/rsh.py -f $SSHKIT/health_only.sh

# 5) 收尾停服
$PY $SSHKIT/rsh.py 'tmux send-keys -t mc-forge-1_21_11 "stop" Enter; ss -tln | grep -E ":25628|:25728"; free -m'
```

产物目录（服务器）`~/mc-test/regress/forge-1_21_11/`，本目录 `artifacts/` 是其**逐字副本**（2026-10-29 20:32 回读）。

## 1. BUG-003 布局取证：真行确实不是 `HH:MM:SS` + 无 logger 段

服务端起服完成行（20:15 首次起服）：

```
[2910月2026 20:15:57.178] [Server thread/INFO] [net.minecraft.server.dedicated.DedicatedServer/]: Done (6.953s)! For help, type "help"
```

重启后（20:24，本节后续所有 E2E 都跑在这次起的服上）：

```
[2910月2026 20:24:42.182] [Server thread/INFO] [net.minecraft.server.dedicated.DedicatedServer/]: Done (0.299s)! For help, type "help"
```

时间戳 = `[2910月2026 20:15:57.178]`（**中文日期 + 毫秒，不是 `[\d{2}:\d{2}:\d{2}]`**），线程段后**多一段 logger**
（`[net.minecraft.server.dedicated.DedicatedServer/]`），冒号在 logger 之后 —— 这正是 BUG-003 描述的布局，
旧模板 `\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: …` 从第一个字符起就匹配不上。

> **与 BUG-003 正文的一处措辞差异（如实登记）**：卡片正文里写的加载器段形态是 `[+MinecraftServer/]`。
> 本实例 Forge 61.2.0 的实测段是 `[net.minecraft.server.MinecraftServer/]`（无 `+` 前缀）：
> `grep -aoE '\[[^]]*\+[^]]*\]' latest.log` 在本轮 70 行日志里**零命中**。
> 说明「`+` 前缀」不是稳定形态，而「线程段后跟一段 `[…]`」才是 —— 现出厂模板的
> `(?: \[[^\]]+\])?` 两者都吃，因此结论不受影响。

本轮 70 行日志里的 logger 段分布（`grep -aoE '\] \[[^]]*\]:' | sort | uniq -c`）：

```
     15 ] [net.minecraft.server.MinecraftServer/]:
     11 ] [net.minecraft.server.dedicated.DedicatedServer/]:
     10 ] [net.minecraft.server.rcon.thread.GenericThread/]:
      9 ] [net.minecraft.server.rcon.thread.RconClient/]:
      3 ] [net.minecraft.server.players.PlayerList/]:
      3 ] [net.minecraft.server.network.ServerGamePacketListenerImpl/]:
      3 ] [cpw.mods.modlauncher.Launcher/MODLAUNCHER]:
      2 ] [net.minecraft.server.level.progress.LoggingLevelLoadListener/]:
      2 ] [net.minecraftforge.fml.VersionChecker/]:
      2 ] [net.minecraftforge.common.ForgeMod/FORGEMOD]:
      1 ] [net.minecraft.world.item.crafting.RecipeManager/]:
      1 ] [net.minecraft.server.rcon.thread.RconThread/]:
```

**14 条事件真行全文**（新模板命中集；聊天行统一带 `[Not Secure] `）：

```
37:[2910月2026 20:28:31.611] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve joined the game
38:[2910月2026 20:28:33.298] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Steve> 大家好，这是普通聊天（不该被转发）
39:[2910月2026 20:28:34.500] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
41:[2910月2026 20:28:36.000] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve left the game
49:[2910月2026 20:28:58.104] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Alex joined the game
50:[2910月2026 20:28:59.475] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Alex> 普通聊天第 1 条（旧模板下应未命中）
51:[2910月2026 20:29:00.376] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Alex> 普通聊天第 2 条（旧模板下应未命中）
52:[2910月2026 20:29:01.279] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Alex> 普通聊天第 3 条（旧模板下应未命中）
54:[2910月2026 20:29:02.993] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Alex left the game
60:[2910月2026 20:29:32.856] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Zoe joined the game
61:[2910月2026 20:29:34.156] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Zoe> 普通聊天第 1 条（旧模板下应未命中）
62:[2910月2026 20:29:35.058] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Zoe> 普通聊天第 2 条（旧模板下应未命中）
63:[2910月2026 20:29:35.960] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Not Secure] <Zoe> 普通聊天第 3 条（旧模板下应未命中）
65:[2910月2026 20:29:37.692] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Zoe left the game
```

注意第 40/53/64 行的 `Steve[/127.0.0.1:49094] logged in with entity id …`、`Steve lost connection: Disconnected`
**不是**事件行（既不该被转发，也不该被算进「候选事件行」看门狗）—— 实测二者都没触发任何 `[群消息]`。

## 2. 副本一致性（证明跑的是 main 的代码，不是旧拷贝）

```
本机 main 8996a1d                                    ~/Y33-Bot（服务器）
46ee24f0…c770e5  config.example.toml           ==    46ee24f0…c770e5
a67c4c45…df8a2   src/y33bot/mclog/patterns.py  ==    a67c4c45…df8a2
478b11f9…b9fb4   src/y33bot/mclog/watcher.py   ==    478b11f9…b9fb4
9971d87b…847b7   src/y33bot/service.py         ==    9971d87b…847b7
39ad5d30…af16    tests/test_log_patterns_real_lines.py == 39ad5d30…af16
```

## 3. `check` 的三态真判定（跳过 ≠ 通过 ≠ 失败）

**(a) 刚重启、日志里还没有事件行 → 「跳过」**（`regress_start.sh forge 1.21.11 new`，20:24）

```
[日志 forge] OK /home/hermes/mc-test/forge/1.21.11/logs/latest.log 可读，偏移 12416 字节
[日志模板 forge] OK 未找到可判定的样例行，跳过
[绑定] OK 0 条
OK
check exit=0
```

这条**不算通过**：日志里只有起服噪声，模板再坏也是这个输出。本卡把它当「前置未满足」的证据留着。

**(b) 真客户端跑过一次之后 → 新出厂模板全命中**（`e2e_family.sh`，20:28；`artifacts/check-new.txt`）

```
[日志模板 forge] OK 样例行 4 条全部命中（join 1 / quit 1 / chat 2）
[绑定] OK 0 条
OK
check(new) exit=0
```

日志更长之后（`e2e_neg.sh` 第 5 步，20:29）：`[日志模板 forge] OK 样例行 14 条全部命中（join 3 / quit 3 / chat 8）`。

**(c) 同一份真行、旧模板 → FAIL 且 exit=1**（`artifacts/check-old.txt`）

```
[配置] OK config-regress-forge-1_21_11-old.toml 解析成功，1 个 MC 服
[QQ] OK access_token 获取成功（有效期 5076s），app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON forge] OK /list -> There are 0 of a max of 20 players online:
[日志 forge] OK /home/hermes/mc-test/forge/1.21.11/logs/latest.log 可读，偏移 8207 字节
[日志模板 forge] FAIL 9 条样例行全部未命中：请按 README §13 调整 [log_patterns]
[绑定] OK 0 条
FAIL
check(old) exit=1
```

同一脚本前一步（4 条真行时）为 `FAIL 4 条样例行全部未命中：请按 README §13 调整 [log_patterns]`、`check(old) exit=1`
（见 `artifacts/summary.txt`）。**旧模板的 `[log_patterns]` 与 `check` 的判定口径都在 `artifacts/` 里逐字可查**：

```toml
join = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) joined the game'
quit = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) left the game'
chat = '\[\d{2}:\d{2}:\d{2}\] \[Async Chat Thread - #\d+/INFO\]: <(?P<player>\w+)> (?P<message>.+)'
```

## 4. `simulate log-event --dry-run` 四类真行的判读

命令（`e2e_family.sh` 第 4 步，配置＝新出厂模板；`artifacts/parse.txt` 是三轮追加的原始记录）：

```bash
cd ~/Y33-Bot && .venv/bin/python -m y33bot simulate log-event --server forge --line "<真行>" --dry-run \
  --config config-regress-forge-1_21_11-new.toml
```

| 类别 | 真行 | 输出 |
|---|---|---|
| join | `… [MinecraftServer/]: Steve joined the game` | `[群消息] Steve进入了forge` |
| `#` 聊天（`[Not Secure]`） | `… [MinecraftServer/]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）` | `[群消息] Steve@forge: 大家好，这是带井号的聊天（应被转发）` |
| 普通聊天（非 `#`） | `… [MinecraftServer/]: [Not Secure] <Steve> 大家好，这是普通聊天（不该被转发）` | `[忽略] 聊天非 # 开头，不转发` |
| quit | `… [MinecraftServer/]: Steve left the game` | `[群消息] Steve退出了forge` |

> `[Not Secure]` 前缀被模板里的 `(?:\[Not Secure\] )?` 吃掉，转发正文里**没有**残留前缀 —— 这是本卡最关键的一条：
> BUG-003 的两半（加载器 logger 段 + `[Not Secure]`）同时生效时仍然正确。

## 5. E2E：真客户端进服 → 三类出站真打 `api.sgroup.qq.com`

`artifacts/client.txt`（mineflayer，协议协商 `1.21.11`）：

```
[client] 连接 127.0.0.1:25628 用户名 Steve
[client] 已 spawn（进服成功），版本协商: 1.21.11
[client] 已发送普通聊天
[client] 已发送 # 聊天
[client] 主动退出
[client] 连接结束
```

机器人侧（`artifacts/run-e2e.txt`，去掉 `^[botpy]` 噪声后）：

```
[启动] y33bot 0.1.0（1 个 MC 服）
[启动] 日志监听已启动: forge
[启动] QQ 网关已连接
[启动] QQ 网关就绪
[RCON forge] /list
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效
[忽略] 聊天非 # 开头，不转发
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效
[RCON forge] /list
[停止] 收到退出信号
[停止] 正在关闭…
[停止] 已退出
--- 计数 ---
QQ 发送调用次数: 4
忽略(非#)次数  : 1
警告次数       : 0
```

原始 botpy 行（4 条，各带独立 `trace_id`，逐字）：

```
[botpy] 接口请求异常，请求连接: https://api.sgroup.qq.com/v2/groups/E2E_DUMMY_GROUP_OPENID/messages, 错误代码: 404, 返回内容: {'message': '请求Query参数group_id无效', 'code': 11321, 'err_code': 40011036, 'trace_id': 'a49045ba75fa76efee6f13faa4e7199a'}, trace_id:a49045ba75fa76efee6f13faa4e7199a
```

（另三条 `trace_id`：`b7178f789129869c6dc467f4f2be4955`、`6b29d63b2c4cba0fe5dc0298c9e1dcae`、`a1b7f2bc66bb989bcff43dd8b4966728`）

**「4 次」的归因（自查过，不是拍的）**：3 类事件 = join 1 + `#` 聊天 1 + quit 1，另有 **1 条启动健康翻转**
`[服务器状态] forge 上线`（`state` 文件在脚本里被删过 ⇒ 首轮健康轮询必然翻转）。
归因实验 `artifacts/run-healthonly.txt`：把 `log_path` 指向**空文件**（事件 0 条）+ 全新 `state`，跑 12 s ——

```
[启动] y33bot 0.1.0（1 个 MC 服）
[启动] 日志监听已启动: forge
[启动] QQ 网关已连接
[启动] QQ 网关就绪
[RCON forge] /list
[错误] QQ 发送失败（不重试）: 请求Query参数group_id无效
[停止] 收到退出信号
--- 计数 ---
QQ 发送调用次数(空日志/全新 state): 1
健康轮询 /list 次数             : 1
```

⇒ 1（健康翻转）+ 3（事件）= 4，实测吻合；普通聊天那 1 条在发送前就被 `[忽略]` 掉了，没有打平台。

> 另注：不要在**同一份长日志**上直接看这个小计 —— 本卡第一次跑（重启前）是 `发送=9 / 忽略=5`，
> 差额来自 `state` 被删后**历史事件行整体回放**（上一轮 Steve/Alex 会话 + 本轮），
> 这也是本文最终取「重启后干净日志」那一轮做证据的原因。

## 6. 看门狗：连续 3 条未命中只报一次

旧模板 + 全新 `state` + `client3.js`（Alex：进服 + 3 条普通聊天 + 退服），`artifacts/run-wd.txt`：

```
[启动] 日志监听已启动: forge
[启动] QQ 网关就绪
[RCON forge] /list
[警告] 疑似事件行连续 3 条未匹配 [log_patterns]（forge）：MC→QQ 方向可能失效，请按 README §13 调整模板
[RCON forge] /list
[停止] 收到退出信号
警告次数: 1
```

- 同一有效期内累计未命中 **9 条**（`e2e_neg` 看门狗段）/ **13 条**（重启前那轮），`[警告]` 计数始终是 **1**
  ⇒ 按「段」报，不按「条」刷屏。
- 反证：模板正确的那一轮（§5），同样有 4 条事件行 + 1 条被忽略的普通聊天，`警告次数: 0` —— 命中即不武装，
  没有被聊天的「未匹配」误伤。
- 已知边界：本轮**没有**在同一次运行里造出「命中 → 重新武装 → 再连续 3 条未命中 → 第二次告警」的段间证据
  （旧模板下真实行一条都命不中，做不出对齐点）。该行为由单测覆盖（`tests/` 里看门狗重新武装的用例），
  本条只声明「一段只报一次」，不声明「多段的关系」已实测。

## 7. 本轮踩到的两个 harness 缺陷（脚本，非产品代码）

| # | 现象（原样） | 根因 | 处置 |
|---|---|---|---|
| 1 | `e2e_family.sh` 第 1 步：`re.error: bad escape \d at position 10` + `sed：无法读取 …config-regress-forge-1_21_11-old.toml：没有那个文件或目录`，随后旧模板 `check` 报的 FAIL 是**「配置文件不存在」而不是模板不匹配**（`[配置] FAIL 配置文件不存在: …-old.toml`），看门狗也因配置缺失没跑（`警告次数: 0`） | `make_old_cfg` 用 `re.sub(pat, f"{key} = {get(o,key)}", …)` 传**字符串**替换体，旧模板里的 `\d` 被当成组引用；Python 3.9 直接抛 `bad escape`。`e2e_neg.sh` 早改过（用 `lambda`），`e2e_family.sh` 漏了 | 改成函数式替换（与 `e2e_neg.sh` 一致），服务器上的 `~/mc-test/harness/e2e_family.sh` 已更新，原件备份 `e2e_family.sh.bak-2026-10-29` |
| 2 | `regress_start.sh` 起服后打印 `第 85 行：[: 0\r\n0：需要整数表达式`（3 次）并给出 `启动结果: 失败 耗时 210s` —— 但同一段输出里 `Done (0.299s)` 与两个端口都在 | `DONE_BEFORE=$(grep -ac 'Done (' "$MC_LOG" 2>/dev/null \|\| echo 0)`：`latest.log` 在 JVM 启动时被重建为空，`grep -c` 输出 `0` 且退出码 1 ⇒ `\|\| echo 0` 再补一个 `0` ⇒ 变量成了 `"0\n0"`，`[ "$NOW" -gt "$DONE_BEFORE" ]` 报错，判据永远不成立 | **只登记不修**（超出本卡「不改脚本交付面」的最小必要范围，且不影响结论：脚本随后照常跑 `check`，端口/`Done` 行是真证据）；建议后续修法：`|| true` + `${VAR:-0}` 或 `grep -ac … \|\| echo 0` 改成 `awk`/`grep -a … \| wc -l` |

## 8. 收尾停服（硬要求）

```
$ tmux send-keys -t mc-forge-1_21_11 "stop" Enter
端口已消失（第 2 次检查，约 6s）
--- 端口 ---
(无监听)
--- tmux ---
no server running on /tmp/tmux-1002/default
--- free ---
               total        used        free      shared  buff/cache   available
Mem:            2679        1137        1013          11         717        1542
--- df ---
/dev/mapper/rlm-root   17G   16G  1.1G   95% /
```

停服前的日志尾部（世界已存盘、RCON 已停）：

```
[2910月2026 20:31:06.838] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: ThreadedAnvilChunkStorage: All dimensions are saved
[2910月2026 20:31:06.853] [Server thread/INFO] [net.minecraft.server.rcon.thread.GenericThread/]: Thread RCON Listener stopped
```

内存可用从 747 MB 回到 **1542 MB**；磁盘 1.1 GB 余量**未继续缩水**（本轮只新增文本产物 ≈ 10 KB）。
**已停服，后续 NeoForge 卡可以起服**。

## 9. 产物清单（`artifacts/`，逐字副本）

| 文件 | 内容 | 取自 |
|---|---|---|
| `real-lines.txt` | JOIN / CHAT / PLAIN / QUIT 四条真行原文 | `e2e_family.sh` 第 3 步 |
| `parse.txt` | `simulate --dry-run` 判读（三次追加，12 行） | 第 4 步（×3 运行） |
| `check-new.txt` | 新出厂模板 `check` = `OK 样例行 4 条全部命中` | 第 5 步 |
| `check-old.txt` | 旧模板 `check` = `FAIL 9 条样例行全部未命中` + `exit=1` | `e2e_neg.sh` 第 3 步（最后一次） |
| `summary.txt` | `e2e_family.sh` 汇总（新 4 条 OK / 旧 4 条 FAIL / 发送 4 / 看门狗 1） | 第 7 步 |
| `run-e2e.txt` | E2E 机器人全量输出（含 botpy 404 原文） | 第 2 步 |
| `run-wd.txt` | 看门狗输出（`[警告]` ×1） | 第 6 步 |
| `run-healthonly.txt` | 归因实验：空日志 + 全新 state ⇒ 发送 1 次 | 本卡补测 |
| `client.txt` / `client3.txt` | mineflayer 客户端输出 | 第 2 / 6 步 |
| `check-new-latest.txt` | **汇总卡 `t_9e9040ed` 补跑**：同一份真机日志（82 行 / 14 条事件行）`[日志模板 forge] OK 样例行 14 条全部命中（join 3 / quit 3 / chat 8）`。**停服后**跑的，`[RCON forge]` 因此 FAIL、整条 `check` = `FAIL` —— 只有 `[日志模板]` 这项是结论（`docs/acceptance.md` §13.9） | 汇总卡 2026-10-29 21:00 |
| `check-old-latest.txt` | **汇总卡 `t_9e9040ed` 补跑**：同一份日志 + 旧模板 → `FAIL 14 条样例行全部未命中`（同上，RCON 项 FAIL） | 汇总卡 2026-10-29 21:00 |

> `summary.txt` 是**早期快照**（4 行日志时生成，里面写 `旧模板 FAIL 4 条`）；**旧模板的最终口径以 `check-old.txt`
> （9 条）/ `check-old-latest.txt`（14 条）为准**，别拿 `summary.txt` 的数字对账。

## 10. 未覆盖的边界（不下结论）

1. **NeoForge**：同族但布局未必完全一致 —— 由看板卡 `t_0ee0c2ff` 单独回归，本目录不含其证据。
2. **`online-mode=true` 的签名聊天行**：本实例 `online-mode=false`，`[Not Secure]` 是这一前提下的形态；
   正版服是否另有前缀（如 `<玩家> ` 前多一段）未验。
3. **段间重新武装**：见 §6 末条。
4. **只测了 Forge 61.2.0 / MC 1.21.11 一个点**：Forge 1.21.3–26.3 的其余版本仍只有 `test-notes/03-forge.md` 的格式取样与外推。
5. **QQ 侧真实投递**：`group_openid` 是假的，404 是**预期**结果；真群能不能收到消息属 S5，不在本卡范围。
