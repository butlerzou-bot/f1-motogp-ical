# F1 + MotoGP 2026 日历订阅

把 2026 赛季 **F1** 和 **MotoGP** 的所有场次（练习赛 / 冲刺排位赛 / 冲刺赛 / 排位赛 / 正赛）做成 iCalendar 订阅源，
iPhone / iPad / Mac 的「日历」App 直接订阅即可，官方时间有变动会自动刷新。

## 订阅地址

| 日历 | 订阅 URL |
|---|---|
| F1 | `https://butlerzou-bot.github.io/f1-motogp-ical/f1.ics` |
| MotoGP | `https://butlerzou-bot.github.io/f1-motogp-ical/motogp.ics` |
| F1 + MotoGP 合并 | `https://butlerzou-bot.github.io/f1-motogp-ical/racing.ics` |

### iPhone / iPad（iOS 17+）

1. 打开 **设置** → **日历** → **账户** → **添加账户** → **其他**
2. 选择 **添加订阅日历**，粘贴上面的 URL
3. 右上角 **添加**，在「日历」App 里会出现一个同名日历，颜色可自定义

### macOS

「日历」App → 菜单 **文件** → **新建日历订阅** → 粘贴 URL。

## 数据来源

| 项目 | 来源 |
|---|---|
| F1 场次时间 | [formula1.com/en/racing/2026](https://www.formula1.com/en/racing/2026) 各分站页面内的 schema.org `SportsEvent.subEvent`（UTC） |
| MotoGP 场次时间 | MotoGP 官方赛事 API `api.pulselive.motogp.com/motogp/v1/events?seasonYear=2026`，取 MotoGP 组别（MGP）的场次 |
| 赛事 logo 徽标 | 系列官方 wordmark（仓库内 `img/brand/`，F1 为 Simple Icons CC0 版 2018 现行标、MotoGP 为官方 Dorna 2025 字标），压品牌底色合成方图（`img/badge/f1.jpg`、`img/badge/moto.jpg`）。官方没有发布每站 GP 专属字标，故按系列计 |
| F1 赛事图 | 各分站页 JSON-LD 里的官方主视觉（`image.url`） |
| MotoGP 赛事图 | 官方赛事 API 的 TOP 资产，无则用 BACKGROUND 官方图 |

- 所有事件以 **UTC** 写入（`DTSTART;...Z`），日历 App 会按设备时区自动换算
- 事件描述里同时给出**赛道当地时间**和**北京时间**
- 标题前带**该站国旗 emoji**（如 `🇦🇺 F1 澳大利亚站 · 练习赛 1`），标题里同时带 `F1` / `MotoGP` 系列文字标
- 每个事件通过 `ATTACH;VALUE=URI` 挂上**赛事 logo 徽标**（系列官方 wordmark 方图 320×320 / 5–6KB），再挂**官方主视觉图**（640px / 单张 10–80KB），均托管在本仓库 `img/`
- **图片显示位置**：iOS / macOS「日历」App 的事件标题是纯文本，**标题旁不会渲染图片**；`ATTACH` 图片出现在**点开事件后的详情页**顶部。想要标题旁就有 logo 缩略图，用 Fantastical 或 Google Calendar App 订阅同一份 `.ics`
- 场次时间变化、临时调整会在每周一自动重新抓取更新

## 本地重新生成

```bash
python generate_ics.py              # 只用 Python 标准库，生成 .ics
pip install pillow && python fetch_images.py   # 刷新官方赛事图（需 Pillow）
pip install pillow && python fetch_logos.py    # 刷新赛事 logo 徽标（需 Pillow）
```

输出 `f1.ics` / `motogp.ics` / `racing.ics` 三个文件。
`cache/` 目录为本地缓存，仅用于调试，CI 中不使用。

## 说明

- 事件 UID 固定，重复导入/刷新为「更新」而非「重复添加」
- MotoGP 只收录 MotoGP 组别（Moto2 / Moto3 组别赛事与赛前发布会未包含）
- F1 2026 冲刺赛周末为：中国、迈阿密、加拿大、英国、荷兰、新加坡（共 6 站）
- MotoGP 2026 每站均有周六冲刺赛
