#!/usr/bin/env bash
# 原版（Vanilla）测试矩阵 · 单版本执行器 —— 卡 t_ac457fe1
#
# 用法: bash ~/mc-test/vanilla-matrix.sh <MC版本> <slot 0-9> [full|probe]
#   full  = 完整用例（启动/连接、check、指令、注入、往返、边界、健康、run 真链路、轮转、退出）
#   probe = 轻量探针（启动 + 真客户端进服/聊天/退服 + 聊天行 A/B）
# 产出目录: ~/mc-test/artifacts/vanilla/<版本>/
#   matrix.out       本次全部输出
#   latest-log.txt   服务端 logs/latest.log（收尾快照）
#   console.txt      服务端控制台输出
#   clientA.out / clientB.out  无头客户端输出
#   run.out          机器人 run 的真实输出（真 QQ 网关 + 假群）
# 约定来自 test-notes/00-env.md（端口表、目录模板、命令模板）。
set -u
. ~/y33-env.sh

VER="${1:?用法: vanilla-matrix.sh <MC版本> <slot 0-9> [full|probe]}"
SLOT="${2:?用法: vanilla-matrix.sh <MC版本> <slot 0-9> [full|probe]}"
MODE="${3:-full}"

BOT="$HOME/Y33-Bot"
PY="$BOT/.venv/bin/python -m y33bot"
NAME="v$(printf '%s' "$VER" | tr '.-' '__')"      # 配置里的服名（只允许 A-Za-z0-9_-）
ARTS="$HOME/mc-test/artifacts/vanilla/$VER"
CLIENT="$HOME/mc-test/client/client-matrix.js"
mkdir -p "$ARTS"

echo "===== 原版矩阵：$VER（slot $SLOT，mode=$MODE）开始 $(date '+%F %T %Z') ====="

write_conf() {                                  # write_conf <file> <chat_pattern>
  cat > "$1" <<EOF
# 自动生成（卡 t_ac457fe1 原版矩阵）：$VER
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
bindings = "data/bindings-vanilla-$VER.toml"
state = "data/state-vanilla-$VER.json"

[[mc_servers]]
name = "$NAME"
host = "127.0.0.1"
port = $MC_RCON_PORT
password_env = "MC_RCON_PASSWORD_MAIN"
log_path = "$MC_LOG"
connect_timeout = 5.0
command_timeout = 5.0

[log_patterns]
join = '\\[\\d{2}:\\d{2}:\\d{2}\\] \\[Server thread/INFO\\]: (?P<player>\\w+) joined the game'
quit = '\\[\\d{2}:\\d{2}:\\d{2}\\] \\[Server thread/INFO\\]: (?P<player>\\w+) left the game'
chat = '$2'
encoding = "utf-8"
EOF
}

case_run() {                                    # case_run <id> <desc> <期望正则> <命令...>
  local id="$1" desc="$2" want="$3"; shift 3
  local out rc
  echo
  echo "----- [$id] $desc -----"
  out=$("$@" 2>&1); rc=$?
  printf '%s\n' "$out"
  if printf '%s\n' "$out" | grep -qE "$want"; then
    echo "[结果] $id PASS（exit=$rc，命中 /$want/）"
  else
    echo "[结果] $id FAIL（exit=$rc，未命中 /$want/）"
  fi
}

# ---------------------------------------------------------------- 0) 错峰（2.6G 内存，同机还有兄弟卡在跑服务端）
WAITED=0
while [ "$WAITED" -lt 240 ]; do
  pgrep -f 'jar server.jar nogui' >/dev/null || break
  AVAIL=$(free -m | awk '/^Mem:/{print $7}')
  [ "${AVAIL:-0}" -ge 900 ] && { echo "[错峰] 其它实例在跑，但可用内存 ${AVAIL}Mi 足够，继续。"; break; }
  echo "[等待] 其它 MC 实例在跑且可用内存仅 ${AVAIL}Mi（$(date '+%T')），等 20s…"
  sleep 20; WAITED=$((WAITED + 20))
done

# ---------------------------------------------------------------- 1) 实例
~/mc-test/new-vanilla.sh "$VER" "$SLOT" 2>&1 | sed 's/^/  /'
. "$HOME/mc-test/vanilla/$VER/instance.env"
CONF="$BOT/config-vanilla-$VER.toml"
CONF_FIX="$BOT/config-vanilla-fix-$VER.toml"
DEFAULT_CHAT='\[\d{2}:\d{2}:\d{2}\] \[Async Chat Thread - #\d+/INFO\]: <(?P<player>\w+)> (?P<message>.+)'
write_conf "$CONF" "$DEFAULT_CHAT"
write_conf "$CONF_FIX" '\[\d{2}:\d{2}:\d{2}\] \[(?:Server thread|Async Chat Thread - #\d+)/INFO\]: (?:\[Not Secure\] )?<(?P<player>\w+)> (?P<message>.+)'

echo
echo "----- 生成的配置（核对端口/日志/服名） -----"
grep -E 'name =|port =|log_path =|state =|^chat =' "$CONF"

# ---------------------------------------------------------------- 2) 启动服务端
echo
echo "----- [C1] 启动原版服务端（JDK $("$JAVA_HOME/bin/java" -version 2>&1 | head -1)） -----"
tmux kill-session -t "$MC_TMUX" 2>/dev/null || true
: > "$MC_DIR/console.out.log"
done_count() { local c=0; if [ -f "$MC_LOG" ]; then c=$(grep -c 'Done (' "$MC_LOG" 2>/dev/null); fi; echo "${c:-0}"; }
BEFORE=$(done_count); START=$(date +%s); READY=0
tmux new -d -s "$MC_TMUX" "cd $MC_DIR && ./start.sh 2>&1 | tee -a console.out.log"
for i in $(seq 1 120); do
  if [ "$(done_count)" -gt "$BEFORE" ] && ss -tln | grep -q ":$MC_RCON_PORT "; then READY=1; break; fi
  sleep 3
done
echo "启动耗时 $(( $(date +%s) - START ))s；READY=$READY（1=Done 行出现且 RCON 端口在听）"
grep -E 'Done \(|RCON running on|Starting remote control' "$MC_LOG" | tail -3
ss -tln | grep -E ":$MC_GAME_PORT |:$MC_RCON_PORT "

if [ "$MODE" = "probe" ]; then
  # ------------------------------------------------------ probe：只做真客户端 + 聊天行 A/B
  export PATH="$HOME/node/bin:$PATH"
  echo
  echo "----- [P1] 真实客户端进服/聊天/退服（mineflayer） -----"
  ( cd "$HOME/mc-test/client" && timeout 120 node client-matrix.js 127.0.0.1 "$MC_GAME_PORT" Steve ) > "$ARTS/clientA.out" 2>&1
  echo "client exit=$?"
  cat "$ARTS/clientA.out"
  sleep 4
  echo
  echo "----- [P2] 服务端真实聊天/进服行 -----"
  grep -a -nE 'joined the game|left the game|<[A-Za-z0-9_]+> ' "$MC_LOG" | tail -12
else
  cd "$BOT"
  case_run C2 "check：配置/QQ 真探活/RCON 真连/日志可读/绑定表" '^OK$' $PY check --config "$CONF"
  case_run C3 "commands：QQ 管理端指令面板清单" '\[指令\] /status' $PY commands --config "$CONF"
  case_run C4 "bind set + list（绑定落盘）" '1A2B3C4D -> Steve' sh -c "$PY bind set 1A2B3C4D Steve --config '$CONF' && $PY bind list --config '$CONF'"
  case_run C5 "QQ→MC 真注入（真 RCON tellraw，无 --dry-run）" 'tellraw @a .*矩阵：真 RCON 注入' $PY simulate group-message --openid 1A2B3C4D --content '#矩阵：真 RCON 注入' --config "$CONF"
  case_run C6 "/status 真往返（读服务端真实 /list 响应）" '\[群消息\] 在线: ' $PY simulate group-message --openid 1A2B3C4D --content '/status' --config "$CONF"
  case_run C7 "未绑定用户 → 绑定提示，不注入" '请先使用 /bind' $PY simulate group-message --openid UNBOUND --content '#你好' --config "$CONF"
  case_run C8 "非触发前缀 → 忽略" '\[忽略\] 非触发前缀' $PY simulate group-message --openid 1A2B3C4D --content '普通消息' --config "$CONF"
  case_run C9 "未知指令 → 未知指令" '未知指令' $PY simulate group-message --openid 1A2B3C4D --content '/unknowncmd' --config "$CONF"
  case_run C10 "/bind 缺参数 → 用法文案" '用法: /bind <游戏ID>' $PY simulate group-message --openid 1A2B3C4D --content '/bind' --config "$CONF"
  case_run C11 "/bind 非法游戏ID → 不合法" '游戏ID 不合法' $PY simulate group-message --openid 1A2B3C4D --content '/bind bad!' --config "$CONF"
  case_run C12 "多行内容只转发第一行（A7）" 'tellraw @a .*第一行' $PY simulate group-message --openid 1A2B3C4D --content "$(printf '#第一行\n第二行')" --config "$CONF"
  case_run C13 "simulate health 离线（首次提示）" "\[服务器状态\] $NAME 离线" $PY simulate health --server "$NAME" --offline --dry-run --config "$CONF"
  case_run C14 "simulate health 离线（第二次不重复提示）" '状态未变化，不重复提示' $PY simulate health --server "$NAME" --offline --dry-run --config "$CONF"
  case_run C15 "simulate health 上线（翻转提示）" "\[服务器状态\] $NAME 上线" $PY simulate health --server "$NAME" --online --dry-run --config "$CONF"
  case_run C16 "旧格式聊天行（文档样例）→ 转发" "\[群消息\] Steve@$NAME: 大家好" $PY simulate log-event --server "$NAME" --line '[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好' --dry-run --config "$CONF"
  case_run C17 "回环防护：命中 ignored_chat_prefixes（文档样例行）" '回环防护' $PY simulate log-event --server "$NAME" --line '[12:00:03] [Async Chat Thread - #0/INFO]: <Steve> [QQ] Steve: 大家好' --dry-run --config "$CONF"
  case_run C18 "join/quit 事件模板（真行格式）" "Steve进入了$NAME" $PY simulate log-event --server "$NAME" --line '[12:00:04] [Server thread/INFO]: Steve joined the game' --dry-run --config "$CONF"

  # ------------------------------------------------------ C19：run 真链路（进服/聊天/退服/轮转/退出）
  echo
  echo "----- [C19] run：真 QQ 网关 + 真实客户端进服/聊天/退服 + 日志轮转 + 优雅退出 -----"
  cd "$BOT"
  rm -f "$ARTS/run.out"
  $PY run --verbose --config "$CONF" > "$ARTS/run.out" 2>&1 &
  BOTPID=$!
  sleep 12
  echo "启动判据（应出现 QQ 网关已连接 / 日志监听已启动）："
  grep -E '\[启动\]' "$ARTS/run.out" || echo "(无 [启动] 行)"
  export PATH="$HOME/node/bin:$PATH"
  echo "--- 客户端 A：Steve 进服 + 普通聊天 + # 聊天 + 退服 ---"
  ( cd "$HOME/mc-test/client" && timeout 120 node client-matrix.js 127.0.0.1 "$MC_GAME_PORT" Steve ) > "$ARTS/clientA.out" 2>&1
  echo "clientA exit=$?"; cat "$ARTS/clientA.out"
  sleep 8
  echo "--- 日志轮转（S6）：清空 latest.log，再让客户端 B 进服/退服 ---"
  : > "$MC_LOG"
  ( cd "$HOME/mc-test/client" && timeout 120 node client-matrix.js 127.0.0.1 "$MC_GAME_PORT" Alex ) > "$ARTS/clientB.out" 2>&1
  echo "clientB exit=$?"; tail -4 "$ARTS/clientB.out"
  sleep 8
  echo "--- SIGTERM（优雅退出，期望 exit=0）---"
  kill -TERM "$BOTPID" 2>/dev/null || true
  wait "$BOTPID"; echo "bot exit=$?"
  # 日志被 truncate 会让服务端在旧偏移继续写 => 日志里出现 NUL 填充，落制品前清掉
  tr -d '\000' < "$ARTS/run.out" > "$ARTS/run.clean" && mv "$ARTS/run.clean" "$ARTS/run.out"
  tr -d '\000' < "$ARTS/clientA.out" > "$ARTS/clientA.clean" && mv "$ARTS/clientA.clean" "$ARTS/clientA.out"
  tr -d '\000' < "$ARTS/clientB.out" > "$ARTS/clientB.clean" && mv "$ARTS/clientB.clean" "$ARTS/clientB.out"
fi

# ---------------------------------------------------------------- 3) 机器人侧输出
if [ -f "$ARTS/run.out" ]; then
  echo
  echo "----- run.out（机器人真实输出，全量） -----"
  cat "$ARTS/run.out"
fi

# ---------------------------------------------------------------- 4) 聊天行 A/B（真行喂模板）
echo
echo "----- [C20] 真实聊天行 vs 默认/放宽 chat 模板（A/B） -----"
CHAT_HASH=$(grep -aE '<[A-Za-z0-9_]+> #' "$MC_LOG" 2>/dev/null | tail -1)
CHAT_PLAIN=$(grep -aE '<[A-Za-z0-9_]+> ' "$MC_LOG" 2>/dev/null | grep -av '#' | tail -1)
JOIN_LINE=$(grep -a 'joined the game' "$MC_LOG" 2>/dev/null | tail -1)
QUIT_LINE=$(grep -a 'left the game' "$MC_LOG" 2>/dev/null | tail -1)
echo "本次会话真实聊天行（# 开头）: ${CHAT_HASH:-(无)}"
echo "本次会话真实聊天行（普通）  : ${CHAT_PLAIN:-(无)}"
echo "本次会话真实进服行          : ${JOIN_LINE:-(无)}"
echo "本次会话真实退服行          : ${QUIT_LINE:-(无)}"
cd "$BOT"
if [ -n "$CHAT_HASH" ]; then
  echo "[A] 默认模板 ← 真实 '#' 聊天行"
  $PY simulate log-event --server "$NAME" --line "$CHAT_HASH" --dry-run --config "$CONF" 2>&1; echo "exit=$?"
  echo "[B] 放宽模板 ← 同一行"
  $PY simulate log-event --server "$NAME" --line "$CHAT_HASH" --dry-run --config "$CONF_FIX" 2>&1; echo "exit=$?"
  echo "[B2] 放宽模板 ← 真实普通聊天行（应忽略）"
  $PY simulate log-event --server "$NAME" --line "$CHAT_PLAIN" --dry-run --config "$CONF_FIX" 2>&1; echo "exit=$?"
  echo "[A2] 默认模板 ← 真实进服行（join 模板应不受影响）"
  $PY simulate log-event --server "$NAME" --line "$JOIN_LINE" --dry-run --config "$CONF" 2>&1; echo "exit=$?"
else
  echo "[A/B] 无真实聊天行（客户端未连上该版本）→ 本版聊天行格式无法判定"
fi

# ---------------------------------------------------------------- 5) 收尾
echo
echo "----- 收尾：停服 + 归档制品 + 回收磁盘 -----"
tmux send-keys -t "$MC_TMUX" 'stop' Enter 2>/dev/null || true
for i in $(seq 1 60); do tmux has-session -t "$MC_TMUX" 2>/dev/null || break; sleep 2; done
if tmux has-session -t "$MC_TMUX" 2>/dev/null; then
  echo "[警告] tmux 会话仍在（服务端可能没退干净），强制结束"
  tmux kill-session -t "$MC_TMUX" 2>/dev/null || true
  sleep 5
fi
echo "端口检查：游戏端口 $MC_GAME_PORT 监听数 = $(ss -tln | grep -c ":$MC_GAME_PORT ")，RCON $MC_RCON_PORT 监听数 = $(ss -tln | grep -c ":$MC_RCON_PORT ")"
tr -d '\000' < "$MC_LOG" > "$ARTS/latest-log.txt" 2>/dev/null || true
tr -d '\000' < "$MC_DIR/console.out.log" > "$ARTS/console.txt" 2>/dev/null || true
echo "本次会话真实玩家日志行："
grep -a -E 'joined the game|left the game|<[A-Za-z0-9_]+> |logged in' "$ARTS/latest-log.txt" 2>/dev/null | tail -14
rm -rf "$MC_DIR/libraries" "$MC_DIR/world" "$MC_DIR/console.out.log" "$MC_DIR/logs" "$MC_DIR/server.jar"
df -h / | tail -1
echo "===== 原版矩阵：$VER 结束 $(date '+%F %T %Z') ====="
