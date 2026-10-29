# `test-notes/regress/` —— 真机回归证据目录索引

这一层放**真机回归**（不是离线复扫）的逐字产物，一族一个目录。所有文件都是服务器
`~/mc-test/regress/<族>-<版本>/` 的**逐字副本**（`-` 连接、版本号 `.`→`_`），
用 paramiko harness `rsh.py` 从 `hermes@10.1.1.4` 取回，**没有经过手工改写**。

| 目录 | 族 / 版本 | 对应验收小节 | 执行卡 |
|---|---|---|---|
| [`vanilla-1.21.11/`](vanilla-1.21.11/README.md) | 原版 Vanilla **1.21.11** | `docs/acceptance.md` §14 | 汇总卡 `t_9e9040ed` |
| [`fabric-1.21.11/`](fabric-1.21.11/README.md) | Fabric **1.21.11**（loader 0.19.5） | §15 | 汇总卡 `t_9e9040ed` |
| [`forge-1.21.11/`](forge-1.21.11/README.md) | Forge **61.2.0** | §13 | 卡 `t_f4d69bba`（汇总卡补 `check-*-latest.txt`） |
| [`neoforge-1.21.11/`](neoforge-1.21.11/README.md) | NeoForge **21.11.48** | §16 | 卡 `t_0ee0c2ff`（汇总卡归档） |
| [`log-slice-events.txt`](log-slice-events.txt) | 四族事件行切片（同一时点一次性采出，带行号） | §17.1 | 汇总卡 `t_9e9040ed` |

跨族汇总、证据分级口径、harness 缺陷与未覆盖边界都在 `docs/acceptance.md` §17。

## 读之前必须知道的四条口径

1. **「服务端在线时的 `check`」与「停服后补跑的 `check`」不是一回事。**
   在线那次整条 `check` 可以是 `OK`（RCON + QQ + 日志模板全过）；停服后补跑的那次 `[RCON]` 必然 `FAIL`，
   整条 `check` 以 `FAIL` 收尾（退出码 1），**只有 `[日志模板 <族>]` 这一行还能当结论**。
   目录里带 `-latest` 后缀的（`check-new-latest.txt` / `check-old-latest.txt`）都是**停服后补跑**的。
2. **`summary.txt` 基本都是早期快照**（`e2e_family.sh` 跑在各种日志长度之前）。对账一律看
   `check-new.txt` / `check-new-latest.txt` / `check-old*.txt` 这几个**单次 `check` 的完整输出**。
3. **`simulate log-event` 的 `[警告]` 与 `run` 的 `[警告]` 不是同一条东西**：
   前者是逐行判读提示（每条未命中打一次），后者才是「连续 3 条未命中 → 打一次」的看门狗。
   目录里 `run-wd.txt` / `run-old-wd.txt` / `run-rearm.txt` 里的「警告次数」都指后者。
4. **合成行必须能被一眼看出**：`neoforge-1.21.11/artifacts/run-rearm.txt` 里的
   `[20:45:00] [Server thread/INFO]: Tester joined the game` 是**为了制造「重新武装」对齐点而手插的**，
   不是真机事件行，已在该族 README 里标注。

## 本轮（2026-10-29）四族的对照结论

| 族 | 新模板 `check` | 旧模板 `check` | 缺陷指纹 | 看门狗 |
|---|---|---|---|---|
| 原版 1.21.11 | `OK 8/8` → `OK 18/18` | `FAIL` 18 条中 8 命中 / 10 未命中 | 只坏 `chat`（BUG-002） | 单段 → 1 次 |
| Fabric 1.21.11 | `OK 4/4` → `OK 14/14` | `FAIL` 14 条中 6 命中 / 8 未命中 | 只坏 `chat`（BUG-002） | **两段 → 2 次** |
| Forge 61.2.0 | `OK 4/4` → `OK 14/14` | `FAIL 14 条全部未命中` | 三模板全灭（BUG-003） | 单段 → 1 次 |
| NeoForge 21.11.48 | `OK 4/4` → `OK 14/14`（在线） | `FAIL 9 条全部未命中` | 三模板全灭（BUG-003） | 单段 1 次；2 段实验 2 次 |

> 一句话：**旧模板的失败指纹就能把两个缺陷分开** —— 原版/Fabric 只死 `chat`（BUG-002），
> Forge/NeoForge 连 `join`/`quit` 一起死（BUG-003）。
