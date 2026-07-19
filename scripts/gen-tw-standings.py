#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-tw-standings.py — 台灣職籃戰績頁（public-basketball/tw/）v2。

Claude Design 元件落地：page-hero＋TPBL/PLG CSS-only tabs（v2 .std 表：斑馬紋＋
seed 晶片＋手機釘欄；晉級門檻未經查核，不畫分帶）＋每聯盟 champ-band＋details FAQ。
吃 leagues/tw-hoops-<date>.json（fetch-tw-hoops.py 產物）。

用法：python3 scripts/gen-tw-standings.py
⚠️ 跑序：build-articles.py 之後跑（sitemap re-merge 自己的 path）。
"""
import glob
import html as html_lib
import importlib.util
import json
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
{ba.BB_HOME_CSS}
{ba.BB_PAGE_EXTRA_CSS}
#t-tpbl:checked~.tablist label[for=t-tpbl],
#t-plg:checked~.tablist label[for=t-plg]{{color:var(--fg);border-bottom-color:var(--accent)}}
#t-tpbl:checked~#p-tpbl,#t-plg:checked~#p-plg{{display:block}}
</style>
</head>
<body>
{ba.site_header_html('data', SITE)}
<main class="wrap">
{body}
</main>
{ba.site_footer_html(SITE)}
<script>{ba.theme_switch_js(SITE)}</script>
</body>
</html>
"""


def _page_faq(season, asof):
    return [
        ("台灣現在有幾個職業籃球聯盟？",
         "兩個：TPBL（台灣職業籃球大聯盟，7 隊）與 P. LEAGUE+（4 隊）。2025 年 7 月兩聯盟的合作與合併討論破局後，"
         "各自營運、各辦選秀；本頁把兩個聯盟的戰績放在同一頁對照。"),
        (f"{season} 賽季兩聯盟的冠軍是誰？",
         "TPBL 總冠軍為福爾摩沙夢想家（總冠軍賽 4:3 勝新北國王，隊史首冠）；"
         "P. LEAGUE+ 總冠軍為桃園璞園領航猿（總冠軍賽 4:3 勝臺北富邦勇士，達成二連霸）。"),
        ("這個頁面的資料來源是什麼？多久更新？",
         f"TPBL 整理自其官網公開賽果資料、PLG 整理自其官網戰績頁，快照日期 {asof}；"
         "目前為休賽季、數字為該季終局。新賽季（依往例約 10 月開打，以官方公告為準）開始後改為每週更新。"),
        ("球隊名稱為什麼跟我印象中的不一樣？",
         "台灣職籃球隊名稱常含冠名贊助（例如台啤永豐、御嵿），冠名可能逐季變動；"
         "本頁採官方目前使用的隊名。查歷史資料時建議以「城市＋隊名」為骨幹對照。"),
        ("這個網站和 TPBL 或 P. LEAGUE+ 官方有關係嗎？",
         "沒有。本站為非官方資料整理站，無任何官方授權；球隊名稱與相關權利屬各聯盟及球團所有，引用請以官方公告為準。"),
    ]


def league_panel(lg, season, asof, source_note):
    band = ""
    if lg.get("champion_zh"):
        band = ('<div class="champ-band"><div class="bseal">冠</div><div class="bt">'
                f'<div class="lbl">{season} 總冠軍</div>'
                f'<div class="nm">{html_lib.escape(lg["champion_zh"])}</div>'
                f'<div class="sr">{html_lib.escape(lg.get("finals_note", ""))}</div>'
                '</div></div>')
    km = ("rank", "team_name", "win", "lose", "pct", "games_behind")
    hint = '<div class="scroll-hint">← 左右滑動看完整欄位 →</div>'
    cap = f'<div class="tbl-cap">{season} 例行賽終局 · 快照 {asof} · {html_lib.escape(source_note)}</div>'
    return band + hint + ba._std_table_v2(lg.get("standings", []), km) + cap


def build_page(snap):
    season = snap.get("season", "")
    asof = snap.get("asof_taipei_date", "")
    canonical = f"{BASE}/tw/"
    tpbl = snap["leagues"]["tpbl"]
    plg = snap["leagues"]["plg"]
    tabs = (
        '<div class="tabwrap tabs">'
        '<input type="radio" name="lg" id="t-tpbl" checked>'
        '<input type="radio" name="lg" id="t-plg">'
        '<div class="tablist"><label for="t-tpbl">TPBL（7 隊）</label><label for="t-plg">P. LEAGUE+（4 隊）</label></div>'
        f'<div class="panel" id="p-tpbl">{league_panel(tpbl, season, asof, "整理自 TPBL 官網公開資料（非官方文件化介面）")}</div>'
        f'<div class="panel" id="p-plg">{league_panel(plg, season, asof, "整理自 PLG 官網戰績頁")}</div>'
        '</div>')
    note = ('<div class="tbl-cap">兩聯盟均未提供官方文件化 API，資料屬非官方整理；'
            '本站與 TPBL、P. LEAGUE+ 及各球團無任何關聯或授權，引用請以官方公告為準。</div>')
    faq = _page_faq(season, asof)
    body = (
        '<section class="page-hero">'
        '<h1>台灣職籃戰績 — <span class="en">TPBL</span> × <span class="en">PLG</span></h1>'
        f'<p class="sub">台灣兩個職業籃球聯盟的 {season} 賽季戰績與總冠軍，同頁對照（截至 {asof}）。'
        '兩聯盟自 2025 年 7 月合併談判破局後並立營運。</p>'
        '</section>'
        + tabs + note + ba.bb_faq_details_html(faq))
    coll = {"@type": "CollectionPage", "@id": canonical, "url": canonical,
            "name": f"台灣職籃戰績：TPBL × P. LEAGUE+（{season}）", "inLanguage": "zh-Hant",
            "isPartOf": {"@id": f"{BASE}/#website"}}
    jsonld = ba.graph_ld([ba.org_node(SITE), ba.website_node(SITE), coll,
                          ba.breadcrumb_node([("首頁", f"{BASE}/"), ("台灣職籃", canonical)]),
                          ba.faq_node(faq, canonical)])
    desc = (f"台灣職籃 {season} 賽季戰績（截至 {asof}）：TPBL 7 隊與 P. LEAGUE+ 4 隊例行賽排名、"
            f"總冠軍（TPBL 福爾摩沙夢想家、PLG 桃園璞園領航猿）。兩聯盟並立現況的非官方數據頁。")
    return _shell(f"台灣職籃戰績：TPBL × P. LEAGUE+（{season}）", desc, canonical, jsonld, body)


def main():
    cands = sorted(glob.glob(str(ROOT / "leagues" / "tw-hoops-*.json")))
    if not cands:
        raise SystemExit("❌ leagues/ 下沒有 tw-hoops-*.json；先跑 fetch-tw-hoops.py。")
    snap = json.loads(pathlib.Path(cands[-1]).read_text(encoding="utf-8"))
    out_dir = ROOT / "public-basketball" / "tw"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(build_page(snap), encoding="utf-8")
    print("✅ public-basketball/tw/index.html")

    sm = ROOT / "public-basketball" / "sitemap.xml"
    keep = ([u for u in re.findall(r"<loc>([^<]+)</loc>", sm.read_text(encoding="utf-8"))
             if "/tw/" not in u] if sm.exists() else [f"{BASE}/"])
    urls = list(dict.fromkeys(keep + [f"{BASE}/tw/"]))
    body = "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
    sm.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                  f"{body}</urlset>\n", encoding="utf-8")
    print(f"🗺️  sitemap.xml → {len(urls)} URLs (+/tw/)")


if __name__ == "__main__":
    main()
