#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-tw-standings.py — 台灣職籃戰績頁（public-basketball/tw/）。

TPBL 與 P. LEAGUE+ 兩聯盟戰績（server-rendered，CSS-only tabs）。台灣職籃現況＝
兩聯盟並立（2025-07 合併談判破局），本頁把兩張戰績表放同一頁、tab 切換。
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

PAGE_CSS = """
.st-h1 { font-family: var(--font-display); font-size: clamp(30px,5vw,46px); line-height:1.1; margin: 4px 0 6px; }
.st-sub { color: var(--fg-soft); font-size: 15px; margin: 10px 0 22px; }
.champ-band { display:flex; align-items:center; gap:14px; border:1px solid var(--accent-line);
  background:var(--accent-soft); border-radius:12px; padding:14px 18px; margin: 0 0 18px; }
.champ-band .ic { font-size: 26px; }
.champ-band .t { font-weight:900; font-size:16px; color:var(--fg); }
.champ-band .d { color:var(--dim); font-size:13px; margin-top:2px; }
.tabs > input[name="twtab"] { position:absolute; opacity:0; width:0; height:0; }
.tablabels { display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 22px; border-bottom:1px solid var(--line); }
.tablabels label { cursor:pointer; padding:9px 16px; font-size:14.5px; font-weight:700; color:var(--dim);
  border-bottom:2px solid transparent; margin-bottom:-1px; transition:color .15s, border-color .15s; }
.tablabels label:hover { color: var(--fg); }
.panel { display:none; }
#twtab-t:checked ~ .tablabels label[for="twtab-t"],
#twtab-p:checked ~ .tablabels label[for="twtab-p"] { color: var(--accent); border-bottom-color: var(--accent); }
#twtab-t:checked ~ .panel-t, #twtab-p:checked ~ .panel-p { display:block; }
.std-table { width:100%; border-collapse:collapse; margin: 8px 0 14px; font-size: 14px; }
.std-table th, .std-table td { padding: 8px 6px; text-align:center; border-bottom:1px solid var(--line); white-space:nowrap; }
.std-table th { color: var(--dim); font-weight:600; font-size:12px; }
.std-table td.l, .std-table th.l { text-align:left; white-space:normal; }
.std-table td.rk { color:var(--dim); font-family:var(--font-mono); font-size:12.5px; }
.std-table tr.lead td.tm { font-weight:800; }
.std-pts { color: var(--accent); font-weight:800; }
.st-asof { color:var(--dim); font-size:12.5px; line-height:1.6; margin: 24px 0 8px; border-top:1px solid var(--line); padding-top:14px; }
.st-faq { margin-top: 20px; display: grid; gap: 10px; }
.st-faq .qa { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 14px 18px; }
.st-faq h3 { font-size: 15px; font-weight: 800; color: var(--fg); margin: 0 0 6px; line-height: 1.45; }
.st-faq p { font-size: 13.5px; color: var(--fg-soft); line-height: 1.7; margin: 0; }
.st-faq-sec { font-family: 'Anton', 'Noto Sans TC', sans-serif; font-size: 20px; letter-spacing: .5px; margin: 28px 0 4px; }
"""


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
{ba.THEME_SWITCH_CSS}
{ba.SITE_HEADER_CSS}
{PAGE_CSS}
</style>
</head>
<body>
{ba.site_header_html('data', SITE)}
<div class="container">
{body}
</div>
{ba.site_footer_html(SITE)}
<script>{ba.theme_switch_js(SITE)}</script>
</body>
</html>
"""


def league_panel(lg, season, asof):
    band = ""
    if lg.get("champion_zh"):
        band = (f'<div class="champ-band"><span class="ic">🏆</span><span>'
                f'<div class="t">{season} 總冠軍：{html_lib.escape(lg["champion_zh"])}</div>'
                f'<div class="d">{html_lib.escape(lg.get("finals_note", ""))}</div></span></div>')
    trs = ""
    for r in lg.get("standings", []):
        lead = ' class="lead"' if r.get("rank") == 1 else ""
        pct = str(r.get("pct", "")).lstrip("0") or "0"
        trs += (f'<tr{lead}><td class="rk">{r.get("rank")}</td>'
                f'<td class="l tm">{html_lib.escape(r.get("team_name", ""))}</td>'
                f'<td class="std-pts">{r.get("win")}</td><td>{r.get("lose")}</td>'
                f'<td>{pct}</td><td>{html_lib.escape(str(r.get("games_behind", "—")))}</td></tr>')
    table = ('<table class="std-table"><thead><tr><th class="rk">#</th><th class="l">球隊</th>'
             '<th>勝</th><th>敗</th><th>勝率</th><th>勝差</th></tr></thead>'
             f'<tbody>{trs}</tbody></table>')
    src = f'<div class="st-sub">例行賽戰績（截至 {asof}）· {html_lib.escape(lg.get("source", ""))}</div>'
    return band + table + src


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


def _faq_html(pairs):
    qa = "".join(
        f'<div class="qa"><h3>{html_lib.escape(q)}</h3><p>{html_lib.escape(a)}</p></div>'
        for q, a in pairs)
    return f'<h2 class="st-faq-sec">常見問題</h2><section class="st-faq">{qa}</section>'


def build_page(snap):
    season = snap.get("season", "")
    asof = snap.get("asof_taipei_date", "")
    canonical = f"{BASE}/tw/"
    tpbl = snap["leagues"]["tpbl"]
    plg = snap["leagues"]["plg"]
    tabs = (
        '<div class="tabs">'
        '<input type="radio" name="twtab" id="twtab-t" checked>'
        '<input type="radio" name="twtab" id="twtab-p">'
        '<div class="tablabels"><label for="twtab-t">TPBL（7 隊）</label>'
        '<label for="twtab-p">P. LEAGUE+（4 隊）</label></div>'
        f'<div class="panel panel-t">{league_panel(tpbl, season, asof)}</div>'
        f'<div class="panel panel-p">{league_panel(plg, season, asof)}</div>'
        '</div>'
    )
    asof_note = (
        f'<p class="st-asof">資料快照日期 {asof}；{season} 賽季已結束，表列為例行賽終局戰績與總冠軍結果。'
        'TPBL 整理自官網公開資料（api.tpbl.basketball，非官方文件化介面）、PLG 整理自官網戰績頁；'
        '兩聯盟均未提供官方文件化 API，資料屬非官方整理。'
        '本站與 TPBL、P. LEAGUE+ 及各球團無任何關聯或授權；引用請以官方公告為準。</p>'
    )
    faq = _page_faq(season, asof)
    body = (f'<h1 class="st-h1">台灣職籃戰績 — TPBL × P. LEAGUE+</h1>'
            f'<div class="st-sub">台灣兩個職業籃球聯盟的 {season} 賽季戰績與總冠軍，同頁對照（截至 {asof}）。</div>'
            f'{tabs}{_faq_html(faq)}{asof_note}')
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
