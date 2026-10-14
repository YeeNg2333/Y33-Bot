# AGENTS.md

本文件是 Y33-Bot 仓库的智能体入口：先说清仓库是什么、哪些文件不能动、命令怎么跑，
末尾维护一份「开发进度」。所有内容都来自仓库里可核对的文件与实跑结果，不是模板。

- 仓库内容：`y33bot` 0.1.0 —— Minecraft Java 版（Vanilla）与 QQ 群双向消息互通的独立 Python 服务端进程，
  与 MC 通信靠 RCON 注入（发）+ `latest.log` 监听（收），不依赖任何插件或 Mod 平台。
- 关键边界：本仓库只有这个 Python 服务端进程；它不改 MC 服务端本体，也不是 MC 插件 / Mod。
- 分流约定：`/` 开头走指令系统，`#` 开头走聊天转发，两者互不干扰（见 `IDEA.md` §3.1）。

## 开发进度

按最新在前记录。每条包含三部分：日期（YYYY-MM-DD）、已完成、进行中、已知阻塞/待办。

### 2026-10-15（BUG-001 调查：QQ 网关静默失效）

- 已完成：登记并调查 **BUG-001**（用户真机观察：QQ 凭据/token 过期后群里无反应、进程还活着、日志没提示）。
  载体是仓库新增的 **`BUGS.md`**（含记录规则 / 索引 / 逐条模板 / 结论落在「回复」小节）：
  - 假设 H1 已由调查卡 `t_6cc56405` **离线复现并升级为结论：真缺陷**。链条：
    `ret_coro=True`（`PLAN.md:145` 的既有装配决定）让 SDK 自带的重连驱动
    `while not self._closed: multi_run(...)`（`botpy/client.py:217-223`）**不执行** → 会话被
    `on_closed` 回填后无人启动（`botpy/connection.py:57-67`）→ 网关协程**正常返回**（无异常 ⇒ 无日志，
    `src/y33bot/qq/gateway.py:132-138`）→ `Service.run()` 只等停止信号（`src/y33bot/service.py:215`）
    → 进程常驻、群里永久无反应、日志干净。
  - 5 个取证用例（`tests/test_bug001_reconnect.py` 新增 2 例 + `test_gateway.py` 2 例 + `test_service.py` 1 例）钉死上述行为；
    另实测 `check` 的 `[QQ] OK` 在**凭据完全无效时照样通过**（RCON 项真连 `/list`、QQ 项只查变量非空）。
  - **未执行**：真机触发链路（Q1 静默时的日志尾部、Q3 QQ 侧关码）——本机无真实 QQ 凭据与真 MC 服，
    已在 `BUGS.md` 如实标注，未编造替代输出。
- 已完成：卡分支 `y33-bot/t_6cc56405-bug-001-qq-token`（`ecf71b2`）合入 main（merge `e5b0782`）；
  复核确认 `src/` 一行未改。合并后 CI 同款实跑：**357 passed、覆盖率 99.30%、ruff 41 文件合规**。
- 已完成：用例数变化的文档同步 —— `README.md` §14、`docs/smoke.md` §7、`docs/acceptance.md` §1/§3
  与新增 §8.6（352 → 357，历史记录按原样保留并标注）。
- 已完成：口径已由用户拍板 —— **网关任务结束即视为故障：打 `[错误]` 并立即以非 0 退出**，交给
  `systemd`/`nssm` 拉起（不做退避重启）；另建议把 `check` 的 QQ 项改为真实探活。
- 进行中：修复要**另开卡**（R2-lite + R5），并走 `PLAN.md` §7 的变更登记；落地后先真机复现一次再验修复。
- 阻塞 / 待办：BUG-001 的真机触发链路（Q1/Q3）仍未验证；S5 真机 8 步仍未执行。

### 2026-10-13（v0.2：真机试跑反馈三条）

- 已完成：按 `需求1.txt` 第 53–55 行的三条真机反馈改造，并在 `PLAN.md` §7 登记为 **V1–V3**（含对
  IDEA §3.3/§3.8 的偏离说明；`IDEA.md`、`需求1.txt` 按规则未改动）。
  - **V1** MC→QQ 文案带来源服名（`[[mc_servers]].name`，不加 `【】`）：进出 `Steve进入了main` /
    `Steve退出了main`，游戏内 `#` 转发 `Steve@main: 你好`。
  - **V2** 取消游戏内 `[→QQ]` 回显：`#` 聊天只在群里出现一行，游戏内不再被注入（玩家自己那行已可见）；
    `ignored_chat_prefixes` 样板随之收窄为 `["[QQ]"]`。
  - **V3** 新增 `y33bot commands` 子命令，打印 QQ 管理端「指令配置」要填的「指令名 + 指令介绍」；
    `README.md` 新增 §5.3 记录平台事实（**管理端手工配置、无注册 API**，指令名 ≤8 中文字符/16 英文字符、
    介绍 ≤15/30、上限 24 条、无需单独提审）。`/list`（群内列举指令）明确**不做**。
- 已完成：本次实跑 —— `pytest -q` **352 passed**；`pytest -q --cov=y33bot --cov-fail-under=70`
  通过、总覆盖 **99.30%**；`ruff check .` 全过、`ruff format --check .` 40 文件合规；`tests/` 无 skip/xfail。
- 已完成：文档同步 —— `PLAN.md`（A4/A8/N13/R10/R11/R28、§3.4 CLI 契约加 `commands`、§3.5/§4.1 配置默认值、
  S3–S6 期望值、新增 §7 变更记录）、`README.md`（§2 功能表、§5.1/§5.3、§6 示例、§8 速查、§13 FAQ13、§14 实测数字）、
  `docs/smoke.md`（S2/S3/S4/S5/S6 片段、例数与覆盖度）、`docs/acceptance.md`（§0/§1、§2.3/§2.4 重跑更新、
  §7 标注为「变更前记录」、新增 §8 v0.2 复验）。
- 已完成：依赖装在仓库 `.venv`（不入库，靠 `requirements*.txt` 复现；pypi 直连超时，本次改用清华镜像
  安装，依赖版本声明未改）。
- 进行中：无。
- 阻塞 / 待办：**S5 真机 8 步仍未执行**（本机无真实 QQ 凭据、无 `enable-rcon=true` 的真 MC 服），
  结论维持「部分通过」（`docs/acceptance.md` §8.5）。待办：上线前按 `docs/smoke.md` 在真机跑一遍手工自测。
- 待办：`IDEA.md` §5「后期规划（不预留，仅记录）」4 项未实施（投票重启、插件式通信、热重载、自定义触发字符）——
  属明确不做，不要顺手扩大范围。

### 2026-10-13

- 已完成：PLAN.md §6 的 T1–T12 全部落地（骨架与依赖、配置与模型、持久化、RCON、日志、指令、
  业务桥与 QQ 适配、服务与 CLI、单元测试、端到端验收、README 与发布、T12 汇总复验）。
- 已完成：看板上 6 张前置卡（`t_8442a7d5`/`t_68925b93`/`t_7b86eb6b`/`t_bcf892eb`/`t_19583dfd`/
  `t_c3a76c90`）均为 done，本卡 `t_3367baf6` 是最后一张。
- 已完成：本次在 `f38b233` 上实跑 `pytest -q --cov=y33bot --cov-fail-under=70` ——
  **348 passed、总覆盖率 99.30%**（门槛 70%），`ruff check .` 全过、`ruff format --check .` 40 文件合规，
  `tests/` 无 skip/xfail。
- 已完成：验收场景 S1（环境与配置自检）、S2（QQ→MC 绑定与转发）、S3（MC→QQ 转发与回环防护）、
  S4（进出通知与健康翻转）、S6（日志轮转）**通过**；逐条证据见 `docs/acceptance.md`。
- 已完成：`v0.1.0` 已打 annotated tag（指向 `f0ddd4e`）；`README.md`、`docs/smoke.md`、
  `docs/acceptance.md` 齐备，文档里的命令与输出都是实测粘贴。
- 已完成：`origin/main` HEAD 已推进到 `f38b233`；据 `docs/acceptance.md` §7.9，`3c27803` 及其后续
  文档提交的 CI 均为 success（本地无 `gh`，CI 结论以该记录为准，本次未独立复核）。
- 进行中：把上述进度写入仓库根目录 `AGENTS.md`（即本次改动），并提交为
  `docs: update development progress in AGENTS.md`。
- 阻塞 / 待办：**S5 真实端到端（真 QQ 群 + 真 MC 服）的 8 步未执行、不作通过声明** ——
  本机没有真实 QQ 机器人凭据，也没有 `enable-rcon=true` 的真 MC 服；步骤与判据留在 `PLAN.md` §5，
  具备环境后回填 `docs/acceptance.md` §2.5。
- 待办：上线前按 `docs/smoke.md` 在真机跑一遍手工自测（含常驻运行 S5 的离线可复现部分）。
- 待办：`IDEA.md` §5「后期规划（不预留，仅记录）」4 项未实施：投票重启服务器、插件式通信、
  热重载配置、自定义触发字符 —— 属于明确不做，不要顺手扩大范围。

## 仓库结构与职责

| 路径 | 职责 |
|---|---|
| `src/y33bot/` | 服务端源码包，入口 `python -m y33bot`；子包 `rcon/`、`mclog/`、`qq/`、`commands/` |
| `tests/` | pytest 用例（`tests/e2e/` 为子进程级端到端），全程离线，不需要 MC 或 QQ |
| `docs/acceptance.md` | 端到端验收记录：每条含命令 / 实际输出 / 结论 |
| `docs/smoke.md` | 手工自测手册（S1–S4、S6 的真机输出） |
| `scripts/dev_setup.sh` | 一键建 `.venv` + 装依赖 + 由模板生成 `config.toml`（已存在则不覆盖） |
| `Makefile` | 开发入口：`setup`/`run`/`check`/`smoke`/`lint`/`fmt`/`test`/`coverage`/`clean` |
| `config.example.toml` | 配置模板（入库）；`config.toml` 是本地副本（不入库） |
| `.github/workflows/ci.yml` | CI：装依赖 → 无密钥扫描 → lint/format → 入口冒烟 → `make test` 带覆盖率门槛 |
| `IDEA.md`、`需求1.txt`、`PLAN.md` | 冻结文档：需求书、原始需求、实施计划 |

## 工作规则（智能体必读）

- 不要改 `PLAN.md` §3.3 冻结的接口签名 —— 实现可以改，签名不得改（PLAN.md 也只为计划类任务而改）。
- 不要改 `IDEA.md`、`需求1.txt`：它们是需求依据，改动会让验收失去参照。
- 不入库清单（`.gitignore` 已覆盖，别用 `git add -f` 绕过）：`.worktrees/`、`.venv/`、`data/`、
  `config.toml`、`.env`、`*.log`。看板每张卡在自己的 `.worktrees/<task-id>/` 里干活。
- 密钥只走环境变量：`QQ_BOT_APP_ID`、`QQ_BOT_APP_SECRET`、`MC_RCON_PASSWORD_<服名大写>`；
  仓库里只能出现占位符，CI 会用 grep 扫源码与 CI 配置。
- 测试必须离线且不假绿：真 RCON 用内存假服务端、QQ 用假网关、日志用临时文件；
  不用 `pytest.skip` / `xfail` 掩盖用例，需要真机的场景写进文档，而不是写成会绿的测试。
- 改完代码要跑 `make test`；用例数或覆盖率变了就同步更新 `README.md` §14 与 `docs/acceptance.md`，
  避免文档与实测脱节。
- 结论落文件：口头结论不算交付，写进 `README.md` / `docs/*.md` / 本文件才算。

## 常用命令

```bash
make setup                 # 建 .venv + 装依赖 + 生成 config.toml（= bash scripts/dev_setup.sh）
make check                 # 启动自检（配置 / QQ / RCON 健康状态）
make test                  # pytest；CI 同款：make test PYTEST_ARGS="-q --cov=y33bot --cov-fail-under=70"
make lint                  # ruff check + ruff format --check
```

- 没装 make（或嫌 Windows 控制台的怪行为）时直接调解释器：
  `.venv/Scripts/python.exe -m pytest -q`（Linux/macOS 为 `.venv/bin/python`）。
- Windows 控制台看 `make help` 的中文乱码时先跑 `chcp 65001`；这是控制台行为，不是缺陷。
- 解释器版本：`requires-python = ">=3.11,<3.14"`，开发与 CI 固定在 3.12（本机实测 Python 3.12.10）。
- 不连外部服务的冒烟：`python -m y33bot --version`；离线走一遍全链路：`python -m y33bot simulate --config config.toml`。
