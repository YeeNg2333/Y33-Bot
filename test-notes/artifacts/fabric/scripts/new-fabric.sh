#!/usr/bin/env bash
# 建/复用 Fabric 服务端实例（Y33-Bot 测试环境，卡 t_5bccfcd8）
#
# 用法: new-fabric.sh <MC版本> <slot 0-9> [loader版本] [online-mode]
#   目录: ~/mc-test/fabric/<版本>/
#   端口: 游戏 25610+slot / RCON 25710+slot     （端口表见 test-notes/00-env.md）
#   Java: 按 ~/mc-test/versions.tsv 里该版本要求的 javaVersion 自动选 ~/jdk-21 或 ~/jdk-25
#   依赖: vanilla server.jar（Mojang，sha1 校验）+ fabric-installer + fabric-api（maven.fabricmc.net）
#   RCON 密码: 取 ~/.env 的 MC_RCON_PASSWORD
set -euo pipefail

VER=${1:?用法: new-fabric.sh <MC版本> <slot> [loader] [online-mode]}
SLOT=${2:?用法: new-fabric.sh <MC版本> <slot> [loader] [online-mode]}
LOADER=${3:-0.19.5}
ONLINE=${4:-false}

if [ -f "$HOME/.env" ]; then set -a; . "$HOME/.env"; set +a; fi

TSV="$HOME/mc-test/versions.tsv"
BASE="$HOME/mc-test/fabric/$VER"
GAME_PORT=$((25610 + SLOT))
RCON_PORT=$((25710 + SLOT))
INSTALLER="$HOME/mc-test/tools/fabric-installer-1.1.2.jar"

URL=$(awk -F'\t' -v v="$VER" '$1==v{print $5}' "$TSV")
SHA=$(awk -F'\t' -v v="$VER" '$1==v{print $6}' "$TSV")
JV=$(awk -F'\t' -v v="$VER" '$1==v{print $3}' "$TSV")
[ -n "$URL" ] || { echo "[错误] 版本 $VER 不在 $TSV"; exit 1; }
JV=${JV:-21}
if [ ! -x "$HOME/jdk-$JV/bin/java" ]; then
  echo "[警告] $VER 需要 Java $JV，但 ~/jdk-$JV 不存在；回退 JDK21"
  JV=21
fi
JAVA_HOME="$HOME/jdk-$JV"

[ -s "$INSTALLER" ] || { echo "[错误] 缺 $INSTALLER"; exit 1; }
[ -n "${MC_RCON_PASSWORD:-}" ] || { echo "[错误] ~/.env 里没有 MC_RCON_PASSWORD"; exit 1; }

mkdir -p "$BASE/mods" "$BASE/logs"
cd "$BASE"

# 1) 原版 server.jar（Mojang，sha1 校验）
if [ ! -s server.jar ]; then
  echo "[下载] vanilla server.jar <- $URL"
  curl -fSL --retry 3 -o server.jar "$URL"
fi
if [ -n "$SHA" ]; then
  echo "$SHA  server.jar" | sha1sum -c - | sed 's/^/  /'
fi

# 2) Fabric loader（installer 复用同目录的 server.jar，不再重复下载）
echo "[安装] fabric-installer $VER loader=$LOADER"
"$JAVA_HOME/bin/java" -jar "$INSTALLER" server \
  -dir "$BASE" -mcversion "$VER" -loader "$LOADER" 2>&1 | sed 's/^/  /'

# 3) fabric-api（挑 maven 上该 MC 版本最新的构建）
if [ ! -s "$HOME/mc-test/fabric-api-$VER.jar" ]; then
  FAPI=$(grep -o "<version>[^<]*+$VER</version>" "$HOME/mc-test/tools/fabric-api-maven-metadata.xml" | tail -1 | sed 's/<[^>]*>//g')
  [ -n "$FAPI" ] || { echo "[警告] maven 上没有 +$VER 的 fabric-api 构建"; FAPI=""; }
  if [ -n "$FAPI" ]; then
    P=$(echo "$FAPI" | sed 's/+/%2B/')
    echo "[下载] fabric-api $FAPI"
    curl -fSL --retry 3 -o "$HOME/mc-test/fabric-api-$VER.jar" \
      "https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/$FAPI/fabric-api-$FAPI.jar"
  fi
fi
FAPI_VER="(none)"
if [ -s "$HOME/mc-test/fabric-api-$VER.jar" ]; then
  cp -f "$HOME/mc-test/fabric-api-$VER.jar" "$BASE/mods/"
  FAPI_VER=$(unzip -p "$BASE/mods/fabric-api-$VER.jar" fabric.mod.json 2>/dev/null \
    | tr ',' '\n' | grep -m1 '"version"' | sed 's/.*: *"//; s/".*//' || echo "?")
fi

# 4) 配置
printf 'eula=true\n' > eula.txt
cat > server.properties <<EOF
enable-rcon=true
rcon.port=$RCON_PORT
rcon.password=$MC_RCON_PASSWORD
server-port=$GAME_PORT
online-mode=$ONLINE
motd=Y33 fabric $VER
max-players=20
view-distance=4
simulation-distance=4
spawn-protection=0
enable-command-block=false
pause-when-empty-seconds=0
EOF

cat > start.sh <<EOF
#!/usr/bin/env bash
cd "\$(dirname "\$0")"
export JAVA_HOME="$JAVA_HOME"
exec "\$JAVA_HOME/bin/java" -Xms512M -Xmx1024M -jar fabric-server-launch.jar nogui
EOF
chmod +x start.sh

cat > instance.env <<EOF
export MC_VERSION="$VER"
export MC_FAMILY="fabric"
export MC_DIR="$BASE"
export MC_GAME_PORT=$GAME_PORT
export MC_RCON_PORT=$RCON_PORT
export MC_TMUX="mc-fabric-${VER//./_}"
export MC_LOADER="$LOADER"
export MC_FAPI="$FAPI_VER"
export JAVA_HOME="$JAVA_HOME"
export MC_LOG="$BASE/logs/latest.log"
EOF

# fabric loader 版本（installer 写的，从 launcher 配置里读出来核对）
LOADER_INSTALLED=$(unzip -p fabric-server-launch.jar fabric-server-launch.properties 2>/dev/null | tr ',' '\n' | grep -m1 loader | sed 's/.*: *"//; s/".*//' || echo "?")
cat <<EOF
[实例] 版本        = $VER（Java $JV）
[实例] 目录        = $BASE
[实例] 游戏端口    = $GAME_PORT     RCON 端口 = $RCON_PORT
[实例] loader      = 请求 $LOADER / launch.jar 内 = $LOADER_INSTALLED
[实例] fabric-api  = $FAPI_VER
[实例] 日志        = $BASE/logs/latest.log
[启动] tmux new -d -s mc-fabric-${VER//./_} "cd $BASE && ./start.sh 2>&1 | tee -a console.out.log"
[停止] tmux send-keys -t mc-fabric-${VER//./_} 'stop' Enter
EOF
