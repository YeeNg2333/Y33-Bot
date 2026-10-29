#!/usr/bin/env bash
# 原版矩阵 · 无头客户端不可用版本的补充用例（卡 t_ac457fe1）
# 用法: bash ~/mc-test/vanilla-synthetic.sh <MC版本> <slot>
# 依据: docs/smoke.md §5 / PLAN.md S6 的手工法 —— 往 logs/latest.log 追加“真实格式”的日志行，
#       让生产 LogWatcher 真读、真解析、真投递；用于 mineflayer 不支持的版本（26.2+）。
set -u
. ~/y33-env.sh

VER="${1:?用法: vanilla-synthetic.sh <MC版本> <slot>}"
SLOT="${2:?用法: vanilla-synthetic.sh <MC版本> <slot>}"
BOT="$HOME/Y33-Bot"
PY="$BOT/.venv/bin/python -m y33bot"
NAME="v$(printf '%s' "$VER" | tr '.-' '__')"
ARTS="$HOME/mc-test/artifacts/vanilla/$VER"
mkdir -p "$ARTS"
echo "===== 合成日志行补充用例：$VER 开始 $(date '+%F %T %Z') ====="

~/mc-test/new-vanilla.sh "$VER" "$SLOT" 2>&1 | sed 's/^/  /'
. "$HOME/mc-test/vanilla/$VER/instance.env"
CONF="$BOT/config-vanilla-$VER.toml"
[ -f "$CONF" ] || { echo "缺少 $CONF（先跑 vanilla-matrix.sh）"; exit 1; }

tmux kill-session -t "$MC_TMUX" 2>/dev/null || true
: > "$MC_DIR/console.out.log"
BEFORE=0; [ -f "$MC_LOG" ] && BEFORE=$(grep -ac 'Done (' "$MC_LOG")
tmux new -d -s "$MC_TMUX" "cd $MC_DIR && ./start.sh 2>&1 | tee -a console.out.log"
for i in $(seq 1 120); do
  N=0; [ -f "$MC_LOG" ] && N=$(grep -ac 'Done (' "$MC_LOG")
  if [ "$N" -gt "$BEFORE" ] && ss -tln | grep -q ":$MC_RCON_PORT "; then break; fi
  sleep 3
done
echo "服务端就绪：$(grep -a 'RCON running on' "$MC_LOG" | tail -1)"

# 真实玩家进服/退服/聊天行（格式取自窗口内实测：Server thread + [Not Secure] 前缀）
: > "$MC_LOG"
printf '%s\n' \
  "[16:00:01] [Server thread/INFO]: Steve[/127.0.0.1:50001] logged in with entity id 10 at (0.5, 64.0, 0.5)" \
  "[16:00:01] [Server thread/INFO]: Steve joined the game" \
  >> "$MC_LOG"

cd "$BOT"
rm -f "$ARTS/run-synth.out"
$PY run --verbose --config "$CONF" > "$ARTS/run-synth.out" 2>&1 &
BOTPID=$!
sleep 12
grep -aE '\[启动\]' "$ARTS/run-synth.out" || true

echo "--- 追加：普通聊天 / # 聊天 / 退服 / 再进服 ---"
printf '%s\n' \
  "[16:00:05] [Server thread/INFO]: [Not Secure] <Steve> 合成行：普通聊天（不该被转发）" \
  "[16:00:06] [Server thread/INFO]: [Not Secure] <Steve> #合成行：带井号聊天（应被转发）" \
  "[16:00:08] [Server thread/INFO]: Steve lost connection: Disconnected" \
  "[16:00:08] [Server thread/INFO]: Steve left the game" \
  >> "$MC_LOG"
sleep 8
echo "--- 轮转（S6）：清空 latest.log 后再追加一行进服 ---"
: > "$MC_LOG"
printf '%s\n' "[16:00:20] [Server thread/INFO]: Alex joined the game" >> "$MC_LOG"
sleep 8
kill -TERM "$BOTPID" 2>/dev/null || true
wait "$BOTPID"; echo "bot exit=$?"
tr -d '\000' < "$ARTS/run-synth.out" > "$ARTS/run-synth.clean" && mv "$ARTS/run-synth.clean" "$ARTS/run-synth.out"
echo "--- run-synth.out 全量 ---"
cat "$ARTS/run-synth.out"

echo "--- 收尾 ---"
tmux send-keys -t "$MC_TMUX" 'stop' Enter 2>/dev/null || true
for i in $(seq 1 60); do tmux has-session -t "$MC_TMUX" 2>/dev/null || break; sleep 2; done
tmux has-session -t "$MC_TMUX" 2>/dev/null && tmux kill-session -t "$MC_TMUX" 2>/dev/null
tr -d '\000' < "$MC_LOG" > "$ARTS/latest-log-synth.txt" 2>/dev/null || true
tr -d '\000' < "$MC_DIR/console.out.log" > "$ARTS/console-synth.txt" 2>/dev/null || true
rm -rf "$MC_DIR/libraries" "$MC_DIR/world" "$MC_DIR/console.out.log" "$MC_DIR/logs" "$MC_DIR/server.jar"
df -h / | tail -1
echo "===== 合成日志行补充用例：$VER 结束 $(date '+%F %T %Z') ====="
