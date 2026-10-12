# Y33-Bot

**把 Minecraft Java 版服务器和 QQ 群双向打通的独立 Python 进程**：QQ 群里的消息/指令进游戏，游戏里的聊天与进服退服进群。

设计边界写在需求书里（[`IDEA.md`](IDEA.md)）：**MC 侧只经 RCON 发指令、只读轮询 `latest.log`**——不装插件、不改服务端、不干预 MC 实例，也就不用给 MC 打任何东西，拿一个现成的 Vanilla 服就能接。

- 需求书（冻结）：[`IDEA.md`](IDEA.md)
- 实施计划（唯一技术依据：假设清单 / 需求映射 / 模块与签名 / CLI 契约 / 验收场景）：[`PLAN.md`](PLAN.md)
- 手工自测手册（含真机粘贴输出）：[`docs/smoke.md`](docs/smoke.md)
- 端到端验收记录：`docs/acceptance.md`（按 `PLAN.md` §5 的 S1–S6 逐条记录）
- 本文命令均在全新克隆中实跑过，输出为实测粘贴（见文末「验证方式」）。

---

## 1. 它解决什么问题

| 痛点 | 本项目的做法 |
|---|---|
| 想让群里的人和游戏里的人聊天，但不想装 Bukkit/Spigot 插件或 Fabric/Forge Mod | 只用 **RCON**（服务端自带协议）注入消息，**只读** `logs/latest.log` 取事件 |
| 不想为了一个转发机器人而改动/重启现有 MC 服务端 | 与 MC 完全解耦：一个独立 Python 进程，MC 那边只多开一个 RCON 端口 |
| 群里想查「服里有几个人」 | `/status` 指令（走 RCON `/list` 解析） |
| 群里的人是谁在游戏里是谁 | `/bind <游戏ID>` 一对一绑定，绑定表落 `data/bindings.toml` |

分流规则很简单：**`/` 开头走指令，`#` 开头走转发**，其余一律忽略。

## 2. 功能一览

| 方向 | 触发 | 行为 |
|---|---|---|
| QQ → MC | 群内 `@机器人` + `#` 开头 | 按发送者 OpenID 查绑定，`tellraw` 注入游戏内，格式 `[QQ] Steve: 你好`；未绑定回复 `请先使用 /bind <游戏ID> 绑定` |
| QQ → MC | 群内 `@机器人` + `/` 开头 | 匹配指令表：`/status`、`/bind <游戏ID>`；未注册指令回复 `未知指令` |
| MC → QQ | 游戏内聊天以 `#` 开头 | 群内发 `Steve: 你好`（去掉 `#`），游戏内回显一行 `[→QQ] Steve: 你好` |
| MC → QQ | 玩家进服 / 退服 | 群内发 `Steve进入游戏` / `Steve退出游戏` |
| MC → QQ | 状态翻转 | 服从在线变离线（或反过来）时提示**一次** `[服务器状态] main 离线` |
| 其它 | — | 忽略，不互通 |

细节：只转发第一行（换行处截断）、单行超 200 字符截断并补 `…`、自动剔除图片/附件标记（`<...>`）、默认忽略以 `[QQ]` / `[→QQ]` 开头的游戏内聊天（防回环，可用 `ignored_chat_prefixes` 覆盖）。

## 3. 环境要求

| 项 | 要求 |
|---|---|
| Python | **3.11 – 3.13**（开发与 CI 用 3.12；`requires-python = ">=3.11,<3.14"`，3.14 不在支持范围） |
| MC 服务端 | Java 版 Vanilla（无需任何插件/Mod），开启 RCON 且能读到 `logs/latest.log` |
| QQ | QQ 开放平台**官方机器人**（AppID + AppSecret），机器人已在目标群里，目标群有 `group_openid` |
| 系统 | Windows / Linux / macOS 均可；需要一个能被进程读到的日志文件路径 |
| 网络 | 进程需能连到每台 MC 的 RCON 端口，并能连 QQ 官方网关（`bots.qq.com:443`） |
| 第三方依赖 | 只有 2 个：`qq-botpy==1.2.1`（腾讯官方 SDK）、`tomli-w==1.2.0`（写 TOML；读 TOML 用标准库 `tomllib`） |

MC 侧（`server.properties`）至少要有：

```properties
enable-rcon=true
rcon.port=25575
rcon.password=<你的RCON密码>
```

## 4. 安装

```bash
git clone https://github.com/YeeNg2333/Y33-Bot.git
cd Y33-Bot

bash scripts/dev_setup.sh          # 建 .venv + 装依赖（含开发依赖）+ 可编辑安装本包 + 生成 config.toml
```

`dev_setup.sh` 跑完会打印下一步要执行的命令，末尾还有一段「环境就绪」提示。

不想跑脚本就手敲这四条（等价）：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt    # 只部署不开发：-r requirements.txt
.venv/bin/python -m pip install -e .
cp config.example.toml config.toml
```

> Windows（git-bash / PowerShell）把 `.venv/bin/python` 换成 `.venv/Scripts/python.exe`。
> 之后本文示例统一写 `python -m y33bot`，前提是先激活虚拟环境：
> `source .venv/bin/activate`（Windows：`source .venv/Scripts/activate`）；
> 不激活也行，把 `python` 换成 `.venv/bin/python`（Windows：`.venv/Scripts/python.exe`）。

## 5. 配置

### 5.1 `config.toml`

字段与校验规则见 [`PLAN.md`](PLAN.md) §4.1；样板即 `config.example.toml`：

```toml
[qq]
group_openid = "填写目标群的 group_openid"   # MC→QQ 方向的发送目标；留空则该方向禁用并告警
app_id_env = "QQ_BOT_APP_ID"
app_secret_env = "QQ_BOT_APP_SECRET"
command_prefix = "/"
chat_prefix = "#"

[behavior]
log_poll_interval = 0.5       # 秒，读日志的轮询间隔
health_poll_interval = 30.0   # 秒，健康探测间隔
max_line_length = 200         # 单行转发长度上限（字符）
ignored_chat_prefixes = ["[QQ]", "[→QQ]"]

[paths]
bindings = "data/bindings.toml"
state = "data/state.json"

[[mc_servers]]
name = "main"                           # 唯一，用于日志与状态文件名
host = "127.0.0.1"
port = 25575
password_env = "MC_RCON_PASSWORD_MAIN"  # 变量不存在时回退 MC_RCON_PASSWORD
log_path = "D:/mc/server/logs/latest.log"
connect_timeout = 5.0
command_timeout = 5.0

[log_patterns]
join = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) joined the game'
quit = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) left the game'
chat = '\[\d{2}:\d{2}:\d{2}\] \[Async Chat Thread - #\d+/INFO\]: <(?P<player>\w+)> (?P<message>.+)'
encoding = "utf-8"
```

要点：

- **`paths.*` 与 `mc_servers[].log_path` 的相对路径按 `config.toml` 所在目录解析**，不是按当前工作目录（实测：从父目录用 `--config repo/config.toml` 运行，日志路径仍是 `repo/logs/latest.log`）。绝对路径原样使用。
- 多台 MC 服就多写一个 `[[mc_servers]]`：QQ→MC 的消息会**广播到所有服**，MC→QQ 的事件**不区分来源服**。
- `[log_patterns]` 是为了兼容 MC 版本差异：日志格式变了只改这里，不用改代码（`join`/`quit` 必须有 `player` 命名组，`chat` 必须有 `player` 与 `message`）。
- `log_poll_interval` 决定事件延迟（默认 0.5 秒）；`health_poll_interval` 决定离线/上线提示的及时性（默认 30 秒）。
- **没有热重载**：改完配置要重启进程。

### 5.2 密钥只走环境变量

仓内不存任何真实密钥，`config.toml` 里写的只是**环境变量名**：

```bash
export QQ_BOT_APP_ID=你的AppID
export QQ_BOT_APP_SECRET=你的AppSecret
export MC_RCON_PASSWORD_MAIN=你的RCON密码
```

- 命名：`QQ_BOT_APP_ID`、`QQ_BOT_APP_SECRET`、`MC_RCON_PASSWORD_<服务器名大写>`（未设置时回退 `MC_RCON_PASSWORD`）。清单模板见 [`.env.example`](.env.example)；多服时 `MC_RCON_PASSWORD_SECOND` 之类按同样规则起名。
- 程序**不解析** `.env` 文件（刻意不引入 `python-dotenv`），变量必须由 shell / 进程管理器注入。

## 6. 最小可用示例（不需要 MC，也不需要 QQ）

把配置里的 `log_path` 改成一个存在的路径、`port` 指向任意端口即可（下面用的是 `logs/latest.log` + `127.0.0.1:34567`）：

```bash
python -m y33bot --version                     # y33bot 0.1.0

python -m y33bot bind set 1A2B3C4D Steve --config config.toml
# [绑定] 已写入 1A2B3C4D -> Steve (data/bindings.toml)

python -m y33bot bind list --config config.toml
# [绑定] 1A2B3C4D -> Steve
```

**QQ → 游戏（`--dry-run` 不发任何网络包，只打印将要执行的 RCON 命令）：**

```bash
python -m y33bot simulate group-message --openid 1A2B3C4D --content '#你好' --dry-run --config config.toml
# [RCON main] tellraw @a {"text":"[QQ] Steve: 你好"}
```

**游戏 → QQ（喂一行真实日志格式的文本进去）：**

```bash
python -m y33bot simulate log-event --server main \
  --line '[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好' --dry-run --config config.toml
# [群消息] Steve: 大家好
# [RCON main] tellraw @a {"text":"[→QQ] Steve: 大家好"}
```

> `--line`（以及 `--content`）后面的文本**一定要用引号包住**：日志行里有空格和 `<>`，不引起来会被 shell 拆成多个参数，argparse 直接报 `unrecognized arguments` 并以退出码 2 结束。

**指令：**

```bash
python -m y33bot simulate group-message --openid UNKNOWN --content '/status' --dry-run --config config.toml
# [RCON main] /list
# [群消息] [服务器状态]
# [群消息] 在线: 0/20
# [群消息] 玩家: 无
```

**健康翻转（同一状态只提示一次）：**

```bash
python -m y33bot simulate health --server main --offline --dry-run --config config.toml
# [RCON main] /list
# [警告] RCON main 命令失败: 假 RCON 服务器离线: 127.0.0.1:34567
# [群消息] [服务器状态] main 离线

python -m y33bot simulate health --server main --offline --dry-run --config config.toml
# [忽略] 状态未变化，不重复提示
```

> 提示只在**状态变化**时出现一次：从全新状态（`data/state.json` 里该服还是 `health_online: null`）先跑一次才会看到 `main 离线`，紧接着再跑就是 `[忽略] 状态未变化，不重复提示`；已经被记成离线的服，再跑多少次 `--offline` 都只会是 `[忽略]`。

去掉 `--dry-run` 就是**真的连 RCON 发指令**（本机用一个最小 RCON 服务端实测过，服务端收到的是 `tellraw @a {"text":"[QQ] Steve: 你好"}` 这种原样命令）。

## 7. 启动服务

先自检，再常驻：

```bash
python -m y33bot check --config config.toml     # 逐项 OK/FAIL，末行 OK/FAIL，退出码 0/1
python -m y33bot run   --config config.toml     # 常驻：QQ 网关 + 日志轮询 + 健康轮询
```

自检通过（RCON 可达）时的实测输出：

```text
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON main] OK /list -> There are 0 of a max of 20 players online:
[日志 main] OK .../logs/latest.log 可读，偏移 0 字节
[绑定] OK 1 条
OK
```

MC 还没起（RCON 连不上）时，这一行变 FAIL、末行 FAIL、退出码 1，**这不是崩溃**，把 MC 起起来或把 `host`/`port` 指对再 check 即可：

```text
[RCON main] FAIL 无法连接 127.0.0.1:34567: 连接 127.0.0.1:34567 失败: [WinError 1225] 远程计算机拒绝网络连接。
FAIL
```

（Linux 上同一分支报 `Connection refused`；报超时则多半是防火墙。）

`run` 启动成功的判据是日志里出现这两行，然后开始干活：

```text
[启动] QQ 网关已连接
[启动] 日志监听已启动: main
```

缺凭据时 `run` 会**快速失败**（不产生任何网络副作用，退出码 1）：

```text
$ python -m y33bot run --config config.toml
[启动] y33bot 0.1.0（1 个 MC 服）
[警告] RCON main 连接失败（服务继续，下次调用自动重连）: 连接 127.0.0.1:34567 失败: [WinError 1225] 远程计算机拒绝网络连接。
[启动] 日志监听已启动: main
[错误] 环境变量 QQ_BOT_APP_ID 未设置
```

凭据写错（AppID / Secret 不对）也是退出码 1，但会先真的连上 QQ 网关再被官方拒绝（实测）：

```text
[botpy] 登录机器人账号中...
[botpy] 获取token失败，请检查appid和secret填写是否正确！
[错误] QQ 网关异常退出: {'code': 10004, 'message': '机器人不存在'}
[错误] QQ 网关启动失败: QQ 网关启动失败: {'code': 10004, 'message': '机器人不存在'}
[停止] 正在关闭…
[停止] 已退出
```

单台 MC 连不上只 `[警告]`，不阻塞启动（该服在 `/status` 里显示离线）；`Ctrl+C` / `SIGTERM` 会优雅退出并把状态落盘：

```text
[停止] 收到退出信号
[停止] 正在关闭…
[停止] 已退出
```

## 8. 命令速查

| 命令 | 作用 |
|---|---|
| `python -m y33bot --version` | 打印 `y33bot 0.1.0` |
| `python -m y33bot check --config config.toml` | 启动自检：配置 / QQ 凭据 / 每服 RCON / 每服日志 / 绑定表，退出码 0 通过、1 失败 |
| `python -m y33bot run --config config.toml` | 常驻运行；`--verbose` 输出 DEBUG 日志（默认 INFO，走 stderr） |
| `python -m y33bot bind list --config config.toml` | 列出绑定 |
| `python -m y33bot bind set <openid> <游戏ID> --config config.toml` | 写绑定（同 openid 覆盖旧值）；游戏 ID 需匹配 `^[A-Za-z0-9_]{3,16}$` |
| `python -m y33bot bind remove <openid> --config config.toml` | 删绑定（不在群里做，只有管理员能操作） |
| `python -m y33bot simulate group-message --openid <id> --content '<文本>' [--dry-run] [--group-openid <gid>]` | 模拟一条群消息；`--dry-run` 用假 RCON，不做网络 IO |
| `python -m y33bot simulate log-event --server <name> --line '<一行日志>' [--dry-run]` | 模拟一行 MC 日志 |
| `python -m y33bot simulate log-event --server <name> --kind join\|quit --player <名字>` | 直接造一条进服/退服事件 |
| `python -m y33bot simulate health --server <name> --online\|--offline [--dry-run]` | 模拟一次健康探测 |

输出行前缀是固定契约，方便按行断言：`[群消息] `（要发到 QQ 群的文本）、`[RCON <服名>] `（实际执行的命令）、`[忽略] `（为什么没触发）、`[警告] `/`[错误] `。用法错误由 argparse 处理，退出码 2。

装完包后也可以直接用控制台脚本 `y33bot ...`（等价于 `python -m y33bot ...`）。

## 9. 数据文件与状态

| 文件 | 内容 | 谁来写 |
|---|---|---|
| `config.toml` | 配置（已在 `.gitignore` 中忽略） | 人工维护 |
| `data/bindings.toml` | OpenID ↔ 游戏ID 绑定表 | 程序（`bind set` 或群里 `/bind`）；也可手写 |
| `data/state.json` | 日志偏移、健康状态、主动消息 `msg_seq` | 程序 |

`data/bindings.toml` 程序写出来的样子（同 openid 覆盖，等价「解绑后重绑」）：

```toml
bindings = [
    { qq_openid = "1A2B3C4D", game_id = "Steve" },
]
```

手写的 `[[bindings]]` 写法同样能读（实测通过）：

```toml
[[bindings]]
qq_openid = "9Z8Y7X"
game_id = "Alex"
```

`data/state.json`：

```json
{
  "version": 1,
  "qq": { "msg_seq": 0 },
  "servers": {
    "main": {
      "log_offset": 0, "log_size": 0, "log_inode": "",
      "health_online": true, "health_changed_at": 1791828331.71
    }
  }
}
```

- `log_offset` = 已经读到日志的第几字节，**重启后从这里续读，不会重复推送历史事件**。
- `health_online` 为 `null` 表示还没探测过；`health_changed_at` 配合「状态变化才提示」。
- 版本号或结构对不上时，程序把旧文件改名成 `state.json.bak` 后重置（不静默丢数据）。

## 10. 目录结构与模块职责

```text
src/y33bot/
  __main__.py        python -m y33bot 入口
  cli.py             子命令：run / check / bind / simulate
  config.py          配置加载与校验、密钥解析（密钥只读环境变量）
  models.py          全部 dataclass（事件、消息、指令结果、健康）
  binding.py         绑定表读写（TOML、覆盖语义、原子落盘）
  state.py           运行状态读写（JSON、偏移/健康/msg_seq）
  bridge.py          触发规则、文案渲染、健康翻转（核心业务）
  service.py         组件装配、三个常驻循环、启动自检、优雅退出
  rcon/              protocol（接口与异常）/ client（Valve RCON：多包响应、串行锁、重连）
                     / pool（多服广播、status、/list 解析）/ fakes（dry-run 替身）
  mclog/             patterns（模板编译、单行解析）/ watcher（字节偏移、轮转重置、残行缓冲）
  qq/                gateway（qq-botpy 适配、主动/被动发送）/ fakes（离线替身）
  commands/          registry（装饰器注册表、别名、分发）/ builtin（/status、/bind）
tests/               单元测试 + tests/e2e/（无网络的端到端）
docs/smoke.md        手工自测手册（逐条对应 PLAN §5）
scripts/dev_setup.sh 一键准备环境      Makefile 常用目标      .github/workflows/ci.yml
```

每个模块的职责、冻结签名与依赖关系见 [`PLAN.md`](PLAN.md) §3.2 / §3.3。

## 11. 部署

**为什么不用容器**：本项目是**单进程、零外部服务**（没有数据库/Redis/消息队列），唯一的外部资源是「宿主上的 MC 日志文件（只读）」和「RCON 端口」。容器化不会带来隔离收益，反而要把日志目录挂载进去、把 RCON 网络打通，并把「只读一个日志文件」的小事变成权限/路径问题——通常 bot 就和 MC 跑在同一台机器上。所以推荐**裸进程 + 进程管理器**（下面三种任选）。真要容器化，注意三点即可：日志目录以只读方式挂载（`-v /path/to/mc/logs:/mc/logs:ro` 并把 `log_path` 写成容器内路径）、网络能到 RCON 端口（同机可用 `--network host`）、密钥用 `-e` 或 env-file 注入。

### 11.1 前台 / 脚本启动（调试用）

```bash
cd /opt/y33bot
set -a; . ./.env-like-file; set +a          # 或平时就在 shell 里 export
.venv/bin/python -m y33bot run --config config.toml
```

后台跑（机器重启不会自动拉起，仅临时用）：

```bash
nohup .venv/bin/python -m y33bot run --config config.toml > y33bot.out 2>&1 &
```

`pm2` 等价写法（若你已经在用 pm2 管别的东西）：

```bash
pm2 start .venv/bin/python --name y33bot -- -m y33bot run --config config.toml
```

### 11.2 Linux（systemd，推荐）

`/etc/y33bot.env`（只放密钥，注意 systemd 的 `KEY=value` 格式，不要写 `export`）：

```ini
QQ_BOT_APP_ID=你的AppID
QQ_BOT_APP_SECRET=你的AppSecret
MC_RCON_PASSWORD_MAIN=你的RCON密码
```

`/etc/systemd/system/y33bot.service`：

```ini
[Unit]
Description=Y33-Bot (Minecraft <-> QQ bridge)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mcbot
WorkingDirectory=/opt/y33bot
EnvironmentFile=/etc/y33bot.env
ExecStart=/opt/y33bot/.venv/bin/python -m y33bot run --config /opt/y33bot/config.toml
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo chmod 600 /etc/y33bot.env
sudo systemctl daemon-reload
sudo systemctl enable --now y33bot
systemctl status y33bot
journalctl -u y33bot -f          # 看 [启动] / [群消息] / [RCON …] 这些行
```

注意事项：`User=mcbot` 必须能**读** `log_path` 指向的文件（把该用户加进 MC 所在组，或用 ACL）；`paths.bindings` / `paths.state` 写在 `WorkingDirectory` 下（`WorkingDirectory` 之外的目录要保证可写）。

> 本节是模板：本次验证在 Windows 11 上完成，systemd 单元未在本机实跑，首次部署请用 `sudo systemd-analyze verify /etc/systemd/system/y33bot.service` 校验并按现场权限调整。

### 11.3 Windows（任务计划程序 / nssm）

密钥建议设成**机器级环境变量**（`setx /M QQ_BOT_APP_ID xxx`，新开的进程才能看到），或交给 nssm 注入：

- **任务计划程序**：「常规」勾选「不管用户是否登录都要运行」+「使用最高权限运行」；「操作」→ 启动程序 = `C:\y33bot\.venv\Scripts\python.exe`，参数 = `-m y33bot run --config C:\y33bot\config.toml`，「起始于」= `C:\y33bot`；「设置」勾选「如果任务失败，按以下频率重新启动」。
- **nssm**（把它注册成 Windows 服务，开机自启）：

```bat
nssm install y33bot C:\y33bot\.venv\Scripts\python.exe -m y33bot run --config C:\y33bot\config.toml
nssm set y33bot AppDirectory C:\y33bot
nssm set y33bot AppStdout C:\y33bot\y33bot.out.log
nssm set y33bot AppStderr C:\y33bot\y33bot.err.log
nssm start y33bot
```

Windows 控制台看中文乱码就先 `chcp 65001`（`mingw32-make help` 里也有这句提示）。

## 12. 备份、状态重置与日志轮转

**备份**（人工数据只有绑定表，一起备份配置最省事）：

```bash
tar czf y33bot-backup-$(date +%F).tgz config.toml data/
```

**重置运行状态但不重推历史**（推荐顺序）：

```bash
# 1) 停服务（systemd: systemctl stop y33bot）
# 2) 把要跳过的历史挪走：清空或改名 latest.log（这正是 MC 自己轮转时做的事）
: > /path/to/mc/logs/latest.log
# 3) 删掉运行状态（绑定表 data/bindings.toml 不要动，那是绑定数据）
rm data/state.json
# 4) 重新启动
```

语义说明（用仓库内 `LogWatcher` 实测）：`state.json` 不存在时偏移视为 **0**，日志里已有的行会在第一轮全部**重新推送**一次 —— 所以「只想重置状态、不想刷屏」时，必须先把 `latest.log` 清掉/改名。随后再轮询一次是 0 个事件（偏移已推进），把文件清空并写入新行会得到：

```text
[警告] 日志文件缩小（size=55 < offset=118），偏移重置为 0
```

**只想把「已读位置」对齐到当前文件末尾**（不清日志、不重推）：停服后手工把 `data/state.json` 里该服的 `log_offset` 改成 `latest.log` 的当前字节数，或直接删掉 `state.json` 并把日志文件轮转一次。

`check` 里 `[日志 main] OK … 可读，偏移 N 字节` 里的 N 就是持久化偏移（实测：把 `log_offset` 写成 100，check 就报「偏移 100 字节」）。

**日志轮转自动处理**：`latest.log` 被清空/重命名后（文件比记录的偏移小），下一轮轮询自动把偏移重置为 0 并从头读（`PLAN.md` §5 S6、`docs/smoke.md` §5）。

## 13. 常见问题

**1）`check` 里 `[RCON main] FAIL`，退出码 1**
MC 没开 RCON、端口不对或被防火墙挡了。确认 `server.properties` 里有 `enable-rcon=true` / `rcon.port` / `rcon.password`，并且 `config.toml` 的 `host`/`port` 与 `MC_RCON_PASSWORD_MAIN` 对得上。如果那行写的是 `环境变量 MC_RCON_PASSWORD_MAIN 未设置（回退变量 MC_RCON_PASSWORD 也未设置）`，那是密码没注入。

**2）`[日志 main] FAIL … 不存在（启动后会持续重试）`**
路径不对。**相对路径是按 `config.toml` 所在目录解析的**，不是按你当前所在的目录；先用 `ls` 确认那个文件真的存在。MC 还没产生 `latest.log` 也算正常：启动后会每 0.5 秒重试，文件出现时从 0 开始读。

**3）群里发了 `#消息` 但游戏里没出现**
先看这一句到底触发了哪条分支（`simulate` 与 `run` 用的是同一套逻辑）：
- 发送者没绑定 → 群里会收到 `请先使用 /bind <游戏ID> 绑定`；
- 消息不是 `#` 开头 → 日志里是 `[忽略] 非触发前缀`；
- 消息里只有图片/表情等 `<...>` 标记 → 剔除后为空，整条丢弃（这是规格要求的「只提取文字」）；
- 消息第一行才是被转发的内容（换行处截断）。

**4）游戏里说话群里没反应**
按顺序排查：① `[qq] group_openid` 是否填了 —— 留空时 MC→QQ 方向被禁用，启动时会打印一次 `[警告] [qq] group_openid 未配置，MC→QQ 方向已禁用`；② 聊天是不是以 `#` 开头（不是的话设计上就不转发）；③ 日志行是否匹配 `[log_patterns]` —— MC 版本不同日志前缀会变，改模板不用改代码；④ 是不是命中回环防护前缀（默认忽略以 `[QQ]`/`[→QQ]` 开头的聊天）。

**5）为什么重新启动后历史消息又被推了一遍**
`data/state.json` 丢了或被重置（偏移归 0）。按 §12 的顺序处理：先清空/轮转 `latest.log` 再删 `state.json`。

**6）`state.json.bak` 是怎么来的**
`state.json` 结构非法或 `version` 与程序不一致时，程序不会静默丢数据，而是把它改名成 `state.json.bak` 再重置。看一眼 `state.json.bak` 就知道旧状态里有什么。

**7）`/bind` 一直说 `游戏ID 不合法`**
游戏 ID 规则是 `^[A-Za-z0-9_]{3,16}$`（MC Java 版用户名规则）：3–16 位字母/数字/下划线。注意 `/bind` 后要带参数，只有 `/bind` 会回 `用法: /bind <游戏ID>`。

**8）群里发 `/status` 只回三行，多台服怎么看**
单服严格三行（IDEA §3.5）；多服时逐服一行再加一行总计，实测：

```text
[群消息] [服务器状态]
[群消息] main: 在线 0/20 玩家: 无
[群消息] second: 在线 0/20 玩家: 无
[群消息] 总计: 0 人在线
```

全部服都连不上时回 `[服务器状态] 服务器离线`。

**9）群里发消息为什么偶尔不回 / `run` 报「QQ 网关启动失败」**
QQ 官方约束：被动回复只在收到事件后的短窗口内有效（本项目的被动回复都带 `msg_id` + `msg_seq=1`），主动消息（进服退服、离线提示）有频控。按规格本项目**失败不重试**，只记 `[错误]` 日志（主动消息的 `msg_seq` 全局递增并持久化，避免重启后重复发送）。私服场景基本不会触限。

如果是 `run` 启动就失败，看错误本身：
- `[错误] QQ 网关启动失败: {'code': 10004, 'message': '机器人不存在'}` → AppID / Secret 不对，或者环境变量没注入到**这个进程**里（本项目不读 shell 的 `.env` 文件，`export` 或进程管理器注入才行）。
- `[错误] QQ 网关异常退出: Cannot connect to host bots.qq.com:443 …` → 进程出不了网（DNS / 代理 / 防火墙）。


**10）改了 `config.toml` 为什么不生效**
没有热重载，改完要重启进程（这是规格里明确的负向项）。

**11）Python 3.14 装不上**
`requires-python = ">=3.11,<3.14"`，依赖的 wheel 在 3.14 上覆盖不稳定，所以显式设了上限。用 3.11–3.13。

**12）`make: command not found`**
`Makefile` 只是便捷入口，Windows 上可以装 `mingw32-make` 并用 `mingw32-make <目标>`，或者直接用等价命令：

| make 目标 | 等价命令 |
|---|---|
| `make setup` | `bash scripts/dev_setup.sh` |
| `make check` | `.venv/bin/python -m y33bot check --config config.toml` |
| `make run` | `.venv/bin/python -m y33bot run --config config.toml` |
| `make test` | `.venv/bin/python -m pytest` |
| `make coverage` | `.venv/bin/python -m pytest --cov=y33bot --cov-report=term-missing` |
| `make lint` | `.venv/bin/python -m ruff check .` + `.venv/bin/python -m ruff format --check .` |

## 14. 测试、检查与验收记录

```bash
python -m pytest -q                                       # 单元 + 端到端（全程离线，不需要 MC/QQ）
python -m pytest -q --cov=y33bot --cov-report=term-missing # 带覆盖率
python -m ruff check . && python -m ruff format --check .  # 静态检查与格式
```

在 v0.1.0 这一提交上，全新克隆实测：`214 passed`、覆盖率 `TOTAL 90%`（CI 门槛 `--cov-fail-under=70`）、`ruff check .` 与 `ruff format --check .` 全过（数字会随后续新增测试变大）。测试全程离线：RCON 用内存假服务端、QQ 用假网关、日志用临时文件。

- 逐条手工自测（S1–S4、S6 的真机输出）：[`docs/smoke.md`](docs/smoke.md)
- 端到端验收记录（每条含命令 / 实际输出 / 结论）：`docs/acceptance.md`
- 真实端到端（S5：真 QQ 群 + 真 MC 服）必须真机执行，步骤见 [`PLAN.md`](PLAN.md) §5。
- CI：`.github/workflows/ci.yml`（push 与 PR）→ 装依赖 → 无密钥扫描 → `ruff check` → `ruff format --check` → 入口冒烟 → `pytest`（含覆盖率门槛）。

## 15. 验证方式

本文所有命令与输出均在**全新 `git clone` 出来的目录**中执行并原样粘贴：Windows 11 + git-bash + Python 3.12.10（与 CI 一致），RCON 侧用一个本地最小 RCON 服务端（仅用于验证，不在仓库内），QQ 侧全程离线。因此文中出现的「群里会收到 …」这类文案来自 `simulate`（与 `run` 共用同一套 `bridge` 逻辑）与 `docs/smoke.md` 的真机记录，而不是凭空写的预期值。

## 许可

MIT，见 [`LICENSE`](LICENSE)。
