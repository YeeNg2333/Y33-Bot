# Y33-Bot
A platform-bindless MC-QQ messages sync assistant.

一个独立的 Python 服务端进程：把 Minecraft Java 版（Vanilla）服务器与 QQ 群双向打通。
MC 侧只用 **RCON 发指令** + **只读轮询 `latest.log`**，不装插件、不改服务端、不干预 MC 实例。

- 需求书（冻结）：[`IDEA.md`](IDEA.md)
- 实施计划（唯一技术依据：假设清单 / 需求映射 / 模块与签名 / CLI 契约 / 验收场景）：[`PLAN.md`](PLAN.md)

## 5 分钟跑起来（骨架阶段）

> 当前处于 `PLAN.md` §6 **T1（骨架、依赖与可运行入口）** 状态：
> 目录结构、依赖、入口、配置机制、CI 已就位；业务模块（`bridge` / `service` / `rcon` /
> `mclog` / `qq` / `commands`）只有**签名占位**，由 T2–T8 逐个填充。
> 因此现在能真正跑通的是 **入口 + 启动自检**；`bind` 与 `simulate` 会明确返回退出码 3（未实现），
> 不会“假装成功”。

```bash
git clone https://github.com/YeeNg2333/Y33-Bot.git
cd Y33-Bot

bash scripts/dev_setup.sh          # = make setup：建 .venv + 装依赖 + 生成 config.toml

source .venv/bin/activate          # Windows(git-bash)：source .venv/Scripts/activate
                                   # 不想激活也行，把下面的 python 换成 .venv/bin/python
                                   # （Windows 为 .venv/Scripts/python.exe）

export QQ_BOT_APP_ID=你的AppID      # 密钥只走环境变量（清单见 .env.example）
export QQ_BOT_APP_SECRET=你的AppSecret
export MC_RCON_PASSWORD_MAIN=你的RCON密码

python -m y33bot --version         # y33bot 0.1.0
python -m y33bot check --config config.toml
```

`check` 逐项输出健康状态（配置 / QQ 凭据 / 每服 RCON / 每服日志 / 绑定表），
末行 `OK`（退出码 0）或 `FAIL`（退出码 1）。MC 没起时的典型输出：

```text
[配置] OK config.toml 解析成功，1 个 MC 服
[QQ] OK app_id 已设置 (env QQ_BOT_APP_ID)，group_openid 已配置
[RCON main] FAIL 无法连接 127.0.0.1:25575: ...
[日志 main] OK D:/mc/server/logs/latest.log 可读，偏移 0 字节
[绑定] OK 0 条
FAIL
```

Windows（git-bash / PowerShell）的虚拟环境解释器是 `.venv/Scripts/python.exe`，
Linux/macOS 是 `.venv/bin/python`；`scripts/dev_setup.sh` 结束时会把可直接复制的命令再打印一遍。

## 常用命令

| 命令 | 作用 |
|---|---|
| `make setup` | 建 `.venv` + 装依赖 + 从 `config.example.toml` 生成 `config.toml` |
| `make check` | 启动自检（等价 `python -m y33bot check --config config.toml`） |
| `make run` | 常驻启动；骨架阶段打印启动自检后退出 0，T8 接入常驻循环 |
| `make smoke` | 入口冒烟：打印版本 + 导入核心模块 |
| `make test` / `make coverage` | `pytest` / 带覆盖率报告 |
| `make lint` / `make fmt` | `ruff check` + `ruff format --check` / 就地格式化 |

## 配置与密钥

- 配置用 TOML：模板 `config.example.toml`，复制为 `config.toml`；字段与校验规则见 `PLAN.md` §4.1。
- **仓库内不存任何真实密钥**：配置文件里只写“环境变量名”，值由进程环境注入。
- 环境变量命名：`QQ_BOT_APP_ID`、`QQ_BOT_APP_SECRET`、
  `MC_RCON_PASSWORD_<服务器名大写>`（缺失回退 `MC_RCON_PASSWORD`），见 `.env.example`。
- 绑定表 `data/bindings.toml` 与运行状态 `data/state.json` 由程序生成，已在 `.gitignore` 中忽略。

## 目录结构

```text
src/y33bot/             cli / config / models / binding / state / bridge / service
src/y33bot/rcon/        protocol（接口与异常）/ client（Valve 协议）/ pool（多服）/ fakes（替身）
src/y33bot/mclog/       patterns（模板编译）/ watcher（字节偏移增量轮询）
src/y33bot/qq/          gateway（qq-botpy 适配）/ fakes（离线替身）
src/y33bot/commands/    registry（装饰器注册表）/ builtin（/status、/bind）
tests/                  pytest（当前为 T1 骨架冒烟，T9/T10 补齐单测与端到端）
scripts/dev_setup.sh    Makefile    .github/workflows/ci.yml
```

每个模块的职责、对外接口、依赖关系与冻结签名见 `PLAN.md` §3.2 / §3.3。

## CI

`.github/workflows/ci.yml`（push 与 PR）：Python 3.12 → 装 `requirements-dev.txt` + `pip install -e .`
→ `ruff check` → `ruff format --check` → 入口冒烟（`--version`）→ `pytest`。全程离线、不需要 MC 或 QQ。

