#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen-basketball-cover.py — 籃球數據誌 特刊封面生成器（basketball.twtools.cc）
HTML template → Chrome headless → 2400×1260 PNG（純文字、IP 安全：無 logo/球員照/隊徽/聯盟標誌）。
品牌：炭黑 #14100e + 暖白 #f3ece4 + 籃球橘 #ef7d3a + 木地板金 #d9a04c（裝飾條/dot）。
與 baseball（navy/金）、foootball（森林綠）區隔。封面寫進 articles/<slug>/cover.png。

用法：python3 gen-basketball-cover.py            # 生成 COVERS 內全部
      python3 gen-basketball-cover.py <slug>...  # 只生成指定 slug（避免重生成全部造成無關 diff）
"""
import os, subprocess, sys, tempfile

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    raise SystemExit("Chrome not found")


# (article_slug, kicker, title_html, subtitle) — 新文章加封面：在這裡加一列再跑本腳本
COVERS = [
    ("nba-league-guide", "NBA · 完全指南",
     "美國職籃<br>完全指南",
     "30 隊 · 東西區　·　附加賽到總冠軍賽一次看懂"),
    ("taiwan-hoops-two-leagues", "台灣職籃 · 並立格局",
     "為什麼有<br>兩個聯盟",
     "TPBL 7 隊 × PLG 4 隊　·　合併破局始末"),
    ("hbl-league-guide", "HBL · 完全指南",
     "高中籃球<br>完全指南",
     "男子組 37 隊 · 女子組 16 隊　·　小巨蛋的 3 月"),
    ("nba-2025-26-season-review", "2025-26 · 賽季回顧",
     "尼克<br>53 年再奪冠",
     "總冠軍賽 4:1 勝馬刺　·　東西區終局全紀錄"),
    ("nba-2026-offseason-moves", "2026 · 休賽季異動",
     "字母哥<br>轉戰熱火",
     "頭條交易 4 筆 · 待確認 1 筆　·　休賽季異動總表"),
    ("lebron-james-76ers-24th-season", "2026 · 生涯數據總表",
     "詹姆斯<br>加盟 76 人",
     "第 24 個賽季 · 第 4 支球隊　·　23 季官方數據拆解"),
    ("taiwan-asian-games-2026-basketball", "名古屋亞運 · 台灣男籃",
     "比開幕式<br>早 9 天開打",
     "B 組對約旦 · 伊朗 · 卡達　·　12 人名單 · 連兩屆第 4"),
    ("tpbl-plg-rules-compared", "台灣職籃 · 規則逐條對照",
     "身分分 2 種<br>還是 4 種",
     "TPBL 對 PLG　·　註冊 · 上場 · 薪資 · 選秀 · 交易"),
    ("nba-2026-draft-results", "2026 · 選秀完整名單",
     "60 個順位<br>27 個換了隊",
     "兩輪逐一列出　·　上台選人的隊 · 選後去向"),
    ("taiwan-hoops-2026-offseason-moves", "台灣職籃 · 2026 休賽季",
     "衛冕軍首輪籤<br>選到了空氣",
     "跨聯盟轉隊 · 林庭謙返台　·　選秀 · 洋將 · 退役"),
    ("don-nelson-nellie-ball", "NBA · Nellie Ball",
     "名人堂說創新者<br>他說只是權宜",
     "例行賽 1,335 勝 · 史上第 2　·　小球 · point forward"),
    ("nba-2026-27-opening-night-christmas-schedule", "NBA · 開幕週與聖誕大戰",
     "詹姆斯開幕戰<br>作客尼克",
     "台北 10/21 早上 7 點　·　聖誕大戰 12/26 星期六"),
]

HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1200px;height:630px;overflow:hidden}}
body{{
  font-family:"PingFang TC","Heiti TC","Noto Sans CJK TC",sans-serif;
  background:
    radial-gradient(1100px 720px at 80% -12%, rgba(239,125,58,.20), transparent 60%),
    linear-gradient(135deg,#241d19 0%,#14100e 52%,#0a0807 100%);
  color:#f3ece4;position:relative;
}}
.frame{{position:absolute;inset:28px;border:1.5px solid rgba(239,125,58,.40);border-radius:10px}}
.seam{{position:absolute;width:1500px;height:1500px;border:3px solid rgba(239,125,58,.18);
  border-radius:50%;right:-820px;top:-340px}}
.seam2{{position:absolute;width:1500px;height:1500px;border:3px solid rgba(239,125,58,.10);
  border-radius:50%;right:-760px;top:-280px}}
.pad{{position:absolute;inset:0;padding:74px 78px 128px;display:flex;flex-direction:column;height:100%}}
.top{{display:flex;align-items:center;gap:18px}}
.mark{{font-family:"Arial Black","PingFang TC",sans-serif;font-weight:900;letter-spacing:1px;
  font-size:30px;color:#ef7d3a}}
.dot{{width:7px;height:7px;border-radius:50%;background:#d9a04c;opacity:.9}}
.mk-tag{{font-size:18px;color:rgba(243,236,228,.62);letter-spacing:2px;font-weight:600}}
.kicker{{margin-top:auto;display:inline-block;align-self:flex-start;
  background:rgba(239,125,58,.16);border:1px solid rgba(239,125,58,.52);
  color:#ef7d3a;font-size:24px;font-weight:700;letter-spacing:3px;
  padding:9px 22px;border-radius:999px}}
h1{{font-size:104px;line-height:1.08;font-weight:900;margin:26px 0 0;
  letter-spacing:1px;color:#fff;text-shadow:0 2px 30px rgba(0,0,0,.40)}}
.bar{{width:96px;height:5px;background:linear-gradient(90deg,#ef7d3a,#d9a04c);
  border-radius:4px;margin:30px 0 22px}}
.sub{{font-size:32px;font-weight:600;color:rgba(243,236,228,.84);letter-spacing:1px}}
.foot{{position:absolute;left:78px;bottom:60px;font-size:21px;letter-spacing:2px;
  color:rgba(239,125,58,.74);font-weight:600}}
</style></head><body>
<div class="seam"></div><div class="seam2"></div>
<div class="frame"></div>
<div class="pad">
  <div class="top"><span class="mark">@BASKETBALL</span><span class="dot"></span>
    <span class="mk-tag">{mktag}</span></div>
  <div class="kicker">{kicker}</div>
  <h1>{title}</h1>
  <div class="bar"></div>
  <div class="sub">{sub}</div>
</div>
<div class="foot">basketball.twtools.cc</div>
</body></html>"""


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    league_tag = {"nba": "NBA", "tpbl": "TPBL", "plg": "PLG", "hbl": "HBL",
                  "taiwan": "台灣籃球"}
    only = set(sys.argv[1:])
    unknown = only - {slug for slug, *_ in COVERS}
    if unknown:
        raise SystemExit(f"未知 slug（不在 COVERS 內）：{', '.join(sorted(unknown))}")
    for slug, kicker, title, sub in COVERS:
        if only and slug not in only:
            continue
        lg = slug.split("-", 1)[0]
        mktag = f"{league_tag.get(lg, 'NBA')} 特刊 · 數據深度"
        html = HTML.format(kicker=kicker, title=title, sub=sub, mktag=mktag)
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html); tmp = f.name
        art_dir = os.path.join(root, "articles", slug)
        os.makedirs(art_dir, exist_ok=True)
        out = os.path.join(art_dir, "cover.png")
        subprocess.run(
            [chrome(), "--headless", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=2", "--window-size=1200,630",
             "--default-background-color=00000000",
             f"--screenshot={out}", f"file://{tmp}"],
            check=True, capture_output=True)
        os.unlink(tmp)
        print(f"✓ {out}")


if __name__ == "__main__":
    main()
