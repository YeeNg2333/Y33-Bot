# 原版 Vanilla 1.21.11 真机回归（新出厂模板 / `check` 判定 / 看门狗）

汇总卡 `t_9e9040ed`，2026-10-29 19:53–20:04 +0800（起服 / E2E / 看门狗）+ 21:00（停服后补跑 `[日志模板]` 项）。

**一句话结论**：原版 1.21.11 的日志布局是 `[HH:MM:SS] [Server thread/INFO]: …`（**无加载器 logger 段**），
聊天行带 `[Not Secure] ` —— 这里只会踩 **BUG-002（chat 模板）**、不会踩 BUG-003。新出厂模板把真事件行
**8/8 → 18/18 全部命中**；同一批真行换旧模板 `FAIL 18 条中 8 条命中、10 条未命中`，且
**命中 8 = join 4 + quit 4、未命中 10 = 全部 chat** —— 这就是「只坏 chat」的现场指纹。
真客户端 E2E 三类出站 + 1 条启动健康翻转共 4 次打到 `api.sgroup.qq.com`（假 `group_openid`，404 是预期）；
旧模板下看门狗单段报 1 次、新模板 0 次。**产品代码零改动**（本卡只做验证与文档）。

## 0. 环境与前置

| 项 | 值 |
|---|---|
| 测试主机 | `hermes@10.1.1.4`（Rocky Linux 9；2.6 GB 内存 / 磁盘 95%） |
| 本机驱动 | Windows + git-bash，paramiko harness `rsh.py`（本机无 `sshpass`/`plink`，SSH 公钥认证被拒） |
| 服务端 | **原版 Vanilla 1.21.11**，目录 `~/mc-test/vanilla/1.21.11`，tmux `mc-vanilla-1_21_11`，游戏 `25600` / RCON `25700` |
| 日志 | `~/mc-test/vanilla/1.21.11/logs/latest.log`（`online-mode=false`） |
| Java | `~/jdk-21`（Temurin 21.0.12.1+1-LTS） |
| 被测副本 | `~/Y33-Bot`＝main `8996a1d` 的归档副本（**非 git 仓库**），`.venv` 可用 |
| 环境恢复 | 上一轮清理脚本 `rm -rf libraries world logs` 后缺 `server.jar`：从 `piston-meta.mojang.com` 拉 manifest → `server.jar`，sha1 `64bb6d763bed0a9f1d632ec347938594144943ed` |
| 真客户端 | mineflayer（`~/mc-test/client/client.js`、`client3.js`），Node v24.1.0，协议协商实测 `1.21.11` |
| QQ 侧 | 真 `app_id`/`app_secret`（`~/y33-env.sh` 载入 `~/.env`）；**假** `group_openid = E2E_DUMMY_GROUP_OPENID` |

复现命令（与 Forge 卡同一套 harness，只换族名）：

```bash
SSHKIT=C:/Users/Lenovo/AppData/Local/hermes/cache/scratch/sshkit
PY=$SSHKIT/.venv/Scripts/python.exe
$PY $SSHKIT/rsh.py -r '~/mc-test/harness/regress_start.sh vanilla 1.21.11 new'
$PY $SSHKIT/rsh.py -r '~/mc-test/harness/e2e_family.sh vanilla 1.21.11'
$PY $SSHKIT/rsh.py -r '~/mc-test/harness/e2e_neg.sh vanilla 1.21.11'
$PY $SSHKIT/rsh.py 'tmux send-keys -t mc-vanilla-1_21_11 "stop" Enter; ss -tln | grep -E ":25600|:25700"; free -m'
```

## 1. 真行原文（`artifacts/real-lines.txt`）

```
JOIN=[20:00:41] [Server thread/INFO]: Steve joined the game
CHAT=[20:00:44] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
PLAIN=[20:00:43] [Server thread/INFO]: [Not Secure] <Steve> 大家好，这是普通聊天（不该被转发）
QUIT=[20:00:46] [Server thread/INFO]: Steve left the game
```

布局：`[HH:MM:SS]` + `[Server thread/INFO]` + **无 logger 段**；聊天行带 `[Not Secure] `
（1.21.2+ 原版在 `online-mode=false` 下的形态）。对应 `docs/acceptance.md` §14.1。

## 2. `check` 的判定（三态 + 负向对照）

| 原文文件 | 时机 | `[日志模板 vanilla]` 输出 | 整条 `check` |
|---|---|---|---|
| `check-new.txt` | 刚起服、日志 0 事件行 | `OK 未找到可判定的样例行，跳过` | `OK`（**跳过 ≠ 通过**） |
| `check-new2.txt` | 真客户端跑过一次（8 条事件行） | `OK 样例行 8 条全部命中（join 2 / quit 2 / chat 4）` | `OK` |
| `check-new-latest.txt` | 停服后同一份日志（18 条事件行，**补跑**） | `OK 样例行 18 条全部命中（join 4 / quit 4 / chat 10）` | `FAIL`（**只因 `[RCON vanilla]` 连不上 127.0.0.1:25700**） |
| `check-old.txt` | 早期 4 条时 + 旧模板 | `FAIL 4 条样例行中 2 条命中、2 条未命中：请按 README §13 调整 [log_patterns]` | `FAIL` |
| `check-old2.txt` | 8 条时 + 旧模板 | `FAIL 8 条样例行中 4 条命中、4 条未命中…` | `FAIL` |
| `check-old-latest.txt` | 18 条时 + 旧模板（补跑） | `FAIL 18 条样例行中 8 条命中、10 条未命中…` | `FAIL`（RCON 项也 FAIL） |

**负向对照的数字本身是结论**：旧模板命中 8 = join 4 + quit 4，未命中 10 = 全部 chat
（旧 `chat` 模板是 `[Async Chat Thread - #\d+/INFO]: <玩家> …`，既不是 `Server thread` 线程名，
也没有 `[Not Secure] ` 可选前缀）。⇒ 原版上 BUG-002 只坏 chat，进出服通知照常 —— **所以负向用例必须靠
连续聊天造未命中，不能指望 join/quit 失败**。

## 3. `simulate log-event --dry-run` 判读（`artifacts/parse-*.txt`）

```
parse-JOIN.txt   → [群消息] Steve进入了vanilla
parse-CHAT.txt   → [群消息] Steve@vanilla: 大家好，这是带井号的聊天（应被转发）
parse-PLAIN.txt  → [忽略] 聊天非 # 开头，不转发
parse-QUIT.txt   → [群消息] Steve退出了vanilla
```

`[Not Secure] ` 被模板里的可选组吃掉，转发正文无残留。

## 4. E2E（`artifacts/run-new.txt`，20:00–20:01，服务端运行中）

客户端（`artifacts/client.txt`）：`已 spawn（进服成功），版本协商: 1.21.11` → 普通聊天 → `#` 聊天 → 主动退出。

机器人侧统计：`QQ 发送失败（不重试）` **4 次**、`[忽略] 聊天非 # 开头` **1 次**、`[警告]` **0 次**；
4 次全部打到 `https://api.sgroup.qq.com/v2/groups/E2E_DUMMY_GROUP_OPENID/messages` 并被
`404 / code 11321 / '请求Query参数group_id无效' / err_code 40011036` 拒绝。

**4 = 3 类事件（join / `#` 聊天 / quit）+ 1 条启动健康翻转**（脚本清空 `state` ⇒ 首轮健康轮询必翻转）。
普通聊天那 1 条在发送前即 `[忽略]`，没打平台。

## 5. 看门狗（BUG-004）

| 原文文件 | 模板 | 造法 | `[警告]` 次数 | 同时的发送/忽略 |
|---|---|---|---|---|
| `run-old-wd.txt` | 旧 | `client3.js`：进服 + 3 条普通聊天 + 退服 | **1** | 发送 2（join/quit 命中）、忽略 0 |
| `run-new-wd.txt` | 新 | 同一套客户端 | **0** | 发送 7、忽略 7 |

旧模板那轮的原文：

```
[警告] 疑似事件行连续 3 条未匹配 [log_patterns]（vanilla）：MC→QQ 方向可能失效，请按 README §13 调整模板
```

原版是**单段**（日志里只有一段连续未命中）；两段的情形见 `fabric-1.21.11/README.md` §5 与
`docs/acceptance.md` §15.5。

## 6. 产物清单（`artifacts/`，逐字副本；21:00 回读）

| 文件 | 内容 | 备注 |
|---|---|---|
| `real-lines.txt` | JOIN / CHAT / PLAIN / QUIT 四条真行 | 权威 |
| `parse-JOIN/CHAT/PLAIN/QUIT.txt` | 四类真行的 `simulate` 判读 | 权威 |
| `check-new.txt` | 起服即跑 → `跳过` | 早期快照（0 事件行） |
| `check-new2.txt` | 8 条全命中 | **服务端在线时的权威证据** |
| `check-new-latest.txt` | 18 条全命中（停服后补跑） | 只 `[日志模板]` 项有效 |
| `check-old.txt` / `check-old2.txt` | 旧模板 4 条 / 8 条时的 FAIL | 早期快照 |
| `check-old-latest.txt` | 旧模板 18 条的 FAIL（停服后补跑） | 数字最全 |
| `run-new.txt` | E2E（4 发送 / 1 忽略 / 0 警告） | 权威 |
| `run-old.txt` | 旧模板下的 E2E（含历史事件整体回放，5 发送） | 只作旁证，不用于计数结论 |
| `run-old-wd.txt` / `run-new-wd.txt` | 看门狗 1 次 / 0 次 | 权威 |
| `client.txt` / `client-old.txt` / `client3.txt` / `client3b.txt` | mineflayer 输出 | 权威 |
| `summary.txt` | `e2e_vanilla.sh` 的早期汇总（新模板当时还是「跳过」、旧模板 `FAIL 4 条中 2 命中`） | **早期快照，别用它对着正文对账** |

## 7. 未覆盖的边界（不下结论）

1. **`online-mode=true` 的签名聊天行**：本实例 `online-mode=false`，`[Not Secure]` 是这一前提下的形态。
2. **版本密度**：只打 1.21.11 一个点；原版 26.2 / 26.3 仍只有 `test-notes/01-vanilla.md` 的格式取样与外推。
3. **QQ 真实投递**：`group_openid` 是假的，404 是预期结果，真群投递属 S5。
4. **停服后补跑的那三份 `check-*-latest.txt`** 不是又一次真机回归，只补 `[日志模板]` 这一项（见本目录上一级 README）。
