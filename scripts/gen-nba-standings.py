#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-nba-standings.py — NBA 戰績頁（public-basketball/standings/）。

東／西區完整排名（server-rendered，CSS-only tabs，無 JS data fetch → crawler 看得到全表）。
吃 leagues/nba-standings-<season>.json（fetch-nba.py 產物，主源 ESPN 公開資料）。
休賽季顯示終局數據 + 冠軍註記，as-of 誠實標示。

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

PAGE_CSS = """
.st-h1 { font-family: var(--font-display); font-size: clamp(30px,5vw,46px); line-height:1.1; margin: 4px 0 6px; }
.st-sub { color: var(--fg-soft); font-size: 15px; margin: 10px 0 22px; }
.st-sub b { color: var(--accent); }
.champ-band { display:flex; align-items:center; gap:14px; border:1px solid var(--accent-line);
  background:var(--accent-soft); border-radius:12px; padding:14px 18px; margin: 0 0 22px; }
.champ-band .ic { font-size: 26px; }
.champ-band .t { font-weight:900; font-size:17px; color:var(--fg); }
.champ-band .d { color:var(--dim); font-size:13px; margin-top:2px; }
.tabs > input[name="cftab"] { position:absolute; opacity:0; width:0; height:0; }
.tablabels { display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 22px; border-bottom:1px solid var(--line); }
.tablabels label { cursor:pointer; padding:9px 16px; font-size:14.5px; font-weight:700; color:var(--dim);
  border-bottom:2px solid transparent; margin-bottom:-1px; transition:color .15s, border-color .15s; }
.tablabels label:hover { color: var(--fg); }
.panel { display:none; }
#cftab-e:checked ~ .tablabels label[for="cftab-e"],
#cftab-w:checked ~ .tablabels label[for="cftab-w"] { color: var(--accent); border-bottom-color: var(--accent); }
#cftab-e:checked ~ .panel-e, #cftab-w:checked ~ .panel-w { display:block; }
.std-table { width:100%; border-collapse:collapse; margin: 8px 0 14px; font-size: 14px; }
.std-table th, .std-table td { padding: 8px 6px; text-align:center; border-bottom:1px solid var(--line); white-space:nowrap; }
.std-table th { color: var(--dim); font-weight:600; font-size:12px; }
.std-table td.l, .std-table th.l { text-align:left; white-space:normal; }
.std-table td.rk { color:var(--dim); font-family:var(--font-mono); font-size:12.5px; }
.std-table tr.lead td.tm { font-weight:800; }
.std-table td.ab { color:var(--faint); font-family:var(--font-mono); font-size:12px; }
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
{ba.theme_switch_html(SITE)}
<div class="container">{ba.site_header_html('data', SITE)}
{body}
{ba.site_footer_html(SITE)}
</div>
<script>{ba.theme_switch_js(SITE)}</script>
</body>
</html>
"""


def conf_table(rows):
    trs = ""
    for r in sorted(rows, key=lambda x: int(x["rank"])):
        lead = ' class="lead"' if str(r["rank"]) == "1" else ""
        pct = str(r.get("pct", "")).lstrip("0") or "0"
        trs += (f'<tr{lead}><td class="rk">{r["rank"]}</td>'
                f'<td class="l tm">{html_lib.escape(r.get("name_zh") or r.get("name", ""))}</td>'
                f'<td class="ab">{html_lib.escape(r.get("abbr", ""))}</td>'
                f'<td class="std-pts">{r["wins"]}</td><td>{r["losses"]}</td>'
                f'<td>{pct}</td><td>{html_lib.escape(str(r.get("games_back", "—")))}</td></tr>')
    return ('<table class="std-table"><thead><tr><th class="rk">#</th><th class="l">球隊</th>'
            '<th>縮寫</th><th>勝</th><th>敗</th><th>勝率</th><th>勝差</th></tr></thead>'
            f'<tbody>{trs}</tbody></table>')


def _page_faq(season, asof, final):
    upd = ("目前為休賽季：本頁顯示該季例行賽終局排名，數字不再變動；新賽季開打後改為每日自動更新。"
           if final else "賽季進行中，本頁每日自動更新一次。")
    return [
        (f"NBA {season} 賽季的排名是最終結果嗎？",
         f"{'是。' if final else '不是，賽季仍在進行。'}本頁排名截至 {asof}，"
         f"為 {season} 例行賽{'終局' if final else '目前'}戰績；排序採各區種子序（playoff seed）。{upd}"),
        ("排名的「勝差」怎麼算？",
         "勝差（GB）＝（區龍頭勝場 − 該隊勝場 ＋ 該隊敗場 − 區龍頭敗場）÷ 2，是追上該區第一名所需的場次差；「—」表示該隊即為區龍頭。"),
        ("這個頁面的資料來源是什麼？",
         "整理自 ESPN 公開之 NBA 數據（site.api.espn.com），非 NBA 官方發布管道；本站與 NBA 及各球團無任何官方關聯，引用請以 NBA 官方公告為準。"),
        ("為什麼不是即時比分？",
         "本站定位是數據內容站而非即時比分服務：頁面為預先產生的靜態內容，標註資料截至日期，適合查排名結構與長期脈絡；即時比分請至官方或即時比分平台。"),
    ]


def _faq_html(pairs):
    qa = "".join(
        f'<div class="qa"><h3>{html_lib.escape(q)}</h3><p>{html_lib.escape(a)}</p></div>'
        for q, a in pairs)
    return f'<h2 class="st-faq-sec">常見問題</h2><section class="st-faq">{qa}</section>'


def build_page(snap):
    season = snap.get("season", "")
    asof = snap.get("asof", "")
    final = bool(snap.get("final"))
    canonical = f"{BASE}/standings/"
    east = [r for r in snap["standings"] if r["conference"] == "Eastern"]
    west = [r for r in snap["standings"] if r["conference"] == "Western"]

    champ_band = ""
    if snap.get("champion_zh"):
        champ_band = (f'<div class="champ-band"><span class="ic">🏆</span><span>'
                      f'<div class="t">{season} 總冠軍：{html_lib.escape(snap["champion_zh"])}'
                      f'（{html_lib.escape(snap.get("champion_en", ""))}）</div>'
                      f'<div class="d">{html_lib.escape(snap.get("finals_note", ""))}</div>'
                      '</span></div>')

    tabs = (
        '<div class="tabs">'
        '<input type="radio" name="cftab" id="cftab-e" checked>'
        '<input type="radio" name="cftab" id="cftab-w">'
        '<div class="tablabels"><label for="cftab-e">東區</label><label for="cftab-w">西區</label></div>'
        f'<div class="panel panel-e">{conf_table(east)}</div>'
        f'<div class="panel panel-w">{conf_table(west)}</div>'
        '</div>'
    )
    status_txt = "例行賽終局" if final else "例行賽進行中"
    asof_note = (
        f'<p class="st-asof">資料整理自 ESPN 公開之 NBA 數據（site.api.espn.com），截至 {asof}；'
        f'{season} 賽季{status_txt}。排序採各區種子序。'
        '本站為非官方資料整理站，與 NBA 及各球團無任何關聯或授權；'
        '球隊名稱與相關權利屬 NBA 及各權利人所有，引用請以官方公告為準。</p>'
    )
    faq = _page_faq(season, asof, final)
    body = (f'<h1 class="st-h1">NBA 戰績 — 東西區排名</h1>'
            f'<div class="st-sub">NBA {season} 賽季 30 隊完整排名（截至 {asof}）。</div>'
            f'{champ_band}{tabs}{_faq_html(faq)}{asof_note}')
    coll = {"@type": "CollectionPage", "@id": canonical, "url": canonical,
            "name": f"NBA 戰績與東西區排名（{season}）", "inLanguage": "zh-Hant",
            "isPartOf": {"@id": f"{BASE}/#website"}}
    jsonld = ba.graph_ld([ba.org_node(SITE), ba.website_node(SITE), coll,
                          ba.breadcrumb_node([("首頁", f"{BASE}/"), ("NBA 戰績", canonical)]),
                          ba.faq_node(faq, canonical)])
    desc = (f"NBA {season} 賽季東西區完整排名（截至 {asof}）：30 隊勝敗、勝率、勝差"
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
