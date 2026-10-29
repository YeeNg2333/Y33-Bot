#!/usr/bin/env bash
# NeoForge 单版本完整实机测试流程（卡 t_efe57773）
#
# 用法: nf_smoke_one.sh <MC版本> <NeoForge版本> <slot>
# 前提: nf_install.sh + nf_setup.sh 已跑完
# 产出: ~/mc-test/artifacts/neoforge/<MC版本>/（原始制品 + results-<版本>.txt 结构化结论行）
#
# 用例与项目文档的对应（docs/smoke.md S1–S6 / PLAN.md §5）：
#   T0 启动（NeoForge 装载全过程 + FML/mixin/ASM 告警扫描 + latest.log 格式取样）
#   T1=S1 check 自检（真 QQ 探活 + 真 RCON + 日志可读）
#   T2=S2 QQ→MC 绑定 + 真 RCON 注入（真客户端核对可见性）
#   T3=S2 /status 真往返（服务端真 /list 响应）
#   T4=S3 MC→QQ 真玩家聊天（普通/#）+ 默认模板 A/B + 放宽模板复测
#   T5=S4 健康翻转；T6=S5 常驻 run + 真玩家 → MC→QQ 真链路
#   T7=S6 日志轮转；T8 run SIGTERM 退出码；T9 优雅停服
set -u
MC=${1:?用法: nf_smoke_one.sh <MC版本> <NeoForge版本> <slot>}
NF=${2:?缺 NeoForge 版本}
SLOT=${3:?缺 slot}
. "$HOME/y33-env.sh" 2>/dev/null || true
export PATH="$HOME/node/bin:$PATH"

D="$HOME/mc-test/neoforge/$MC"
ARTS="$HOME/mc-test/artifacts/neoforge/$MC"
mkdir -p "$ARTS"
CFG="config-neoforge-$MC.toml"
CFGFIX="config-neoforge-$MC-fix.toml"
NAME="nf$(printf '%s' "$MC" | tr -d '.-')"
GAME=$((25630 + SLOT)); RCON=$((25730 + SLOT))
SESS="mc-neoforge-$(printf '%s' "$MC" | tr '.' '_')"
BOT="$HOME/Y33-Bot"
PYBIN="$BOT/.venv/bin/python"
CLIENT_DIR="$HOME/mc-test/client"
LOG="$D/logs/latest.log"
RES="$ARTS/results-$MC.txt"
: > "$RES"

case "$MC" in
  26.2|26.3|26.4*) HAVE_CLIENT=0 ;;
  *) HAVE_CLIENT=1 ;;
esac

log()  { echo; echo "===================== $* ====================="; echo; }
mark() { echo "$1" >> "$RES"; echo ">>> [RESULT] $1"; }

[ -x "$PYBIN" ] || { echo "[错误] 缺 $PYBIN"; exit 2; }

write_fix_config() {
  cat > "$BOT/$CFGFIX" <<EOF
# Y33-Bot 测试配置：NeoForge $NF / MC $MC —— 仅把 [log_patterns] 放宽到 NeoForge 的 latest.log 格式
# NeoForge 真行样例： [1810月2026 15:21:27.992] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve2 joined the game
[qq]
group_openid = "E2E_DUMMY_GROUP_OPENID"
app_id_env = "QQ_BOT_APP_ID"
app_secret_env = "QQ_BOT_APP_SECRET"
command_prefix = "/"
chat_prefix = "#"

[behavior]
log_poll_interval = 0.5
health_poll_interval = 3600.0
max_line_length = 200
ignored_chat_prefixes = ["[QQ]"]

[paths]
bindings = "data/bindings-neoforge-$MC-fix.toml"
state = "data/state-neoforge-$MC-fix.json"

[[mc_servers]]
name = "$NAME"
host = "127.0.0.1"
port = $RCON
password_env = "MC_RCON_PASSWORD_MAIN"
log_path = "$LOG"
connect_timeout = 5.0
command_timeout = 5.0

[log_patterns]
join = '\\[\\d+月\\d+ \\d{2}:\\d{2}:\\d{2}\\.\\d{3}\\] \\[Server thread/INFO\\] \\[[^\\]]*\\]: (?P<player>\\w+) joined the game'
quit = '\\[\\d+月\\d+ \\d{2}:\\d{2}:\\d{2}\\.\\d{3}\\] \\[Server thread/INFO\\] \\[[^\\]]*\\]: (?P<player>\\w+) left the game'
chat = '\\[\\d+月\\d+ \\d{2}:\\d{2}:\\d{2}\\.\\d{3}\\] \\[(?:Server thread|Async Chat Thread - #\\d+)/INFO\\] \\[[^\\]]*\\]: (?:\\[Not Secure\\] )?<(?P<player>\\w+)> (?P<message>.+)'
encoding = "utf-8"
EOF
}

echo "########## NeoForge $NF（MC $MC，slot $SLOT）完整测试流程 开始 $(date '+%F %T') ##########"
sed 's/^/  /' "$D/instance.env"
printf '  java: '; java -version 2>&1 | head -1
printf '  无头客户端: '; [ "$HAVE_CLIENT" = 1 ] && echo "使用（mineflayer）" || echo "跳过（mineflayer 不支持 $MC）"
echo "  制品目录: $ARTS"

# ------------------------------------------------------------------ T0 启动
log "T0 启动 NeoForge 服务端（游戏 $GAME / RCON $RCON，tmux $SESS）"
tmux kill-session -t "$SESS" 2>/dev/null || true
for _i in $(seq 1 40); do ss -tln | grep -q ":$RCON" || break; sleep 2; done
: > "$D/console.out.log"
: > "$LOG"
START=$(date +%s)
tmux new -d -s "$SESS" "cd $D && ./start.sh 2>&1 | tee -a console.out.log"
ok=0; i=0
for i in $(seq 1 120); do
  if grep -q 'Done (' "$LOG" 2>/dev/null && ss -tln | grep -q ":$RCON"; then ok=1; break; fi
  sleep 3
done
ELAPSED=$(( $(date +%s) - START ))
echo "启动耗时: ${ELAPSED}s（等待轮次=$i 就绪=$ok）"
grep -nE 'NeoForge|Loading Minecraft|Loading [0-9]+ mods|Done \(|RCON running|ModLauncher|Mixin' "$LOG" | tail -12
ss -tln | grep -E ":$GAME|:$RCON" || echo "[警告] 端口未监听"
echo "--- latest.log 头部（格式取样） ---"
head -4 "$LOG" | tee "$ARTS/log-format-sample-$MC.txt"
echo "--- NeoForge 装载期告警扫描（console） ---"
grep -inE 'exception|error|failed|caused by|incompatible|unsupported|mixin.*(fail|error)|ASM' "$D/console.out.log" | head -20 || echo "(无)"
mark "start_ok=$ok"
mark "startup_seconds=$ELAPSED"
if [ "$ok" != "1" ]; then
  echo "--- 启动失败：日志尾部 ---"; tail -40 "$D/console.out.log"
  cp -f "$LOG" "$ARTS/latest-log-$MC.txt" 2>/dev/null || true
  cp -f "$D/console.out.log" "$ARTS/console-$MC.txt" 2>/dev/null || true
  if [ -d "$D/crash-reports" ]; then cp -f "$D"/crash-reports/* "$ARTS/" 2>/dev/null || true; fi
  mark "conclusion_$MC=启动失败（原始日志与 console 已落盘）"
  exit 0
fi
cp -f "$LOG" "$ARTS/latest-log-boot-$MC.txt"

# ------------------------------------------------------------------ T1 check
log "T1 (S1) check：真 QQ 探活 + 真 RCON /list + 日志可读"
cd "$BOT" || exit 1
"$PYBIN" -m y33bot check --config "$CFG"; mark "check_exit=$?"

# ------------------------------------------------------------------ T2 QQ→MC
log "T2 (S2) QQ→MC：绑定 + 真 RCON tellraw 注入（真客户端核对可见性）"
"$PYBIN" -m y33bot bind set 1A2B3C4D Steve --config "$CFG"; echo "bind exit=$?"
"$PYBIN" -m y33bot bind list --config "$CFG"
HOLD_OUT="$ARTS/client-hold-$MC.txt"; : > "$HOLD_OUT"
if [ "$HAVE_CLIENT" = 1 ]; then
  ( cd "$CLIENT_DIR" && node client_hold.js 127.0.0.1 "$GAME" Watcher 30 > "$HOLD_OUT" 2>&1 ) &
  sleep 12; head -3 "$HOLD_OUT"
  grep -E '版本协商|已 spawn|出错|被踢出' "$HOLD_OUT" | head -5
else
  echo "[跳过] 无头客户端不支持 $MC"
fi
"$PYBIN" -m y33bot simulate group-message --openid 1A2B3C4D --content '#你好' --config "$CFG"; mark "tellraw_exit=$?"
sleep 3
if [ "$HAVE_CLIENT" = 1 ]; then
  if grep -q '\[QQ\] Steve: 你好' "$HOLD_OUT"; then saw=yes; else saw=no; fi
  mark "client_saw_tellraw=$saw"
  grep -n '收到' "$HOLD_OUT" | tail -5
fi
grep -nE 'tellraw' "$D/console.out.log" | tail -3

# ------------------------------------------------------------------ T3 /status
log "T3 (S2) /status 真往返（服务端真 /list 响应解析）"
"$PYBIN" -m y33bot simulate group-message --openid 1A2B3C4D --content '/status' --config "$CFG"; mark "status_exit=$?"

# ------------------------------------------------------------------ T4 MC→QQ
log "T4 (S3) MC→QQ：真玩家进服/聊天（普通 + #）/退服 → 真实日志行 + 模板 A/B"
if [ "$HAVE_CLIENT" = 1 ]; then
  ( cd "$CLIENT_DIR" && node client.js 127.0.0.1 "$GAME" Steve > "$ARTS/client-$MC.txt" 2>&1 )
  echo "client exit=$?"; cat "$ARTS/client-$MC.txt"
  sleep 3
  grep -E 'joined the game' "$LOG" | tail -1 > "$ARTS/real-join-line-$MC.txt"
  grep -E 'left the game'   "$LOG" | tail -1 > "$ARTS/real-quit-line-$MC.txt"
  grep -E '<Steve>' "$LOG" | tail -3 > "$ARTS/real-chat-lines-raw-$MC.txt"
  grep -E '<Steve> #' "$LOG" | tail -1 > "$ARTS/real-chat-line-$MC.txt"
  grep -E '<Steve>' "$LOG" | grep -vE '<Steve> #' | tail -1 > "$ARTS/real-chatplain-line-$MC.txt"
  echo "--- 真聊天行（带 #） ---"; cat "$ARTS/real-chat-line-$MC.txt"
  echo "--- 真聊天行（普通） ---"; cat "$ARTS/real-chatplain-line-$MC.txt"
  echo "--- 真进服行 ---"; cat "$ARTS/real-join-line-$MC.txt"
  echo "--- 真退服行 ---"; cat "$ARTS/real-quit-line-$MC.txt"
  JLINE=$(cat "$ARTS/real-join-line-$MC.txt"); QLINE=$(cat "$ARTS/real-quit-line-$MC.txt")
  CLINE=$(cat "$ARTS/real-chat-line-$MC.txt"); PLINE=$(cat "$ARTS/real-chatplain-line-$MC.txt")
  write_fix_config
  for TPL in "default:$CFG" "relaxed:$CFGFIX"; do
    LBL=${TPL%%:*}; C=${TPL#*:}
    for CASE in "join:$JLINE" "quit:$QLINE" "chat:$CLINE" "chatplain:$PLINE"; do
      KIND=${CASE%%:*}; LINE=${CASE#*:}
      log "T4 [$LBL] $KIND 模板用例"
      "$PYBIN" -m y33bot simulate log-event --server "$NAME" --line "$LINE" --dry-run --config "$C"; rc=$?
      mark "${LBL}_${KIND}_exit=$rc"
    done
  done
  log "T4 [default] 回环防护（真行格式的 [QQ] 注入文本）"
  "$PYBIN" -m y33bot simulate log-event --server "$NAME" \
    --line "[12:00:03] $(echo "$CLINE" | sed 's/^\[[0-9:]*\] //; s/<Steve> #.*/<Steve> [QQ] Steve: 大家好/')" \
    --dry-run --config "$CFG"
  mark "loop_guard_tested=yes"
else
  mark "real_client=unsupported_version"
  write_fix_config
fi

# ------------------------------------------------------------------ T5 健康翻转
log "T5 (S4) 健康翻转：离线→重复离线→上线"
"$PYBIN" -m y33bot simulate health --server "$NAME" --offline --config "$CFG"
"$PYBIN" -m y33bot simulate health --server "$NAME" --offline --config "$CFG"
"$PYBIN" -m y33bot simulate health --server "$NAME" --online --config "$CFG"
mark "health_flip_tested=yes"

# ------------------------------------------------------------------ T6 run 真链路
log "T6 (S5 离线可复现部分) 常驻 run：真 QQ 网关 + 运行期真玩家 → MC→QQ 真链路"
RUNOUT="$ARTS/run-$MC.txt"; : > "$RUNOUT"
"$PYBIN" -m y33bot run --config "$CFG" --verbose > "$RUNOUT" 2>&1 &
BOTPID=$!
sleep 14
grep -nE '\[启动\]|\[错误\]' "$RUNOUT" | tail -6
if [ "$HAVE_CLIENT" = 1 ]; then
  ( cd "$CLIENT_DIR" && node client.js 127.0.0.1 "$GAME" Steve2 > "$ARTS/client-run-$MC.txt" 2>&1 ) &
  CLIPID=$!
  sleep 18
  wait "$CLIPID" 2>/dev/null
  echo "--- 运行期真客户端输出 ---"; cat "$ARTS/client-run-$MC.txt"
  echo "--- run 中 MC→QQ 相关行（含警告） ---"
  grep -nE '进入|退出|群消息|发送失败|日志行未匹配|非 # 开头|回环|警告|错误' "$RUNOUT" | tail -25
else
  echo "[跳过] 无头客户端不支持 $MC"
fi
mark "run_started=yes"

# ------------------------------------------------------------------ T7 日志轮转 (S6)
log "T7 (S6) 日志轮转：运行中清空 latest.log 再写入真实进服行"
cp -f "$LOG" "$ARTS/latest-log-before-rotate-$MC.txt" 2>/dev/null || true
SZ=$(stat -c %s "$LOG")
: > "$LOG"
sleep 4
echo "清空前 $SZ 字节 → 清空后 $(stat -c %s "$LOG") 字节"
if [ -s "$ARTS/real-join-line-$MC.txt" ]; then
  cat "$ARTS/real-join-line-$MC.txt" >> "$LOG"
else
  echo "[12:00:04] [Server thread/INFO]: Steve joined the game" >> "$LOG"
fi
sleep 6
grep -nE '日志文件缩小|偏移重置|进入了' "$RUNOUT" | tail -6
mark "rotation_tested=yes"

# ------------------------------------------------------------------ T8 SIGTERM
log "T8 run 收尾：SIGTERM → 退出码"
kill -TERM "$BOTPID" 2>/dev/null
wait "$BOTPID" 2>/dev/null; rc=$?
mark "run_exit=$rc"
tail -20 "$RUNOUT"

# ------------------------------------------------------------------ T9 停服
log "T9 优雅停服"
tmux send-keys -t "$SESS" 'stop' Enter
for i in $(seq 1 40); do ss -tln | grep -q ":$RCON" || break; sleep 2; done
echo "停服等待轮次=$i"
ss -tln | grep -E ":$GAME|:$RCON" || echo "(端口已释放)"
mark "server_stopped=yes"

# ------------------------------------------------------------------ 制品
cp -f "$LOG" "$ARTS/latest-log-$MC.txt"
cp -f "$D/console.out.log" "$ARTS/console-$MC.txt"
cp -f "$BOT/data/state-neoforge-$MC.json" "$ARTS/state-$MC.txt" 2>/dev/null || true
cp -f "$BOT/data/bindings-neoforge-$MC.toml" "$ARTS/bindings-$MC.txt" 2>/dev/null || true
if [ -d "$D/crash-reports" ]; then cp -f "$D"/crash-reports/* "$ARTS/" 2>/dev/null || true; fi
grep -nE 'mixin|ASM|ModLauncher|FML|Loading [0-9]+ mods' "$D/console.out.log" | head -20 > "$ARTS/loader-notes-$MC.txt"
echo "--- NeoForge 装载/告警摘录 ---"; cat "$ARTS/loader-notes-$MC.txt"
ls -l "$ARTS" | sed 's/^/  /'
df -h / | tail -1; free -m | head -2
mark "conclusion_$MC=已跑完（见 $RES 各标记与同目录原始制品）"
echo "########## NeoForge $MC 完整测试流程 结束 $(date '+%F %T') ##########"
