# test-notes/ —— 实机测试矩阵的记录（说明）

本目录是「MC 版本 × 加载器」实机测试矩阵的**逐版本记录**，随 `BUGS.md` 一起提交。
本目录**只放记录，不放代码**：全程没有改动 `src/`、`tests/`、`docs/` 里的任何文件。

| 文件 | 来源卡 | 分支 / 提交 | 内容 |
|---|---|---|---|
| `00-env.md` | `t_a4c6c3ae` | `wt/t_a4c6c3ae` @ `3c20315` | 测试环境基座：JDK21/JDK25、Python、项目 `.venv`、MC 实例目录/端口分配表、脚本与命令模板、冒烟结果 |
| `01-vanilla.md` | `t_ac457fe1` | `wt/t_ac457fe1` @ `d387de5`、`bb9166e` | 原版 15 个正式版 × 17 条用例 + 常驻真链路，失败项 F-V1 / F-V2 |
| `02-fabric.md` | `t_5bccfcd8` | `wt/t_5bccfcd8` @ `c8ef7bc` | Fabric 9 个版本 + loader 0.20.0 变体，失败项 F-1 |
| `03-forge.md` | `t_157ba7fe` | `wt/t_157ba7fe` @ `5f25918` | Forge 12 个版本 + D1–D4 补充观察，失败项 F1 / F2 |
| `04-neoforge.md` | `t_efe57773` | `wt/t_efe57773` @ `ee94d57` | NeoForge 9 个版本（T0–T9），核心发现 §5.1 |

**这五份文件是上述分支里同名文件的逐字副本**（sha256 与分支版本一致，随 `BUGS.md` 一起提交，
好让 `BUGS.md` 引用的 §/F 编号在同一棵树里就能查到）：

| 文件 | sha256（前 16 位） |
|---|---|
| `00-env.md` | `a0944ea9edb10bf7` |
| `01-vanilla.md` | `924a66c6d5d84a46` |
| `02-fabric.md` | `994a59fb67441a4a` |
| `03-forge.md` | `944f61bb1fea87ba` |
| `04-neoforge.md` | `7b687b9be07386af` |

> 注意：这批文件里 `§7-10`、`§4 F-1`、`§5.1` 之类的编号是**各自文件内部**的小节号；
> `BUGS.md` 里引用时都写了「文件 + 小节」，例如 `04-neoforge.md §5.1`。

## 原始制品在哪里

真正的原始输出（服务端 `latest.log`、控制台输出、机器人 `run` 输出、`simulate` 结果、安装日志、
逐版本 `results-*.txt`、复现脚本等）**体量大，没有随本目录提交**，位置：

- 各自卡的分支：`test-notes/artifacts/vanilla|fabric|forge|neoforge/**`
  （`wt/t_ac457fe1` 113 个、`wt/t_5bccfcd8` 163 个、`wt/t_157ba7fe` 297 个、`wt/t_efe57773` 193 个文件）；
- 测试机 `hermes@10.1.1.4`：
  `~/Y33-Bot/test-notes/artifacts/`、实例目录 `~/mc-test/<族>/<版本>/`、
  脚本 `~/mc-test/*.sh`（`new-vanilla.sh` / `new-fabric.sh` / `new-forge.sh` / `nf_*.sh` / `*matrix*.sh`）。

`BUGS.md` 的每条证据都给到「文件 + 小节」或「制品相对路径 + 真行原文」，因此即使不搬制品也能核对。
