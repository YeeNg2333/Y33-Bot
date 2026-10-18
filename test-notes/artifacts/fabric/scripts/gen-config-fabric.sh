#!/usr/bin/env bash
# 生成单个 Fabric 版本的 Y33-Bot 测试配置（卡 t_5bccfcd8）
# 用法: gen-config-fabric.sh <MC版本> <slot> [服名]
# 日志模板 = config.example.toml 的原样默认模板（本卡要检验默认模板是否匹配该版本真机日志）
set -eu
VER=${1:?用法: gen-config-fabric.sh <版本> <slot> [服名]}
SLOT=${2:?用法: gen-config-fabric.sh <版本> <slot> [服名]}
NAME=${3:-"fab$(printf '%s' "$VER" | tr -d '.')"}
RCON=$((25710 + SLOT))

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
echo "$HOME/Y33-Bot/config-fabric-$VER.toml"
