#!/bin/bash
# NeoForge 实例收尾配置 + 生成 y33bot 测试配置（卡 t_efe57773）
# 用法: nf_setup.sh <MC版本> <NeoForge版本> <slot 0-9>
# 前提: ~/mc-test/neoforge/<MC版本>/ 已由 nf_install.sh 装好（libraries + run.sh）
set -u
MC=${1:?用法: nf_setup.sh <MC版本> <NeoForge版本> <slot>}
NF=${2:?缺 NeoForge 版本}
SLOT=${3:?缺 slot}
. "$HOME/y33-env.sh" 2>/dev/null || true
if [ -f "$HOME/.env" ]; then set -a; . "$HOME/.env"; set +a; fi
[ -n "${MC_RCON_PASSWORD:-}" ] || { echo "[错误] ~/.env 缺 MC_RCON_PASSWORD"; exit 1; }

case "$MC" in 26.*) JDK=25 ;; *) JDK=21 ;; esac
D="$HOME/mc-test/neoforge/$MC"
GAME=$((25630 + SLOT)); RCON=$((25730 + SLOT))
SESS="mc-neoforge-$(printf '%s' "$MC" | tr '.' '_')"
NAME="nf$(printf '%s' "$MC" | tr -d '.-')"
BOT="$HOME/Y33-Bot"
CFG="$BOT/config-neoforge-$MC.toml"
[ -d "$D/libraries" ] || { echo "[错误] $D/libraries 不存在，先跑 nf_install.sh"; exit 1; }

echo "eula=true" > "$D/eula.txt"
cat > "$D/server.properties" <<EOF
enable-rcon=true
rcon.port=$RCON
rcon.password=$MC_RCON_PASSWORD
server-port=$GAME
online-mode=false
motd=Y33 neoforge $MC
max-players=20
view-distance=4
simulation-distance=4
spawn-protection=0
pause-when-empty-seconds=0
EOF

cat > "$D/user_jvm_args.txt" <<EOF
-Xms512M
-Xmx1024M
EOF

cat > "$D/start.sh" <<'EOS'
#!/bin/bash
# NeoForge 启动：先载入 instance.env 选对 JDK（注：26.x 需要 Java 25，默认 PATH 上是 21）
cd "$(dirname "$0")"
. ./instance.env
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"
exec ./run.sh nogui
EOS
chmod +x "$D/start.sh" "$D/run.sh" 2>/dev/null || true
mkdir -p "$D/mods" "$D/logs"

cat > "$D/instance.env" <<EOF
# NeoForge 实例（卡 t_efe57773）—— . 它即可拿到全部变量
MC_VERSION=$MC
MC_NEOFORGE=$NF
MC_FAMILY=neoforge
MC_DIR=$D
MC_GAME_PORT=$GAME
MC_RCON_PORT=$RCON
MC_TMUX=$SESS
JAVA_HOME=$HOME/jdk-$JDK
MC_LOG=$D/logs/latest.log
EOF

cat > "$CFG" <<EOF
# Y33-Bot 实机测试配置：NeoForge $NF / MC $MC（卡 t_efe57773）
# [log_patterns] 保持 config.example.toml 的默认模板不动 —— 本卡要检验默认模板对 NeoForge 服务端真机日志是否匹配
# group_openid 用假群：让 MC→QQ 方向真的走到平台（预期被平台拒），验证完整链路
[qq]
group_openid = "E2E_DUMMY_GROUP_OPENID"
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
bindings = "data/bindings-neoforge-$MC.toml"
state = "data/state-neoforge-$MC.json"

[[mc_servers]]
name = "$NAME"
host = "127.0.0.1"
port = $RCON
password_env = "MC_RCON_PASSWORD_MAIN"
log_path = "$D/logs/latest.log"
connect_timeout = 5.0
command_timeout = 5.0

[log_patterns]
join = '\\[\\d{2}:\\d{2}:\\d{2}\\] \\[Server thread/INFO\\]: (?P<player>\\w+) joined the game'
quit = '\\[\\d{2}:\\d{2}:\\d{2}\\] \\[Server thread/INFO\\]: (?P<player>\\w+) left the game'
chat = '\\[\\d{2}:\\d{2}:\\d{2}\\] \\[Async Chat Thread - #\\d+/INFO\\]: <(?P<player>\\w+)> (?P<message>.+)'
encoding = "utf-8"
EOF

echo "[实例] $D（游戏 $GAME / RCON $RCON，JDK$JDK，tmux $SESS）"
echo "[配置] $CFG（服名 $NAME）"
ls -l "$D/run.sh" "$D/user_jvm_args.txt" "$D/server.properties" "$D/start.sh"
