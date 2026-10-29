#!/usr/bin/env bash
# Fabric 单版本完整实机测试流程（卡 t_5bccfcd8）
#
# 用法: fabric_smoke_one.sh <MC版本> <slot>
# 前提: new-fabric.sh 已建好实例；~/Y33-Bot/config-fabric-<版本>.toml 已生成（用项目默认日志模板）
# 产出: $D/artifacts/（原始制品）+ $D/artifacts/results-<版本>.txt（结构化结果行）
#
# 用例与项目文档的对应关系（docs/smoke.md S1-S6 / PLAN.md §5）：
#   T1=S1 check 自检；T2=S2 QQ→MC 绑定+真 RCON 注入（并在真客户端里核对可见）；
#   T3=S2 /status 真往返；T4=S3 MC→QQ 真玩家聊天 + 默认模板匹配；T5=S4 进出通知；
#   T6=S4 健康翻转；T7=S5 常驻 run + 真玩家 + MC→QQ 真链路；T8=S6 日志轮转
set -u
VER=${1:?用法: fabric_smoke_one.sh <版本> <slot>}
SLOT=${2:?用法: fabric_smoke_one.sh <版本> <slot>}
. "$HOME/y33-env.sh" 2>/dev/null || true
export PATH="$HOME/node/bin:$PATH"

D="$HOME/mc-test/fabric/$VER"
ARTS="$D/artifacts"; mkdir -p "$ARTS"
CFG="config-fabric-$VER.toml"
NAME="fab$(printf '%s' "$VER" | tr -d '.')"
GAME=$((25610 + SLOT))
RCON=$((25710 + SLOT))
SESS="mc-fabric-$(printf '%s' "$VER" | tr '.' '_')"
PY="$HOME/Y33-Bot/.venv/bin/python"
CLIENT="$HOME/mc-test/client/client.js"
CLIENT_HOLD="$HOME/mc-test/client/client_hold.js"
RES="$ARTS/results-$VER.txt"
JOIN_REAL="$ARTS/real-join-line-$VER.txt"
QUIT_REAL="$ARTS/real-quit-line-$VER.txt"
CHAT_REAL="$ARTS/real-chat-line-$VER.txt"
CHATPLAIN_REAL="$ARTS/real-chatplain-line-$VER.txt"
: > "$RES"

case "$VER" in
  26.2|26.3|26.4*) HAVE_CLIENT=0 ;;
  *) HAVE_CLIENT=1 ;;
esac

log()  { echo; echo "===================== $* ====================="; echo; }
mark() { echo "$1" >> "$RES"; echo ">>> [RESULT] $1"; }

cd "$HOME/Y33-Bot" || exit 1
echo "########## Fabric $VER 完整测试流程 开始 $(date '+%F %T') ##########"
echo "--- 实例静态信息 ---"
sed 's/^/  /' "$D/instance.env"
printf '  java: '; java -version 2>&1 | head -1
echo "--- 配置 ---"
grep -E 'group_openid|state|bindings|name =|port =|log_path|^chat ' "$CFG" | sed 's/^/  /'

# ---------------------------------------------------------------- T0 启动
log "T0 启动服务端（游戏 $GAME / RCON $RCON，tmux $SESS）"
tmux kill-session -t "$SESS" 2>/dev/null || true
: > "$D/console.out.log"
tmux new -d -s "$SESS" "cd $D && ./start.sh 2>&1 | tee -a console.out.log"
ok=0
for i in $(seq 1 100); do
  if grep -q 'Done (' "$D/logs/latest.log" 2>/dev/null && ss -tln | grep -q ":$RCON"; then ok=1; break; fi
  sleep 3
done
echo "等待轮次=$i 就绪=$ok"
grep -nE 'Loading Minecraft|Loading [0-9]+ mods|Done \(|RCON running' "$D/logs/latest.log" | tail -6
ss -tln | grep -E ":$GAME|:$RCON" || echo "[警告] 端口未监听"
mark "start_ok=$ok"
if [ "$ok" != "1" ]; then
  echo "--- 启动失败时的错误行 ---"
  grep -inE 'exception|error|failed|caused by|incompatible|unsupported|missing' "$D/console.out.log" | tail -30
  mark "conclusion_$VER=启动失败"
  mark "cleanup_hint=保留 $D/libraries 供排查"
  exit 0
fi

# ---------------------------------------------------------------- T1 check
log "T1 (S1) check 自检：真 QQ 探活 + 真 RCON /list"
"$PY" -m y33bot check --config "$CFG"; rc=$?
mark "check_exit=$rc"

# ---------------------------------------------------------------- T2 QQ→MC
log "T2 (S2) QQ→MC：绑定 + 真 RCON tellraw 注入（真客户端核对可见性）"
"$PY" -m y33bot bind set 1A2B3C4D Steve --config "$CFG"; echo "bind exit=$?"
"$PY" -m y33bot bind list --config "$CFG"

HOLD_OUT="$ARTS/client-hold-$VER.txt"
: > "$HOLD_OUT"
if [ "$HAVE_CLIENT" = "1" ]; then
  ( cd "$HOME/mc-test/client" && node client_hold.js 127.0.0.1 "$GAME" Watcher 30 > "$HOLD_OUT" 2>&1 ) &
  HOLDPID=$!
  sleep 12
  head -3 "$HOLD_OUT"
else
  echo "[跳过] 无头客户端不支持 $VER，跳过真客户端可见性核对"
fi

"$PY" -m y33bot simulate group-message --openid 1A2B3C4D --content '#你好' --config "$CFG"; rc=$?
mark "tellraw_exit=$rc"
sleep 3
if [ "$HAVE_CLIENT" = "1" ]; then
  if grep -q '\[QQ\] Steve: 你好' "$HOLD_OUT"; then saw=yes; else saw=no; fi
  mark "client_saw_tellraw=$saw"
  grep -n '收到' "$HOLD_OUT" | tail -5
fi

# ---------------------------------------------------------------- T3 /status
log "T3 (S2) QQ→MC：/status 真往返（服务端真 /list 响应解析）"
"$PY" -m y33bot simulate group-message --openid 1A2B3C4D --content '/status' --config "$CFG"; rc=$?
mark "status_exit=$rc"

# ---------------------------------------------------------------- T4 MC→QQ 真玩家
log "T4 (S3) MC→QQ：真玩家进服/聊天（普通+#）/退服 → 真实日志行"
if [ "$HAVE_CLIENT" = "1" ]; then
  if [ -f "$HOLDPID" ] 2>/dev/null; then :; fi
  grep -nE 'joined the game|left the game|<Steve>' "$D/logs/latest.log" | tail -6
  ( cd "$HOME/mc-test/client" && node client.js 127.0.0.1 "$GAME" Steve > "$ARTS/client-$VER.txt" 2>&1 )
  echo "client exit=$?"
  cat "$ARTS/client-$VER.txt"
  sleep 2
  grep -E "joined the game" "$D/logs/latest.log" | tail -1 > "$JOIN_REAL"
  grep -E "left the game"   "$D/logs/latest.log" | tail -1 > "$QUIT_REAL"
  grep -E "<Steve>" "$D/logs/latest.log" | grep -v '^\s*$' | tail -2 > "$ARTS/real-chat-lines-raw-$VER.txt"
  grep -E "<Steve>" "$D/logs/latest.log" | grep -E '<Steve> #' | tail -1 > "$CHAT_REAL"
  grep -E "<Steve>" "$D/logs/latest.log" | grep -vE '<Steve> #' | tail -1 > "$CHATPLAIN_REAL"
  echo "--- 真聊天行（带 #） ---"; cat "$CHAT_REAL"
  echo "--- 真聊天行（普通） ---"; cat "$CHATPLAIN_REAL"
  echo "--- 真进服行 ---"; cat "$JOIN_REAL"
  echo "--- 真退服行 ---"; cat "$QUIT_REAL"

  mark_part=""
  JLINE=$(cat "$JOIN_REAL")
  QLINE=$(cat "$QUIT_REAL")
  CLINE=$(cat "$CHAT_REAL")
  PLINE=$(cat "$CHATPLAIN_REAL")
  log "T4a 默认 join 模板对真进服行"
  "$PY" -m y33bot simulate log-event --server "$NAME" --line "$JLINE" --dry-run --config "$CFG"; rc=$?
  mark "join_template_match=$([ $rc -eq 0 ] && echo yes || echo no)"
  log "T4b 默认 quit 模板对真退服行"
  "$PY" -m y33bot simulate log-event --server "$NAME" --line "$QLINE" --dry-run --config "$CFG"; rc=$?
  mark "quit_template_match=$([ $rc -eq 0 ] && echo yes || echo no)"
  log "T4c 默认 chat 模板对真 # 聊天行（项目默认模板是否匹配该版本日志格式）"
  "$PY" -m y33bot simulate log-event --server "$NAME" --line "$CLINE" --dry-run --config "$CFG"; rc=$?
  mark "chat_template_match=$([ $rc -eq 0 ] && echo yes || echo no)"
  log "T4d 默认 chat 模板对真普通聊天行（匹配时应输出「非 # 开头，不转发」）"
  "$PY" -m y33bot simulate log-event --server "$NAME" --line "$PLINE" --dry-run --config "$CFG"; rc=$?
  mark "chatplain_template_match=$([ $rc -eq 0 ] && echo yes || echo no)"
  log "T4e 回环防护（用真行格式的 [QQ] 注入文本）"
  "$PY" -m y33bot simulate log-event --server "$NAME" \
    --line "[12:00:03] $(echo "$CLINE" | sed 's/^\[[0-9:]*\] //; s/<Steve> #.*/<Steve> [QQ] Steve: 大家好/')" \
    --dry-run --config "$CFG"
  mark "loop_guard_tested=yes"
else
  echo "[跳过] $VER：无头客户端（mineflayer/minecraft-data）不支持，无法造真玩家日志行"
  mark "real_client=unsupported_version"
  mark "chat_template_match=unverified(no_real_line)"
  mark "join_template_match=unverified(no_real_line)"
  mark "quit_template_match=unverified(no_real_line)"
fi

# ---------------------------------------------------------------- T5 健康翻转
log "T6 (S4) 健康翻转：离线→重复离线→上线"
"$PY" -m y33bot simulate health --server "$NAME" --offline --config "$CFG"
"$PY" -m y33bot simulate health --server "$NAME" --offline --config "$CFG"
"$PY" -m y33bot simulate health --server "$NAME" --online --config "$CFG"
mark "health_flip_tested=yes"

# ---------------------------------------------------------------- T7 run + 真链路
log "T7 (S5) 常驻 run：真 QQ 网关 + 运行期真玩家 → MC→QQ 真链路"
RUNOUT="$ARTS/run-$VER.txt"
: > "$RUNOUT"
"$PY" -m y33bot run --config "$CFG" --verbose > "$RUNOUT" 2>&1 &
BOT=$!
sleep 14
echo "--- run 启动阶段 ---"
grep -nE '\[启动\]|\[错误\]' "$RUNOUT" | tail -6
if [ "$HAVE_CLIENT" = "1" ]; then
  ( cd "$HOME/mc-test/client" && node client.js 127.0.0.1 "$GAME" Steve2 > "$ARTS/client-run-$VER.txt" 2>&1 ) &
  CLIPID=$!
  sleep 18
  wait $CLIPID 2>/dev/null
  echo "--- 运行期真客户端输出 ---"; cat "$ARTS/client-run-$VER.txt"
  echo "--- run 中与 MC→QQ 相关的行 ---"
  grep -nE '进入|退出|群消息|发送失败|日志行未匹配|非 # 开头|回环|警告' "$RUNOUT" | tail -20
fi

# ---------------------------------------------------------------- T8 S6 日志轮转
log "T8 (S6) 日志轮转：运行中清空 latest.log 再写入真实进服行"
cp -f "$D/logs/latest.log" "$ARTS/latest-log-before-rotate-$VER.txt" 2>/dev/null || true
SZ=$(stat -c %s "$D/logs/latest.log")
: > "$D/logs/latest.log"
sleep 4
echo "日志已清空（清空前大小 $SZ 字节），当前大小 $(stat -c %s "$D/logs/latest.log")"
if [ -s "$JOIN_REAL" ]; then
  cat "$JOIN_REAL" >> "$D/logs/latest.log"
else
  echo "[12:00:04] [Server thread/INFO]: Steve joined the game" >> "$D/logs/latest.log"
fi
sleep 6
echo "--- 轮转相关行 ---"
grep -nE '日志文件缩小|偏移重置|进入了' "$RUNOUT" | tail -6
mark "rotation_tested=yes"

# ---------------------------------------------------------------- 收尾：SIGTERM
log "T7b run 收尾：SIGTERM → 退出码"
kill -TERM $BOT 2>/dev/null
wait $BOT 2>/dev/null; rc=$?
mark "run_exit=$rc"
echo "--- run 尾部 ---"
tail -25 "$RUNOUT"

# ---------------------------------------------------------------- T9 停服
log "T9 优雅停服"
tmux send-keys -t "$SESS" 'stop' Enter
for i in $(seq 1 30); do ss -tln | grep -q ":$RCON" || break; sleep 2; done
echo "停服等待轮次=$i"
ss -tln | grep -E ":$GAME|:$RCON" || echo "(端口已释放)"
tmux ls 2>&1 | head -3

# ---------------------------------------------------------------- 制品
cp -f "$D/logs/latest.log" "$ARTS/latest-log-$VER.txt"
cp -f "$D/console.out.log" "$ARTS/console-$VER.txt"
cp -f "$HOME/Y33-Bot/data/state-fabric-$VER.json" "$ARTS/state-$VER.txt" 2>/dev/null || true
cp -f "$HOME/Y33-Bot/data/bindings-fabric-$VER.toml" "$ARTS/bindings-$VER.txt" 2>/dev/null || true
ls -l "$ARTS" | sed 's/^/  /'

# ---------------------------------------------------------------- 清理（再生的目录）
rm -rf "$D/libraries" "$D/world" "$D/logs" "$D/console.out.log"
echo "已清理 libraries/world/logs（保留 server.jar + 制品）"
df -h / | tail -1
free -m | head -2

mark "conclusion_$VER=已跑完（见 $RES 上方各标记与 artifacts 原始制品）"
echo "########## Fabric $VER 完整测试流程 结束 $(date '+%F %T') ##########"
