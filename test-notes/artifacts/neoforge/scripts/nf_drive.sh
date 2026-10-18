#!/bin/bash
# NeoForge 测试矩阵驱动（卡 t_efe57773）：逐版本 安装 → 配置 → 完整用例 → 清理
# 用法: nohup setsid bash nf_drive.sh > ~/mc-test/neoforge/logs/nf-drive.out 2>&1 &
#
# 版本清单（与理由，详见 test-notes/04-neoforge.md §2）：
#   近两年（2024-10-18 之后）正式版里「每个版本线的首个正式版」，再按 NeoForge 官方是否发布过稳定版收敛：
#   1.21.3 (NF 21.3.100)   1.21.2 只有 21.2.0-beta → 该线用 1.21.3
#   1.21.4 (NF 21.4.161)
#   1.21.5 (NF 21.5.101)
#   1.21.8 (NF 21.8.57)    1.21.6/1.21.7 只有 beta → 该线用 1.21.8
#   1.21.10 (NF 21.10.64)  1.21.9 只有 beta → 该线用 1.21.10
#   1.21.11 (NF 21.11.48)  线末对照版本（也是默认 chat 模板问题的现场版本）
#   26.1.2 (NF 26.1.2.122) MC 26.1 / 26.1.1 无 NeoForge 稳定版
#   26.2 (NF 26.2.0.93)
#   26.3 (NF 26.3.0.89)    最新
set -u
. "$HOME/y33-env.sh" 2>/dev/null || true
BASE="$HOME/mc-test/neoforge"
SCR="$BASE/scripts"
LOGS="$BASE/logs"
ART="$HOME/mc-test/artifacts/neoforge"
mkdir -p "$LOGS" "$ART"

SLOTS="1.21.4:21.4.161:0 1.21.11:21.11.48:4 26.3:26.3.0.89:8 26.2:26.2.0.93:7 26.1.2:26.1.2.122:6 1.21.3:21.3.100:5 1.21.5:21.5.101:1 1.21.8:21.8.57:2 1.21.10:21.10.64:3"

echo "########## NeoForge 矩阵驱动开始 $(date '+%F %T') ##########"
for ITEM in $SLOTS; do
  MC=${ITEM%%:*}; REST=${ITEM#*:}; NF=${REST%%:*}; SLOT=${REST##*:}
  DRV="$LOGS/drive-$MC.out"
  echo "===== [$MC / NF $NF / slot $SLOT] $(date '+%F %T') =====" | tee -a "$LOGS/nf-drive.out"
  # 已完成（有结论行）则跳过
  if [ -s "$ART/$MC/results-$MC.txt" ] && grep -q "^conclusion_" "$ART/$MC/results-$MC.txt" 2>/dev/null; then
    echo "[跳过] $MC 已有结论：$(grep '^conclusion_' "$ART/$MC/results-$MC.txt")" | tee -a "$LOGS/nf-drive.out"
    continue
  fi
  {
    echo "### 1) 安装 $(date '+%F %T')"
    bash "$SCR/nf_install.sh" "$MC" "$NF" "$SLOT"
    echo "### 2) 配置 $(date '+%F %T')"
    bash "$SCR/nf_setup.sh" "$MC" "$NF" "$SLOT"
    echo "### 3) 完整用例 $(date '+%F %T')"
    bash "$SCR/nf_smoke_one.sh" "$MC" "$NF" "$SLOT"
    echo "### 4) 收尾 $(date '+%F %T')"
    echo "installer_exit_summary: $(grep -c 'The server installed successfully' "$BASE/$MC/install.out" 2>/dev/null || echo 0)"
    echo "download_errors: $(grep -c 'SocketTimeoutException\|UnknownHostException' "$BASE/$MC/install.out" 2>/dev/null || echo 0)"
  } >> "$DRV" 2>&1
  echo "  -> $MC 完成，见 $DRV 与 $ART/$MC/" | tee -a "$LOGS/nf-drive.out"
  # 每版本收尾：清理可再生产物（libraries/world/logs）以省磁盘
  if grep -q '^conclusion_.*=启动失败' "$ART/$MC/results-$MC.txt" 2>/dev/null; then
    echo "  [失败版本] 保留 $BASE/$MC/libraries 供排查" | tee -a "$LOGS/nf-drive.out"
  else
    rm -rf "$BASE/$MC/libraries" "$BASE/$MC/world" "$BASE/$MC/logs" "$BASE/$MC/console.out.log"
    echo "  [清理] 已删 libraries/world/logs（保留 run.sh + server.jar + 制品）" | tee -a "$LOGS/nf-drive.out"
  fi
  df -h / | tail -1 | tee -a "$LOGS/nf-drive.out"
  free -m | sed -n 2p | tee -a "$LOGS/nf-drive.out"
  sleep 15
done
echo "########## NeoForge 矩阵驱动结束 $(date '+%F %T') ##########" | tee -a "$LOGS/nf-drive.out"
echo "--- 汇总 ---" | tee -a "$LOGS/nf-drive.out"
for d in "$ART"/*/; do
  v=$(basename "$d")
  echo "== $v: $(grep -h '^conclusion_\|^start_ok=\|^chat_template_match=\|^check_exit=\|^run_exit=' "$d/results-$v.txt" 2>/dev/null | tr '\n' ' ')" | tee -a "$LOGS/nf-drive.out"
done
