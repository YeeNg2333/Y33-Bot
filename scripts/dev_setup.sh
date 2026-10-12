#!/usr/bin/env bash
# 一条命令准备好开发环境：建 .venv → 装依赖（含开发依赖）→ 可编辑安装本包 → 准备 config.toml。
#
#   bash scripts/dev_setup.sh          # 或 make setup
#
# 跨平台：Linux/macOS 用 .venv/bin/python，Windows(git-bash/PowerShell) 用 .venv/Scripts/python.exe。
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN=python
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[错误] 找不到 python3 / python，请先安装 Python 3.11–3.13" >&2
  exit 1
fi

echo "[1/4] 使用解释器: $("$PYTHON_BIN" -c 'import sys; print(sys.executable, sys.version.split()[0])')"

if [ ! -d .venv ]; then
  echo "[2/4] 创建虚拟环境 .venv"
  "$PYTHON_BIN" -m venv .venv
else
  echo "[2/4] 复用已有虚拟环境 .venv"
fi

if [ -x .venv/bin/python ]; then
  VENV_PY=.venv/bin/python
elif [ -f .venv/Scripts/python.exe ]; then
  VENV_PY=.venv/Scripts/python.exe
else
  echo "[错误] 虚拟环境里找不到 python，请删除 .venv 后重试" >&2
  exit 1
fi

echo "[3/4] 安装依赖（requirements-dev.txt + 可编辑安装本包）"
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -r requirements-dev.txt
"$VENV_PY" -m pip install -e .

if [ ! -f config.toml ]; then
  echo "[4/4] 生成 config.toml（复制 config.example.toml）"
  cp config.example.toml config.toml
else
  echo "[4/4] 已存在 config.toml，保持不变"
fi

cat <<EOF

环境就绪。下一步：

  # 1) 注入密钥（不写进任何文件；.env.example 是清单模板）
  export QQ_BOT_APP_ID=你的AppID
  export QQ_BOT_APP_SECRET=你的AppSecret
  export MC_RCON_PASSWORD_MAIN=你的RCON密码

  # 2) 按实际环境改 config.toml（host/port/log_path/group_openid）

  # 3) 自检（逐项打印健康状态，退出码 0 通过 / 1 失败）
  $VENV_PY -m y33bot check --config config.toml

  # 4) 查看版本 / 常驻启动
  $VENV_PY -m y33bot --version
  $VENV_PY -m y33bot run --config config.toml

  # 5) 跑测试与 lint
  $VENV_PY -m pytest
  $VENV_PY -m ruff check .

Windows(git-bash) 下把 \`.venv/bin/python\` 换成 \`.venv/Scripts/python.exe\`。
EOF
