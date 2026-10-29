# 端到端验收记录（acceptance）

本文件是任务卡 **T10（`t_7b86eb6b`：补齐自动化测试并完成端到端验收）** 的产出，逐条对应
`PLAN.md` §5 的验收场景。下面每条都给出**命令 + 真实输出 + 结论**，输出是实际执行后粘贴的，
不是手写预期值。手工自测手册（含每个模块的自测点）见 `docs/smoke.md`。

> **「变更前记录」标注（2026-10-29 追加）**：本文件 **§0–§9 是日志模板变更之前**的记录
> （出厂默认还是 vanilla 1.20.x 窄模板；当时例数 **381**、覆盖率 **99.33%**、ruff **43 文件**），
> **原文一字未改**，仅在此加标注，避免与最新数字混淆。模板改成「四族通吃」之后的实测见 **§10**。

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
| 变更批次 | 2026-10-13 **v0.2**（真机反馈 V1–V3，见 `PLAN.md` §7）：§2.3 / §2.4 的文案已按新契约**重跑并更新**；§7 保留 v0.2 之前的原始记录（可核对历史），v0.2 的完整复验见 **§8** |

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
| V1–V3 真机反馈变更（MC→QQ 带服名 / 取消游戏内回显 / 指令面板清单） | **通过**（按新契约重跑，无回归） | §8 |

自动化方面（§3）：`make test` 一键 **381 passed、总覆盖率 99.33%**（门槛 70%；v0.2 后 352、取证合入后 357、BUG-001 修复后 381，见 §8.6 与 §9），`ruff check` +
`ruff format --check` 全绿，全仓**无 skip/xfail**，CI 里跑的就是同一条 `make test`。

> **变更后（2026-10-29）**：日志模板改「四族通吃」之后的最新实测是 **409 passed** / 总覆盖率 **99.33%**
> （门槛 70%）/ `ruff check .` 全过 + `ruff format --check .` **45 文件**；真日志复扫 **361/361**。
> 上段与 §3 的 381 / 348 是**变更前记录**（数字不改写），最新证据见 **§10.4**。

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

> **注（2026-10-15，BUG-001 修复后）**：本节两份粘贴是**变更前**的原始记录，未改写。
> 当时 `[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置` 只证明「环境变量非空」——
> 凭据完全无效也照样 OK（`BUGS.md` 的 F4）。现在 QQ 项默认真探活、新增 `--no-probe`，
> 本轮复验见 **§9.1**。

自动化等价物：`tests/e2e/test_entrypoint.py::test_entrypoint_s1_check_reports_each_item`（真子进程）、
`…::test_entrypoint_s1_check_missing_secret`、`…::test_entrypoint_check_missing_config`、
`tests/test_cli.py::test_check_*`（含探活成功/失败两条）、`tests/test_qq_probe.py`。

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
[群消息] Steve@main: 大家好
exit=0

$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:02] [Async Chat Thread - #0/INFO]: <Steve> 普通聊天' --dry-run --config config.toml
[忽略] 聊天非 # 开头，不转发
exit=0

$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:03] [Async Chat Thread - #0/INFO]: <Steve> [QQ] Steve: 大家好' --dry-run --config config.toml
[忽略] 回环防护：命中 ignored_chat_prefixes
exit=0
```

**结论：通过。** 群消息带来源服名（`Steve@main: 大家好`，`main` = `[[mc_servers]].name`）；v0.2 起
**游戏内不再回显**，所以只剩一行 `[群消息]`、没有 `[RCON …]`；回环前缀被拦下，非 `#` 聊天不转发。

自动化等价物：`tests/e2e/test_entrypoint.py::test_entrypoint_s3_s4_events_and_health_flip`、
`tests/e2e/test_acceptance.py::test_s3_chat_forward_and_loop_guard`。

### 2.4 S4 进出通知与健康翻转（只提示一次）

```bash
$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:04] [Server thread/INFO]: Steve joined the game' --dry-run --config config.toml
[群消息] Steve进入了main
exit=0

$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:05] [Server thread/INFO]: Steve left the game' --dry-run --config config.toml
[群消息] Steve退出了main
exit=0

$ $BP -m y33bot simulate log-event --server main --kind join --player Steve --config config.toml
[群消息] Steve进入了main
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

> **变更前记录**（2026-10-13 的实测，原文不改写）：本节命令输出里的 `348 passed` / `40 files` 是模板变更之前的数字。
> 模板改「四族通吃」之后的最新一次实跑（2026-10-29）：**409 passed** / `Total coverage: 99.33%` /
> `ruff check .` 全过 / `ruff format --check .` **45 files**，见 **§10.4**。

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

测试文件分工（下面的例数是 T10 落地时的口径；v0.2 后 352 例、BUG-001 取证合入后 **357 例**、BUG-001 修复后 **381 例**，见 §9）：

| 文件 | 例数 | 说明 |
|---|---|---|
| `tests/test_boundaries.py` | 63 | **本卡新增**：config/binding/state/patterns/registry/网关文本 的边界与类型错误（空输入、越界、缺字段、损坏文件） |
| `tests/test_failures.py` | 61 | **本卡新增**：RCON 客户端/池、QQ 网关、常驻服务、CLI 的失败分支（畸形包、id 不匹配、半途断连、写盘/关闭失败、参数不合法） |
| `tests/e2e/test_entrypoint.py` | 10 | **本卡新增**：**真子进程**跑 `python -m y33bot …`，逐条断言 S1/S2/S3/S4 的 stdout 与退出码（含用法错误退出码 2） |
| `tests/e2e/test_acceptance.py` | 7 | T8 产出：同进程内按 §5 文案逐条断言（S1–S4、S6） |
| `tests/test_bug001_reconnect.py` | 2 | **BUG-001 取证新增**（卡 `t_6cc56405`）：用真 SDK 的 `ConnectionSession` 复刻「`multi_run` 一次性」与「网关协程返回后 `Service.run()` 仍存活」 |
| 其余 13 个逐模块文件 | 207（+3） | T8 产出：常规路径 + 关键分支；`+3` 为 BUG-001 取证新增（`test_gateway.py` 2 例、`test_service.py` 1 例） |

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

> **v0.2 提示**：本节是 v0.2 变更**之前**的原始记录（保留以便核对历史）。§7.5 的游戏内回显、§7.6
> 的进出文案在 v0.2 中已变更，变更后的复验见 **§8**。

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

结论与 §3 一致：**348 例全过（v0.2 后为 352 例，见 §8）、总覆盖率 99.30%、静态检查全绿、无 skip/xfail**。

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

**结论：通过**，与 §2.3 一致，且回显那一步有服务端回执佐证。（v0.2 起游戏内**不再回显**，此处的
`[→QQ]` 回执属变更前行为，最新文案见 §8。）

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

（本节这三行进出文案属 v0.2 变更前的形式；v0.2 后为 `Steve进入了main` / `Steve退出了main`，见 §8.3。）

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

> 本节（§7）本身随 commit `51d810e` 入库；该文档提交在 `main` 与
> `y33-bot/t_c3a76c90-idea.md` 上的 CI 也都是 **success**（run
> [#22](https://github.com/YeeNg2333/Y33-Bot/actions/runs/38293910730) / [#21](https://github.com/YeeNg2333/Y33-Bot/actions/runs/38293905317)）。

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
| 一键测试 | **348 passed / 99.30%**（门槛 70%），无 skip/xfail（v0.2 后为 **352 passed**，见 §8） |
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

---

## 8. v0.2 变更复验（2026-10-13，真机反馈 V1–V3）

变更内容与对 IDEA 的偏离登记见 `PLAN.md` §7。本节是变更**之后**的重跑记录，环境与 §0 相同
（`SIM-*` 假凭据、`--dry-run`、故意不可达的 `127.0.0.1:34567`；验收目录
`…/cache/scratch/y33bot-v02/`）。§2 里 S3/S4 的文案已按本轮输出更新。

### 8.1 V3 指令面板清单（新增子命令）

```bash
$ $BP -m y33bot commands --config config.toml
[指令] /bind 绑定游戏ID
[指令] /status 查询在线状态
exit=0
```

指令名带 `command_prefix`、介绍压到「≤15 中文字符」限制内；管理端没有注册接口，这份清单要手工抄进
【发布设置 → 功能配置 → 指令配置】，步骤与字段限制见 `README.md` §5.3 与 `PLAN.md` §7 V3。

### 8.2 S3 变更后（V1 带服名 + V2 取消回显）

```bash
$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好' --dry-run --config config.toml
[群消息] Steve@main: 大家好

$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:02] [Async Chat Thread - #0/INFO]: <Steve> 普通聊天' --dry-run --config config.toml
[忽略] 聊天非 # 开头，不转发

$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:03] [Async Chat Thread - #0/INFO]: <Steve> [QQ] Steve: 大家好' --dry-run --config config.toml
[忽略] 回环防护：命中 ignored_chat_prefixes

$ $BP -m y33bot simulate log-event --server main --kind join --player Steve --config config.toml
[群消息] Steve进入了main
```

**V2 的判据**：第 1 条只有一行 `[群消息] Steve@main: 大家好`，**没有** `[RCON main] tellraw …`
—— 游戏内不再被注入任何回显行。**V1 的判据**：前缀 `main` 就是该事件来源服的 `[[mc_servers]].name`。

### 8.3 S4 变更后（V1 带服名）

```bash
$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:04] [Server thread/INFO]: Steve joined the game' --dry-run --config config.toml
[群消息] Steve进入了main

$ $BP -m y33bot simulate log-event --server main \
    --line '[12:00:05] [Server thread/INFO]: Steve left the game' --dry-run --config config.toml
[群消息] Steve退出了main

$ $BP -m y33bot simulate health --server main --offline --dry-run --config config.toml   # 第 1 次
[RCON main] /list
[警告] RCON main 命令失败: 假 RCON 服务器离线: 127.0.0.1:34567
[群消息] [服务器状态] main 离线

$ $BP -m y33bot simulate health --server main --offline --dry-run --config config.toml   # 第 2 次
[RCON main] /list
[警告] RCON main 命令失败: 假 RCON 服务器离线: 127.0.0.1:34567
[忽略] 状态未变化，不重复提示

$ $BP -m y33bot simulate health --server main --online --dry-run --config config.toml
[RCON main] /list
[群消息] [服务器状态] main 上线
```

健康分支的行为**未变**（仍只提示一次），只有进出文案换成带服名的版本。

### 8.4 一键测试与静态检查

```bash
$ $BP -m pytest -q
352 passed in 49.30s
$ $BP -m pytest -q --cov=y33bot --cov-report=term-missing --cov-fail-under=70
Required test coverage of 70% reached. Total coverage: 99.30%
$ $BP -m ruff check . && $BP -m ruff format --check .
All checks passed!
40 files already formatted
```

用例数 348 → 352：新增 `test_bridge.py::test_chat_loop_protection_is_config_driven`、
`tests/test_cli.py::test_commands_*`（3 例）、`tests/e2e/test_entrypoint.py::test_entrypoint_commands_lists_panel_items`，
并删掉一条已不存在的 `[→QQ]` 参数化用例。

### 8.5 结论

| 项 | 结论 |
|---|---|
| V1 MC→QQ 文案带来源服名 | **通过**：`Steve进入了main` / `Steve退出了main` / `Steve@main: 大家好`，服名取 `[[mc_servers]].name` |
| V2 取消游戏内回显 | **通过**：`#` 聊天只产生一行 `[群消息]`，无任何 `[RCON …]` 注入 |
| V3 指令面板清单 | **通过**：`y33bot commands` 的输出与 `dispatch()` 认得的指令名一致；管理端配置步骤与平台限制已写入 `README.md` §5.3 |
| 连带影响 | `ignored_chat_prefixes` 样板收窄为 `["[QQ]"]`（服务只注入这一个标记）；回环判断先于 `#` 判断，且「可配置」已被自动化用例锁住 |
| 回归 | **无**：S1/S2/S5 离线片段/S6 的文案与退出码未变；352 例全绿、覆盖率 99.30%、ruff 全绿 |
| S5 真机 8 步 | **仍未执行**，结论维持 §2.5 的「部分通过」；其中「指令面板是否自动带 @」已由用户真机确认（仅 @消息触发），故无需改 intent |
| 未做 | `/list`（群内列举指令）按用户决定不做，可发现性交给 QQ 客户端指令面板（`PLAN.md` §7 末） |

### 8.6 BUG-001 取证用例合入后的复验（2026-10-15）

BUG-001 的调查卡 `t_6cc56405`（分支 `y33-bot/t_6cc56405-bug-001-qq-token`，提交 `ecf71b2`）已合入 main
（merge `e5b0782`），带来 5 个取证用例（`tests/test_bug001_reconnect.py` 新增 2 例、`tests/test_gateway.py` +2、
`tests/test_service.py` +1），**`src/` 一行未改**。合并后在 main 上重跑 CI 同款：

```bash
$ .venv/Scripts/python.exe -m pytest -q --cov=y33bot --cov-report=term-missing --cov-fail-under=70
TOTAL                              1766      6    388      9    99%
Required test coverage of 70% reached. Total coverage: 99.30%
357 passed in 46.60s

$ .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format --check .
All checks passed!
41 files already formatted
```

- 用例数 **352 → 357**，总覆盖率仍 99.30%；每模块覆盖度不变（`bridge`/`cli`/`rcon.client` 99%，
  `qq.gateway`/`service` 98%，其余 100%）。
- §8.4 粘贴的输出是 v0.2 那一轮（352 例）的**原始记录，未改写**；本节是本轮合入后的复验。
  少数「历史记录」按原样保留：§3 的逐文件例数（T10 口径）、§7.2 / §7.11（T12 复验，348 例）。
- 缺陷结论、影响面与推荐修复方向见 `BUGS.md` 的 BUG-001「回复」（**真缺陷**；真机触发链路 Q1/Q3 **未执行**）。

---

## 9. BUG-001 修复落地后的复验（2026-10-15，看板卡 `t_80249809`）

本卡按 `BUGS.md` 的推荐方向落地 **R2-lite**（运行期网关失效 → `[错误]` + 非 0 退出，不做退避重启）
与 **R5**（`check` 的 QQ 项真探活），并同步 `PLAN.md` §3.2/§3.3/§3.4/§3.6/§5/§7.2 与 README、`docs/smoke.md`。
**§7 / §8 的粘贴与 348/352/357 这些数字是历史记录，未改写**；本节是本轮复验。

### 9.0 执行环境与前置

| 项 | 值 |
|---|---|
| 日期 | 2026-10-15（03:05–03:09 +0800） |
| 机器 | Y33NG-LAPTOP（Windows 11 + git-bash／MSYS），Python 3.12.10（仓库内 `.venv`） |
| 代码版本 | 分支 `y33-bot/t_80249809-bug-001-0-r2-lite-check-qq-r5`；对照基线 = `757db31`（本卡起点，`git archive` 出 `src/`） |
| 取证目录 | 仓库**之外**：`…/cache/scratch/bug001-fix`（`config.toml`（`port = 34567` 故意不可达、`group_openid = "GROUP-OPENID-1"`）+ `logs/latest.log` + 对照脚本 `verify_gateway_death.py`） |
| 环境变量 | `QQ_BOT_APP_ID=102000000`、`QQ_BOT_APP_SECRET=this-secret-is-bogus-and-never-issued`（**从未签发的假值**）、`MC_RCON_PASSWORD_MAIN=bogus-rcon` |
| 未执行 | **真机触发链路**（Q1 静默那一刻的日志尾部、Q3 QQ 侧关码）与 **S5 真机 8 步**：本机没有真实 QQ 机器人凭据、也没有 `enable-rcon=true` 的真 MC 服。本节所有证据都在**离线**（真网络只用到 §9.1 平台的 token 接口） |

### 9.1 R5：`check` 的 QQ 项真探活（同一个假凭据，修复前 vs 修复后）

修复前（`757db31` 的 `src`，`PYTHONPATH` 指过去）：

```bash
$ PYTHONPATH=<757db31>/src $BP -m y33bot check --config config.toml        # 2026-10-15 03:08:21 +0800
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置          ← 凭据是完全假的，也照样 OK
[RCON main] FAIL 无法连接 127.0.0.1:34567: 连接 127.0.0.1:34567 失败: [WinError 1225] 远程计算机拒绝网络连接。
[日志 main] OK …\bug001-fix\logs\latest.log 可读，偏移 0 字节
[绑定] OK 0 条
FAIL
exit=1
```

修复后（本卡 `src`，默认真探活）：

```bash
$ PYTHONPATH=<本卡>/src $BP -m y33bot check --config config.toml           # 2026-10-15 03:08:04 +0800
[警告] RCON main 命令失败: 连接 127.0.0.1:34567 失败: [WinError 1225] 远程计算机拒绝网络连接。
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] FAIL access_token 获取失败: 平台返回错误: code=10004 message=机器人不存在
[RCON main] FAIL 无法连接 127.0.0.1:34567: 连接 127.0.0.1:34567 失败: [WinError 1225] 远程计算机拒绝网络连接。
[日志 main] OK …\bug001-fix\logs\latest.log 可读，偏移 0 字节
[绑定] OK 0 条
FAIL
exit=1
```

（`code=10004 message=机器人不存在` 是**平台真的回话**了 —— 探活确实发出了一次 HTTPS 请求，
而不是本地提前失败。同一台机器上两次 `check` 耗时之差约 0.15s，即那次取 token 的往返。）

修复后（`--no-probe`，离线环境/CI 用）：

```bash
$ PYTHONPATH=<本卡>/src $BP -m y33bot check --config config.toml --no-probe
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，未探活（--no-probe），group_openid 已配置
[RCON main] FAIL 无法连接 127.0.0.1:34567: 连接 127.0.0.1:34567 失败: [WinError 1225] 远程计算机拒绝网络连接。
[日志 main] OK …\bug001-fix\logs\latest.log 可读，偏移 0 字节
[绑定] OK 0 条
FAIL
exit=1
```

| 分支 | 命令 | 结果 | 结论 |
|---|---|---|---|
| 凭据无效（假值） | `check`（默认探活） | `[QQ] FAIL access_token 获取失败: 平台返回错误: code=10004 message=机器人不存在` | **通过**（修复前是 `[QQ] OK`） |
| 离线跳过 | `check --no-probe` | `[QQ] OK …未探活（--no-probe）…` | **通过**（文案自己说明「未探活」） |
| 凭据缺失 | `env -u QQ_BOT_APP_SECRET check` | `[QQ] FAIL 环境变量 QQ_BOT_APP_SECRET 未设置` | **通过**（与旧行为一致，且不联网） |
| 凭据有效 | —— | 预期 `[QQ] OK access_token 获取成功（有效期 <N>s），…` | **未执行**：本机没有真实凭据；单元测试用替身锁住该文案（`tests/test_cli.py::test_check_probes_credentials_by_default`） |

自动化等价物：`tests/test_qq_probe.py`（解析/平台报错/HTTP 错误/非 JSON/网络不可达，全程离线）、
`tests/test_cli.py::test_check_probes_credentials_by_default`、`…::test_check_reports_unusable_credentials`、
`tests/test_service.py::test_startup_checks_reports_unusable_credentials`（探活失败 → `CheckResult(ok=False)`）、
`…::test_startup_checks_without_probe_keeps_offline_path`、`…::test_service_default_probe_is_the_real_one`。

### 9.2 R2-lite：运行期网关失效 → `[错误]` + 非 0 退出（同脚本前后对照）

同一份脚本（`…/bug001-fix/verify_gateway_death.py`：桩网关 `start()` 成功、0.3s 后网关任务结束，
用 `asyncio.wait_for` 做 3s 看门狗，超时判定为「没有退出」）、同一份 `config.toml`，只换 `PYTHONPATH`：

```bash
$ PYTHONPATH=<757db31>/src $BP verify_gateway_death.py config.toml 0.3 3      # 2026-10-15 03:07:47 +0800
修复前 退出码(99=run() 在 3s 内没有返回)=99
INFO [启动] y33bot 0.1.0（1 个 MC 服）
INFO [启动] 日志监听已启动: main
INFO [停止] 正在关闭…                                  ← 只有看门狗的取消才让它走关闭流程
INFO [停止] 已退出
run() 在 3s 内没有返回：网关 started=True，进程仍在常驻（静默）
```

```bash
$ PYTHONPATH=<本卡>/src $BP verify_gateway_death.py config.toml 0.3 3
修复后 退出码=1
INFO [启动] y33bot 0.1.0（1 个 MC 服）
INFO [启动] 日志监听已启动: main
ERROR [错误] QQ 网关已断开（收不到群消息），进程退出等待重启
INFO [停止] 正在关闭…
INFO [停止] 已退出
网关 started=True closed=True
exit=1
```

（修复前那份日志里**一条 `[错误]` 都没有**，正是 BUG-001 描述的「进程常驻、日志干净」。）

反向对照（不能把「我们自己主动关」也报成故障）：`tests/test_service.py::test_run_returns_0_when_stopped_by_signal`
断言收到停止信号时退出码 0 且 `[错误]` 记录为空；端到端的整链回归（真 SDK 的 `multi_run()` + 真 `BotpyGateway`
+ 真 `Service.run()`）在 `tests/test_bug001_reconnect.py::test_service_reports_and_exits_when_sdk_gateway_coroutine_returns`。

| 分支 | 结果 | 结论 |
|---|---|---|
| 启动后网关任务结束 | `[错误] QQ 网关已断开（收不到群消息），进程退出等待重启` + `exit=1` + 走完 `shutdown()` | **通过**（修复前：3s 看门狗判超时、无 `[错误]`） |
| 收到停止信号（`Ctrl+C`/`SIGTERM`） | `exit=0`、无 `[错误]` | **通过** |
| 启动期网关失败 | `[错误] QQ 网关启动失败: …` + `exit=1` | **通过**（原有行为未变） |
| 真机断线（断网 / 重置 AppSecret / 等 token 过期） | —— | **未执行**（无真实凭据与真 MC 服）；`PLAN.md` §5 S5 已补上「新增观察点」与期望输出 |

### 9.3 一键测试与静态检查

```bash
$ $BP -m pytest -q
381 passed in 47.11s

$ $BP -m pytest -q --cov=y33bot --cov-report=term-missing --cov-fail-under=70
TOTAL                              1839      6    400      9    99%
Required test coverage of 70% reached. Total coverage: 99.33%
381 passed in 47.11s

$ $BP -m ruff check . && $BP -m ruff format --check .
All checks passed!
43 files already formatted
```

用例数 357 → 381（+24）：新增 `tests/test_qq_probe.py`（10 例，探活解析与失败文案）、
`tests/test_gateway.py` +3（`wait_closed` 的三个语义）、`tests/test_service.py` +5
（探活失败/`--no-probe`/默认真探活/网关死亡退出 1/正常停止退出 0）、
`tests/test_cli.py` +2（默认探活成功、探活失败）；另有 5 例按新契约**改写**（原本钉「静默失效」的取证用例）：
`tests/test_service.py::test_run_ignores_gateway_task_ending` → `…::test_run_returns_1_when_gateway_dies_after_start`（同一场景，断言反过来了）、
`tests/test_bug001_reconnect.py::test_service_stays_alive_when_sdk_gateway_coroutine_returns` → `…::test_service_reports_and_exits_when_sdk_gateway_coroutine_returns`，
以及 `tests/test_cli.py` / `tests/e2e/*` / `tests/test_smoke.py` 里 `check` 的期望行（补 `--no-probe` 与新文案）。
`tests/` 仍**无 skip/xfail**；覆盖率 99.30% → 99.33%（`qq.probe` 100%，其余模块覆盖度不变）。

> 说明：上面那句「改写」是**契约变了才改**，不是把失败用例改绿 —— 旧用例钉的是「网关死了没人管」这个当时的事实，
> 修复后它必须钉相反的行为；`BUGS.md` 的「回复」原文未改，其引用的旧用例名/行号只代表修复前状态，
> 本轮「修复记录」小节已注明对应关系。

### 9.4 结论

| 项 | 结论 |
|---|---|
| R2-lite 运行期网关失效报警退出 | **通过**（离线前后对照 + 整链回归用例；真机触发链路未执行） |
| R5 `check` 真探活 | **通过**（真网络实测：假凭据 → `[QQ] FAIL access_token 获取失败: 平台返回错误: code=10004`；离线路径 `--no-probe` 可用） |
| 回归 | **无**：S1–S4/S6 的离线契约（`simulate`、bind、日志轮转）未改；正常退出仍是 `exit=0` 且无 `[错误]`；381 例全绿、覆盖率 99.33%、ruff 43 文件全绿 |
| 未执行 | 真机断线三连与 Q1/Q3 取证、S5 真机 8 步 —— 原因见 §9.0；`PLAN.md` §5 已补期望输出，具备环境后按 `docs/smoke.md` 回填 |
| 文档 | `PLAN.md` §7.2 变更登记 + §3.1/§3.2/§3.3/§3.4/§3.6/§5 同步；`README.md` §7/§8/§13/§14；`docs/smoke.md` §1/§6/§7；`BUGS.md` BUG-001 状态「已修复」+「修复记录」 |
| AGENTS.md | **本次未写入**：「开发进度」那条要加的条目已写好，但运行环境把 `AGENTS.md` 当作**受保护的智能体指令文件**，写入需要交互批准，而本卡是无人值守运行（无用户在场可批准），故未落盘。待补内容（含文件清单、测试数字、真机是否执行、遗留项）原文见看板卡 `t_80249809` 的评论，人工或有批准能力的会话可直接粘贴 |

---

## 10. 日志模板「四族通吃」变更后复验（2026-10-29，看板卡 `t_33baa9bb`）

> **本节是模板变更之后**的实测。§0–§9 保留模板变更**之前**的记录（当时 381 例 / 99.33% / ruff 43 文件、
> 出厂默认是 vanilla 1.20.x 窄模板），按要求**只加「变更前记录」标注、不改写历史内容**。
> 变更登记见 `PLAN.md` §7.3，缺陷侧见 `BUGS.md` BUG-002/003。

### 10.0 执行环境与前置

| 项 | 值 |
|---|---|
| 日期 | 2026-10-29 |
| 机器 | Y33NG-LAPTOP（Windows 11 + git-bash／MSYS），Python 3.12.10（仓库内 `.venv`） |
| 代码版本 | 分支 `wt/t_33baa9bb`（= main + `wt/t_2a31fd67` 的出厂模板与夹具 + `wt/t_739a0487` 的回归锁），**`src/` 零改动** |
| 抽检对象 | `test-notes/artifacts/` 下 2026-10-18 实机测试矩阵的原始日志：`00-env`、`vanilla`、`fabric`、`forge`、`neoforge` |
| 判定方式 | 用 `config.example.toml` **自身的** `[log_patterns]` 编译后逐行过 `parse_line`（不在脚本里硬编码模板），按族、按事件类型统计命中 |
| 扫描脚本 | 临时脚本，**未入库**：`…/cache/scratch/factory_default_sweep.py`（改后）、`…/cache/scratch/y33_before_sweep_t33baa9bb.py`（改前，模板取自 `git show main:config.example.toml`） |
| 真机回归 | **未执行**：本机没有可用的四族 MC 服。本轮做的是「真日志离线复扫 + 文档/出厂默认一致性 + 自动化回归」 |

### 10.1 同一批真行：改前 vs 改后逐族命中

「改前」= `main:config.example.toml` 的出厂默认（vanilla 1.20.x 窄形态）；「改后」= 本轮出厂默认（四族通吃）。

| 族 | 改前 join | 改前 quit | 改前 chat | 改后 join | 改后 quit | 改后 chat |
|---|---|---|---|---|---|---|
| `00-env`（环境基座） | 1/1 | 1/1 | 0/2 | 1/1 | 1/1 | 2/2 |
| `vanilla` | 27/27 | 26/26 | **0/52** | 27/27 | 26/26 | 52/52 |
| `fabric` | 23/23 | 22/22 | **0/28** | 23/23 | 22/22 | 28/28 |
| `forge` | **0/36** | **0/24** | **0/48** | 36/36 | 24/24 | 48/48 |
| `neoforge` | **1/22** | **0/21** | **0/28** | 22/22 | 21/21 | 28/28 |
| **合计** | — | — | — | **361/361（MISS 0）** | — | — |

改前合计 **101/361**，改后 **361/361**。改前的漏判正好对上 `BUGS.md` 的两条缺陷：
Forge 全族 0 命中（BUG-002：中文日期时间戳 + logger 后多一段 `[net.minecraft.server.MinecraftServer/]`）、
≥1.21.2 起聊天 0 命中（BUG-003：聊天回到主线程且多 `[Not Secure] ` 前缀）。

改后一遍的实际输出：

```text
== 出货默认 == sweep 脚本候选A ==
  join: True
  quit: True
  chat: True

== 出货默认（config.example.toml）逐族命中 ==
  00-env     join=1/1  quit=1/1  chat=2/2
  fabric     join=23/23  quit=22/22  chat=28/28
  forge      join=36/36  quit=24/24  chat=48/48
  neoforge   join=22/22  quit=21/21  chat=28/28
  vanilla    join=27/27  quit=26/26  chat=52/52
  合计 361/361
  MISS 数: 0
```

改前一遍的实际输出（同一批行、旧模板）：

```text
== 改前模板（main:config.example.toml）逐族命中 ==
  00-env     join=1/1  quit=1/1  chat=0/2
  fabric     join=23/23  quit=22/22  chat=0/28
  forge      join=0/36  quit=0/24  chat=0/48
  neoforge   join=1/22  quit=0/21  chat=0/28
  vanilla    join=27/27  quit=26/26  chat=0/52
  合计 101/361
```

### 10.2 ≤ 1.21.1 旧形态仍然命中（回归不退）

制品矩阵里没有 ≤1.21.1 的真行，用文档样例行（`Async Chat Thread - #0/#12`）单独验：

```text
== ≤1.21.1 旧形态（文档样例行）==
  chat: True -> ('chat', 'Steve', '#大家好')
  chat-12: True -> ('chat', 'Alex', '#hi 😀')
  plain: True -> ('chat', 'Steve', '普通聊天')
  旧形态全部命中: True
```

3/3 命中 —— 换成「四族通吃」形态没有丢掉旧版本。

### 10.3 三方逐字相等回归锁与真行用例

`tests/test_log_patterns_real_lines.py`（28 例）把三份「出厂默认」钉成**逐字相等**：
`config.example.toml` ≡ `tests/conftest.py` 的三条夹具常量 ≡ `PLAN.md` §3.5 的样板代码块
（§3.5 用 `tomllib` 解析，顺带验证样板是合法 TOML）。另有 16 条内联行
（13 条真机真行：vanilla ≥1.21.2 / Fabric 26.1 / Forge 两种 logger 形态 / NeoForge 1.21.4；3 条 ≤1.21.1 旧形态文档样例行 ——
制品矩阵里没有该形态的真行）逐条断言 `kind` / `player` / `message`，2 条非事件行断言**不**误判，2 条语义断言
（非 `#` 聊天仍被 bridge 忽略、`#` 聊天仍转发 `Steve@main: …`）。

```bash
$ .venv/Scripts/python.exe -m pytest tests/test_log_patterns_real_lines.py -q
............................                                             [100%]
28 passed in 0.12s
```

红锁验证（本卡复核）：把 `PLAN.md` §3.5 的 `[log_patterns]` 回退成旧模板后重跑 ——

```text
$ .venv/Scripts/python.exe -m pytest tests/test_log_patterns_real_lines.py -q -k plan_section
FAILED tests/test_log_patterns_real_lines.py::test_plan_section_equals_factory_defaults[join]
FAILED tests/test_log_patterns_real_lines.py::test_plan_section_equals_factory_defaults[quit]
FAILED tests/test_log_patterns_real_lines.py::test_plan_section_equals_factory_defaults[chat]
3 failed, 25 deselected in 0.20s
```

恢复后 28 例全绿（`…… 28 passed in 0.47s`）。也就是说「文档里贴的样板」与「出厂默认」再也不会各自漂移：
改任一处而不同步另外两处，这三条用例立红。

### 10.4 一键测试与静态检查

```bash
$ .venv/Scripts/python.exe -m pytest -q --cov=y33bot --cov-report=term-missing --cov-fail-under=70
TOTAL                              1839      6    400      9    99%
Required test coverage of 70% reached. Total coverage: 99.33%
409 passed in 48.43s

$ .venv/Scripts/python.exe -m ruff check .
All checks passed!
$ .venv/Scripts/python.exe -m ruff format --check .
45 files already formatted
```

用例数 **381 → 409**（+28，全部来自新增的 `tests/test_log_patterns_real_lines.py`），覆盖率 **99.33%**（不变），
ruff 合规文件 **45**（2026-10-15 那轮记录的是 43，期间新增了测试文件；本卡**没有**新增 `.py`）。

### 10.5 结论

| 项 | 结论 |
|---|---|
| 模板改后四族真行 | **通过**：361/361 命中、MISS 0（改前同一批行 101/361） |
| ≤1.21.1 旧形态回归 | **通过**：3/3 仍命中 |
| 文档与出厂默认一致 | **通过**：三方逐字相等锁 6 条用例全绿，红锁验证有效（回退 §3.5 后 3 条立红） |
| 自动化回归 | **通过**：409 passed、覆盖率 99.33%（门槛 70%）、ruff check/format 全绿（45 文件） |
| 产品代码 | **零改动**：`git diff main..HEAD -- src/` 为空 |
| 真机回归 | **未执行**：本机没有四族 MC 服；真行取自 `test-notes/artifacts/` 的矩阵制品，不是本轮新采的真机日志。恢复真机后按 `docs/smoke.md` §3 回填 |
| 历史记录 | §0–§9 **原文未改**，仅加「变更前记录」标注；本轮数字全部落在 §10 |

### 10.6 根卡终局复核（2026-10-29，看板卡 `t_13b9be2a`，PR #5）

子卡把模板 / 夹具 / 回归锁 / 文档 / `BUGS.md` 分别落地后，根卡在自己的 worktree 上把
`wt/t_e7da5bef`（PR #5 的 head `60db1aa`）合并进来做一次**独立复核**，不引用子卡结论，全部重跑：

```bash
$ git merge --no-ff 60db1aa        # 合并树：e6efc29
 11 files changed, 706 insertions(+), 36 deletions(-)

$ git diff --stat 73400e0..HEAD -- src/          # 产品代码
（空）
$ git diff --stat 73400e0..HEAD -- IDEA.md 需求1.txt AGENTS.md
（空）

$ .venv/Scripts/python.exe -m pytest -q --cov=y33bot --cov-fail-under=70
TOTAL                              1839      6    400      9    99%
Required test coverage of 70% reached. Total coverage: 99.33%
409 passed in 49.13s

$ .venv/Scripts/python.exe -m ruff check .
All checks passed!
$ .venv/Scripts/python.exe -m ruff format --check .
45 files already formatted
```

离线复扫（同一批 `test-notes/artifacts/**` 真行，脚本在仓库外，模板取自本 worktree 的 `config.example.toml`）：

```text
== 出货默认 == sweep 脚本候选A ==
  join: True  quit: True  chat: True
== 出货默认（config.example.toml）逐族命中 ==
  00-env     join=1/1  quit=1/1  chat=2/2
  fabric     join=23/23  quit=22/22  chat=28/28
  forge      join=36/36  quit=24/24  chat=48/48
  neoforge   join=22/22  quit=21/21  chat=28/28
  vanilla    join=27/27  quit=26/26  chat=52/52
  合计 361/361
  MISS 数: 0
== ≤1.21.1 旧形态（文档样例行）==
  旧形态全部命中: True
```

改前同一批行的对照（模板取自 `git show main:config.example.toml`）：`合计 101/361`
（forge join 0/36、quit 0/24、chat 0/48；neoforge join 1/22、quit 0/21、chat 0/28；
vanilla / fabric chat 0/52、0/28）。

GitHub 侧（`api.github.com`，2026-10-29）：

| 项 | 实测 |
|---|---|
| PR | [#5](https://github.com/YeeNg2333/Y33-Bot/pull/5) `fix(log_patterns): 出厂默认模板兼容 1.21.2+ 与 Forge/NeoForge 布局`，正文首行 `Closes #1` |
| PR 状态 | `state=open`、`merged=false`、`mergeable_state=clean`、`changed_files=797`（含 origin/main 落后的既有提交，见卡片遗留项） |
| CI | head `60db1aa` 的 `test (3.12)` 两次运行均 `completed / success` |
| issue #1 | `state=open`（合并 PR 后由 `Closes #1` 自动关闭，本轮未手动关闭） |

结论：与 §10.1–§10.5 的子卡实录**逐项一致**（361/361、409 例、99.33%、45 文件、`src/` 零改动）。
真机四族端到端回归**仍未执行**——本机没有 vanilla / Fabric / Forge / NeoForge 服与 QQ 凭据，
替代证据是上面这份 361 条真机采集行的全量复扫 + 28 例回归锁；真机就绪后按 `docs/smoke.md` §3 回填。
