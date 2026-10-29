# AGENTS.md

本文件是 Y33-Bot 仓库的智能体入口：先说清仓库是什么、哪些文件不能动、命令怎么跑。
**开发进度不在这里** —— 进度台账在 [`docs/progress.md`](docs/progress.md)（2026-10-28 迁出，原因见该文件抬头）。
本文件只写**稳定内容**：仓库边界、目录职责、工作规则、常用命令。所有内容都来自仓库里可核对的文件与实跑结果，不是模板。

- 仓库内容：`y33bot` 0.1.0 —— Minecraft Java 版（Vanilla）与 QQ 群双向消息互通的独立 Python 服务端进程，
  与 MC 通信靠 RCON 注入（发）+ `latest.log` 监听（收），不依赖任何插件或 Mod 平台。
- 关键边界：本仓库只有这个 Python 服务端进程；它不改 MC 服务端本体，也不是 MC 插件 / Mod。
- 分流约定：`/` 开头走指令系统，`#` 开头走聊天转发，两者互不干扰（见 `IDEA.md` §3.1）。

## 开发进度

**不要在本文件写进度。** 进度、时间线、用例数/覆盖率快照一律写 [`docs/progress.md`](docs/progress.md)：

- 该文件**最新在前**，每条含「日期 / 已完成 / 进行中 / 阻塞待办」，看板卡与 worker 直接追加即可；
- 本文件是**受保护的智能体指令文件**（写入需要人工交互批准），无人值守的看板卡写不进来 ——
  这正是进度迁出的原因：上一轮实机测试矩阵（2026-10-18）的进度就因为这条限制而漏记；
- 只有**仓库结构、工作规则、常用命令**这三类内容变化时才改本文件。

## 仓库结构与职责

| 路径 | 职责 |
|---|---|
| `src/y33bot/` | 服务端源码包，入口 `python -m y33bot`；子包 `rcon/`、`mclog/`、`qq/`、`commands/` |
| `tests/` | pytest 用例（`tests/e2e/` 为子进程级端到端），全程离线，不需要 MC 或 QQ |
| `docs/acceptance.md` | 端到端验收记录：每条含命令 / 实际输出 / 结论 |
| `docs/smoke.md` | 手工自测手册（S1–S4、S6 的真机输出） |
| `docs/progress.md` | **开发进度台账**（最新在前：已完成 / 进行中 / 阻塞待办 + 当前数字基线）；看板卡直接写这里 |
| `BUGS.md` | 缺陷与疑似缺陷记录（汇总表 / 逐条根因 / 证据来源 / 根卡复核记录） |
| `test-notes/` | 实机测试矩阵的逐版本记录（`00-env` ~ `04-neoforge`）与原始制品 |
| `scripts/dev_setup.sh` | 一键建 `.venv` + 装依赖 + 由模板生成 `config.toml`（已存在则不覆盖） |
| `Makefile` | 开发入口：`setup`/`run`/`check`/`smoke`/`lint`/`fmt`/`test`/`coverage`/`clean` |
| `config.example.toml` | 配置模板（入库）；`config.toml` 是本地副本（不入库） |
| `.github/workflows/ci.yml` | CI：装依赖 → 无密钥扫描 → lint/format → 入口冒烟 → `make test` 带覆盖率门槛 |
| `IDEA.md`、`需求1.txt`、`PLAN.md` | 冻结文档：需求书、原始需求、实施计划 |

## 工作规则（智能体必读）

- **记进度改 `docs/progress.md`，不要改本文件** —— 本文件写入需交互批准，无人值守的看板卡会被拒绝，也不许绕过。
- 不要改 `PLAN.md` §3.3 冻结的接口签名 —— 实现可以改，签名不得改（PLAN.md 也只为计划类任务而改）。
- 不要改 `IDEA.md`、`需求1.txt`：它们是需求依据，改动会让验收失去参照。
- 不入库清单（`.gitignore` 已覆盖，别用 `git add -f` 绕过）：`.worktrees/`、`.venv/`、`data/`、
  `config.toml`、`.env`、`*.log`。看板每张卡在自己的 `.worktrees/<task-id>/` 里干活。
- 密钥只走环境变量：`QQ_BOT_APP_ID`、`QQ_BOT_APP_SECRET`、`MC_RCON_PASSWORD_<服名大写>`；
  仓库里只能出现占位符，CI 会用 grep 扫源码与 CI 配置。
- 测试必须离线且不假绿：真 RCON 用内存假服务端、QQ 用假网关、日志用临时文件；
  不用 `pytest.skip` / `xfail` 掩盖用例，需要真机的场景写进文档，而不是写成会绿的测试。
- 改完代码要跑 `make test`；用例数或覆盖率变了就同步更新 `README.md` §14 与 `docs/acceptance.md`，
  并回填 `docs/progress.md` 顶部的「当前基线」表，避免文档与实测脱节。
- **多批修复抢同一个「追加点」时用 stack PR**（后一批的分支 base 指向前一批，PR 的 base 同理）。
  本仓每批修复都会往同一批文档的同一位置追加：`docs/acceptance.md` 的 `## N.`、`PLAN.md` 的 `### 7.x`、
  `README.md` §13 的下一条，以及四处数字基线（`README.md` §14 / `docs/smoke.md` §7 / `docs/acceptance.md`
  §1+§3 / `docs/progress.md` 基线表）。三批各从 main 切实测撞号 3 次（2026-10-29），每次都要重排编号、
  改交叉引用、重填四处数字。**不共享追加点时不要 stack**：各写各的目录（如 `test-notes/<族>/`）时并行合并
  0 冲突（2026-10-18 六卡实证），串成链只会强制造串行合并与 review 顺序耦合。
- 结论落文件：口头结论不算交付，写进 `README.md` / `docs/*.md` / `BUGS.md` / `docs/progress.md` 才算。

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
