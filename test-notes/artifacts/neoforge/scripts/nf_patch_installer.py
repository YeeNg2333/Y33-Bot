#!/usr/bin/env python3
"""把 NeoForge installer 里嵌的 maven.neoforged.net 主机替换成可达镜像，重打包成新 jar。

用法: nf_patch_installer.py <in.jar> <out.jar> [mirror_base=https://maven.creeperhost.net]
背景: 测试机 DNS 被污染 + 真实 IP 被墙，maven.neoforged.net 完全不可达；installer 的所有下载
      URL 都写死在 install_profile.json / version.json 里，替换主机即可让 install 走镜像。
"""

import re
import sys
import zipfile

OLD_HOST = "https://maven.neoforged.net/releases"
OLD_HOST2 = "https://maven.neoforged.net/"


def main() -> int:
    src, dst = sys.argv[1], sys.argv[2]
    mirror = (sys.argv[3] if len(sys.argv) > 3 else "https://maven.creeperhost.net").rstrip("/")
    stats = {}
    with zipfile.ZipFile(src) as zin:
        items = zin.infolist()
        blobs = {i.filename: zin.read(i.filename) for i in items}
    for name in ("install_profile.json", "version.json"):
        if name not in blobs:
            continue
        txt = blobs[name].decode("utf-8")
        n1 = txt.count(OLD_HOST)
        txt = txt.replace(OLD_HOST, mirror)
        n2 = txt.count(OLD_HOST2)
        txt = txt.replace(OLD_HOST2, mirror + "/")
        if name == "install_profile.json":
            # 镜像清单指向被墙的 mirrors.neoforged.net -> 换成不可路由地址，避免卡住
            txt = re.sub(r'"mirrorList"\s*:\s*"[^"]*"', '"mirrorList": "http://127.0.0.1:9/disabled.json"', txt)
        blobs[name] = txt.encode("utf-8")
        stats[name] = (n1, n2)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for i in items:
            zout.writestr(i, blobs[i.filename])
    print(f"patched {src} -> {dst} (mirror={mirror})")
    for k, (a, b) in stats.items():
        print(f"  {k}: {a} x {OLD_HOST} -> {b} x {OLD_HOST2}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
