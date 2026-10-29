# Fabric 1.21.11 真机回归（新出厂模板 / `check` 判定 / 看门狗 2 次告警的定论）

汇总卡 `t_9e9040ed`，2026-10-29 20:05–20:08 +0800（起服 / E2E / 看门狗）+ 21:00（停服后补跑 `[日志模板]` 项与逐行重放）。

**一句话结论**：Fabric 1.21.11 的日志布局与原版同形（`[HH:MM:SS] [Server thread/INFO]: …`，无加载器 logger 段），
所以同样**只踩 BUG-002**：新出厂模板 `OK 4/4 → 14/14`，旧模板 `FAIL 14 条中 6 条命中、8 条未命中`
（6 = join 3 + quit 3，8 = 全部 chat）。本轮**唯一出现 2 次看门狗告警**的族 —— 用逐行重放证实是
**两个彼此独立的连续未命中段**（被 `Alex left the game` 打断），**行为正确，不开 BUG-006**。

## 0. 环境与前置

| 项 | 值 |
|---|---|
| 测试主机 | `hermes@10.1.1.4`（Rocky Linux 9；2.6 GB 内存 / 磁盘 95%），paramiko harness `rsh.py` |
| 服务端 | **Fabric 1.21.11（loader 0.19.5）**，目录 `~/mc-test/fabric/1.21.11`，tmux `mc-fabric-1_21_11`，游戏 `25615` / RCON `25715` |
| 日志 | `~/mc-test/fabric/1.21.11/logs/latest.log`（`online-mode=false`） |
| 环境恢复 | 上一轮清理删掉 `.fabric/`，`fabric-server-launch.jar` 只剩 **639 字节桩** ⇒ 官方安装器重装：`java -jar ~/mc-test/tools/fabric-installer-1.1.2.jar server -mcversion 1.21.11 -loader 0.19.5 -downloadMinecraft -dir ~/mc-test/fabric/1.21.11` |
| 被测副本 / 客户端 / QQ 侧 | 同 `vanilla-1.21.11/README.md` §0（main `8996a1d` 归档副本；mineflayer 协议协商 `1.21.11`；假 `group_openid`） |

## 1. 真行原文（`artifacts/real-lines.txt`）

```
JOIN=[20:06:16] [Server thread/INFO]: Steve joined the game
CHAT=[20:06:19] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
PLAIN=[20:06:17] [Server thread/INFO]: [Not Secure] <Steve> 大家好，这是普通聊天（不该被转发）
QUIT=[20:06:20] [Server thread/INFO]: Steve left the game
```

## 2. `check` 的判定

| 原文文件 | 时机 | `[日志模板 fabric]` 输出 | 整条 `check` |
|---|---|---|---|
| `check-new.txt` | 真客户端跑过一次（4 条事件行，**服务端在线**） | `OK 样例行 4 条全部命中（join 1 / quit 1 / chat 2）` | `OK` |
| `check-new-latest.txt` | 停服后同一份日志（14 条事件行，**补跑**） | `OK 样例行 14 条全部命中（join 3 / quit 3 / chat 8）` | `FAIL`（**只因 `[RCON fabric]` 连不上 127.0.0.1:25715**） |
| `check-old.txt` | 旧模板（9 条时，服务端在线） | `FAIL 9 条样例行中 4 条命中、5 条未命中：请按 README §13 调整 [log_patterns]` | `FAIL` |
| `check-old-latest.txt` | 旧模板（14 条时，补跑） | `FAIL 14 条样例行中 6 条命中、8 条未命中…` | `FAIL` |

旧模板命中 6 = join 3 + quit 3，未命中 8 = 全部 chat ⇒ 与 §14（原版）完全同一指纹：**只坏 chat**。

## 3. `simulate` 判读（`artifacts/parse.txt`）

```
[群消息] Steve进入了fabric
[群消息] Steve@fabric: 大家好，这是带井号的聊天（应被转发）
[忽略] 聊天非 # 开头，不转发
[群消息] Steve退出了fabric
```

## 4. E2E（`artifacts/run-e2e.txt`）

`QQ 发送失败（不重试）` **4 次** / `[忽略]` **1 次** / `[警告]` **0 次**；4 次都是
`api.sgroup.qq.com` 的 `404 / 11321 / 请求Query参数group_id无效`。
**4 = 3 类事件 + 1 条启动健康翻转**（同原版/Forge/NeoForge）。

## 5. 看门狗：**2 次**告警的定论（两个独立段，符合设计）

`artifacts/run-wd.txt`（20:08，旧模板 + `client3.js` 两轮：Alex、Zoe）：`[警告]` 出现 **2 次**，两次逐字相同：

```
[警告] 疑似事件行连续 3 条未匹配 [log_patterns]（fabric）：MC→QQ 方向可能失效，请按 README §13 调整模板
```

为了区分「两段独立」与「同一段被报两次」，21:00 用**旧模板 + `simulate log-event`** 对留存日志里
14 条候选行**按出现顺序**逐条重放，原文落 `artifacts/replay-old-template.txt`：

```
 1  HIT             [20:06:16] … Steve joined the game
 2  MISS(连续第 1 条)  [20:06:17] … [Not Secure] <Steve> 大家好，这是普通聊天（不该被转发）
 3  MISS(连续第 2 条)  [20:06:19] … [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
 4  HIT             [20:06:20] … Steve left the game
 5  HIT             [20:06:42] … Alex joined the game
 6  MISS(连续第 1 条)  [20:06:43] … [Not Secure] <Alex> 普通聊天第 1 条（旧模板下应未命中）
 7  MISS(连续第 2 条)  [20:06:44] … <Alex> 普通聊天第 2 条
 8  MISS(连续第 3 条)  [20:06:45] … <Alex> 普通聊天第 3 条
   └─ 段 1 结束：连续未命中 3 条，起始行 = [20:06:43] … <Alex> 普通聊天第 1 条
 9  HIT             [20:06:47] … Alex left the game
10  HIT             [20:07:55] … Zoe joined the game
11  MISS(连续第 1 条)  [20:07:56] … <Zoe> 普通聊天第 1 条
12  MISS(连续第 2 条)  [20:07:57] … <Zoe> 普通聊天第 2 条
13  MISS(连续第 3 条)  [20:07:58] … <Zoe> 普通聊天第 3 条
   └─ 段 2 结束：连续未命中 3 条，起始行 = [20:07:56] … <Zoe> 普通聊天第 1 条
14  HIT             [20:08:00] … Zoe left the game

候选行 14 条：命中 6 / 未命中 8；≥3 条的独立连续未命中段 = 2 段
```

**结论**：两段彼此独立（Alex 段 20:06:43–45、Zoe 段 20:07:56–58），中间被 `[20:06:47] Alex left the game`
这条**命中行**打断 ⇒ 每段各报 1 次、共 2 次 = **符合设计**（命中任一事件即重新武装）。
**不按缺陷处理，不新开 BUG**；NeoForge 的「段间重新武装」真机实验（2 段 ⇒ 2 次）与此互相印证。

> 别把两种「警告」混成一条：`simulate log-event` 里每条未命中会**逐条**打 `[警告] 日志行未匹配任何模板`；
> `run` 里才是「连续 3 条 → 打**一次**」的看门狗。§5 说的 2 次是后者。

## 6. 产物清单（`artifacts/`，逐字副本；21:00 回读）

| 文件 | 内容 | 备注 |
|---|---|---|
| `real-lines.txt` | 四条真行 | 权威 |
| `parse.txt` | 四类判读 | 权威 |
| `check-new.txt` | 4 条全命中（在线） | **在线权威证据** |
| `check-new-latest.txt` | 14 条全命中（停服后补跑） | 只 `[日志模板]` 项有效 |
| `check-old.txt` | 旧模板 9 条中 4 命中 / 5 未命中 | 在线权威 |
| `check-old-latest.txt` | 旧模板 14 条中 6 命中 / 8 未命中（补跑） | 数字最全 |
| `run-e2e.txt` | E2E（4 发送 / 1 忽略 / 0 警告） | 权威 |
| `run-wd.txt` | 看门狗 `[警告]` ×2 | 权威 |
| `replay-old-template.txt` | 旧模板逐行重放 + 段划分 | 21:00 补跑，§5 的依据 |
| `client.txt` / `client3.txt` | mineflayer 输出 | 权威 |
| `summary.txt` | `e2e_family.sh` 早期汇总（`看门狗: 警告=0`，那是 wd 那一轮**之前**的快照） | **早期快照，别用它对着 §5 对账** |

## 7. 未覆盖的边界（不下结论）

1. `online-mode=true` 的签名聊天行（本实例 `online-mode=false`）。
2. 版本密度：只打 1.21.11 + loader 0.19.5 一个组合；Fabric 1.21.2–26.1 其余版本仍只有格式取样（`test-notes/02-fabric.md`）。
3. QQ 真实投递属 S5；`group_openid` 是假值，404 是预期。
