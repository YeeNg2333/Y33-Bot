# 端到端验收记录（acceptance）

本文件是任务卡 **T10（`t_7b86eb6b`：补齐自动化测试并完成端到端验收）** 的产出，逐条对应
`PLAN.md` §5 的验收场景。下面每条都给出**命令 + 真实输出 + 结论**，输出是实际执行后粘贴的，
不是手写预期值。手工自测手册（含每个模块的自测点）见 `docs/smoke.md`。

---

## 0. 执行环境与前置

| 项 | 值 |
|---|---|
| 日期 | 2026-10-13 |
| 机器 | Y33NG-LAPTOP（Windows 11 + git-bash／MSYS），Python 3.12.10（仓库内 `.venv`） |
| 代码版本 | `29bc742`（= main，T8 完成点）+ 本卡改动 |
| 验收目录 | 仓库**之外**的临时目录（`…/cache/scratch/y33bot-acc2`），避免污染工作树 |
| 配置 | `config.example.toml` 复制为 `config.toml` 后只改 4 处：`group_openid = "SIM-GROUP-OPENID"`、`port = 34567`（故意指向不可达端口，用来看 RCON FAIL 分支）、`log_path = "logs/latest.log"`、`connect/command_timeout = 1.0` |
| 环境变量 | `QQ_BOT_APP_ID`／`QQ_BOT_APP_SECRET`／`MC_RCON_PASSWORD_MAIN` 都是 `SIM-*` 假值：只用于自检分支与 `--dry-run`，**全程不连真 QQ、不连真 MC** |
| 通用命令 | 下文 `$BP` = `<repo>/.venv/Scripts/python.exe`（Linux 换成 `.venv/bin/python`） |

验收目录里的实际命令与完整输出留档在：`…/cache/scratch/y33bot-acc2/transcript.txt`（153 行）。

---

## 1. 结论总表

| 场景 | 结论 | 位置 |
|---|---|---|
| S1 环境与配置自检 | **通过**（FAIL 分支与缺密钥分支均符合契约） | §2.1 |
| S2 QQ→MC 绑定与转发 | **通过** | §2.2 |
| S3 MC→QQ 聊天转发与回环防护 | **通过** | §2.3 |
| S4 进出通知与健康翻转（只提示一次） | **通过** | §2.4 |
| S5 真实端到端（真 QQ 群 + 真 MC 服） | **部分通过**：离线可复现片段（缺凭据快速失败）**通过**；真机 8 步**未执行**——本机没有可用的 QQ 机器人凭据与 MC 服（前置缺失，见 §6） | §2.5 |
| S6 日志轮转 | **通过**（离线等价复现：`LogWatcher` 直接跑同一路径；真机手工版见 `docs/smoke.md` §5） | §2.6 |

自动化方面（§3）：`make test` 一键 **348 passed、总覆盖率 99.30%**（门槛 70%），`ruff check` +
`ruff format --check` 全绿，全仓**无 skip/xfail**，CI 里跑的就是同一条 `make test`。

---

## 2. 逐条场景记录

### 2.1 S1 环境与配置自检

```bash
$ $BP -m y33bot --version
y33bot 0.1.0
exit=0

$ $BP -m y33bot check --config config.toml
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON main] FAIL 无法连接 127.0.0.1:34567: 连接 127.0.0.1:34567 超时（1.0s）
[日志 main] OK C:\Users\Lenovo\AppData\Local\hermes\cache\scratch\y33bot-acc2\logs\latest.log 可读，偏移 0 字节
[绑定] OK 0 条
FAIL
exit=1

$ env -u QQ_BOT_APP_SECRET $BP -m y33bot check --config config.toml     # 缺 secret 分支
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] FAIL 环境变量 QQ_BOT_APP_SECRET 未设置
[RCON main] FAIL 无法连接 127.0.0.1:34567: 连接 127.0.0.1:34567 超时（1.0s）
[日志 main] OK …\logs\latest.log 可读，偏移 0 字节
[绑定] OK 0 条
FAIL
exit=1
```

**结论：通过。** 逐项 `OK|FAIL` + 末行 `OK|FAIL` + 退出码 0/1 与 `PLAN.md` §3.4 一致；把 RCON
指向可达端口/真服后 `[RCON main]` 会变 `OK /list -> …`（`tests/test_smoke.py::test_check_passes_with_reachable_rcon`
用内存假 RCON 服验证了这一分支）。

**平台差异（不是缺陷）**：Windows 上连不可达的本地端口表现为 **1s 超时**，Linux 上通常是
`Connection refused`；两者都落在 `[RCON main] FAIL 无法连接 <host>:<port>: …` 同一契约下。
`check` 的明细日志走 stderr（§3.6），stdout 只有上面 6 行契约文本。

自动化等价物：`tests/e2e/test_entrypoint.py::test_entrypoint_s1_check_reports_each_item`（真子进程）、
`…::test_entrypoint_s1_check_missing_secret`、`…::test_entrypoint_check_missing_config`、
`tests/test_cli.py::test_check_*`。

### 2.2 S2 QQ→MC 绑定与转发

```bash
$ $BP -m y33bot bind set 1A2B3C4D Steve --config config.toml
[绑定] 已写入 1A2B3C4D -> Steve (data/bindings.toml)
exit=0

$ $BP -m y33bot bind list --config config.toml
[绑定] 1A2B3C4D -> Steve
exit=0

$ $BP -m y33bot simulate group-message --openid 1A2B3C4D --content '#你好
世界' --dry-run --config config.toml
[RCON main] tellraw @a {"text":"[QQ] Steve: 你好"}
exit=0

$ $BP -m y33bot simulate group-message --openid UNKNOWN --content '#hi' --dry-run --config config.toml
[群消息] 请先使用 /bind <游戏ID> 绑定
exit=0

$ $BP -m y33bot simulate group-message --openid UNKNOWN --content '普通消息' --dry-run --config config.toml
[忽略] 非触发前缀
exit=0

$ $BP -m y33bot simulate group-message --openid UNKNOWN --content '/bind' --dry-run --config config.toml
[群消息] 用法: /bind <游戏ID>
exit=0

$ $BP -m y33bot simulate group-message --openid UNKNOWN --content '/unknowncmd' --dry-run --config config.toml
[群消息] 未知指令
exit=0

$ $BP -m y33bot simulate group-message --openid UNKNOWN --content '/status' --dry-run --config config.toml
[RCON main] /list
[群消息] [服务器状态]
[群消息] 在线: 0/20
[群消息] 玩家: 无
exit=0
```

**结论：通过。** 换行输入按 A7 只转发第一行（`世界` 被丢弃）；未绑定用户只回绑定提示且
**没有** `[RCON …]` 行；非触发前缀与缺参数/未知指令的文案逐字符一致。

自动化等价物：`tests/e2e/test_entrypoint.py::test_entrypoint_s2_bind_then_forward`、
`…::test_entrypoint_s2_hints_and_unknown_command`、`tests/e2e/test_acceptance.py::test_s2_*`。

### 2.3 S3 MC→QQ 聊天转发与回环防护

```bash
$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好' --dry-run --config config.toml
[群消息] Steve: 大家好
[RCON main] tellraw @a {"text":"[→QQ] Steve: 大家好"}
exit=0

$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:02] [Async Chat Thread - #0/INFO]: <Steve> 普通聊天' --dry-run --config config.toml
[忽略] 聊天非 # 开头，不转发
exit=0

$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:03] [Async Chat Thread - #0/INFO]: <Steve> [→QQ] Steve: 大家好' --dry-run --config config.toml
[忽略] 回环防护：命中 ignored_chat_prefixes
exit=0
```

**结论：通过。** 群消息与游戏内回显各一次，回环前缀被拦下，非 `#` 聊天不转发。

自动化等价物：`tests/e2e/test_entrypoint.py::test_entrypoint_s3_s4_events_and_health_flip`、
`tests/e2e/test_acceptance.py::test_s3_chat_forward_and_loop_guard`。

### 2.4 S4 进出通知与健康翻转（只提示一次）

```bash
$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:04] [Server thread/INFO]: Steve joined the game' --dry-run --config config.toml
[群消息] Steve进入游戏
exit=0

$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:05] [Server thread/INFO]: Steve left the game' --dry-run --config config.toml
[群消息] Steve退出游戏
exit=0

$ $BP -m y33bot simulate log-event --server main --kind join --player Steve --config config.toml
[群消息] Steve进入游戏
exit=0

$ $BP -m y33bot simulate health --server main --offline --dry-run --config config.toml      # 第 1 次
[RCON main] /list
[警告] RCON main 命令失败: 假 RCON 服务器离线: 127.0.0.1:34567
[群消息] [服务器状态] main 离线
exit=0

$ $BP -m y33bot simulate health --server main --offline --dry-run --config config.toml      # 第 2 次
[RCON main] /list
[警告] RCON main 命令失败: 假 RCON 服务器离线: 127.0.0.1:34567
[忽略] 状态未变化，不重复提示
exit=0

$ $BP -m y33bot simulate health --server main --online --dry-run --config config.toml
[RCON main] /list
[群消息] [服务器状态] main 上线
exit=0

$ cat data/state.json
{
  "version": 1,
  "qq": { "msg_seq": 0 },
  "servers": {
    "main": {
      "log_offset": 0,
      "log_size": 0,
      "log_inode": "",
      "health_online": true,
      "health_changed_at": 1791828365.4286687
    }
  }
}
```

**结论：通过。** 离线只提示一次（第二次 `[忽略] 状态未变化，不重复提示`），恢复后提示一次上线；
翻转状态落在 `data/state.json` 的 `health_online`。`simulate health` 会真跑一次健康探测，所以
多出 `[RCON main] /list` 与离线时的 `[警告]` —— 契约要求回显实际执行的命令（`docs/smoke.md` §8）。

自动化等价物：`tests/e2e/test_entrypoint.py::test_entrypoint_s3_s4_events_and_health_flip`、
`tests/e2e/test_acceptance.py::test_s4_join_quit_and_health_once`。

### 2.5 S5 真实端到端（真 QQ 群 + 真 MC 服）

**未执行**：本机没有可用的 QQ 机器人凭据（`QQ_BOT_APP_ID/SECRET` 需要真实开放平台应用）与
可连的 MC 服（需要 `enable-rcon=true` 的真实服务端），因此 S5 的 8 步真机流程无法在此环境复现，
不能声称通过。真机步骤与判据保留在 `PLAN.md` §5 S5 与 `docs/smoke.md` §6，等具备真实环境时按
原文执行并回填本节。

在线下可复现的那一段（缺凭据快速失败，不产生任何网络副作用）**通过**：

```bash
$ env -u QQ_BOT_APP_ID -u QQ_BOT_APP_SECRET $BP -m y33bot run --config config.toml
[启动] y33bot 0.1.0（1 个 MC 服）
[警告] RCON main 连接失败（服务继续，下次调用自动重连）: 连接 127.0.0.1:34567 超时（1.0s）
[启动] 日志监听已启动: main
[错误] 环境变量 QQ_BOT_APP_ID 未设置
exit=1
```

**结论：部分通过**——单服连不上只告警不阻塞启动（§3.6）、缺凭据时以退出码 1 快速失败，两条
行为都符合契约；S5-1…S5-8 的真机现象未验证。

自动化覆盖到的 S5 相邻行为：
`tests/e2e/test_entrypoint.py::test_entrypoint_run_fails_fast_without_credentials`（真子进程 + 退出码）、
`tests/test_service.py::test_run_polls_log_pushes_and_persists_offset`（假网关＋假 RCON 跑常驻逻辑：
追加日志 → 群内收到通知 → 退出后 `log_offset` 等于文件大小，即 S5-7「重启不重复推送」）、
`tests/test_failures.py::test_service_run_builds_gateway_from_credentials`（凭据齐全时用它们构造真网关的装配路径）。

### 2.6 S6 日志轮转

离线等价复现（`LogWatcher` 直接跑 S6 的同一条路径：先读到偏移非 0 → 文件被清空/重命名 →
偏移重置为 0 → 新写入的进服日志被解析并推送）：

```bash
$ $BP -m pytest tests/test_mclog_watcher.py::test_rotation_resets_offset tests/e2e/test_acceptance.py::test_s6_log_rotation -q
..                                                                       [100%]
2 passed in 0.72s
```

**结论：通过。** 用例断言了 `[警告] 日志文件缩小（size=… < offset=…），偏移重置为 0`、新行被解析为
`join` 事件、以及 `log_offset` 被推进到新文件大小；真机手工版（先 `run`、再 `: > latest.log`、
再写一行）在 `docs/smoke.md` §5。

补充：本轮还补了 **inode 变化** 这条轮转路径（文件被重命名/替换但体积没变小），
见 `tests/test_failures.py::test_watcher_inode_change_triggers_rotation`。

---

## 3. 自动化测试、覆盖率与静态检查

一键入口（本地与 CI 同一条命令）：

```bash
$ mingw32-make test PYTEST_ARGS="-q --cov=y33bot --cov-report=term-missing --cov-fail-under=70"
.venv/Scripts/python.exe -m pytest -q --cov=y33bot --cov-report=term-missing --cov-fail-under=70
........................................................................ [ 20%]
…（略）
348 passed in 42.74s
Required test coverage of 70% reached. Total coverage: 99.30%
exit=0
```

逐模块覆盖率（`term-missing` 实测，2026-10-13）：

| 模块 | 覆盖 | 模块 | 覆盖 |
|---|---|---|---|
| `binding` / `commands.*` / `config` / `mclog.*` / `models` / `rcon.fakes` / `rcon.pool` / `rcon.protocol` / `state` / `qq.fakes` / `__main__` | 100% | `bridge` | 99% |
| `rcon.client` | 99% | `cli` | 99% |
| `qq.gateway` | 98% | `service` | 98% |

`qq.gateway` 的 `33-34` 是「本机没装 `qq-botpy`」才会走到的 import 兜底分支（本机装了依赖，
所以走不到）；其余未覆盖行都是防御性分支（`132->exit`、`227->232` 等），核心函数行覆盖远高于
`PLAN.md` §6 T9 要求的 70%。

```bash
$ $BP -m ruff check src tests
All checks passed!
$ $BP -m ruff format --check src tests
40 files already formatted

$ grep -RInE '(QQ_BOT_APP_SECRET|MC_RCON_PASSWORD)[[:space:]]*=[[:space:]]*[^[:space:]]' \
      --include='*.py' --include='*.yml' --include='*.toml' src tests .github      # CI 同款命令
（无匹配）

$ grep -rnE "pytest\.(skip|xfail)|@pytest\.mark\.(skip|xfail)|skipif" tests/
（无 skip/xfail/skipif）
```

测试文件分工（348 例）：

| 文件 | 例数 | 说明 |
|---|---|---|
| `tests/test_boundaries.py` | 63 | **本卡新增**：config/binding/state/patterns/registry/网关文本 的边界与类型错误（空输入、越界、缺字段、损坏文件） |
| `tests/test_failures.py` | 61 | **本卡新增**：RCON 客户端/池、QQ 网关、常驻服务、CLI 的失败分支（畸形包、id 不匹配、半途断连、写盘/关闭失败、参数不合法） |
| `tests/e2e/test_entrypoint.py` | 10 | **本卡新增**：**真子进程**跑 `python -m y33bot …`，逐条断言 S1/S2/S3/S4 的 stdout 与退出码（含用法错误退出码 2） |
| `tests/e2e/test_acceptance.py` | 7 | T8 产出：同进程内按 §5 文案逐条断言（S1–S4、S6） |
| 其余 13 个逐模块文件 | 207 | T8 产出：常规路径 + 关键分支 |

设计取舍：新增的失败分支用例都断言**可观测结果**（异常类型与文案、日志、退出码、落盘文件），
不使用 `pytest.skip`/`xfail` 掩盖任何用例；需要外部资源（真 QQ/真 MC）的场景一律留在文档里，
不写成会假绿的测试。

---

## 4. CI 集成

`.github/workflows/ci.yml` 的测试步骤改成与本地完全相同的**一键命令**，一条命令同时打开
覆盖率门槛（不再另跑一遍 pytest）：

```yaml
- name: 测试（make test：pytest + 覆盖率门槛）
  # CI 走的就是开发者本地那一条一键命令：make test（PLAN.md §6 T9 / T10）
  run: make test PYTEST_ARGS="-q --cov=y33bot --cov-report=term-missing --cov-fail-under=70"
  env:
    PYTHONHASHSEED: "0"
```

`Makefile` 同步做了一处改动，让这条命令在干净环境里都能跑：`VENV_PY` 优先用仓库内 `.venv`，
没有 `.venv` 时（CI 直接用 `setup-python` 的解释器）回退到 `$(PY)`；`test` 目标支持 `PYTEST_ARGS`。
本地验证：

```bash
$ mingw32-make test VENV=no-such-venv PY="$(pwd)/.venv/Scripts/python.exe" PYTEST_ARGS="-q tests/test_boundaries.py"
…/.venv/Scripts/python.exe -m pytest -q tests/test_boundaries.py
60 passed in 1.09s
```

CI 运行结论（推送后实测，commit `f0e85db`）：

| 分支 | run | 结论 | 测试步骤 |
|---|---|---|---|
| `wt/t_7b86eb6b` | [#17](https://github.com/YeeNg2333/Y33-Bot/actions/runs/38291796691) | **success** | 第 9 步「测试（make test：pytest + 覆盖率门槛）」success；同 job 内 checkout／装 Python／装依赖／无密钥检查／Lint／Format check／Smoke 也全部 success |
| `main`（快进到同一 commit） | [#18](https://github.com/YeeNg2333/Y33-Bot/actions/runs/38291806391) | **success** | 同上 |

即 CI 上跑的确实是本卡改写的那一条一键命令 `make test PYTEST_ARGS="… --cov-fail-under=70"`，
所以 CI 绿 = 覆盖率门槛在 CI 上生效。逐 step 结论取自 GitHub Actions jobs API
（`/actions/runs/<id>/jobs`）；该 API 的**日志文本**下载需要鉴权（未登录请求返回 403），
因此这里只引用 step 级结论，CI 侧的具体数字（用例数/覆盖率）以本地同命令的输出为准（§3）。

---

## 5. 本轮发现的缺陷与修复

* **产品缺陷：0 条。** 逐条执行 S1–S6 未发现与 `PLAN.md` 契约不符的行为，因此本卡没有改动
  `src/y33bot/**`（改动集中在 `tests/`、`Makefile`、CI 与本文档）。
* 执行过程中出现的两次「失败」都是**我这边的验收脚本问题**，不是产品缺陷，记录以免误判：
  1. 把 S6 的两条 pytest 命令放在验收目录里跑（那里没有 `tests/`）→ `ERROR: file or directory not found`；
     改到仓库根目录执行即通过（§2.6）。
  2. 采集脚本用 `| head -120` 截断输出，导致 tee 收到 SIGPIPE、transcript 被截断；改成直接重定向到
     文件后完整留档。
* 补回的回归用例（原先完全没有用例覆盖的失败分支，逐条对应代码行）：
  `cli` 的 bind/simulate 遇到损坏绑定表与写盘失败、`simulate health` 未知服务器、`_display_path` 越出 CWD；
  `service` 的日志/健康轮询异常、关闭失败、信号处理器两种安装路径、缺凭据时关闭连接池；
  `rcon.client` 的畸形包长、鉴权 id 异常/超时/握手中断、响应 id 不匹配、半途断连、`_drop` 容错；
  `rcon.pool` 的重名/缺密码/不可解析 `/list`、`tellraw` 超长收缩；
  `mclog.watcher` 的 inode 轮转、读失败、空读、空行、残行缓冲；
  `binding`/`state`/`config` 的损坏文件、类型错误、缺字段、越界值。

---

## 6. 诚实边界（本机无法覆盖的部分）

| 项 | 原因 | 处理 |
|---|---|---|
| S5-1…S5-8 真机流程 | 无真实 QQ 机器人凭据、无真 MC 服（`enable-rcon=true`） | 文档保留步骤与判据，具备环境后回填 §2.5；离线可复现片段与常驻逻辑已由自动化用例覆盖 |
| `qq/gateway.py` 33-34（缺 `qq-botpy` 兜底） | 本机/CI 都装了 `qq-botpy==1.2.1`，该分支不可达 | 该分支的行为由 `tests/test_gateway.py::test_start_requires_botpy` 用 monkeypatch 强制覆盖 |
| `make help` 的中文在 Windows 控制台乱码 | mingw32-make 的输出不经 UTF-8 控制台 | 已在 `make help` 首行提示 `chcp 65001`（T1 既有约定，非本卡改动） |

---

## 7. T12 汇总复验（根卡 `t_c3a76c90`，2026-10-13）

本节的复验对象是**已发布的 `origin/main` = `3c27803`**（不是任何分支的工作树内容），并且复验
**从 `git archive origin/main` 导出的纯净树**开始，避免被本地 `.venv`/`config.toml`/`data/` 干扰。
与 §2 的差别：§2 用 `--dry-run` + 假端口（完全不发网络包），本节额外**真起了一个 RCON 服务端**，
逐条核对服务端实际收到的命令，用来证明"去掉 `--dry-run` 就是真的注入"。

### 7.1 复验环境

| 项 | 值 |
|---|---|
| 代码版本 | `origin/main` = `3c27803`（`git archive` 导出，无 `.git`、无 `.venv`、无 `data/`） |
| 解释器 | 全新 `python3 -m venv .venv`（Python 3.12.10），`pip install -r requirements-dev.txt -e .` |
| 真 RCON 服务端 | 自写 40 行 stdlib 服务端（Valve 二进制协议：`LOGIN(3)` 鉴权、`COMMAND(2)` 应答、逐条落盘收到的命令），监听 `127.0.0.1:25575` |
| 真日志文件 | `_verify/mcserver/logs/latest.log`（真文件，供 S6 做真截断） |
| 环境变量 | `QQ_BOT_APP_ID=102000001`／`QQ_BOT_APP_SECRET=fake-secret`（朝 QQ 方向永不联网）／`MC_RCON_PASSWORD_MAIN=s3cret` |

### 7.2 一键测试与静态检查（与 CI 同一条命令）

```bash
$ mingw32-make test PYTEST_ARGS="-q --cov=y33bot --cov-fail-under=70"
348 passed in 45.83s
Required test coverage of 70% reached. Total coverage: 99.30%

$ .venv/Scripts/python.exe -m ruff check .
All checks passed!
$ .venv/Scripts/python.exe -m ruff format --check .
40 files already formatted

$ grep -rnE "pytest\.(skip|xfail)|@pytest\.mark\.(skip|xfail)|skipif" tests/
（无 skip/xfail/skipif）
```

结论与 §3 一致：**348 例全过、总覆盖率 99.30%、静态检查全绿、无 skip/xfail**。

### 7.3 S1 环境与配置自检（两个分支都复验）

```bash
$ $BP -m y33bot check --config config.toml                      # RCON 可达（真服务端）
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON main] OK /list -> OK: /list
[日志 main] OK …\mcserver\logs\latest.log 可读，偏移 0 字节
[绑定] OK 0 条
OK
exit=0

$ $BP -m y33bot check --config config_unreachable.toml          # 不可达端口 34567，超时 1s
[配置] OK config_unreachable.toml 解析成功，1 个 MC 服
[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON main] FAIL 无法连接 127.0.0.1:34567: 连接 127.0.0.1:34567 超时（1.0s）
[日志 main] OK …\mcserver\logs\latest.log 可读，偏移 0 字节
[绑定] OK 1 条
FAIL
exit=1

$ env -u QQ_BOT_APP_SECRET $BP -m y33bot check --config config_unreachable.toml
[QQ] FAIL 环境变量 QQ_BOT_APP_SECRET 未设置
…
FAIL
exit=1
```

**结论：通过。** 与 §2.1 逐行一致（含 Windows 上"不可达端口 = 1s 超时"而非 `Connection refused` 的
平台差异）；`OK` 分支是本轮**真连 RCON** 得到的，不再是推断。

### 7.4 S2 QQ→MC（真注入 + 真换行输入）

```bash
$ $BP -m y33bot bind set 1A2B3C4D Steve
[绑定] 已写入 1A2B3C4D -> Steve (data/bindings.toml)
$ $BP -m y33bot bind list
[绑定] 1A2B3C4D -> Steve

$ $BP -m y33bot simulate group-message --openid 1A2B3C4D --content $'#你好\n世界'   # 真换行
[RCON main] tellraw @a {"text":"[QQ] Steve: 你好"}

$ $BP -m y33bot simulate group-message --openid 1A2B3C4D --content '/status'       # RCON 可达
[RCON main] /list
[群消息] [服务器状态]
[群消息] 在线: 1/20
[群消息] 玩家: Steve

$ $BP -m y33bot simulate group-message --openid UNKNOWN --content '#hi'
[群消息] 请先使用 /bind <游戏ID> 绑定
$ $BP -m y33bot simulate group-message --openid 1A2B3C4D --content '普通消息'
[忽略] 非触发前缀
$ $BP -m y33bot simulate group-message --openid 1A2B3C4D --content '/bind'
[群消息] 用法: /bind <游戏ID>
$ $BP -m y33bot simulate group-message --openid 1A2B3C4D --content '/unknowncmd'
[群消息] 未知指令
```

真 RCON 服务端**实际收到**的命令（`_verify/rcon_received.log`）：

```text
AUTH OK from ('127.0.0.1', 14773)
CMD tellraw @a {"text":"[QQ] Steve: 你好"}
AUTH OK from ('127.0.0.1', 14783)
CMD /list
AUTH OK from ('127.0.0.1', 3401)
CMD /list
```

**结论：通过（比 §2.2 更强）。** 三处增量：① 换行输入这次是**真换行**（`$'#你好\n世界'`），
输出仍是 `[QQ] Steve: 你好` —— A7「只转发第一行」在真输入下成立；② 注入不是打印，而是**服务端
真的收到了 `tellraw` 原样命令**；③ RCON 可达时 `/status` 渲染的是真实名单
（`在线: 1/20` / `玩家: Steve`），§2.2 因故意指向不可达端口只能验到 `0/20`、`玩家: 无` 分支。

### 7.5 S3 MC→QQ 聊天转发与回环防护

```bash
$ $BP -m y33bot simulate log-event --server main --line '[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好'
[群消息] Steve: 大家好
[RCON main] tellraw @a {"text":"[→QQ] Steve: 大家好"}
（服务端回执：CMD tellraw @a {"text":"[→QQ] Steve: 大家好"}）

$ $BP -m y33bot simulate log-event --server main --line '[12:00:02] [Async Chat Thread - #0/INFO]: <Steve> 普通聊天'
[忽略] 聊天非 # 开头，不转发

$ $BP -m y33bot simulate log-event --server main --line '[12:00:03] [Async Chat Thread - #0/INFO]: <Steve> [→QQ] Steve: 大家好'
[忽略] 回环防护：命中 ignored_chat_prefixes
```

**结论：通过**，与 §2.3 一致，且回显那一步有服务端回执佐证。

### 7.6 S4 进出通知与健康翻转

```bash
$ $BP -m y33bot simulate log-event --server main --line '[12:00:04] [Server thread/INFO]: Steve joined the game'
[群消息] Steve进入游戏
$ $BP -m y33bot simulate log-event --server main --line '[12:00:05] [Server thread/INFO]: Steve left the game'
[群消息] Steve退出游戏
$ $BP -m y33bot simulate log-event --server main --kind join --player Steve
[群消息] Steve进入游戏

$ $BP -m y33bot simulate health --server main --offline      # 第 1 次
[RCON main] /list
[警告] RCON main 命令失败: 假 RCON 服务器离线: 127.0.0.1:25575
[群消息] [服务器状态] main 离线
$ $BP -m y33bot simulate health --server main --offline      # 第 2 次
[忽略] 状态未变化，不重复提示

$ $BP -m y33bot simulate health --server main --online       # 真探测，第 1 次
[RCON main] /list
[群消息] [服务器状态] main 上线
$ $BP -m y33bot simulate health --server main --online       # 第 2 次
[忽略] 状态未变化，不重复提示
```

`data/state.json` 的 `health_online` 随翻转变化（本轮最后一次为 `true`，`health_changed_at` 同步刷新）。

**结论：通过**，与 §2.4 一致，并补验了线上行的"再来一次也是 `[忽略]`"。

### 7.7 S6 日志轮转（头一次用真文件、真截断复现）

§2.6 的复现走的是 pytest 用例；本轮额外用**生产代码 `LogWatcher` + `StateStore` 直接跑一个真文件**
（`_verify/s6_rotation_real.py`，无 mock：真目录、真 `latest.log`、用 `"w"` 模式真截断）：

```text
--- poll#1 初始文件: events=[('join', 'Steve')] offset=56 size=56
--- poll#2 追加一行: events=[('chat', 'Steve')] offset=118 size=118
WARNING [警告] 日志文件缩小（size=55 < offset=118），偏移重置为 0
--- poll#3 清空+新写（轮转）: events=[('join', 'Alex')] offset=55 size=55

PASS poll#1 解析 join/Steve
PASS poll#2 解析 chat/Steve
PASS poll#3 轮转后解析新行 join/Alex
PASS poll#3 偏移重置并推进到新文件大小
S6_REAL_RESULT=PASS
```

同时复跑 §2.6 引用的两个用例：

```bash
$ $BP -m pytest tests/test_mclog_watcher.py::test_rotation_resets_offset tests/e2e/test_acceptance.py::test_s6_log_rotation -q
2 passed in 0.98s
```

**结论：通过。**

### 7.8 S5 真实端到端（真 QQ 群 + 真 MC 服）

**仍未执行**，且本轮**没有**新增任何真机证据：本机依然没有真实 QQ 机器人凭据与
`enable-rcon=true` 的真 MC 服，S5-1…S5-8 的玩家可见现象无法复现，结论维持 **§2.5 的「部分通过」**。

离线可复现片段与自动化等价物**全部复跑通过**：

```bash
$ env -u QQ_BOT_APP_ID -u QQ_BOT_APP_SECRET $BP -m y33bot run --config config.toml
[启动] y33bot 0.1.0（1 个 MC 服）
[启动] 日志监听已启动: main
[错误] 环境变量 QQ_BOT_APP_ID 未设置
exit=1

$ $BP -m pytest tests/test_service.py::test_run_polls_log_pushes_and_persists_offset \
        tests/e2e/test_entrypoint.py::test_entrypoint_run_fails_fast_without_credentials \
        tests/test_failures.py::test_service_run_builds_gateway_from_credentials -q
3 passed
```

（`test_run_polls_log_pushes_and_persists_offset` 覆盖 S5-7「重启不重复推送」：假网关 + 假 RCON 下
追加日志 → 群内收到通知 → 退出后 `log_offset` 等于文件大小。）

### 7.9 CI 与发布物

```bash
$ curl -s "https://api.github.com/repos/YeeNg2333/Y33-Bot/actions/runs?per_page=8"
3c27803 main          run#20  CI  completed  success   (…/runs/38292082660)
3c27803 wt/t_7b86eb6b run#19  CI  completed  success   (…/runs/38292077395)
f0e85db main          run#18  CI  completed  success
f0e85db wt/t_7b86eb6b run#17  CI  completed  success
5178e84 wt/t_7b86eb6b run#16  CI  completed  success
1587081 main          run#15  CI  completed  success
1587081 wt/t_bcf892eb run#14  CI  completed  success
f0ddd4e main          run#13  CI  completed  success
```

即**`origin/main` 的 HEAD（`3c27803`）CI 为 success**，且近期 8 次运行全绿。

发布物 `v0.1.0` 是 **annotated tag**（`first working release`）→ commit `f0ddd4e`：

```bash
$ git diff --stat v0.1.0 origin/main
 .github/workflows/ci.yml     |   5 +-
 Makefile                     |  15 +-
 README.md                    |   2 +
 docs/acceptance.md           | 374 +++++++++++++++
 docs/smoke.md                |  23 +-
 tests/e2e/test_entrypoint.py | 255 ++++++++++
 tests/test_boundaries.py     | 543 ++++++++++++++++++
 tests/test_failures.py       | 1070 +++++++++++++++++++++++++++++++++
 8 files changed, 2270 insertions(+), 17 deletions(-)
```

**关键结论：`v0.1.0` 与 `main` 的差异里 `src/` 一行都没有** —— 产品代码完全同一份，tag 之后新增的
只有测试、CI/Makefile 机制与文档。因此 T11 遗留的「要不要补 v0.1.1」问题在本轮有明确答案：
**不需要**（`src/` 无变化，T10 也未发现产品缺陷；补版本号只会让两个 tag 的产物代码完全相同）。
tag 树本身可独立运行（用 tag 树的 `src` 直接加载）：

```bash
$ PYTHONPATH=<tag-tree>/src $BP -m y33bot --version
y33bot 0.1.0
$ PYTHONPATH=<tag-tree>/src $BP -m y33bot bind list
[绑定] 无绑定记录          # exit=0
```

### 7.10 无硬编码密钥与冻结文件

```bash
$ grep -RInE '(QQ_BOT_APP_SECRET|MC_RCON_PASSWORD)[[:space:]]*=[[:space:]]*[^[:space:]]' \
      --include='*.py' --include='*.yml' --include='*.toml' src tests .github   # CI 同款
（无匹配）

# 更宽的扫描（含 *.md/*.sh/*.example/*.json，排除 .venv）只命中占位符：
README.md:137/383        QQ_BOT_APP_SECRET=你的AppSecret
docs/smoke.md:23         export QQ_BOT_APP_SECRET=<AppSecret>
scripts/dev_setup.sh:56  export QQ_BOT_APP_SECRET=你的AppSecret
（以及代码里的 password=<变量> 关键字参数）
```

冻结文件（相对初次提交 `489f751`）：

| 文件 | 状态 |
|---|---|
| `IDEA.md` | 未改动，blob `4a6620f8f272` |
| `需求1.txt` | 未改动，blob `a43b6afcda7c` |
| `PLAN.md` | 只在 T0 卡（`t_19583dfd`）之后按 §3.1 补了一行 `.gitignore` 说明（commit `3d83eb7`「docs: require .worktrees/ in gitignore spec」），此后未再改动 |

### 7.11 T12 结论

| 项 | 结论 |
|---|---|
| S1 环境与配置自检 | **通过**（`OK`/`FAIL`/缺密钥三条分支，`OK` 分支为真连 RCON） |
| S2 QQ→MC 绑定与转发 | **通过**（真换行输入 + 服务端收到原样 `tellraw` + 真实名单渲染） |
| S3 MC→QQ 聊天转发与回环防护 | **通过** |
| S4 进出通知与健康翻转 | **通过**（离线/上线各只提示一次） |
| S5 真实端到端 | **部分通过**（离线片段 + 自动化等价物通过；真机 8 步缺环境，未执行、不作通过声明） |
| S6 日志轮转 | **通过**（pytest 用例 + 真文件真截断双证据） |
| 一键测试 | **348 passed / 99.30%**（门槛 70%），无 skip/xfail |
| 静态检查 | `ruff check` 全过、40 文件已格式化 |
| CI | `origin/main` HEAD `3c27803` **success**，近期 8 次全绿 |
| 硬编码密钥 | **无**（CI 同款 grep 无匹配；宽扫描仅占位符） |
| 冻结文档 | IDEA.md / 需求1.txt 未动；PLAN.md 仅 T0 卡内一处按 §3.1 追加 |
| 产品缺陷 | **0 条**（本轮未改动 `src/`、`tests/`、`Makefile`、CI 任何一行） |

复验脚本自身出过两次问题，都是**我这边的脚本问题、不是产品缺陷**，记录以免误判：
① 手写 S6 复现脚本第一次把仓库根目录传成了 MSYS 路径（`/c/…`），Python 当成相对路径 → 改用
`pwd -W`；② 该脚本一开始直接给 `MCServerConfig` 赋值，撞上 dataclass 不可变 → 改用
`dataclasses.replace`。两次都在脚本层解决，未触碰仓库代码。

证据留档：`…/cache/scratch/y33bot-root-verify-801/_verify/`（`transcript.txt`、`transcript2.txt`、
`rcon_received.log`、`s6_rotation_real.py`、`mini_rcon_server.py`、`ci_runs.json`）与
`…/cache/scratch/y33bot-tag-verify-2348/`（`v0.1.0` 导出树）。
