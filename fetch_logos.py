#!/usr/bin/env python3
"""生成每个分站的「赛事 logo」徽标图，供 .ics 的 ATTACH 使用。

组成（全部为官方素材）：
  F1     : 官方 F1 wordmark（media.formula1.com）+ 官方赛道轮廓图
           （分站页 payload 里的 circuitImage.public_id，黑线版）
  MotoGP : 官方 MotoGP wordmark（static.dorna.com）+ 官方赛道轮廓图
           （官方赛事 API 里 circuit.tracks[].assets.simple，白线版）

输出：
  img/badge/f1/<slug>.jpg     每站一张 320x320
  img/badge/moto/<code>.jpg
  img/badge/manifest.json     slug/code -> 相对路径
"""

import io
import json
import os
import re
import sys
import time
import urllib.request

from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "cache")
OUT_DIR = os.path.join(BASE, "img", "badge")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

SIZE = 320            # 输出边长
LOGO_W = 190          # wordmark 宽度
CIRCUIT_W = 190       # 赛道轮廓最大宽度
CIRCUIT_H = 115       # 赛道轮廓最大高度
QUALITY = 85

F1_LOGO = ("https://media.formula1.com/image/upload/f_auto,q_auto/"
           "v1677237319/etc/designs/fom-website/images/f1_logo.png")
MOTO_LOGO = "https://static.dorna.com/assets/logos/mgp/brand/mgp-logo-on-dark.png"

F1_BG = (225, 6, 0)     # F1 官方红
MOTO_BG = (12, 12, 12)  # MotoGP 官方深色底


def http_get(url, cache_name=None, tries=4):
    """带缓存与重试的 GET；图片类请求返回 bytes。"""
    if cache_name:
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, cache_name)
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            with open(path, "rb") as fh:
                return fh.read()
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read()
        except Exception as exc:  # CDN 偶发断连
            last = exc
            time.sleep(2 + i * 2)
    raise last


def next_payload(html):
    """解出 Next.js RSC payload 里的字符串。"""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,\s*"(.*?)"\]\)</script>', html, re.S)
    return "".join(chunks).encode().decode("unicode_escape", errors="ignore")


def f1_circuit_public_id(slug):
    """分站页 payload 里的官方赛道轮廓 public_id。"""
    from generate_ics import F1_ROUNDS, http_get as get_html

    html = get_html(f"https://www.formula1.com/en/racing/2026/{slug}", f"f1_{slug}.html")
    m = re.search(r'"circuitImage":\{"public_id":"([^"]+)"', next_payload(html))
    return m.group(1) if m else None


def moto_circuit_urls():
    """{shortname: 官方赛道轮廓 PNG URL}，取赛事 API 里 tracks[0].assets.simple。"""
    from generate_ics import http_get as get_json

    raw = get_json("https://api.pulselive.motogp.com/motogp/v1/events?seasonYear=2026",
                    "motogp_events.json")
    out = {}
    for ev in json.loads(raw):
        if ev.get("kind") != "GP":
            continue
        tracks = ((ev.get("circuit") or {}).get("tracks") or [])
        for t in tracks:
            simple = ((t.get("assets") or {}).get("simple") or {})
            if simple.get("path"):
                out[ev["shortname"].lower()] = simple["path"]
                break
    return out


def load_logo(url, cache_name):
    raw = http_get(url, cache_name)
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    bb = im.getchannel("A").getbbox()
    return im.crop(bb) if bb else im


def load_circuit(raw):
    """官方赛道轮廓线稿 -> 白色、裁掉留白、放大并锐化。"""
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    bb = im.getchannel("A").getbbox()
    if bb:
        im = im.crop(bb)
    w, h = im.size
    if not w or not h:
        return None
    sc = min(CIRCUIT_W / w, CIRCUIT_H / h)
    im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS)
    # 原图线条偏细，放大后做一次阈值锐化，避免发糊
    a = im.getchannel("A").point(lambda v: 255 if v > 110 else (int(v * 1.4) if v > 40 else 0))
    white = Image.new("RGBA", im.size, (255, 255, 255, 255))
    white.putalpha(a)
    return white


def compose(bg, logo, circuit, out_path):
    canvas = Image.new("RGBA", (SIZE, SIZE), bg + (255,))
    lw = LOGO_W
    logo = logo.resize((lw, max(1, int(logo.size[1] * lw / logo.size[0]))), Image.LANCZOS)
    canvas.alpha_composite(logo, ((SIZE - lw) // 2, 78))
    if circuit is not None:
        canvas.alpha_composite(circuit, ((SIZE - circuit.size[0]) // 2,
                                        205 - circuit.size[1] // 2))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.convert("RGB").save(out_path, "JPEG", quality=QUALITY, optimize=True)
    return os.path.getsize(out_path)


def main():
    from generate_ics import F1_ROUNDS

    manifest = {"f1": {}, "moto": {}}
    failed = []

    f1_logo = load_logo(F1_LOGO, "f1_wordmark.png")
    moto_logo = load_logo(MOTO_LOGO, "motogp_wordmark.png")

    print("生成 F1 赛事 logo ...")
    for slug, *_ in F1_ROUNDS:
        try:
            pid = f1_circuit_public_id(slug)
            circuit = None
            if pid:
                raw = http_get(f"https://media.formula1.com/image/upload/f_auto,q_auto/{pid}",
                               f"f1_track_{slug}.png")
                circuit = load_circuit(raw)
            rel = f"img/badge/f1/{slug}.jpg"
            size = compose(F1_BG, f1_logo, circuit, os.path.join(BASE, rel))
            manifest["f1"][slug] = rel
            print(f"  {slug:22} {size // 1024:4d} KB  {pid or '(无赛道图)'}")
        except Exception as exc:
            failed.append((slug, str(exc)))
            print(f"  !! {slug}: {exc}")

    print("生成 MotoGP 赛事 logo ...")
    for code, url in moto_circuit_urls().items():
        try:
            raw = http_get(url, f"moto_track_{code}.png")
            circuit = load_circuit(raw)
            rel = f"img/badge/moto/{code}.jpg"
            size = compose(MOTO_BG, moto_logo, circuit, os.path.join(BASE, rel))
            manifest["moto"][code] = rel
            print(f"  {code:22} {size // 1024:4d} KB")
        except Exception as exc:
            failed.append((code, str(exc)))
            print(f"  !! {code}: {exc}")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    print(f"赛事 logo 清单已写出：F1 {len(manifest['f1'])} 张，MotoGP {len(manifest['moto'])} 张")
    if failed:
        print(f"警告：{len(failed)} 张生成失败", file=sys.stderr)


if __name__ == "__main__":
    main()
