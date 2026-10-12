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
