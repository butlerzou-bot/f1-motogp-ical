#!/usr/bin/env python3
"""生成 F1 / MotoGP 2026 赛季 iCalendar (.ics) 订阅源。

数据源（均为官方）：
  F1     : https://www.formula1.com/en/racing/2026/<round>  页面内 JSON-LD (schema.org SportsEvent.subEvent)
  MotoGP : https://api.pulselive.motogp.com/motogp/v1/events?seasonYear=2026

输出：
  f1.ics      F1 2026 全部分场次
  motogp.ics  MotoGP 2026 全部分场次
  racing.ics  两者合并

时间统一以 UTC (DTSTART;TZID 之外的 Z 形式) 写入，iOS 会按手机时区显示；
描述里额外给出赛道当地时间和北京时间。
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "cache")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
SHANGHAI = ZoneInfo("Asia/Shanghai")

F1_ROUNDS = [
    ("australia", "澳大利亚站", "墨尔本 · 阿尔伯特公园赛道", "Australia/Melbourne"),
    ("china", "中国站", "上海国际赛车场", "Asia/Shanghai"),
    ("japan", "日本站", "铃鹿赛道", "Asia/Tokyo"),
    ("miami", "美国迈阿密站", "迈阿密花园赛道", "America/New_York"),
    ("canada", "加拿大站", "蒙特利尔 · 吉尔·维伦纽夫赛道", "America/Toronto"),
    ("monaco", "摩纳哥站", "蒙特卡洛赛道", "Europe/Monaco"),
    ("barcelona-catalunya", "巴塞罗那站", "加泰罗尼亚赛道", "Europe/Madrid"),
    ("austria", "奥地利站", "施皮尔贝格 · 红牛环", "Europe/Vienna"),
    ("great-britain", "英国站", "银石赛道", "Europe/London"),
    ("belgium", "比利时站", "斯帕-弗朗科尔尚赛道", "Europe/Brussels"),
    ("hungary", "匈牙利站", "布达佩斯赛道", "Europe/Budapest"),
    ("netherlands", "荷兰站", "赞德沃特赛道", "Europe/Amsterdam"),
    ("italy", "意大利站", "蒙扎赛道", "Europe/Rome"),
    ("spain", "西班牙站", "马德里赛道", "Europe/Madrid"),
    ("azerbaijan", "阿塞拜疆站", "巴库赛道", "Asia/Baku"),
    ("bahrain", "巴林站（马来西亚）", "雪邦国际赛车场", "Asia/Kuala_Lumpur"),
    ("singapore", "新加坡站", "滨海湾赛道", "Asia/Singapore"),
    ("united-states", "美国站", "奥斯汀 · 美洲赛道", "America/Chicago"),
    ("mexico", "墨西哥站", "墨西哥城 · 埃罗德里戈·迭斯赛道", "America/Mexico_City"),
    ("brazil", "巴西站", "圣保罗 · 若昂·保罗赛道", "America/Sao_Paulo"),
    ("las-vegas", "美国拉斯维加斯站", "拉斯维加斯赛道", "America/Los_Angeles"),
    ("qatar", "卡塔尔站", "卢赛尔国际赛道", "Asia/Qatar"),
    ("united-arab-emirates", "阿布扎比站", "亚斯码头赛道", "Asia/Dubai"),
]

MOTO_ROUNDS = {
    "THAILAND": ("泰国站", "武里南国际赛道"),
    "BRAZIL": ("巴西站", "戈亚尼亚 · 塞纳赛道"),
    "USA": ("美国站", "奥斯汀 · 美洲赛道"),
    "SPAIN": ("西班牙站", "赫雷斯赛道"),
    "FRANCE": ("法国站", "勒芒 · 布萨奇赛道"),
    "CATALONIA": ("加泰罗尼亚站", "巴塞罗那-加泰罗尼亚赛道"),
    "ITALY": ("意大利站", "穆加洛赛道"),
    "HUNGARY": ("匈牙利站", "巴拉顿赛道"),
    "CZECHIA": ("捷克站", "布尔诺赛道"),
    "NETHERLANDS": ("荷兰站", "阿森赛道"),
    "GERMANY": ("德国站", "萨克森环赛道"),
    "GREAT BRITAIN": ("英国站", "银石赛道"),
    "ARAGON": ("阿拉贡站", "阿拉贡 MotorLand 赛道"),
    "SAN MARINO": ("圣马力诺站", "米萨诺赛道"),
    "AUSTRIA": ("奥地利站", "红牛环赛道"),
    "JAPAN": ("日本站", "茂木赛道"),
    "INDONESIA": ("印度尼西亚站", "曼达利卡赛道"),
    "AUSTRALIA": ("澳大利亚站", "菲利普岛赛道"),
    "MALAYSIA": ("马来西亚站", "雪邦国际赛车场"),
    "QATAR": ("卡塔尔站", "卢赛尔国际赛道"),
    "PORTUGAL": ("葡萄牙站", "波尔蒂芒赛道"),
    "VALENCIA": ("瓦伦西亚站", "里克·托尔莫赛道"),
}

SERIES_ICON = {"F1": "🏎️", "MotoGP": "🏍️"}

# 每站对应的国旗 emoji（用作标题前的赛事标识）
F1_FLAG = {
    "australia": "🇦🇺", "china": "🇨🇳", "japan": "🇯🇵", "miami": "🇺🇸",
    "canada": "🇨🇦", "monaco": "🇲🇨", "barcelona-catalunya": "🇪🇸", "austria": "🇦🇹",
    "great-britain": "🇬🇧", "belgium": "🇧🇪", "hungary": "🇭🇺", "netherlands": "🇳🇱",
    "italy": "🇮🇹", "spain": "🇪🇸", "azerbaijan": "🇦🇿", "bahrain": "🇲🇾",
    "singapore": "🇸🇬", "united-states": "🇺🇸", "mexico": "🇲🇽", "brazil": "🇧🇷",
    "las-vegas": "🇺🇸", "qatar": "🇶🇦", "united-arab-emirates": "🇦🇪",
}

MOTO_FLAG = {
    "tha": "🇹🇭", "bra": "🇧🇷", "usa": "🇺🇸", "spa": "🇪🇸", "fra": "🇫🇷",
    "cat": "🇪🇸", "ita": "🇮🇹", "hun": "🇭🇺", "cze": "🇨🇿", "ned": "🇳🇱",
    "ger": "🇩🇪", "gbr": "🇬🇧", "ara": "🇪🇸", "rsm": "🇸🇲", "aut": "🇦🇹",
    "jpn": "🇯🇵", "ina": "🇮🇩", "aus": "🇦🇺", "mal": "🇲🇾", "qat": "🇶🇦",
    "por": "🇵🇹", "val": "🇪🇸",
}

# 赛事图片托管地址（GitHub Pages）
IMAGE_BASE = "https://butlerzou-bot.github.io/f1-motogp-ical"


def load_manifest():
    path = os.path.join(BASE, "img", "manifest.json")
    if not os.path.exists(path):
        return {"f1": {}, "moto": {}}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


F1_SESSION_CN = {
    "Practice 1": "练习赛 1",
    "Practice 2": "练习赛 2",
    "Practice 3": "练习赛 3",
    "Sprint Qualifying": "冲刺排位赛",
    "Sprint": "冲刺赛",
    "Qualifying": "排位赛",
    "Race": "正赛",
}

MOTO_SESSION_CN = {
    "FP1": "练习赛 FP1",
    "PR": "练习赛 Practice",
    "FP2": "练习赛 FP2",
    "Q1": "排位赛 Qualifying",
    "Q2": "排位赛 Qualifying",
    "Q3": "排位赛 Qualifying",
    "Q": "排位赛 Qualifying",
    "SPR": "冲刺赛 Sprint",
    "WUP": "热身赛 Warm Up",
    "RAC": "正赛 Race",
    "RAC2": "正赛 Race",
}

# 合并到同一个日历事件的分组键（Q1/Q2/Q3 同属排位赛）
MOTO_GROUP = {"Q1": "Q", "Q2": "Q", "Q3": "Q", "RAC2": "RAC"}


def http_get(url, cache_name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, cache_name)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8", "ignore")
    last = None
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = resp.read().decode("utf-8", "ignore")
            with open(path, "w") as fh:
                fh.write(body)
            return body
        except Exception as exc:  # 网络抖动重试
            last = exc
            time.sleep(3)
    raise RuntimeError(f"抓取失败 {url}: {last}")


def parse_utc(s):
    """'2026-03-13T03:30:00.000Z' / '2026-11-06T14:00:00+0300' -> aware datetime(UTC)"""
    s = s.strip()
    if s.endswith("Z"):
        s = re.sub(r"\.\d+$", "", s[:-1])
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})([+-])(\d{2})(\d{2})$", s)
    if m:
        base = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
        off = timedelta(hours=int(m.group(3)), minutes=int(m.group(4)))
        if m.group(2) == "-":
            off = -off
        return base.replace(tzinfo=timezone(off)).astimezone(timezone.utc)
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc)


def tz_lookup(name):
    """zoneinfo 对大小写敏感，这里做容错。"""
    for cand in (name, name.title(), name.capitalize()):
        try:
            return ZoneInfo(cand)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            continue
    return timezone.utc


def local_str(dt_utc, tz, fmt="%m-%d %H:%M"):
    return dt_utc.astimezone(tz).strftime(fmt)


def beijing_str(dt_utc):
    return dt_utc.astimezone(SHANGHAI).strftime("%m-%d %H:%M")


# ---------------------------------------------------------------- F1 数据

def load_f1():
    events = []
    manifest = load_manifest().get("f1", {})
    for slug, cn, circuit, tzname in F1_ROUNDS:
        url = f"https://www.formula1.com/en/racing/2026/{slug}"
        html = http_get(url, f"f1_{slug}.html")
        data = None
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                d = json.loads(m.group(1))
            except Exception:
                continue
            if isinstance(d, dict) and d.get("subEvent"):
                data = d
                break
        if not data:
            raise RuntimeError(f"F1 页面缺少 session 数据: {slug}")
        tz = tz_lookup(tzname)
        gp_name = cn
        for s in data["subEvent"]:
            key = s["name"].split(" - ")[0].strip()
            cn_session = F1_SESSION_CN.get(key)
            if not cn_session:
                continue
            start = parse_utc(s["startDate"])
            end = parse_utc(s.get("endDate") or s["startDate"])
            icon = f"{SERIES_ICON['F1']} {F1_FLAG.get(slug, '')}".strip()
            events.append({
                "uid": f"f1-2026-{slug}-{key.lower().replace(' ', '-')}@racing.multica.ai",
                "summary": f"{icon} F1 {gp_name} · {cn_session}",
                "start": start,
                "end": end,
                "location": circuit,
                "tz": tz,
                "tzname": tzname,
                "series": "F1",
                "url": url,
                "image": f"{IMAGE_BASE}/{manifest[slug]}" if slug in manifest else "",
                "extra": f"场次类型：{key}",
            })
    return events


# ------------------------------------------------------------- MotoGP 数据

def load_motogp():
    raw = http_get("https://api.pulselive.motogp.com/motogp/v1/events?seasonYear=2026",
                   "motogp_events.json")
    data = json.loads(raw)
    manifest = load_manifest().get("moto", {})
    events = []
    for ev in data:
        if ev.get("kind") != "GP":
            continue
        cn_name, circuit_cn = MOTO_ROUNDS.get(ev.get("additional_name", "").strip(),
                                                (ev.get("additional_name", "").strip(), ""))
        cn_name = cn_name or ev.get("additional_name", "").strip()
        tz = tz_lookup(ev.get("time_zone", "UTC"))
        city = (ev.get("circuit") or {}).get("city", "")
        country = (ev.get("circuit") or {}).get("country", "")
        where = ", ".join(x for x in (city, country) if x)
        loc = f"{circuit_cn}（{where}）" if circuit_cn else where

        # 只取 MotoGP 组别（MGP）的场次
        sess = []
        for b in ev.get("broadcasts") or []:
            cat = (b.get("category") or {}).get("acronym")
            if cat != "MGP":
                continue
            code = b.get("shortname")
            if code not in MOTO_SESSION_CN:
                continue
            start = parse_utc(b["date_start"])
            end = parse_utc(b.get("date_end") or b["date_start"])
            if end <= start:
                end = start + (timedelta(minutes=30) if code == "SPR" else timedelta(minutes=120))
            sess.append((code, start, end, b.get("name", "")))

        # 同一分组、连续时间的场次合并成一个日历事件（如 FP1 三段、Q1+Q2）
        merged = []
        for code, start, end, ename in sorted(sess, key=lambda x: x[1]):
            gcode = MOTO_GROUP.get(code, code)
            if merged and merged[-1][0] == gcode and (start - merged[-1][2]).total_seconds() < 7200:
                merged[-1] = (gcode, merged[-1][1], max(end, merged[-1][2]), ename)
            else:
                merged.append((gcode, start, end, ename))

        for code, start, end, ename in merged:
            short = ev.get("shortname", "").lower()
            icon = f"{SERIES_ICON['MotoGP']} {MOTO_FLAG.get(short, '')}".strip()
            events.append({
                "uid": f"motogp-2026-{short}-{code.lower()}@racing.multica.ai",
                "summary": f"{icon} MotoGP {cn_name} · {MOTO_SESSION_CN[code]}",
                "start": start,
                "end": end,
                "location": loc,
                "tz": tz,
                "tzname": ev.get("time_zone", "UTC"),
                "series": "MotoGP",
                "url": "https://www.motogp.com/en/calendar",
                "image": f"{IMAGE_BASE}/{manifest[short]}" if short in manifest else "",
                "extra": f"官方场次：{ename}",
            })
    return events


# ------------------------------------------------------------------- ICS

def esc(text):
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    """RFC 5545 按 75 字节折行"""
    data = line.encode("utf-8")
    if len(data) <= 73:
        return line
    out, cur = [], b""
    limit = 73
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > limit:
            out.append(cur.decode("utf-8"))
            cur = b""
            limit = 72
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def build_ics(events, cal_name, description, color, now):
    L = []
    L.append("BEGIN:VCALENDAR")
    L.append("VERSION:2.0")
    L.append("PRODID:-//Multica Racing Calendar//F1+MotoGP 2026//CN")
    L.append("CALSCALE:GREGORIAN")
    L.append("METHOD:PUBLISH")
    L.append(f"X-WR-CALNAME:{esc(cal_name)}")
    L.append(f"X-WR-CALDESC:{esc(description)}")
    L.append("X-WR-TIMEZONE:Asia/Shanghai")
    L.append("REFRESH-INTERVAL;VALUE=DURATION:P1D")
    L.append("X-PUBLISHED-TTL:PT12H")
    L.append(f"X-APPLE-CALENDAR-COLOR:{color}")
    L.append("BEGIN:VTIMEZONE")
    L.append("TZID:Asia/Shanghai")
    L.append("BEGIN:STANDARD")
    L.append("DTSTART:19700101T000000")
    L.append("TZOFFSETFROM:+0800")
    L.append("TZOFFSETTO:+0800")
    L.append("TZNAME:CST")
    L.append("END:STANDARD")
    L.append("END:VTIMEZONE")

    for e in events:
        desc = (
            f"{e['extra']}\n"
            f"地点：{e['location']}\n"
            f"赛道当地时间：{local_str(e['start'], e['tz'], '%Y-%m-%d %H:%M')} ({e['tzname']})\n"
            f"北京时间：{beijing_str(e['start'])} (UTC+8)\n"
            f"时长：{int((e['end'] - e['start']).total_seconds() // 60)} 分钟\n"
            f"官方页面：{e['url']}\n"
            f"数据来源：{'formula1.com 官方赛历' if e['series'] == 'F1' else 'MotoGP 官方赛事 API'}"
        )
        L.append("BEGIN:VEVENT")
        L.append(f"UID:{e['uid']}")
        L.append(f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}")
        L.append(f"DTSTART:{e['start'].strftime('%Y%m%dT%H%M%SZ')}")
        L.append(f"DTEND:{e['end'].strftime('%Y%m%dT%H%M%SZ')}")
        L.append(f"SUMMARY:{esc(e['summary'])}")
        L.append(f"DESCRIPTION:{esc(desc)}")
        L.append(f"LOCATION:{esc(e['location'])}")
        L.append(f"URL:{e['url']}")
        L.append(f"CATEGORIES:{e['series']}")
        if e.get("image"):
            L.append(f"ATTACH;VALUE=URI:{e['image']}")
        L.append("STATUS:CONFIRMED")
        L.append("TRANSP:OPAQUE")
        L.append("END:VEVENT")

    L.append("END:VCALENDAR")
    return "\r\n".join(fold(x) for x in L) + "\r\n"


def write(path, content):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    print(f"  写出 {os.path.basename(path):16} {len(content):7d} bytes")


def main():
    now = datetime.now(timezone.utc)
    print("抓取 F1 2026 ...")
    f1 = load_f1()
    print(f"  F1 场次 {len(f1)} 条 / {len(F1_ROUNDS)} 站")
    print("抓取 MotoGP 2026 ...")
    moto = load_motogp()
    print(f"  MotoGP 场次 {len(moto)} 条")
    if len(f1) < len(F1_ROUNDS) * 5 or len(moto) < 22 * 7:
        raise RuntimeError("场次数量异常，拒绝写出（可能是数据源临时异常）")

    f1.sort(key=lambda e: e["start"])
    moto.sort(key=lambda e: e["start"])
    allv = sorted(f1 + moto, key=lambda e: e["start"])

    write(os.path.join(BASE, "f1.ics"), build_ics(
        f1, "F1 2026 赛程", "2026 赛季 F1 全部分场次（练习赛/冲刺排位/冲刺赛/排位赛/正赛），时间为 UTC，iOS 自动换算当地时间", "#0A84FF", now))
    write(os.path.join(BASE, "motogp.ics"), build_ics(
        moto, "MotoGP 2026 赛程", "2026 赛季 MotoGP 全部分场次（练习赛/排位赛/冲刺赛/热身赛/正赛），时间为 UTC，iOS 自动换算当地时间", "#FF9F0A", now))
    write(os.path.join(BASE, "racing.ics"), build_ics(
        allv, "F1 + MotoGP 2026 赛程", "2026 赛季 F1 与 MotoGP 全部场次", "#30D158", now))


if __name__ == "__main__":
    main()
