#!/usr/bin/env python3
"""抓取并压缩 F1 / MotoGP 官方赛事图片，供 .ics 的 ATTACH 使用。

输出：
  img/f1/<slug>.jpg      F1 每站官方主视觉（formula1.com 分站页 JSON-LD image）
  img/moto/<code>.jpg    MotoGP 每站官方赛事图（官方赛事 API 的 TOP 资产，无则用 BACKGROUND）
  img/manifest.json      slug/code -> 相对路径 的映射

图片统一裁成最长边 640px 的 JPEG（质量 72），单张控制在 60KB 以内，
避免 iPhone 上一个日历里 269 张图把流量跑满。
"""

import io
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

from PIL import Image, ImageOps

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "cache")
IMG_DIR = os.path.join(BASE, "img")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MAX_SIDE = 640
QUALITY = 72


def http_get(url, cache_name=None, accept="*/*"):
    if cache_name:
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, cache_name)
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            with open(path, "rb") as fh:
                return fh.read()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def save_jpeg(raw, out_path):
    im = Image.open(io.BytesIO(raw))
    if im.mode not in ("RGB",):
        im = im.convert("RGB")
    # 官方赛事图普遍偏暗，做一次轻度自动对比度，日历缩略图更清晰
    im = ImageOps.autocontrast(im, cutoff=1)
    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    im.save(out_path, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return os.path.getsize(out_path)


def f1_images():
    """返回 {slug: url}，来源是各分站页 JSON-LD 里的官方主视觉。"""
    from generate_ics import F1_ROUNDS, http_get  # 复用抓取与缓存

    out = {}
    for slug, *_ in F1_ROUNDS:
        html = http_get(f"https://www.formula1.com/en/racing/2026/{slug}", f"f1_{slug}.html")
        url = None
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                d = json.loads(m.group(1))
            except Exception:
                continue
            if isinstance(d, dict) and d.get("subEvent"):
                url = (d.get("image") or {}).get("url")
                break
        if url:
            out[slug] = url
    return out


def moto_images():
    """返回 {shortname: url}，取官方赛事 API 的 TOP 资产，没有则退回 BACKGROUND。"""
    from generate_ics import http_get

    raw = http_get("https://api.pulselive.motogp.com/motogp/v1/events?seasonYear=2026",
                   "motogp_events.json")
    data = json.loads(raw)
    out = {}
    for ev in data:
        if ev.get("kind") != "GP":
            continue
        assets = {}
        for a in ev.get("assets") or []:
            assets.setdefault(a.get("type"), []).append(a)
        pick = None
        for typ in ("TOP", "BACKGROUND"):
            cands = [a for a in assets.get(typ, []) if "@1x" in (a.get("quality") or "")] \
                or assets.get(typ, [])
            if cands:
                pick = cands[0].get("path")
                break
        if pick:
            out[ev["shortname"].lower()] = pick
    return out


def download(url, tries=4):
    """图片 CDN 偶发断连，重试几次。"""
    last = None
    for i in range(tries):
        try:
            return http_get(url, accept="image/jpeg,image/png,image/*")
        except Exception as exc:
            last = exc
            time.sleep(2 + i * 2)
    raise last


def main():
    manifest = {"f1": {}, "moto": {}}
    failed = []

    print("下载 F1 官方赛事图 ...")
    for slug, url in f1_images().items():
        try:
            raw = download(url)
            rel = f"img/f1/{slug}.jpg"
            size = save_jpeg(raw, os.path.join(BASE, rel))
            manifest["f1"][slug] = rel
            print(f"  {slug:22} {size // 1024:4d} KB  {url.split('/')[-1][:50]}")
        except Exception as exc:
            failed.append((slug, str(exc)))
            print(f"  !! {slug}: {exc}")

    print("下载 MotoGP 官方赛事图 ...")
    for code, url in moto_images().items():
        try:
            raw = download(url)
            rel = f"img/moto/{code}.jpg"
            size = save_jpeg(raw, os.path.join(BASE, rel))
            manifest["moto"][code] = rel
            print(f"  {code:22} {size // 1024:4d} KB  {url}")
        except Exception as exc:
            failed.append((code, str(exc)))
            print(f"  !! {code}: {exc}")

    manifest["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(IMG_DIR, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    print(f"图片清单已写出：F1 {len(manifest['f1'])} 张，MotoGP {len(manifest['moto'])} 张")
    if failed:
        print(f"警告：{len(failed)} 张下载失败", file=sys.stderr)


if __name__ == "__main__":
    main()
