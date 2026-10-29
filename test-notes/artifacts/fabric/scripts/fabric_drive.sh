#!/usr/bin/env bash
# Fabric 矩阵驱动：逐版本建实例 → 生成配置 → 跑完整测试流程（卡 t_5bccfcd8）
# 用法: nohup setsid bash ~/mc-test/fabric-drive.sh > ~/mc-test/fabric-drive.out 2>&1 &
#
# 版本清单理由（写在 test-notes/02-fabric.md）：
#   近两年（2024-10-18 之后）正式版里，每个「版本线」的首个正式版（不细化到其补丁版）：
#   1.21.2 / 1.21.4 / 1.21.5 / 1.21.6 / 1.21.9 / 26.1 / 26.2 / 26.3
#   外加 1.21.11（已知 chat 模板问题的现场版本，作对照）。
set -u
. "$HOME/y33-env.sh" 2>/dev/null || true
mkdir -p "$HOME/mc-test/fabric"

VERSIONS="1.21.2:0 1.21.4:1 1.21.5:2 1.21.6:3 1.21.9:4 1.21.11:5 26.1:6 26.2:7 26.3:8"

gen_config() {
  local VER=$1 SLOT=$2 NAME=$3 RCON=$((25710 + SLOT))
  cat > /tmp/cfg-fabric-template.toml <<'EOF'
# Y33-Bot 实机测试配置：Fabric __VER__（卡 t_5bccfcd8）
# [log_patterns] 是 config.example.toml 的原样默认模板 —— 本卡就是要检验默认模板对该版本真机日志是否匹配
[qq]
group_openid = "E2E_DUMMY_GROUP_OPENID"   # 假群：让 MC→QQ 真的走到平台（预期被平台拒），验证完整链路
app_id_env = "QQ_BOT_APP_ID"
app_secret_env = "QQ_BOT_APP_SECRET"
command_prefix = "/"
chat_prefix = "#"

[behavior]
log_poll_interval = 0.5
health_poll_interval = 30.0
max_line_length = 200
ignored_chat_prefixes = ["[QQ]"]

[paths]
bindings = "data/bindings-fabric-__VER__.toml"
state = "data/state-fabric-__VER__.json"

[[mc_servers]]
name = "__NAME__"
host = "127.0.0.1"
port = __RCON__
password_env = "MC_RCON_PASSWORD_MAIN"
log_path = "/home/hermes/mc-test/fabric/__VER__/logs/latest.log"
connect_timeout = 5.0
command_timeout = 5.0

[log_patterns]
join = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) joined the game'
quit = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) left the game'
chat = '\[\d{2}:\d{2}:\d{2}\] \[Async Chat Thread - #\d+/INFO\]: <(?P<player>\w+)> (?P<message>.+)'
encoding = "utf-8"
EOF
  sed -e "s/__VER__/$VER/g" -e "s/__NAME__/$NAME/g" -e "s/__RCON__/$RCON/g" \
    /tmp/cfg-fabric-template.toml > "$HOME/Y33-Bot/config-fabric-$VER.toml"
}

gate() {
  local i n avail
  for i in $(seq 1 90); do
    n=$(pgrep -f 'fabric-server-launch.jar|server.jar nogui' | wc -l)
    avail=$(free -m | awk '/^Mem:/{print $7}')
    if [ "$n" -eq 0 ] && [ "${avail:-0}" -ge 900 ]; then
      echo "[门控] 无其他 MC 实例在跑、可用内存 ${avail}M → 开始"
      return 0
    fi
    echo "[门控] 等待资源（其他 MC 进程=$n，可用内存=${avail}M，第 $i 次，20s 后重试）"
    sleep 20
  done
  echo "[门控][警告] 等待超时（其他进程=$n，可用=${avail}M），继续执行并记录"
  return 0
}

echo "########## Fabric 矩阵开始 $(date '+%F %T') ##########"
echo "版本清单: $VERSIONS"
for pair in $VERSIONS; do
  VER=${pair%%:*}
  SLOT=${pair##*:}
  NAME="fab$(printf '%s' "$VER" | tr -d '.')"
  echo
  echo "################################################################"
  echo "### 版本 $VER（slot $SLOT，游戏 $((25610 + SLOT)) / RCON $((25710 + SLOT))，服名 $NAME）$(date '+%F %T')"
  echo "################################################################"
  gate
  bash "$HOME/mc-test/new-fabric.sh" "$VER" "$SLOT" > "/tmp/newfabric-$VER.out" 2>&1
  echo "--- new-fabric rc=$? ---"
  tail -14 "/tmp/newfabric-$VER.out"
  bash "$HOME/mc-test/gen-config-fabric.sh" "$VER" "$SLOT" "$NAME"
  echo "--- 配置已生成: config-fabric-$VER.toml ---"
  bash "$HOME/mc-test/fabric_smoke_one.sh" "$VER" "$SLOT" 2>&1 \
    | tee "$HOME/mc-test/fabric/$VER/test-$VER.txt"
  cp -f "$HOME/mc-test/fabric/$VER/artifacts/results-$VER.txt" "$HOME/mc-test/fabric/results-$VER.txt" 2>/dev/null || true
  echo "### 版本 $VER 结束 $(date '+%F %T')"
done
echo "########## Fabric 矩阵全部结束 $(date '+%F %T') ##########"
