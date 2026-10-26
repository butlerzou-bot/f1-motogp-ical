#!/usr/bin/env python3
"""生成「赛事 logo」徽标图，供 .ics 的 ATTACH 使用。

官方并没有发布每站 GP 的专属字标（只有系列 logo），所以徽标 = 系列官方 wordmark
（仓库内置 img/brand/，F1 为 Simple Icons CC0 版 2018 现行标，MotoGP 为官方
Dorna 2025 字标），压在自己的品牌底色上做成方图，缩略图尺寸下也能认出来。

输出：
  img/badge/f1.jpg    F1 徽标：官方红底 + 白色 F1 wordmark
  img/badge/moto.jpg  MotoGP 徽标：深色底 + 白色 MotoGP wordmark
"""

import os

from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "img", "badge")
BRAND_DIR = os.path.join(BASE, "img", "brand")

SIZE = 320        # 输出边长
LOGO_W = 250      # wordmark 宽度
QUALITY = 92

F1_LOGO = os.path.join(BRAND_DIR, "f1-logo-white.png")
MOTO_LOGO = os.path.join(BRAND_DIR, "motogp-logo-white.png")

F1_BG = (225, 6, 0)     # F1 官方红
MOTO_BG = (17, 17, 17)  # MotoGP 官方深色底


def load_logo(path):
    """本地品牌 logo（白色单色版，透明底）"""
    im = Image.open(path).convert("RGBA")
    bb = im.getchannel("A").getbbox()
    return im.crop(bb) if bb else im


def compose(bg, logo, out_path):
    canvas = Image.new("RGBA", (SIZE, SIZE), bg + (255,))
    w = LOGO_W
    logo = logo.resize((w, max(1, int(logo.size[1] * w / logo.size[0]))), Image.LANCZOS)
    canvas.alpha_composite(logo, ((SIZE - w) // 2, (SIZE - logo.size[1]) // 2))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.convert("RGB").save(out_path, "JPEG", quality=QUALITY, optimize=True)
    return os.path.getsize(out_path)


def main():
    for src, bg, name in ((F1_LOGO, F1_BG, "f1.jpg"), (MOTO_LOGO, MOTO_BG, "moto.jpg")):
        out = os.path.join(OUT_DIR, name)
        size = compose(bg, load_logo(src), out)
        print(f"  {name:12} {size // 1024:3d} KB  -> {os.path.relpath(out, BASE)}")


if __name__ == "__main__":
    main()
