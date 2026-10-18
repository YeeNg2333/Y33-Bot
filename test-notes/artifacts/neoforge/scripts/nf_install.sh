#!/bin/bash
# 部署一个 NeoForge 服务端实例（卡 t_efe57773）
# 用法: nf_install.sh <MC版本> <NeoForge版本> <slot 0-9>
# 端口遵循 00-env.md：游戏 25630+slot，RCON 25730+slot；目录 ~/mc-test/neoforge/<MC版本>/
set -u
V=${1:?用法: nf_install.sh <MC版本> <NeoForge版本> <slot>}
NF=${2:?缺 NeoForge 版本}
SLOT=${3:?缺 slot}
. ~/y33-env.sh 2>/dev/null || true
MIRROR=https://maven.creeperhost.net
case "$V" in
  26.*) JDK=25 ;;
  *)    JDK=21 ;;
esac
export JAVA_HOME="$HOME/jdk-$JDK"
export PATH="$JAVA_HOME/bin:$PATH"
TOOLS="$HOME/mc-test/neoforge/tools"
LOGS="$HOME/mc-test/neoforge/logs"
D="$HOME/mc-test/neoforge/$V"
GAME=$((25630 + SLOT)); RCON=$((25730 + SLOT))
mkdir -p "$TOOLS" "$LOGS" "$D"

echo "=== [$(date '+%F %T')] 部署 NeoForge $NF（MC $V，slot $SLOT，JDK$JDK） ==="
java -version 2>&1 | head -1
echo "mirror=$MIRROR  game=$GAME  rcon=$RCON  dir=$D"

INST="$TOOLS/nf-$NF-installer.jar"
if [ ! -s "$INST" ]; then
  curl -4 -sS --max-time 300 -o "$INST" -w 'installer 下载 http=%{http_code} bytes=%{size_download} time=%{time_total}\n' \
    "$MIRROR/net/neoforged/neoforge/$NF/neoforge-$NF-installer.jar"
fi
ls -l "$INST"
# 记录镜像侧声明的 sha1（.sha1 文件）与本地实际值，便于核对
curl -4 -sS --max-time 60 -o "$D/installer.sha1.remote" "$MIRROR/net/neoforged/neoforge/$NF/neoforge-$NF-installer.jar.sha1" || true
sha1sum "$INST" | awk '{print $1}' > "$D/installer.sha1.local"
echo "remote sha1: $(cat "$D/installer.sha1.remote" 2>/dev/null | head -c 60)"
echo "local  sha1: $(cat "$D/installer.sha1.local")"

PATCHED="$TOOLS/nf-$NF-installer-patched.jar"
python3 "$HOME/mc-test/neoforge/scripts/nf_patch_installer.py" "$INST" "$PATCHED" "$MIRROR"

cd "$D"
echo "=== [$(date '+%F %T')] --installServer 开始 ==="
java -Xmx1200M -jar "$PATCHED" --installServer 2>&1 | tee install.out
RC=${PIPESTATUS[0]}
echo "=== [$(date '+%F %T')] installer exit=$RC ==="
ls -la "$D" | head -25
du -sh "$D/libraries" 2>/dev/null
echo "--- 失败库统计 ---"
grep -c 'SocketTimeoutException\|UnknownHost\|failed to download' install.out || true
echo "--- 生成的启动脚本 ---"
ls -l run.sh run.bat user_jvm_args.txt 2>/dev/null
df -h / | tail -1
