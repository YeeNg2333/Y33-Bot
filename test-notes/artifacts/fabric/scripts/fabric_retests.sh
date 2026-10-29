#!/usr/bin/env bash
# 补测脚本（卡 t_5bccfcd8）
#   补测A：1.21.11 的 QQ→MC 真客户端可见性 —— 首轮因客户端 spawn 慢于注入而漏测，
#          这次先等客户端打印「已 spawn」再注入 tellraw。
#   补测B：26.3 上 mineflayer 无头客户端到底能不能连（记录失败原文，作为「无法造真玩家日志行」的证据）。
# 用法: fabric_retests.sh
set -u
. "$HOME/y33-env.sh" 2>/dev/null || true
export PATH="$HOME/node/bin:$PATH"
PY="$HOME/Y33-Bot/.venv/bin/python"
cd "$HOME/Y33-Bot" || exit 1

start_srv() { # $1=版本 $2=slot
  local VER=$1 SLOT=$2 D="$HOME/mc-test/fabric/$1" SESS="mc-fabric-$(printf '%s' "$1" | tr '.' '_')" RCON=$((25710 + $2))
  tmux kill-session -t "$SESS" 2>/dev/null || true
  tmux new -d -s "$SESS" "cd $D && ./start.sh 2>&1 | tee -a console.out.log"
  for i in $(seq 1 100); do
    grep -q 'Done (' "$D/logs/latest.log" 2>/dev/null && ss -tln | grep -q ":$RCON" && break
    sleep 3
  done
  echo "[补测] $VER 启动等待轮次=$i 端口 $(ss -tln | grep -c ":$RCON")"
}
stop_srv() { # $1=版本 $2=slot
  local SESS="mc-fabric-$(printf '%s' "$1" | tr '.' '_')" RCON=$((25710 + $2))
  tmux send-keys -t "$SESS" 'stop' Enter
  for i in $(seq 1 30); do ss -tln | grep -q ":$RCON" || break; sleep 2; done
  echo "[补测] $1 已停（等待轮次=$i）"
}

# ---------------------------------------------------------------- 补测 A：1.21.11
echo
echo "############ 补测 A：1.21.11 QQ→MC 真客户端可见性（等 spawn 后再注入） $(date '+%F %T') ############"
D="$HOME/mc-test/fabric/1.21.11"; A="$D/artifacts"
[ -s "$D/server.jar" ] || echo "[补测] 缺 server.jar，new-fabric.sh 会重新下载"
bash "$HOME/mc-test/new-fabric.sh" 1.21.11 5 >/dev/null 2>&1
start_srv 1.21.11 5
HOLD="$A/client-hold-1.21.11-retest.txt"; : > "$HOLD"
( cd "$HOME/mc-test/client" && node client_hold.js 127.0.0.1 25615 Watcher 40 > "$HOLD" 2>&1 ) &
HP=$!
spawned=no
for i in $(seq 1 30); do
  grep -q '已 spawn' "$HOLD" && { spawned=yes; break; }
  sleep 2
done
echo "[补测A] 客户端 spawn 等待轮次=$i spawned=$spawned"
"$PY" -m y33bot simulate group-message --openid 1A2B3C4D --content '#你好' --config config-fabric-1.21.11.toml; echo "tellraw exit=$?"
sleep 6
saw=no
grep -q '\[QQ\] Steve: 你好' "$HOLD" && saw=yes
echo "[补测A] 客户端收到注入消息: $saw"
grep '收到' "$HOLD" | tail -6
wait $HP 2>/dev/null
{ echo "retest_at=$(date '+%F %T')"; echo "client_spawned=$spawned"; echo "client_saw_tellraw_retest=$saw"; } > "$A/results-1.21.11-retest.txt"
sed -i '/client_saw_tellraw_retest=/d' "$A/results-1.21.11.txt"
cp -f "$A/results-1.21.11.txt" "$HOME/mc-test/fabric/results-1.21.11.txt"
cp -f "$A/results-1.21.11-retest.txt" "$HOME/mc-test/fabric/results-1.21.11-retest.txt"
cp -f "$D/logs/latest.log" "$A/latest-log-1.21.11-retest.txt"
stop_srv 1.21.11 5

# ---------------------------------------------------------------- 补测 B：26.3 客户端能力
echo
echo "############ 补测 B：26.3 上 mineflayer 客户端能力探测 $(date '+%F %T') ############"
D="$HOME/mc-test/fabric/26.3"; A="$D/artifacts"
[ -s "$D/server.jar" ] || echo "[补测] 缺 server.jar，new-fabric.sh 会重新下载"
bash "$HOME/mc-test/new-fabric.sh" 26.3 8 >/dev/null 2>&1
start_srv 26.3 8
OUT="$A/client-26.3-probe.txt"
( cd "$HOME/mc-test/client" && timeout 75 node client.js 127.0.0.1 25618 Watcher > "$OUT" 2>&1 ); echo "client exit=$?"
cat "$OUT"
# minecraft-data 实际支持的版本尾部（作为该结论的旁证）
node -e 'const mc=require("/home/hermes/mc-test/client/node_modules/minecraft-data");const v=mc.supportedVersions.pc;console.log("minecraft-data 支持的版本尾部: "+v.slice(-10).join(" "))' > "$A/minecraft-data-versions.txt" 2>&1
cat "$A/minecraft-data-versions.txt"
cp -f "$D/logs/latest.log" "$A/latest-log-26.3-retest.txt"
stop_srv 26.3 8
echo "############ 补测结束 $(date '+%F %T') ############"
