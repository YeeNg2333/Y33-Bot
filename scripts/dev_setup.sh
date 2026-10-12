#!/usr/bin/env bash
# 一条命令准备好开发环境（PLAN.md §2.7）
# 用法： bash scripts/dev_setup.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-.venv}"

case "$(uname -s 2>/dev/null || echo unknown)" in
  MINGW*|MSYS*|CYGWIN*) VENV_BIN="$VENV/Scripts" ;;
  *) VENV_BIN="$VENV/bin" ;;
esac

if [ ! -x "$VENV_BIN/python" ] && [ ! -x "$VENV_BIN/python.exe" ]; then
  echo "==> 创建虚拟环境 $VENV ($($PYTHON -V 2>&1))"
  "$PYTHON" -m venv "$VENV"
fi

PY="$VENV_BIN/python"

echo "==> 升级 pip"
"$PY" -m pip install --upgrade pip --quiet

echo "==> 安装运行时与开发依赖"
"$PY" -m pip install -r requirements-dev.txt --quiet
"$PY" -m pip install -e . --quiet

mkdir -p data

cat <<'EOF'

环境就绪。下一步：
  1) cp config.example.toml config.toml
  2) 设置环境变量（至少 MC_RCON_PASSWORD_MAIN）：
       export MC_RCON_PASSWORD_MAIN=你的RCON密码
  3) 自检：  $VENV_BIN/python -m y33bot check --config config.toml
  4) 启动：  $VENV_BIN/python -m y33bot run --config config.toml
  5) 跑测试：$VENV_BIN/python -m pytest -q
EOF
