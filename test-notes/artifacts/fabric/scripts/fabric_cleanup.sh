#!/usr/bin/env bash
# 收尾清理（卡 t_5bccfcd8）：删掉 Fabric 实例里可再生的大目录，保留 server.jar / mods / 制品 / 配置
set -u
echo "=== 清理前 ==="
du -sh "$HOME"/mc-test/fabric/*/ 2>/dev/null
for d in "$HOME"/mc-test/fabric/*/; do
  rm -rf "$d/libraries" "$d/world" "$d/logs" "$d/console.out.log"
done
echo "=== 清理后 ==="
du -sh "$HOME"/mc-test/fabric/*/ 2>/dev/null
echo "=== 制品仍在 ==="
find "$HOME"/mc-test/fabric -name '*.txt' | wc -l
echo "=== 磁盘 ==="
df -h / | tail -1
free -m | head -2 | tail -1
