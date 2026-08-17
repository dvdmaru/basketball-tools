#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-basketball-data-hub.py — 數據總覽 hub 頁（public-basketball/data/）。

nav「數據」的落地頁：把 NBA 戰績（/standings/）、台灣職籃（/tw/）、HBL（/hbl/）
三個數據頁集中分流（drill-down tiles），並說明各聯盟的數據範圍。server-rendered，
沿用 build-articles 共用外殼 + basketball（ember／籃球數據誌）站身分，active nav = "data"。

⚠️ 跑序：build-articles.py 會整個覆寫 sitemap → 必須先 build-articles，再跑本腳本（re-merge /data/）。

用法：python3 scripts/gen-basketball-data-hub.py
"""
import html as html_lib
import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ba = _load("build_articles", "build-articles.py")
SITE = ba.SITES.get("basketball")
BASE = SITE["base"]

# 數據頁清單：(href, icon, 標題, 說明)
# ⚠️ NBA 卡片的賽季／狀態定語由快照衍生（season 欄＋final 旗標），不寫死賽季字面值，
#    否則開季後 /data/ 會繼續宣稱「休賽季顯示 20XX-XX 終局數據」。
def dests():
    nba = ba._dash_latest("nba-standings-*.json")
    st = ba.bb_season_state(nba)
    if st["offseason"]:
        nba_state = f"休賽季顯示 {st['season_seg']}終局數據。"
    else:
        nba_state = f"{st['season_seg']}進行中，每日自動更新。"
    return [
        ("/standings/", "🏆", "NBA 戰績與東西區排名",
         "美國職籃 30 隊完整排名（勝負・勝率・勝差・種子序）與總冠軍結果。"
         f"整理自 ESPN 公開資料；{nba_state}"),
        ("/tw/", "🇹🇼", "台灣職籃：TPBL × P. LEAGUE+",
         "台灣兩個職業籃球聯盟同頁對照：TPBL 7 隊與 PLG 4 隊的例行賽戰績與總冠軍。整理自兩聯盟官網公開資料。"),
        ("/hbl/", "🏀", "HBL 高中籃球甲級",
         "HBL 男子甲級、女子甲級總決賽四強最終名次與冠軍戰結果，附歷屆冠軍榜（可回溯至 106 學年度）。整理自 hbl.com.tw 公開賽果。"),
    ]


def _shell(title, desc, canonical, jsonld, body):
    return f"""<!DOCTYPE html>
<html lang="zh-Hant" data-theme="{SITE['default_theme']}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_lib.escape(title)} | {SITE['title_suffix']}</title>
<meta name="description" content="{html_lib.escape(desc)}">
<meta property="og:title" content="{html_lib.escape(title)}">
<meta property="og:description" content="{html_lib.escape(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{SITE['org_name']}">
<meta property="og:locale" content="zh_TW">
<link rel="canonical" href="{canonical}">
{jsonld}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Archivo:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap" rel="stylesheet">
{ba.ga_snippet(SITE)}
<style>
{ba.SHARED_TOKENS_CSS}{ba.extra_theme_css(SITE)}
{ba.SITE_HEADER_CSS}
{ba.BB_LANDING_CSS}
{ba.BB_DASH_CSS}
.hub-grid{{display:grid;gap:14px;margin-top:6px}}
.hub-card{{display:flex;align-items:flex-start;gap:16px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius-sm);padding:20px 22px;text-decoration:none;color:var(--fg);transition:border-color .15s,transform .15s}}
.hub-card:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.hub-card .ic{{font-size:30px;line-height:1}}
.hub-card .tt{{display:block;font-size:19px;font-weight:800;color:var(--fg)}}
.hub-card .dd{{display:block;font-size:14px;color:var(--fg-soft);line-height:1.65;margin-top:6px}}
.hub-card .go{{margin-left:auto;color:var(--accent);font-weight:800;align-self:center;font-size:15px}}
</style>
</head>
<body>
{ba.site_header_html('data', SITE)}
<div class="bb-shell">
<main>
{body}
</main>
</div>
{ba._bb_footer(SITE)}
<script>{ba.theme_switch_js(SITE)}</script>
</body>
</html>
"""


def build_page():
    cards = ""
    for href, ic, tt, dd in dests():
        cards += (f'<a class="hub-card" href="{href}"><span class="ic">{ic}</span>'
                  f'<span><span class="tt">{html_lib.escape(tt)}</span>'
                  f'<span class="dd">{html_lib.escape(dd)}</span></span>'
                  f'<span class="go">→</span></a>')
    body = f"""<section class="bb-hero" style="padding-bottom:6px">
    <h1>數據總覽</h1>
    <p>NBA 與台灣籃球數據的入口。概覽看<a href="/" style="color:var(--accent)">首頁儀表板</a>；要完整排名、兩聯盟對照與 HBL 名次，從下方進入。</p>
  </section>
  <div class="bb-sec"><h2>數據頁</h2><span class="ln"></span></div>
  <div class="hub-grid">{cards}</div>"""
    canonical = f"{BASE}/data/"
    coll = {"@type": "CollectionPage", "@id": canonical, "url": canonical,
            "name": "數據總覽", "inLanguage": "zh-Hant",
            "isPartOf": {"@id": f"{BASE}/#website"}}
    jsonld = ba.graph_ld([ba.org_node(SITE), ba.website_node(SITE), coll,
                          ba.breadcrumb_node([("首頁", f"{BASE}/"), ("數據", canonical)])])
    desc = ("籃球數據誌數據總覽：NBA 東西區完整排名、台灣職籃 TPBL × PLG 戰績對照、"
            "HBL 高中籃球四強與歷屆冠軍。概覽見首頁儀表板。")
    return _shell("數據總覽", desc, canonical, jsonld, body)


def main():
    out_dir = ROOT / "public-basketball" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(build_page(), encoding="utf-8")
    print("✅ public-basketball/data/index.html")

    sm = ROOT / "public-basketball" / "sitemap.xml"
    keep = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm.read_text(encoding="utf-8"))
            if "/data/" not in u] if sm.exists() else [f"{BASE}/"]
    urls = list(dict.fromkeys(keep + [f"{BASE}/data/"]))
    body = "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
    sm.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                  f"{body}</urlset>\n", encoding="utf-8")
    print(f"🗺️  sitemap.xml → {len(urls)} URLs (+/data/)")


if __name__ == "__main__":
    main()
