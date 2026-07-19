#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-nba-standings.py — NBA 戰績頁（public-basketball/standings/）v2。

Claude Design standings.html mock 落地：page-hero＋champ-band＋東/西區 CSS-only tabs
（v2 .std 表：斑馬紋＋1-6/7-10 分帶＋seed 晶片＋縮寫欄＋手機釘欄橫捲）＋details FAQ。
口徑沿用查核桌修正版：**例行賽名次**（非附加賽後種子；mock 文案的「排序採種子序」為
查核前舊口徑，不移植）。吃 leagues/nba-standings-<season>.json（fetch-nba.py）。

用法：python3 scripts/gen-nba-standings.py
⚠️ 跑序：build-articles.py 會整個覆寫 sitemap → 必須先 build-articles，再跑本腳本（re-merge 自己的 path）。
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
/* 東西區雙 tab（本頁專屬 id 對映） */
#t-e:checked~.tablist label[for=t-e],
#t-w:checked~.tablist label[for=t-w]{{color:var(--fg);border-bottom-color:var(--accent)}}
#t-e:checked~#p-e,#t-w:checked~#p-w{{display:block}}
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


def _page_faq(season, asof, final):
    upd = ("目前為休賽季：本頁顯示該季例行賽終局排名，數字不再變動；新賽季開打後改為每日自動更新。"
           if final else "賽季進行中，本頁每日自動更新一次。")
    return [
        (f"NBA {season} 賽季的排名是最終結果嗎？",
         f"{'是。' if final else '不是，賽季仍在進行。'}本頁排名截至 {asof}，"
         f"為 {season} 例行賽{'終局' if final else '目前'}名次（同勝率球隊之先後依聯盟正式比序）；"
         f"附加賽結果可能使季後賽種子與例行賽名次不同，本頁呈現的是例行賽名次。{upd}"),
        ("季後賽與附加賽的分帶怎麼看？",
         "每區例行賽第 1–6 名直接晉級季後賽（本頁以橘色帶標示）；第 7–10 名進入附加賽"
         "（play-in，金色帶）爭奪最後兩張季後賽門票；第 11–15 名該季止步例行賽。"
         "分帶僅為閱讀輔助，實際晉級與種子以官方賽制為準。"),
        ("排名的「勝差」怎麼算？",
         "勝差（GB）＝（區龍頭勝場 − 該隊勝場 ＋ 該隊敗場 − 區龍頭敗場）÷ 2，是追上該區第一名所需的場次差；「—」表示該隊即為區龍頭。"),
        ("這個頁面的資料來源是什麼？",
         "整理自 ESPN 公開之 NBA 數據（site.api.espn.com），非 NBA 官方發布管道；本站與 NBA 及各球團無任何官方關聯，引用請以 NBA 官方公告為準。"),
        ("為什麼不是即時比分？",
         "本站定位是數據內容站而非即時比分服務：頁面為預先產生的靜態內容，標註資料截至日期，適合查排名結構與長期脈絡；即時比分請至官方或即時比分平台。"),
    ]


def build_page(snap):
    season = snap.get("season", "")
    asof = snap.get("asof", "")
    final = bool(snap.get("final"))
    canonical = f"{BASE}/standings/"
    km = ("rank", "name_zh", "wins", "losses", "pct", "games_back")
    east = sorted([r for r in snap["standings"] if r["conference"] == "Eastern"], key=lambda r: r["rank"])
    west = sorted([r for r in snap["standings"] if r["conference"] == "Western"], key=lambda r: r["rank"])

    champ_band = ""
    if snap.get("champion_zh"):
        champ_band = (
            '<div class="champ-band"><div class="bseal">冠</div><div class="bt">'
            f'<div class="lbl">{season} 總冠軍</div>'
            f'<div class="nm">{html_lib.escape(snap["champion_zh"])} {html_lib.escape(snap.get("champion_en", ""))}</div>'
            f'<div class="sr">{html_lib.escape(snap.get("finals_note", ""))}</div>'
            '</div></div>')

    legend = ('<div class="legend"><span><i class="po"></i>直接晉級季後賽（第 1–6 名）</span>'
              '<span><i class="pi"></i>附加賽區（第 7–10 名）</span></div>')
    hint = '<div class="scroll-hint">← 左右滑動看完整欄位 →</div>'
    tabs = (
        '<div class="tabwrap tabs">'
        '<input type="radio" name="conf" id="t-e" checked>'
        '<input type="radio" name="conf" id="t-w">'
        '<div class="tablist"><label for="t-e">東區 Eastern</label><label for="t-w">西區 Western</label></div>'
        f'<div class="panel" id="p-e">{hint}{ba._std_table_v2(east, km, po_max=6, pi_max=10, abbr_key="abbr")}{legend}</div>'
        f'<div class="panel" id="p-w">{hint}{ba._std_table_v2(west, km, po_max=6, pi_max=10, abbr_key="abbr")}{legend}</div>'
        '</div>')
    status_txt = "例行賽終局" if final else "例行賽進行中"
    cap = (f'<div class="tbl-cap">{season} {status_txt}名次 · 截至 {asof} · '
           '排序為例行賽名次（同勝率之先後依聯盟正式比序）；附加賽後的季後賽種子可能與例行賽名次不同。'
           '整理自 ESPN 公開資料（site.api.espn.com），非官方發布管道。</div>')

    faq = _page_faq(season, asof, final)
    body = (
        '<section class="page-hero">'
        '<h1><span class="en">NBA</span> 戰績 — 東西區排名</h1>'
        f'<p class="sub">NBA {season} 賽季 30 隊完整例行賽名次（截至 {asof}），'
        '標示季後賽（1–6 名）與附加賽（7–10 名）分帶。</p>'
        '</section>'
        + champ_band + tabs + cap + ba.bb_faq_details_html(faq))
    coll = {"@type": "CollectionPage", "@id": canonical, "url": canonical,
            "name": f"NBA 戰績與東西區排名（{season}）", "inLanguage": "zh-Hant",
            "isPartOf": {"@id": f"{BASE}/#website"}}
    jsonld = ba.graph_ld([ba.org_node(SITE), ba.website_node(SITE), coll,
                          ba.breadcrumb_node([("首頁", f"{BASE}/"), ("NBA 戰績", canonical)]),
                          ba.faq_node(faq, canonical)])
    desc = (f"NBA {season} 賽季東西區完整例行賽名次（截至 {asof}）：30 隊勝敗、勝率、勝差與季後賽/附加賽分帶"
            + (f"；總冠軍 {snap.get('champion_zh')}（{snap.get('finals_note', '')}）" if snap.get("champion_zh") else "")
            + "。整理自 ESPN 公開資料的非官方數據頁。")
    return _shell(f"NBA 戰績與東西區排名（{season}）", desc, canonical, jsonld, body)


def main():
    cands = sorted(glob.glob(str(ROOT / "leagues" / "nba-standings-*.json")))
    if not cands:
        raise SystemExit("❌ leagues/ 下沒有 nba-standings-*.json；先跑 fetch-nba.py。")
    snap = json.loads(pathlib.Path(cands[-1]).read_text(encoding="utf-8"))
    out_dir = ROOT / "public-basketball" / "standings"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(build_page(snap), encoding="utf-8")
    print("✅ public-basketball/standings/index.html")

    sm = ROOT / "public-basketball" / "sitemap.xml"
    keep = ([u for u in re.findall(r"<loc>([^<]+)</loc>", sm.read_text(encoding="utf-8"))
             if "/standings/" not in u] if sm.exists() else [f"{BASE}/"])
    urls = list(dict.fromkeys(keep + [f"{BASE}/standings/"]))
    body = "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
    sm.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                  f"{body}</urlset>\n", encoding="utf-8")
    print(f"🗺️  sitemap.xml → {len(urls)} URLs (+/standings/)")


if __name__ == "__main__":
    main()
