#!/usr/bin/env bash
# E1：QQ 网关「启动」路径的重复尝试（卡 t_ac457fe1）
# 背景：1.21.8 首跑出现过 [错误] QQ 网关异常退出 / 网关启动失败: 'NoneType' object is not subscriptable
#      （botpy 打了一行「请求超时，请求连接: https://api.sgroup.qq.com/gateway/bot」）。
# 这里做 3 次冷启动尝试，记录每次「网关是否连上」与进程退出码；不依赖 MC 服务端在线。
. ~/y33-env.sh
BOT="$HOME/Y33-Bot"
PY="$BOT/.venv/bin/python -m y33bot"
ARTS="$HOME/mc-test/artifacts/vanilla/_gateway-restart"
mkdir -p "$ARTS"
cd "$BOT"
echo "===== E1 网关启动重复尝试 开始 $(date '+%F %T %Z') ====="
for i in 1 2 3; do
  OUT="$ARTS/attempt-$i.out"
  $PY run --verbose --config config-vanilla-1.21.2.toml > "$OUT" 2>&1 &
  P=$!
  sleep 14
  kill -TERM "$P" 2>/dev/null || true
  wait "$P"; RC=$?
  GW_OK=$(grep -ac '\[启动\] QQ 网关已连接' "$OUT")
  GW_FAIL=$(grep -ac '网关启动失败' "$OUT")
  echo "--- 尝试 $i：exit=$RC 网关已连接=$GW_OK 网关启动失败=$GW_FAIL ---"
  grep -aE '\[启动\]|\[错误\]|请求超时|Traceback|[A-Za-z]*Error' "$OUT" | head -12
  sleep 5
done
tr -d '\000' < /dev/null
echo "===== E1 结束 $(date '+%F %T %Z') ====="
