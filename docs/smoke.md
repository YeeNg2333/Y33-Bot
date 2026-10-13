# 手工自测（smoke）—— 每完成一个模块就跑一遍

本文件是**实现任务（T2–T8）的产出**，逐条对应 `PLAN.md` §5 的验收场景。
下面的输出都是在本机（Windows 11 + git-bash + Python 3.12.10）**真实执行后粘贴**的，
不是手写预期值；真实端到端（S5：真 QQ 群 + 真 MC 服）见 `PLAN.md` §5，端到端验收记录见 `docs/acceptance.md`。

---

## 0. 准备

```bash
# 1) 依赖与可执行入口（Python 3.12，仓库内 .venv）
bash scripts/dev_setup.sh          # 或 make setup：建 .venv + 装依赖 + 可编辑安装 + 生成 config.toml
.venv/Scripts/python -m pip install -e .

# 2) 配置
#    dev_setup.sh 会从 config.example.toml 复制出 config.toml（已存在则不覆盖）
#    然后按机器实际情况改 [mc_servers] host/port/log_path 与 [qq] group_openid
#    （group_openid 留空则 MC→QQ 方向禁用并告警）

# 3) 密钥（只走环境变量，仓内不存）
export QQ_BOT_APP_ID=<AppID>
export QQ_BOT_APP_SECRET=<AppSecret>
export MC_RCON_PASSWORD_MAIN=<RCON密码>
```

下文命令里的 `python -m y33bot` 在 Linux 下用 `.venv/bin/python -m y33bot`。

自测目录示例（下文输出里的 `SIM-GROUP-OPENID` / `127.0.0.1:34567` / `logs/latest.log` 就是按这个来的）：

```
config.toml      # log_path = "logs/latest.log"，port = 34567（故意指向不可达端口，用来看 FAIL 分支）
logs/latest.log  # 空文件
data/            # bindings.toml / state.json 由程序生成
```

---

## 1. 版本与配置自检（S1）

```bash
$ python -m y33bot --version
y33bot 0.1.0

$ python -m y33bot check --config config.toml
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON main] FAIL 无法连接 127.0.0.1:34567: 连接 127.0.0.1:34567 超时（1.0s）
[日志 main] OK .../logs/latest.log 可读，偏移 0 字节
[绑定] OK 0 条
FAIL
$ echo $?
1
```

- 逐项 OK/FAIL + 末行 `OK`/`FAIL`，退出码 0/1（`PLAN.md` §3.4）。
- 把 `host`/`port` 指向可达的 RCON 后，那一行变成 `[RCON main] OK /list -> There are 0 of a max of 20 players online:`，末行 `OK`、退出码 0。
- 缺 `QQ_BOT_APP_SECRET` → `[QQ] FAIL 环境变量 QQ_BOT_APP_SECRET 未设置`；缺 RCON 密码 → `[RCON main] FAIL …MC_RCON_PASSWORD_MAIN 未设置`；日志文件不存在 → `[日志 main] FAIL … 不存在（启动后会持续重试）`。
- **说明**：`check` 的详细日志走 stderr，所以 stdout 只有上面 6 行；stderr 里会多一行
  `[警告] RCON main 命令失败: …`（原因与 stdout 的 FAIL 行同源，便于排查）。

自测（自动化等价物：`tests/test_cli.py::test_check_*`、`tests/test_service.py::test_startup_checks_*`）：

```bash
$ python -m pytest tests/test_cli.py -q -k check
```

---

## 2. QQ → MC：绑定与转发（S2）

```bash
$ python -m y33bot bind set 1A2B3C4D Steve --config config.toml
[绑定] 已写入 1A2B3C4D -> Steve (data/bindings.toml)

$ python -m y33bot bind list --config config.toml
[绑定] 1A2B3C4D -> Steve

$ python -m y33bot simulate group-message --openid 1A2B3C4D --content '#你好
世界' --dry-run --config config.toml
[RCON main] tellraw @a {"text":"[QQ] Steve: 你好"}
```

- 第二行 `世界` 被换行截断丢掉（A7：只转发第一行）。
- 未绑定：`--openid UNKNOWN` → 只有 `[群消息] 请先使用 /bind <游戏ID> 绑定`，**没有** `[RCON …]` 行。
- 非触发前缀：`--content '普通消息'` → `[忽略] 非触发前缀`，不发送。
- 缺参数：`--content '/bind'` → `[群消息] 用法: /bind <游戏ID>`。
- 未知指令：`--content '/unknowncmd'` → `[群消息] 未知指令`。
- `/status`（dry-run 的假 RCON 会先回显命令）：

```
$ python -m y33bot simulate group-message --openid UNKNOWN --content '/status' --dry-run --config config.toml
[RCON main] /list
[群消息] [服务器状态]
[群消息] 在线: 0/20
[群消息] 玩家: 无
```

真实 MC（去掉 `--dry-run`）：游戏内所有在线玩家看到 `[QQ] Steve: 你好`，日志出现 `[RCON main] tellraw …`。
多服时命令会广播到每个服（每个服一行 `[RCON <name>] …`）。

自测：`tests/test_cli.py::test_simulate_*`、`tests/e2e/test_acceptance.py::test_s2_*`。

---

## 3. MC → QQ：聊天转发与回环防护（S3）

```bash
$ python -m y33bot simulate log-event --server main \
    --line '[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好' --dry-run --config config.toml
[群消息] Steve: 大家好
[RCON main] tellraw @a {"text":"[→QQ] Steve: 大家好"}

$ python -m y33bot simulate log-event --server main \
    --line '[12:00:02] [Async Chat Thread - #0/INFO]: <Steve> 普通聊天' --dry-run --config config.toml
[忽略] 聊天非 # 开头，不转发

$ python -m y33bot simulate log-event --server main \
    --line '[12:00:03] [Async Chat Thread - #0/INFO]: <Steve> [→QQ] Steve: 大家好' --dry-run --config config.toml
[忽略] 回环防护：命中 ignored_chat_prefixes
```

`--kind join|quit --player <名字>` 可以不经日志模板直接造事件，用来查通知链路：

```bash
$ python -m y33bot simulate log-event --server main --kind join --player Steve --config config.toml
[群消息] Steve进入游戏
```

自测：`tests/test_cli.py::test_simulate_log_event_*`、`tests/e2e/test_acceptance.py::test_s3_*`。

---

## 4. 进出通知与健康翻转（S4）

```bash
$ python -m y33bot simulate log-event --server main \
    --line '[12:00:04] [Server thread/INFO]: Steve joined the game' --dry-run --config config.toml
[群消息] Steve进入游戏

$ python -m y33bot simulate log-event --server main \
    --line '[12:00:05] [Server thread/INFO]: Steve left the game' --dry-run --config config.toml
[群消息] Steve退出游戏

$ python -m y33bot simulate health --server main --offline --dry-run --config config.toml
[RCON main] /list
[警告] RCON main 命令失败: 假 RCON 服务器离线: 127.0.0.1:34567
[群消息] [服务器状态] main 离线

$ python -m y33bot simulate health --server main --offline --dry-run --config config.toml   # 再执行一次
[RCON main] /list
[警告] RCON main 命令失败: 假 RCON 服务器离线: 127.0.0.1:34567
[忽略] 状态未变化，不重复提示

$ python -m y33bot simulate health --server main --online --dry-run --config config.toml
[RCON main] /list
[群消息] [服务器状态] main 上线

$ cat data/state.json
{ "version": 1, "qq": { "msg_seq": 0 },
  "servers": { "main": { "log_offset": 0, "log_size": 0, "log_inode": "",
                         "health_online": true, "health_changed_at": 1791827101.77 } } }
```

- **说明**：`simulate health` 会真的走一次健康探测（`[RCON …] /list` 是命令回显），离线分支用假 RCON 模拟，
  所以会多一行 `[警告] RCON main 命令失败: …`。关键断言是 `[群消息] [服务器状态] main 离线` **只出现一次**，
  第二次变成 `[忽略] 状态未变化，不重复提示` —— 状态存在 `data/state.json` 的 `health_online`。
- S5-8 的真实现象（30s 内提示一次离线、恢复后提示一次上线）由同一段逻辑（`Bridge.poll_health` + `health_poll_interval`）驱动。

自测：`tests/test_bridge.py::test_poll_health_*`、`tests/e2e/test_acceptance.py::test_s4_*`。

---

## 5. 日志轮转（S6 离线复现）

S6 原文要求先 `run` 再手动清空 `latest.log`；CI/离线环境下用 `LogWatcher` 直接复现同一路径：

```bash
$ python -m pytest tests/test_mclog_watcher.py::test_rotation_resets_offset -q
```

该用例做的事与 S6 逐步一致：先读取两行进服日志（偏移推进）→ 清空文件再写入一行新日志 →
`[警告] 日志文件缩小（size=… < offset=…），偏移重置为 0` 且新日志被解析为 `join` 事件。
`tests/e2e/test_acceptance.py::test_s6_log_rotation` 里还能看到实际告警文本。

真实环境手工版：

```bash
$ python -m y33bot run --config config.toml        # 先跑起来，等它读完当前 latest.log
$ : > /path/to/logs/latest.log                     # 或 mv latest.log latest.log.1
$ echo '[12:00:04] [Server thread/INFO]: Steve joined the game' >> /path/to/logs/latest.log
[警告] 日志文件缩小（size=… < offset=…），偏移重置为 0
[群消息] Steve进入游戏
```

---

## 6. 常驻运行（S5 的离线可复现部分）

`run` = QQ 网关 + 日志轮询 + 健康轮询。QQ 侧需要真实凭据，下面的证据分两部分：

**(a) 缺凭据时快速失败（不产生任何网络副作用）**

```bash
$ env -u QQ_BOT_APP_ID -u QQ_BOT_APP_SECRET MC_RCON_PASSWORD_MAIN=… \
    python -m y33bot run --config config.toml
[启动] y33bot 0.1.0（1 个 MC 服）
[警告] RCON main 连接失败（服务继续，下次调用自动重连）: 连接 127.0.0.1:34567 超时（1.0s）
[启动] 日志监听已启动: main
[错误] 环境变量 QQ_BOT_APP_ID 未设置
$ echo $?
1
```

单服连不上只告警、不阻塞启动（`PLAN.md` §3.6）。

**(b) 进入常驻后的日志轮询 / 退出落盘（自动化，假网关 + 假 RCON）**

```bash
$ python -m pytest tests/test_service.py::test_run_polls_log_pushes_and_persists_offset -q
```

该用例：启动 `Service.run()` → 往 `latest.log` 追加一行进服日志 → 断言群里收到 `Steve进入游戏`
→ 触发退出信号 → 断言退出码 0、网关已关闭、`data/state.json` 的 `log_offset` 等于日志文件大小（S5-7：重启不重复推送）。

真机跑 S5 的步骤（需要真 QQ 机器人与真 MC 服）见 `PLAN.md` §5；启动成功的判据是日志出现：

```
[启动] QQ 网关已连接
[启动] 日志监听已启动: main
```

---

## 7. 全量自测（一条命令）

```bash
$ make test                              # 或 .venv/Scripts/python -m pytest -q
348 passed
$ make test PYTEST_ARGS="-q --cov=y33bot --cov-report=term-missing --cov-fail-under=70"
TOTAL 99%（CI 门槛 --cov-fail-under=70；这条就是 CI 里跑的那一行）
$ make lint                              # ruff check src tests + ruff format --check src tests
All checks passed!
40 files already formatted
```

> `make` 只是便捷入口：Windows 上可能只有 `mingw32-make`，Linux/CI 上就是 `make`；
> `Makefile` 优先用仓库内 `.venv`，没有 `.venv` 时回退到系统解释器，所以 CI 直接 `make test` 即可。
> 等价的直连命令是 `.venv/Scripts/python -m pytest`（Windows）/ `.venv/bin/python -m pytest`（Linux）。

测试文件分工：`tests/test_smoke.py`（入口/边界/仓库约定）、逐模块单测（config/binding/state/
mclog/rcon/commands/bridge/gateway/service/cli）、`tests/test_boundaries.py`（各模块边界与类型错误）、
`tests/test_failures.py`（各模块失败分支）、`tests/e2e/test_acceptance.py`（S1-S4/S6，同进程）、
`tests/e2e/test_entrypoint.py`（**真子进程**跑 `python -m y33bot`，逐条断言 S1-S4 的 stdout 与退出码）。

覆盖度（2026-10-13 实测，348 例）：总覆盖 99%，`binding`/`config`/`state`/`mclog`/`commands`/`rcon`/
`models`/`qq.fakes`/`__main__` 为 100%，`bridge`/`cli`/`rcon.client` 99%，`qq.gateway` 98%、`service` 98%。
逐条验收记录（命令 + 真实输出 + 结论）见 `docs/acceptance.md`。

---

## 8. 已知的输出细节（不是缺陷）

| 现象 | 原因 |
|---|---|
| `check` 的 stdout 只有逐项结果行，stderr 另有一行 `[警告] …` | 日志按 `PLAN.md` §3.6 走 stderr，结果行才是 stdout 契约 |
| `simulate health` 会多出 `[RCON <server>] /list` 与离线时的 `[警告]` | 健康探测真的执行了一次 `/list`；契约要求回显实际执行的命令 |
| `simulate group-message --content '/status'` 的回复每行都带 `[群消息] ` 前缀 | 契约里 `[群消息] ` 标记「要发到 QQ 群的文本」，逐行加前缀便于按行断言 |
| 多服时 `/status` 输出 `main: 在线 1/20 玩家: …` + `总计: N 人在线` | `PLAN.md` A1 的多服渲染规则（单服仍是 IDEA §3.5 的三行格式） |
