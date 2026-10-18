#!/usr/bin/env bash
# 批量跑原版矩阵：bash ~/mc-test/run-matrix.sh <mode> <版本:slot> [<版本:slot> ...]
# 例: bash ~/mc-test/run-matrix.sh full 1.21.3:2 1.21.4:3
MODE="$1"; shift
for pair in "$@"; do
  VER="${pair%%:*}"
  SLOT="${pair##*:}"
  mkdir -p "$HOME/mc-test/artifacts/vanilla/$VER"
  echo "########## $VER (slot $SLOT) 开始 $(date '+%F %T') ##########"
  bash "$HOME/mc-test/vanilla-matrix.sh" "$VER" "$SLOT" "$MODE" > "$HOME/mc-test/artifacts/vanilla/$VER/matrix.out" 2>&1
  RC=$?
  NF=$(grep -ac '\[结果\]' "$HOME/mc-test/artifacts/vanilla/$VER/matrix.out")
  NFALL=$(grep -acE '\[结果\] C[0-9]+ FAIL' "$HOME/mc-test/artifacts/vanilla/$VER/matrix.out")
  echo "########## $VER rc=$RC 用例=$NF 失败=$NFALL 结束 $(date '+%F %T') ##########"
done
echo "########## 批量结束 $(date '+%F %T') ##########"
