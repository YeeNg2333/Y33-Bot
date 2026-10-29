#!/bin/bash
# 生成 NeoForge 版本矩阵表（卡 t_efe57773）：族 / 对应MC / stable 首末 / 各通道计数
set -u
T="$HOME/mc-test/tools/nf-metadata.xml"
OUT="$HOME/mc-test/artifacts/neoforge/version-matrix.tsv"
mkdir -p "$(dirname "$OUT")"
python3 - "$T" "$OUT" <<'PY'
import re, sys, collections
txt = open(sys.argv[1]).read()
vers = re.findall(r"<version>([^<]+)</version>", txt)
g = collections.defaultdict(lambda: collections.defaultdict(list))
for v in vers:
    b = re.split(r"[-+]", v)[0]
    p = b.split(".")
    if len(p) < 3 or not all(x.isdigit() for x in p):
        continue
    ch = "stable" if ("-" not in v and "+" not in v) else ("alpha" if "-alpha" in v else ("beta" if "-beta" in v else "snapshot"))
    g[".".join(p[:2])][ch].append(v)
def k(f):
    return tuple(int(x) for x in f.split("."))
rows = []
for f in sorted(g, key=k):
    d = g[f]
    st = sorted(d.get("stable", []), key=lambda v: [int(x) for x in v.split(".")])
    rows.append((f, len(st), st[0] if st else "-", st[-1] if st else "-",
                 len(d.get("alpha", [])), len(d.get("beta", [])), len(d.get("snapshot", []))))
with open(sys.argv[2], "w") as fh:
    fh.write("neoforge_family\tstable_first\tstable_last\tstable_count\talpha\tbeta\tsnapshot\n")
    for r in rows:
        fh.write("\t".join(str(x) for x in (r[0], r[2], r[3], r[1], r[4], r[5], r[6])) + "\n")
    fh.write(f"# metadata total versions = {len(vers)}\n")
print(open(sys.argv[2]).read())
PY
