# AGENTS.md

本文件是 Y33-Bot 仓库的智能体入口：先说清仓库是什么、哪些文件不能动、命令怎么跑，
末尾维护一份「开发进度」。所有内容都来自仓库里可核对的文件与实跑结果，不是模板。

- 仓库内容：`y33bot` 0.1.0 —— Minecraft Java 版（Vanilla）与 QQ 群双向消息互通的独立 Python 服务端进程，
  与 MC 通信靠 RCON 注入（发）+ `latest.log` 监听（收），不依赖任何插件或 Mod 平台。
- 关键边界：本仓库只有这个 Python 服务端进程；它不改 MC 服务端本体，也不是 MC 插件 / Mod。
- 分流约定：`/` 开头走指令系统，`#` 开头走聊天转发，两者互不干扰（见 `IDEA.md` §3.1）。

## 开发进度

按最新在前记录。每条包含三部分：日期（YYYY-MM-DD）、已完成、进行中、已知阻塞/待办。

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
