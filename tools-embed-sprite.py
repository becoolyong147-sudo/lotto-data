# -*- coding: utf-8 -*-
"""
tools-embed-sprite.py — 把 ChatGPT 生成的素材图转成可内嵌 HTML 的 webp base64

用法:  python tools-embed-sprite.py celebrate.png
输出:  celebrate.png.b64.txt  (内容是 data:image/webp;base64,... 一整行)
       并在 console 打印尺寸/压缩前后大小

规则: 宽度超过 2048 自动等比缩到 2048; webp 质量 82（和现有生肖雪碧图一致的量级）
"""
import sys, os, base64, io
from PIL import Image

def main():
    if len(sys.argv) < 2:
        print("用法: python tools-embed-sprite.py <图片文件> [质量默认82]")
        return
    path = sys.argv[1]
    q = int(sys.argv[2]) if len(sys.argv) > 2 else 82
    im = Image.open(path)
    w, h = im.size
    orig_kb = os.path.getsize(path) // 1024
    if w > 2048:
        nh = round(h * 2048 / w)
        im = im.resize((2048, nh), Image.LANCZOS)
        print(f"缩放: {w}x{h} → 2048x{nh}")
        w, h = 2048, nh
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, format="WEBP", quality=q, method=6)
    b64 = base64.b64encode(buf.getvalue()).decode()
    out = "data:image/webp;base64," + b64
    out_path = path + ".b64.txt"
    with open(out_path, "w") as f:
        f.write(out)
    print(f"完成: {path} ({orig_kb}KB) → webp q{q} {len(buf.getvalue())//1024}KB → base64 {len(out)//1024}KB")
    print(f"尺寸: {w}x{h}  |  输出: {out_path}")

if __name__ == "__main__":
    main()
