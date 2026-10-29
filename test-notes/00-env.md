# 00 · 测试环境基座（卡 t_a4c6c3ae）

> 本文件是**后续所有实机测试卡的公共前提**：JDK、Python、Y33-Bot 本体、MC 服务端实例约定、
> 端口分配表、测试脚本命令模板、以及本卡跑出来的冒烟结果。文中的每条输出都是在这台测试机上
> 真实执行后粘贴的（原始制品见 `test-notes/artifacts/00-env/`）。
> 卡内约束：本卡**只搭环境 + 冒烟**，不做问题评估、不改项目代码。

---

## 0. 验收对照（卡 t_a4c6c3ae）

| 验收项 | 要求 | 实测结果 | 证据 |
|---|---|---|---|
| `java -version` 显示 21 | JDK21 装在用户目录、JAVA_HOME/PATH 配好 | ✅ `openjdk version "21.0.12.1"`（Temurin），`javac` 也在；写入 `~/y33-env.sh` 并由 `~/.bashrc` 加载 | §3、§7-1 |
| MC 服务端可正常启动 | 原版服务端能起、RCON 可连 | ✅ 原版 **1.21.11** 9s 起完，`RCON running on 0.0.0.0:25700`；原版 **26.3**（Java 25）3.6s 起完 | §5、§7-2/7-9 |
| 机器人能连上服务端 | y33bot 真连 RCON（真发命令、真读响应） | ✅ `check` 全 OK 退出码 0；真 `tellraw` 注入；真 `/list` 往返解析出 `在线: 0/20` | §7-3/4/5 |
| 脚本能正常执行与退出 | 命令可复制执行、退出码符合契约 | ✅ `run` 真连 QQ 网关后 SIGTERM 优雅退出 `exit=0`；`check=0`、`simulate=0` | §7-6 |
| 端口 / 目录分配表 | 明确写清，后续任务可直接复用 | ✅ §5 端口表 + 目录模板 + `instance.env` | §5 |
| 后续任务无需再动环境 | 兄弟卡复制命令即用 | ✅ 见 §6 命令模板；已建 2 个可复用实例 | §5/§6 |

**额外收获（供兄弟卡直接用）**：装好了 JDK 25（26.x 需要）、Python 3.12、无头 MC 客户端（mineflayer），
并在冒烟中拿到一条**真机现场证据**：原版 1.21.11 的聊天日志行格式与项目默认 `chat` 模板不匹配（§7-10）。

---

## 1. 服务器与账号

| 项 | 实测 |
|---|---|
| 入口 | `ssh hermes@10.1.1.4`（密码 = `hermes`，`10.1.1.4` 可达且延迟 0ms） |
| 系统 | Rocky Linux 9.7 (Blue Onyx)，kernel 5.14.0-611，hostname `localhost.localdomain` |
| 资源 | 2 vCPU / 内存 **2.6Gi**（可用约 900Mi）/ `/` 17G 已用 15G（**可用约 2.5G**） |
| 时区 / 语言 | `CST`（`2026-10-18 14:30:20 CST`）、`LANG=zh_CN.UTF-8` |
| 权限 | **无 sudo**（`sudo` 需要密码），全部装 `~` 下 |
| 已有服务 | 1panel/docker；已在听的端口 `22 111 5432 9090 3306 25555` —— **25555 被占用，端口表故意避开 255xx 老段** |

本卡所有 SSH 操作是通过本机 `paramiko` 脚本完成的（密码只在脚本里，未写入仓库、未打印）。

## 2. 出网能力（决定后面各卡能下什么）

| 目标 | 结果 | 说明 / 替代 |
|---|---|---|
| `mirrors.tuna.tsinghua.edu.cn`（Adoptium / miniconda / nodejs / pypi） | ✅ **约 7 MB/s** | JDK、Python、Node 全部走这里 |
| `piston-meta.mojang.com` / `piston-data.mojang.com` | ✅ | 版本清单与 `server.jar` |
| `meta.fabricmc.net` / `files.minecraftforge.net` / `maven.minecraftforge.net` / `repo1.maven.org` | ✅ | Fabric / Forge 装机没问题 |
| `maven.neoforged.net` | ❌ 443 超时 | **NeoForge 卡的第一道坎**：官方 maven 不通，需要镜像/代理方案 |
| `github.com:443`（含 `git clone`） | ❌ 连接被拒 | 但 `codeload.github.com` ✅（可下 tar.gz）、`raw.githubusercontent.com` ✅、`gh-proxy.com` ✅（慢，实测 ~270KB/s） |
| `registry.npmjs.org` / `registry.npmmirror.com` | ✅ | mineflayer 安装走 npmmirror |
| `pypi.org` + `pypi.tuna.tsinghua.edu.cn` | ✅ | 已把 tuna 写进 `~/.pip/pip.conf` |

## 3. Java 工具链

| 路径 | 版本 | 用途 |
|---|---|---|
| `~/jdk-21` | **Temurin 21.0.12.1+1 LTS**（`java` + `javac`） | **默认**（`JAVA_HOME`/`PATH` 指向它） |
| `~/jdk-25` | **Temurin 25.0.4.1+1 LTS**（`java` + `javac`） | 26.x 专用，`y33java 25` 切换 |
| `/usr/bin/java` | OpenJDK **1.8**.0_504 | 系统自带，**不要用** |
| `/usr/lib/jvm/java-21-openjdk-*` | 只有 JRE（无 `javac`） | 也不要用 |

`~/y33-env.sh`（mode 600，`~/.bashrc` 会自动 source，**非交互 ssh 要手动 `. ~/y33-env.sh`**）提供：

```bash
. ~/y33-env.sh          # JAVA_HOME=~/jdk-21, PATH, Y33_* 变量，并自动载入 ~/.env
y33java 21 | y33java 25 # 切换 JAVA_HOME/PATH（打印切换后的 java -version）
y33keys                 # 载入 ~/.env 并打印「已载入哪些变量名」（不打印值）
```

实测：

```
$ java -version
openjdk version "21.0.12.1" 2026-08-18 LTS
$ y33java 25
openjdk version "25.0.4.1" 2026-08-18 LTS
```

**近两年各版本要求的 Java（从 Mojang 版本 JSON 的 `javaVersion` 抓取，已写入 `~/mc-test/versions.tsv`）**：

| MC 版本 | 发布时间 | 需要 Java |
|---|---|---|
| 1.21.2 / 1.21.3 / 1.21.4 / 1.21.5 / 1.21.6 / 1.21.7 / 1.21.8 / 1.21.9 / 1.21.10 / 1.21.11 | 2024-10 → 2025-12 | **21** |
| 26.1 / 26.1.1 / 26.1.2 / 26.2 / 26.3 | 2026-03 → 2026-09 | **25** |

> 「近两年 = 2024-10-18 之后」；`1.21.0`(2024-06)、`1.21.1`(2024-08) 在窗口外。
> 新版本号从 26.x 起是「年份.序号」，所以 **x.xx.0 形态的版本 = 26.1 / 26.2 / 26.3（都要 Java 25）** —— 这就是本卡额外装 JDK25 的原因。
> 当前最新正式版：**26.3**（2026-09-15），最新快照 `26.4-snapshot-4`。

## 4. Python 与 Y33-Bot 本体

| 项 | 实测 |
|---|---|
| 系统 python | `python3 = 3.9.23`（**不满足** `requires-python >=3.11,<3.14`；`pip3` 不存在，`ensurepip` 可用） |
| 测试用 Python | `~/py312` = Miniconda3-py312 24.11.1 → **Python 3.12.8**（`~/py312/bin/python`，537M） |
| 项目目录 | `~/Y33-Bot`（源码 **f7fd5cb**，从本卡工作区打包上传；未带 `.git`） |
| 虚拟环境 | `~/Y33-Bot/.venv`（由 `~/py312/bin/python -m venv` 创建，装了 `requirements-dev.txt` + `pip install -e .`） |
| 版本自检 | `y33bot 0.1.0` |
| 单元测试 | `~/Y33-Bot/.venv/bin/python -m pytest -q` → **381 passed in 14.71s**（与本地/CI 数字一致） |
| 密钥 | `~/.env`（mode 600）：`QQ_BOT_APP_ID`(10) / `QQ_BOT_APP_SECRET`(32) / `MC_RCON_PASSWORD`(24，本卡生成) —— **值不在任何文档里抄写** |

配置文件（都在 `~/Y33-Bot/`，`config*.toml` 已被 `.gitignore` 忽略）：

| 文件 | 用途 |
|---|---|
| `config.toml` | 基准配置：`main` → 原版 1.21.11（RCON 25700），`group_openid` 留空 |
| `config-26.3.toml` | `v263` → 原版 26.3（RCON 25701） |
| `config-e2e.toml` | **假 `group_openid`**，用来让 MC→QQ 生产链路真跑（见 §7-8） |
| `config-fix.toml` | 与 e2e 相同，但把 `chat` 模板放宽（见 §7-10） |

**两个坑（后续卡必读）**：

1. `~/.env` 原本**没有收尾换行**，直接 `>>` 追加会把新变量粘到上一行（本卡第一次就踩了：`QQ_BOT_APP_SECRET` 变成 73 字符）。
   已修好并留证 `~/.env.bak-before-newline-fix`；`new-vanilla.sh` 里也加了「先补换行」的防御。
2. **多个配置文件共用 `data/state.json` 会互相污染日志偏移**。本卡给每个配置单独的状态文件（`state-26.3.json` / `state-e2e.json`…）。
   新配置请照抄：`[paths] state = "data/state-<名字>.json"`。
3. **跑 `pytest` 前要先把 RCON 密码变量摘掉**：`tests/test_cli.py::test_check_reports_missing_rcon_password`
   只 `delenv("MC_RCON_PASSWORD_MAIN")`，而代码会**回退**到 `MC_RCON_PASSWORD`（A18，设计如此）；
   shell 里 `export` 了 `MC_RCON_PASSWORD` 时这条用例就会失败。实测：

   ```bash
   $ .venv/bin/python -m pytest -q                                        # 带 MC_RCON_PASSWORD → 1 failed, 380 passed
   $ env -u MC_RCON_PASSWORD -u MC_RCON_PASSWORD_MAIN .venv/bin/python -m pytest -q   # → 381 passed（与 CI 一致）
   ```
   这是**测试环境假设**，不是产品缺陷；`y33-env.sh` 会替你 export 它，所以跑单测时显式 `env -u`。

---

## 5. MC 实例约定：目录、端口、启动

### 5.1 目录模板

```
~/mc-test/
  versions.tsv            # id / 发布日期 / 需要的 Java / 版本 JSON / server.jar URL / sha1 / size
  mkversions.py           # 重新生成 versions.tsv（python3 直跑，无需第三方库）
  new-vanilla.sh          # 建/复用原版实例（按版本自动挑 JDK、分配端口、写 start.sh+instance.env）
  smoke.sh                # 冒烟全流程脚本（本卡用的那份，可照抄改端口/版本）
  client/client.js        # 无头 MC 客户端（mineflayer），真进服/真聊天/真退服
  vanilla/1.21.11/        # ← 已建实例（slot 0）
  vanilla/26.3/           # ← 已建实例（slot 1）
  <family>/<version>/     # 其余族按同样模板（fabric / forge / neoforge）
```

单个实例目录里的内容：

```
server.jar  eula.txt  server.properties  start.sh  instance.env  logs/latest.log  console.out.log
```

`instance.env`（`new-vanilla.sh` 生成，直接 `.` 它就能拿到全部变量）：

```bash
. ~/mc-test/vanilla/1.21.11/instance.env
# MC_VERSION / MC_FAMILY / MC_DIR / MC_GAME_PORT / MC_RCON_PORT / MC_TMUX / JAVA_HOME / MC_LOG
```

### 5.2 端口分配表（本卡定稿，兄弟卡照用，不要另起一套）

每个族分 **10 个 slot（0–9）**，规则：**游戏端口 = 族基址 + slot，RCON 端口 = 族基址 + 100 + slot**。

| 加载器 / 族 | 目录 | 游戏端口 | RCON 端口 | 已占用 |
|---|---|---|---|---|
| 原版 Vanilla | `~/mc-test/vanilla/<版本>` | **25600–25609** | **25700–25709** | slot 0 = 1.21.11（25600/25700）；slot 1 = 26.3（25601/25701） |
| Fabric | `~/mc-test/fabric/<版本>` | **25610–25619** | **25710–25719** | 空 |
| Forge | `~/mc-test/forge/<版本>` | **25620–25629** | **25720–25729** | 空 |
| NeoForge | `~/mc-test/neoforge/<版本>` | **25630–25639** | **25730–25739** | 空 |

- 为什么不从 25565/25575 开始：机器上已有进程占了 **25555**，整个 255xx 段一律避开，减少冲突面。
- slot 建议按各自 `0X-*.md` 里版本清单的顺序分配；**同一个 slot 不要跨族复用目录之外的资源**（端口已经隔开）。
- 给机器人配 `[[mc_servers]]` 时 `port` 填 **RCON 端口**（不是游戏端口）。

### 5.3 `server.properties` 约定（每个实例一致）

```properties
enable-rcon=true
rcon.port=<25700+slot>
rcon.password=<~/.env 的 MC_RCON_PASSWORD>
server-port=<25600+slot>
online-mode=false            # 离线模式，任何测试客户端都能进；旁边有 WARN 是正常的
motd=Y33 smoke <版本>
max-players=20
view-distance=4              # 2 vCPU/2.6G 的机器，别开大
simulation-distance=4
spawn-protection=0
pause-when-empty-seconds=0   # 1.21.2+ 默认 60s 空服自动暂停，测试机关掉更可预测
```

- **RCON 密码统一用 `~/.env` 的 `MC_RCON_PASSWORD`**；`config.toml` 里写 `password_env = "MC_RCON_PASSWORD_MAIN"` 时该变量不存在会**自动回退** `MC_RCON_PASSWORD`，所以后续卡不用为每个实例造密码。
- 服务端首次启动会把缺失的键按默认值补写进 `server.properties`（例如自己加上 `pause-when-empty-seconds=60`），改完 key 记得重启进程。
- 日志固定是 `<实例目录>/logs/latest.log`。**MC 启动时会轮转**：旧内容进 `logs/2026-10-18-N.log.gz`，`latest.log` 重新开始 —— 这正是 `PLAN.md` S6 的场景。

### 5.4 启停命令模板

```bash
# 启动（tmux 会话名把 '.' 换成 '_'：mc-vanilla-1.21.11 → mc-vanilla-1_21_11）
tmux new -d -s mc-vanilla-1_21_11 "cd ~/mc-test/vanilla/1.21.11 && ./start.sh 2>&1 | tee -a console.out.log"

# 等就绪（看日志 + 端口，别只看日志：日志启动时会轮转，容易被旧行骗到）
for i in $(seq 1 80); do grep -q 'Done (' ~/mc-test/vanilla/1.21.11/logs/latest.log && ss -tln | grep -q ':25700' && break; sleep 3; done

# 停止（优雅，会落盘世界）
tmux send-keys -t mc-vanilla-1_21_11 'stop' Enter

# 看状态
tmux ls; ss -tln | grep -E ':256[0-9][0-9]|:257[0-9][0-9]'
```

### 5.5 无头 MC 客户端（真玩家进服/聊天/退服）

`~/mc-test/client/`（Node v24.1.0 + mineflayer，`minecraft-data` 支持到 **26.1**）：

```bash
export PATH="$HOME/node/bin:$PATH"
cd ~/mc-test/client
node client.js 127.0.0.1 25600 Steve      # host port username（auth=offline）
# [client] 已 spawn（进服成功），版本协商: 1.21.11
# 会依次发一条普通聊天、一条 '#' 聊天，然后退出
```

用途：**造出真实的 `joined the game` / `<Steve> 消息` / `left the game` 日志行**，让 MC→QQ 方向的测试不再只能靠 `simulate`。
（本卡实测：1.21.11 可进、可聊天；26.3 未测，因为 mineflayer 目前最高到 26.1。）

### 5.6 资源预算（重要）

| 资源 | 实测 | 结论 |
|---|---|---|
| 内存 | 总 2.6Gi；一个原版实例 RSS ≈ **717MB** | **同一时刻只跑 1 个实例**（2 个就会开始换页/抢内存） |
| 磁盘 | 可用 **约 2.5G** | 一个原版实例 ≈ 110M（jar 56M + 解压的 libraries 40M + world 5M）；Forge/NeoForge 会更大。**测完就清**（§9） |
| CPU | 2 vCPU | 服务端启动（含解压）≈ 9s，够用 |

---

## 6. 测试脚本 / 命令模板（复制即用）

```bash
# ── 0) 每个非交互 ssh 会话第一件事 ──────────────────────────────
. ~/y33-env.sh                       # JAVA_HOME/PATH/Y33_*，并载入 ~/.env（QQ 密钥 + RCON 密码）

# ── 1) 环境自检（配置 / QQ 真探活 / RCON 真连 / 日志可读 / 绑定表） ──
cd ~/Y33-Bot
.venv/bin/python -m y33bot check --config config.toml
.venv/bin/python -m y33bot check --config config.toml --no-probe   # 离线/不联网时用

# ── 2) QQ→MC：绑定 + 真 RCON 注入（去掉 --dry-run 就是真发） ─────
.venv/bin/python -m y33bot bind set 1A2B3C4D Steve --config config.toml
.venv/bin/python -m y33bot simulate group-message --openid 1A2B3C4D --content '#你好' --config config.toml
.venv/bin/python -m y33bot simulate group-message --openid 1A2B3C4D --content '/status' --config config.toml

# ── 3) MC→QQ：单行日志事件（--dry-run 只打印，不发网络） ─────────
.venv/bin/python -m y33bot simulate log-event --server main \
  --line '[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好' --dry-run --config config.toml

# ── 4) 常驻跑一段（真连 QQ 网关），Ctrl+C/SIGTERM 退出 ───────────
.venv/bin/python -m y33bot run --config config.toml > run.out 2>&1 &
BOT=$!; sleep 12; kill -TERM $BOT; wait $BOT; echo "exit=$?"; cat run.out
# 启动成功判据：[启动] QQ 网关已连接 / [启动] QQ 网关就绪 / [启动] 日志监听已启动: main

# ── 5) 冒烟一键（启动服务端 → check → 真注入 → 真往返 → run+真客户端 → 停服） ──
bash ~/mc-test/smoke.sh 2>&1 | tee ~/mc-test/smoke-1.21.11.log

# ── 6) 别的版本/族：先建实例再照抄配置 ─────────────────────────
~/mc-test/new-vanilla.sh 1.21.4 2            # 原版 1.21.4 → 游戏 25602 / RCON 25702
# Fabric/Forge/NeoForge: 用官方 installer 装到 ~/mc-test/<family>/<版本>/，
#   server.properties 里填本族端口（§5.2）+ rcon.password=$MC_RCON_PASSWORD，
#   启动脚本里用 `y33java 21|25` 选对 JDK、`-Xms512M -Xmx1024M`

# ── 7) 项目自带单测（离线跑；注意先摘掉 RCON 密码变量，见 §4 坑 3） ──
env -u MC_RCON_PASSWORD -u MC_RCON_PASSWORD_MAIN .venv/bin/python -m pytest -q   # 381 passed
```

给新实例配机器人（关键是 `port` = RCON 端口、`state` 用独立文件）：

```toml
[[mc_servers]]
name = "vanilla1214"
host = "127.0.0.1"
port = 25702
password_env = "MC_RCON_PASSWORD_MAIN"   # 回退到 ~/.env 的 MC_RCON_PASSWORD
log_path = "/home/hermes/mc-test/vanilla/1.21.4/logs/latest.log"
```

---

## 7. 冒烟结果（命令 + 实测输出 + 结论）

原始制品：`test-notes/artifacts/00-env/`

| 文件 | 内容 |
|---|---|
| `smoke-1.21.11.txt` | 冒烟全流程原始输出（本文件 §7-2/3/4/5/7/8/10 的来源） |
| `vanilla-1.21.11-latest-log.txt` | 服务端真实 `latest.log`（含真玩家进服/聊天/退服行） |
| `vanilla-1.21.11-console.txt` | 服务端控制台输出（含启动全过程） |
| `run-e2e.out` | `y33bot run` 的真实输出（QQ 网关连接 + 平台 400 错误） |

> 命名约定（后续卡注意）：
> 1. 仓库 `.gitignore` 里有 `*.log` / `logs/`，**原始日志制品要入库就得改名成 `.txt`**（本卡就是这么做的），否则只能留在服务器 `~/mc-test/` 下用路径引用。
> 2. `.gitignore` 第 8 行是 `ENV/`，而 Windows 上 git 默认 `core.ignorecase=true` ⇒ **任何叫 `env` / `Env` 的目录都会被忽略**。
>    本卡一开始把制品放在 `artifacts/env/`，`git add` 静默不入库（`git status --ignored` 才看得到 `!! test-notes/artifacts/`），
>    已改名 `artifacts/00-env/`。后续卡别用 `env` 当目录名（用 `vanilla` / `fabric` / `forge` / `neoforge` 就好）。
> 服务器上的同一份制品放在 `~/Y33-Bot/test-notes/artifacts/00-env/`。

### 7-1 JDK（验收项）

```
$ java -version
openjdk version "21.0.12.1" 2026-08-18 LTS
OpenJDK Runtime Environment Temurin-21.0.12.1+1 (build 21.0.12.1+1-LTS)
$ javac -version
javac 21.0.12.1
```
✅ 通过。（`y33java 25` 切到 Temurin 25.0.4.1 也实测通过。）

### 7-2 原版服务端启动（1.21.11，JDK21）

```
启动耗时: 9s
[14:29:54] [Server thread/INFO]: Done (0.339s)! For help, type "help"
[14:29:54] [Server thread/INFO]: Starting remote control listener
[14:29:54] [Server thread/INFO]: RCON running on 0.0.0.0:25700
LISTEN 0 4096 *:25600 *:*
LISTEN 0  50 *:25700 *:*
```
✅ 通过。9s 是 `smoke.sh` 实测（libraries 已存在）；另一次在 `libraries/` 被删掉后重启，
日志时间戳 `14:25:00` 起、`14:25:08` Done —— 即**重新解压 libraries 也只要 8s**。

### 7-3 `check`（真 QQ 探活 + 真 RCON）

```
$ .venv/bin/python -m y33bot check --config config-e2e.toml
[配置] OK config-e2e.toml 解析成功，1 个 MC 服
[QQ] OK access_token 获取成功（有效期 3195s），app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON main] OK /list -> There are 0 of a max of 20 players online:
[日志 main] OK /home/hermes/mc-test/vanilla/1.21.11/logs/latest.log 可读，偏移 2713 字节
[绑定] OK 1 条
OK
check exit=0
```
✅ 通过：**`.env` 里的 QQ 凭据在这台机器上真的能用**（`access_token` 拿到了）。

### 7-4 QQ→MC 真注入（无 `--dry-run`）

```
[RCON main] tellraw @a {"text":"[QQ] Steve: 冒烟：真 RCON 注入"}
exit=0
```
✅ 通过（无 `[警告] RCON … 命令失败`，即服务端接受了这条命令）。

### 7-5 QQ→MC 真往返（`/status` → 服务端 `/list`）

```
[RCON main] /list
[群消息] [服务器状态]
[群消息] 在线: 0/20
[群消息] 玩家: 无
exit=0
```
✅ 通过：三行内容全部来自**服务端真实响应**的解析（不是 dry-run 的假数据）。

### 7-6 `run` 真连 QQ 网关 + 优雅退出

```
[启动] y33bot 0.1.0（1 个 MC 服）
[启动] 日志监听已启动: main
[botpy] 登录机器人账号中...
[启动] QQ 网关已连接
[botpy] 机器人「y33-test」启动成功！
[启动] QQ 网关就绪
[停止] 收到退出信号
[停止] 正在关闭…
[停止] 已退出
bot exit=0
```
✅ 通过。机器人在这台机上叫 **「y33-test」**，SIGTERM 退出码 0（符合契约；不是 BUG-001 那种运行期断开）。

### 7-7 无头客户端真进服/聊天/退服 → 真实日志行

```
[client] 已 spawn（进服成功），版本协商: 1.21.11
[14:30:07] [Server thread/INFO]: Steve[/127.0.0.1:33502] logged in with entity id 90 at (-5.5, 79.0, 13.5)
[14:30:07] [Server thread/INFO]: Steve joined the game
[14:30:08] [Server thread/INFO]: [Not Secure] <Steve> 大家好，这是普通聊天（不该被转发）
[14:30:09] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
[14:30:11] [Server thread/INFO]: Steve lost connection: Disconnected
[14:30:11] [Server thread/INFO]: Steve left the game
```
✅ 通过：后续卡可以直接产出**真实**的进服/聊天/退服日志，不必再用 `simulate` 造行。

### 7-8 MC→QQ 生产链路真跑（日志事件 → bridge → 生产 BotpyGateway → 平台）

用**假 `group_openid`**（`E2E_DUMMY_GROUP_OPENID`）故意让 MC→QQ 方向开着：

```
[错误] QQ 发送失败（不重试）: 请求的资源不存在(用户/群已注销)      ← 出现 2 次 = 进服通知 + 退服通知
（run-e2e.out 里还有 botpy 原始报文：
  https://api.sgroup.qq.com/v2/groups/E2E_DUMMY_GROUP_OPENID/messages → code 11255 / err_code 40011028）
```
✅ 通过：进服/退服事件被真的解析并真的走到了 QQ 平台（平台 400 正是「群不存在」的预期结果），
`data/state-e2e.json` 里 `msg_seq=2`、`log_offset` 追平日志大小，说明主动消息序号与偏移都正确落盘。

### 7-9 原版 26.3（Java 25，JDK25 路径）

```
Done (3.589s)! ... RCON running on 0.0.0.0:25701
[QQ] OK access_token 获取成功（有效期 4456s）…
[RCON v263] OK /list -> There are 0 of a max of 20 players online:
[RCON v263] tellraw @a {"text":"[QQ] Steve: 26.3 冒烟"}
[群消息] [服务器状态] / 在线: 0/20 / 玩家: 无
check exit=0   tellraw exit=0   status exit=0
```
✅ 通过：**26.x 需要 JDK25 这条路已经打通**，机器人对 26.3 的 RCON 也完全可用。

### 7-10 ⚠️ 真机现场证据：1.21.11 的聊天行与默认 `chat` 模板不匹配

（本卡只记录症状与现场证据；根因分析/登记由汇总卡 `t_1c0e88a4` 与各矩阵卡负责。）

**真日志行**（`vanilla-1.21.11-latest.log`，两个客户端版本都复现）：

```
[14:30:09] [Server thread/INFO]: [Not Secure] <Steve> #大家好，这是带井号的聊天（应被转发）
```

而 `config.example.toml` / `config.toml` 里的默认 `chat` 模板是：

```
\[\d{2}:\d{2}:\d{2}\] \[Async Chat Thread - #\d+/INFO\]: <(?P<player>\w+)> (?P<message>.+)
```

A/B 实测（同一条真行）：

```
[A] 默认模板 → [警告] 日志行未匹配任何模板        （无 [群消息]，即游戏内 # 聊天不会被转发）
    对照组：老格式行 '[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好' → [群消息] Steve@main: 大家好  ✅ 能匹配

[B] 放宽模板（只改配置，不改代码）：
    chat = '\[\d{2}:\d{2}:\d{2}\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\]: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)'
    真行   → [群消息] Steve@main: 大家好，这是带井号的聊天（应被转发）        ✅
    普通行 → [忽略] 聊天非 # 开头，不转发                                  ✅
    回环行 → [忽略] 回环防护：命中 ignored_chat_prefixes                    ✅
    进服行 → [群消息] Steve进入了main（模板改动不影响 join/quit）           ✅
```

**症状**：在 1.21.11 上，群里收不到游戏内 `#` 聊天（`chat` 模板匹配不上），而进出服通知正常。
**波及面**：至少 1.21.11（新线程名 `Server thread` + 新增 `[Not Secure] ` 前缀）；具体从哪个版本开始变的由矩阵卡判定。
**可用绕法**：`[log_patterns]` 本来就是「格式变了只改这里」，上面那条放宽模板已验证可用（`config-fix.toml`）。
`~/mc-test/vanilla/26.3` 的聊天行格式本卡**未验证**（mineflayer 最高到 26.1）。

### 7-11 交卡时的机器状态（收尾核对，实测）

```
$ java -version          → openjdk version "21.0.12.1" 2026-08-18 LTS
$ javac -version         → javac 21.0.12.1
$ ~/jdk-25/bin/java -version → openjdk version "25.0.4.1" 2026-08-18 LTS
$ ~/Y33-Bot/.venv/bin/python -m y33bot --version → y33bot 0.1.0
$ ls -d ~/mc-test/*/*/   → ~/mc-test/vanilla/1.21.11/、~/mc-test/vanilla/26.3/
$ 实例端口              → 25600/25700（1.21.11）、25601/25701（26.3），enable-rcon=true、online-mode=false
$ tmux ls                → no server running on /tmp/tmux-1002/default      （交卡时没有实例在跑，请自行启动）
$ ss -tln                → 无 256xx / 257xx 端口在听
$ ~/.env（600）          → QQ_BOT_APP_ID(10) / QQ_BOT_APP_SECRET(32) / MC_RCON_PASSWORD(24)
$ 资源                   → 空闲内存 881Mi；/ 可用 2.5G
$ 单测                   → 381 passed（env -u MC_RCON_PASSWORD -u MC_RCON_PASSWORD_MAIN .venv/bin/python -m pytest -q）
```

---

## 8. 已知限制 / 后续卡会碰到的墙

1. **`group_openid` 未知**：`~/.env` 只有 AppID/AppSecret；SDK（botpy 1.2.1）只有 `post_group_message` / `post_group_file`，
   **没有「列出机器人所在群」的 API**，所以拿不到群 openid。⇒ 「真群里发/收消息」这类端到端项（S5 的群侧步骤）
   需要人去群里 `@机器人` 抓一次事件、或由用户直接给出群 openid。本卡的 MC→QQ 链路只能用假群验证（§7-8）。
2. **只有无头客户端**：参数化到 26.1；26.2+ 的客户端行为（聊天日志格式）测不了。
3. **NeoForge 的 maven 不通**（§2）：NeoForge 卡需要先解决下载（镜像/代理），否则装不上。
4. **同时只能跑 1 个实例**（内存 2.6G，单实例 ~717MB），磁盘只剩 ~2.5G。
5. **本卡没有做的事**：Fabric/Forge/NeoForge 服务端实例（兄弟卡负责）；任何项目代码改动（只新增 `test-notes/`）。

## 9. 资源占用与回收

| 目录 | 占用 | 说明 |
|---|---|---|
| `~/jdk-21` | 345M | 必须保留 |
| `~/jdk-25` | 303M | 26.x 需要，必须保留 |
| `~/py312` | 537M | 项目 venv 的基座，必须保留 |
| `~/node` + `~/mc-test/client` | 194M + 468M | 无头客户端；**磁盘紧张时可删 `node_modules`（470M），只是失去真玩家能力** |
| `~/Y33-Bot` | 73M | 项目 + .venv |
| `~/mc-test/vanilla/*` | 约 114M | 两个实例（server.jar 56M+62M，libraries/world 已清） |
| `/` 可用 | **约 2.5G** | 单实例跑起来再吃 ~45M（libraries）+ ~5M（world） |

清理模板（测完一个版本就做）：

```bash
D=~/mc-test/forge/1.21.4
tmux send-keys -t mc-forge-1_21_4 'stop' Enter   # 先优雅停服
sleep 10
rm -rf "$D/libraries" "$D/world" "$D/console.out.log" "$D/logs"   # 可再生
rm -rf ~/mc-test/client/node_modules                              # 只在确实需要腾 470M 时
```

## 10. 从零重建本环境（一次性清单）

```bash
# 1) JDK21 + JDK25（tuna Adoptium → ~/jdk-21、~/jdk-25，解压即用）
# 2) Python 3.12：tuna Miniconda3-py312_*-Linux-x86_64.sh -b -p ~/py312
# 3) 项目：把工作区打包上传 → ~/Y33-Bot → ~/py312/bin/python -m venv .venv
#    .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pip install -e .
# 4) ~/.env 写 QQ_BOT_APP_ID / QQ_BOT_APP_SECRET / MC_RCON_PASSWORD（600，注意结尾换行）
# 5) ~/y33-env.sh（JAVA_HOME/PATH/Y33_*/y33keys/y33java）→ ~/.bashrc 里 source
# 6) python3 ~/mc-test/mkversions.py          # 生成 versions.tsv
# 7) ~/mc-test/new-vanilla.sh 1.21.11 0       # 建实例（自动下 jar + 校验 sha1 + 写配置）
# 8) bash ~/mc-test/smoke.sh                  # 冒烟全流程
```

---

## 11. 补记（2026-10-29 真机回归批）：实例目录「跑完即清空」+ 四族恢复配方

> 本节由汇总卡 `t_9e9040ed` 补写。来源是**连续四族回归（原版 / Fabric / Forge / NeoForge @ MC 1.21.11）**
> 中实际踩到的状态，不是模板。

### 11.1 为什么实例目录总是「跑完即清空」

§9 的清理模板（`rm -rf libraries world logs`）是每轮回归的收尾动作，跑完之后各实例会缺东西，
下一张卡**必须先补再起服**，否则 `start.sh` 直接失败：

| 族 | 清理后的残缺状态（本轮实测） | 恢复动作 |
|---|---|---|
| 原版 Vanilla | 缺 `server.jar` | 从 `piston-meta.mojang.com` 拉 manifest → `server.jar`；**sha1 `64bb6d763bed0a9f1d632ec347938594144943ed`**（本轮核过，NeoForge 卡复用的就是这一份） |
| Fabric | `fabric-server-launch.jar` 只剩 **639 字节桩**（`.fabric/` 被删） | `java -jar ~/mc-test/tools/fabric-installer-1.1.2.jar server -mcversion 1.21.11 -loader 0.19.5 -downloadMinecraft -dir <实例目录>` |
| Forge | 缺整个 `libraries/` | 官方安装器 `--installServer`；`maven.minecraftforge.net` **可达**（HTTP 200）。**注意**：`piston-data` 下 54 MB 那步会卡住 ⇒ 可复用已核的原版 jar 改名 `minecraft_server.1.21.11.jar`；被中断的安装会留**坏包** `server-1.21.11-bundled.jar`，用 `zipfile.testzip()` 扫出来删掉再重跑 |
| NeoForge | 缺 `libraries/`，且 `maven.neoforged.net` **不可达**（443 超时） | 只能用**离线打补丁安装器**：先把已核原版 jar 命名为 `minecraft_server.1.21.11.jar`，再 `java -jar ~/mc-test/neoforge/tools/nf-21.11.48-installer-patched.jar --installServer <实例目录>`；成功标志是 `libraries/net/neoforged/neoforge/21.11.48/unix_args.txt`。本轮**一次过**，未触发坏包兜底（`libraries` 134 MB，实例其余约 65 MB） |

### 11.2 本轮四族的实例坐标（照用即可）

| 族 / 版本 | 实例目录 | 游戏 / RCON | tmux 会话 | 日志 |
|---|---|---|---|---|
| 原版 1.21.11 | `~/mc-test/vanilla/1.21.11` | `25600` / `25700` | `mc-vanilla-1_21_11` | `logs/latest.log`（布局 `[HH:MM:SS] [Server thread/INFO]:`） |
| Fabric 1.21.11（loader 0.19.5） | `~/mc-test/fabric/1.21.11` | `25615` / `25715` | `mc-fabric-1_21_11` | 同上（无 logger 段） |
| Forge 61.2.0 | `~/mc-test/forge/1.21.11` | `25628` / `25728` | `mc-forge-1_21_11` | `[2910月2026 20:28:31.611] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]:` |
| NeoForge 21.11.48 | `~/mc-test/neoforge/1.21.11` | `25634` / `25734` | `mc-neoforge-1_21_11` | 同 Forge 族，加载器段是 `net.neoforged.*`（无 `cpw.mods.modlauncher`） |

### 11.3 资源与收尾（本轮实测）

- 起一个服务端约吃 700 MB；机器 2.6 GB 内存 ⇒ **四族必须串行**，一轮跑完就 `stop` + 收 tmux。
- 本轮收尾状态：四族服务端全部停服（端口无监听、`tmux ls` 无会话），可用内存 1583 → **1569 MB**，
  `/` 余量 **884 MB**（NeoForge 的 `libraries` 134 MB 与 Forge 的 173 MB 保留供后续回归，未删）。
- 产物一律落 `~/mc-test/regress/<族>-<版本>/`（`-` 连接、版本号 `.`→`_`），本仓库的
  `test-notes/regress/<族>-<版本>/artifacts/` 是**逐字副本**；`test-notes/regress/log-slice-events.txt`
  是四族事件行切片（同一时间点一次性采出）。

### 11.4 harness 的两个已知缺陷（脚本，不影响 `src/`）

1. `regress_start.sh` 起服判定：`DONE_BEFORE=$(grep -ac 'Done (' … || echo 0)` 在空日志时得到 `"0\n0"`
   → 打印 `[: 0：需要整数表达式`，判定行报「失败」而服务器其实起来了（Forge 那轮）或反过来报「成功」
   （NeoForge 那轮）。**该行两个方向都不可信**，真证据只看 `Done (…)` 行 + `ss -tln` 端口。
2. `e2e_family.sh` 的 `make_old_cfg`：Python 3.9 下 `re.sub` 传字符串替换体，旧模板里的 `\d` 被当组引用
   → `re.error: bad escape \d`，旧模板配置根本没生成。**已修**（改 `lambda`，服务器副本更新，原件备份
   `.bak-2026-10-29`）；`e2e_neg.sh` 早已是 `lambda` 写法。
