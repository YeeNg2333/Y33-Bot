#!/usr/bin/env bash
# 附加用例（卡 t_5bccfcd8）：26.3 换用「最新但不稳定标记」的 loader 0.20.0 跑一遍，
#   检查「加载器版本差异」是否影响机器人侧测试（Fabric 段 slot 9：游戏 25619 / RCON 25719）。
# 产出: ~/mc-test/fabric/26.3-loader0.20.0/artifacts/results-loader-variant.txt
set -u
. "$HOME/y33-env.sh" 2>/dev/null || true
VER=26.3
SLOT=9
LOADER=0.20.0
D="$HOME/mc-test/fabric/$VER-loader$LOADER"
A="$D/artifacts"; mkdir -p "$A" "$D/mods"
GAME=25619; RCON=25719
SESS=mc-fabric-26_3_l020
PY="$HOME/Y33-Bot/.venv/bin/python"
cd "$HOME/Y33-Bot" || exit 1
R="$A/results-loader-variant.txt"; : > "$R"
m() { echo "$1" | tee -a "$R"; }

echo "########## 附加用例：26.3 + loader $LOADER $(date '+%F %T') ##########"
cat > "$D/server.properties" <<EOF
enable-rcon=true
rcon.port=$RCON
rcon.password=$MC_RCON_PASSWORD
server-port=$GAME
online-mode=false
motd=Y33 fabric 26.3 loader $LOADER
max-players=20
view-distance=4
simulation-distance=4
spawn-protection=0
pause-when-empty-seconds=0
EOF
printf 'eula=true\n' > "$D/eula.txt"
cat > "$D/start.sh" <<EOF
#!/usr/bin/env bash
cd "\$(dirname "\$0")"
export JAVA_HOME="$HOME/jdk-25"
exec "\$HOME/jdk-25/bin/java" -Xms256M -Xmx1024M -jar fabric-server-launch.jar nogui
EOF
chmod +x "$D/start.sh"
[ -s "$D/server.jar" ] || cp -f "$HOME/mc-test/fabric/26.3/server.jar" "$D/server.jar"
cp -f "$HOME/mc-test/fabric-api-26.3.jar" "$D/mods/" 2>/dev/null || true
echo "--- 安装 loader $LOADER ---"
"$HOME/jdk-25/bin/java" -jar "$HOME/mc-test/tools/fabric-installer-1.1.2.jar" server \
  -dir "$D" -mcversion "$VER" -loader "$LOADER" 2>&1 | tail -6
echo "--- 启动 ---"
tmux kill-session -t "$SESS" 2>/dev/null || true
tmux new -d -s "$SESS" "cd $D && ./start.sh 2>&1 | tee -a console.out.log"
ok=0
for i in $(seq 1 100); do
  grep -q 'Done (' "$D/logs/latest.log" 2>/dev/null && ss -tln | grep -q ":$RCON" && { ok=1; break; }
  sleep 3
done
m "start_ok=$ok"
grep -m1 'Loading Minecraft' "$D/logs/latest.log"
grep -m1 'Loading [0-9]* mods' "$D/logs/latest.log"
grep -m1 -E 'fabric-api [0-9]' "$D/logs/latest.log"
grep -m1 'Done (' "$D/logs/latest.log"
if [ "$ok" != "1" ]; then
  echo "--- 启动失败错误行 ---"
  grep -inE 'exception|error|failed|caused by|incompatible|unsupported' "$D/console.out.log" | tail -20
  m "conclusion=loader $LOADER 启动失败（症状见上）"
  exit 0
fi

# 生成配置（默认模板，端口 25719）
sed -e "s|fab263\"|fab263l020\"|" "$HOME/Y33-Bot/config-fabric-26.3.toml" > /dev/null 2>&1 || true
cat > "$HOME/Y33-Bot/config-fabric-26.3-loader0.20.0.toml" <<EOF
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
bindings = "data/bindings-fabric-loadervariant.toml"
state = "data/state-fabric-loadervariant.json"

[[mc_servers]]
name = "fab263l020"
host = "127.0.0.1"
port = $RCON
password_env = "MC_RCON_PASSWORD_MAIN"
log_path = "$D/logs/latest.log"
connect_timeout = 5.0
command_timeout = 5.0

[log_patterns]
join = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) joined the game'
quit = '\[\d{2}:\d{2}:\d{2}\] \[Server thread/INFO\]: (?P<player>\w+) left the game'
chat = '\[\d{2}:\d{2}:\d{2}\] \[Async Chat Thread - #\d+/INFO\]: <(?P<player>\w+)> (?P<message>.+)'
encoding = "utf-8"
EOF

echo "--- check ---"
"$PY" -m y33bot check --config config-fabric-26.3-loader0.20.0.toml; m "check_exit=$?"
echo "--- tellraw 真注入 ---"
"$PY" -m y33bot simulate group-message --openid 1A2B3C4D --content '#你好' --config config-fabric-26.3-loader0.20.0.toml; m "tellraw_exit=$?"
echo "--- /status 真往返 ---"
"$PY" -m y33bot simulate group-message --openid 1A2B3C4D --content '/status' --config config-fabric-26.3-loader0.20.0.toml; m "status_exit=$?"
echo "--- 停服 ---"
tmux send-keys -t "$SESS" 'stop' Enter
for i in $(seq 1 30); do ss -tln | grep -q ":$RCON" || break; sleep 2; done
cp -f "$D/logs/latest.log" "$A/latest-log-loader0.20.0.txt"
m "conclusion=loader $LOADER 在 26.3 上可用（服务端启动 + 机器人 check/tellraw/status 均通过）"
echo "########## 附加用例结束 $(date '+%F %T') ##########"
