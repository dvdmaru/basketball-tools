#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-hbl-page.py — HBL 高中籃球頁（public-basketball/hbl/）。

男甲／女甲 四強最終名次 + 冠軍戰結果（server-rendered，CSS-only tabs），另附
歷屆冠軍榜（leagues/hbl-history.json，若存在；fetch-hbl.py --history 產生，
官網 API 僅回溯至 106 學年度）。

紅線：HBL 球員為未成年學生——本頁只呈現隊伍層賽果與名次，不列個別球員數據；
影音為 Hami Video 獨家授權，不嵌入、不連結串流。

用法：python3 scripts/gen-hbl-page.py
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
.tabs > input[name="hbtab"] { position:absolute; opacity:0; width:0; height:0; }
.tablabels { display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 22px; border-bottom:1px solid var(--line); }
.tablabels label { cursor:pointer; padding:9px 16px; font-size:14.5px; font-weight:700; color:var(--dim);
  border-bottom:2px solid transparent; margin-bottom:-1px; transition:color .15s, border-color .15s; }
.tablabels label:hover { color: var(--fg); }
.panel { display:none; }
#hbtab-b:checked ~ .tablabels label[for="hbtab-b"],
#hbtab-g:checked ~ .tablabels label[for="hbtab-g"] { color: var(--accent); border-bottom-color: var(--accent); }
#hbtab-b:checked ~ .panel-b, #hbtab-g:checked ~ .panel-g { display:block; }
.std-table { width:100%; border-collapse:collapse; margin: 8px 0 14px; font-size: 14px; }
.std-table th, .std-table td { padding: 8px 6px; text-align:center; border-bottom:1px solid var(--line); white-space:nowrap; }
.std-table th { color: var(--dim); font-weight:600; font-size:12px; }
.std-table td.l, .std-table th.l { text-align:left; white-space:normal; }
.std-table td.rk { color:var(--dim); font-family:var(--font-mono); font-size:12.5px; }
.std-table tr.lead td.tm { font-weight:800; }
.std-pts { color: var(--accent); font-weight:800; }
.hist-sec { font-family: 'Anton', 'Noto Sans TC', sans-serif; font-size: 20px; letter-spacing: .5px; margin: 30px 0 4px; }
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


def division_panel(div, season_label):
    band = (f'<div class="champ-band"><span class="ic">🏆</span><span>'
            f'<div class="t">{season_label}{html_lib.escape(div["label"])}冠軍：'
            f'{html_lib.escape(div["champion"])}</div>'
            f'<div class="d">{html_lib.escape(div.get("final_note", ""))}</div></span></div>')
    trs = ""
    rank_zh = {1: "冠軍", 2: "亞軍", 3: "季軍", 4: "殿軍"}
    for r in div.get("final_four", []):
        lead = ' class="lead"' if r.get("rank") == 1 else ""
        trs += (f'<tr{lead}><td class="rk">{rank_zh.get(r.get("rank"), r.get("rank"))}</td>'
                f'<td class="l tm">{html_lib.escape(r.get("school", ""))}</td>'
                f'<td class="l">{html_lib.escape(r.get("note", ""))}</td></tr>')
    table = ('<table class="std-table"><thead><tr><th class="rk">名次</th><th class="l">學校</th>'
             '<th class="l">附註</th></tr></thead>'
             f'<tbody>{trs}</tbody></table>')
    return band + table


def history_table(hist):
    rows = sorted(hist.get("seasons", []), key=lambda r: -int(r["season"]))
    trs = ""
    for r in rows:
        trs += (f'<tr><td class="rk">{r["season"]}學年度</td>'
                f'<td class="l">{html_lib.escape(r.get("boys_champion") or "—")}</td>'
                f'<td class="l">{html_lib.escape(r.get("girls_champion") or "—")}</td></tr>')
    return ('<h2 class="hist-sec">歷屆冠軍（106 學年度起）</h2>'
            '<div class="st-sub">官網公開賽果可回溯至 106 學年度（2017-18）；更早屆次不在此列。</div>'
            '<table class="std-table"><thead><tr><th class="rk">學年度</th>'
            '<th class="l">男子甲級冠軍</th><th class="l">女子甲級冠軍</th></tr></thead>'
            f'<tbody>{trs}</tbody></table>')


def _page_faq(season_label, divisions):
    b = divisions.get("boys", {})
    g = divisions.get("girls", {})
    return [
        ("HBL 是什麼？",
         "HBL（高級中等學校籃球聯賽）是由中華民國高級中等學校體育總會主辦的全國高中籃球賽事，"
         "本頁聚焦最高層級的甲級聯賽（男子組與女子組）。賽季約從 10 月打到隔年 3 月，"
         "四強決賽近年固定在臺北小巨蛋舉行。"),
        (f"{season_label} HBL 男甲、女甲冠軍是誰？",
         f"男子甲級冠軍為{b.get('champion', '')}（{b.get('final_note', '')}）；"
         f"女子甲級冠軍為{g.get('champion', '')}（{g.get('final_note', '')}）。"),
        ("這個頁面的資料來源是什麼？",
         "整理自 HBL 官方網站（hbl.com.tw）公開賽果；本頁僅整理隊伍層的比分與名次，"
         "不涉及個別球員數據。本站與主辦單位無任何官方關聯，引用請以官方公告為準。"),
        ("哪裡可以看 HBL 比賽轉播？",
         "HBL 新媒體轉播由中華電信 Hami Video（HBLTV）取得授權，部分場次另有電視台轉播；"
         "本站不提供任何賽事影音，請至獲授權平台觀看。"),
    ]


def _faq_html(pairs):
    qa = "".join(
        f'<div class="qa"><h3>{html_lib.escape(q)}</h3><p>{html_lib.escape(a)}</p></div>'
        for q, a in pairs)
    return f'<h2 class="st-faq-sec">常見問題</h2><section class="st-faq">{qa}</section>'


def build_page(snap, hist):
    season_label = snap.get("season_label", "")
    asof = snap.get("asof_taipei_date", "")
    canonical = f"{BASE}/hbl/"
    dvs = snap.get("divisions", {})
    tabs = (
        '<div class="tabs">'
        '<input type="radio" name="hbtab" id="hbtab-b" checked>'
        '<input type="radio" name="hbtab" id="hbtab-g">'
        '<div class="tablabels"><label for="hbtab-b">男子甲級</label>'
        '<label for="hbtab-g">女子甲級</label></div>'
        f'<div class="panel panel-b">{division_panel(dvs["boys"], season_label) if dvs.get("boys") else ""}</div>'
        f'<div class="panel panel-g">{division_panel(dvs["girls"], season_label) if dvs.get("girls") else ""}</div>'
        '</div>'
    )
    hist_sec = history_table(hist) if hist else ""
    asof_note = (
        f'<p class="st-asof">資料整理自 HBL 官方網站（hbl.com.tw）公開賽果，快照日期 {asof}；'
        f'{season_label}賽事已完賽，表列為總決賽最終名次。本頁僅整理隊伍層賽果，不列個別球員數據。'
        '本站為非官方資料整理站，與中華民國高級中等學校體育總會及各校無任何關聯或授權；'
        '賽事名稱與相關權利屬各權利人所有，引用請以官方公告為準。</p>'
    )
    faq = _page_faq(season_label, dvs)
    body = (f'<h1 class="st-h1">HBL 高中籃球 — 甲級四強與冠軍</h1>'
            f'<div class="st-sub">{season_label} HBL 高中籃球甲級聯賽男子組、女子組總決賽結果（截至 {asof}）。</div>'
            f'{tabs}{hist_sec}{_faq_html(faq)}{asof_note}')
    coll = {"@type": "CollectionPage", "@id": canonical, "url": canonical,
            "name": f"HBL 高中籃球甲級四強與冠軍（{season_label}）", "inLanguage": "zh-Hant",
            "isPartOf": {"@id": f"{BASE}/#website"}}
    jsonld = ba.graph_ld([ba.org_node(SITE), ba.website_node(SITE), coll,
                          ba.breadcrumb_node([("首頁", f"{BASE}/"), ("HBL", canonical)]),
                          ba.faq_node(faq, canonical)])
    b, g = dvs.get("boys", {}), dvs.get("girls", {})
    desc = (f"{season_label} HBL 高中籃球甲級聯賽：男甲冠軍{b.get('champion', '')}"
            f"（{b.get('final_note', '')}）、女甲冠軍{g.get('champion', '')}"
            f"（{g.get('final_note', '')}），四強最終名次與歷屆冠軍榜。整理自官方公開賽果的非官方頁面。")
    return _shell(f"HBL 高中籃球甲級四強與冠軍（{season_label}）", desc, canonical, jsonld, body)


def main():
    cands = sorted(glob.glob(str(ROOT / "leagues" / "hbl-*.json")))
    cands = [c for c in cands if "history" not in c]
    if not cands:
        raise SystemExit("❌ leagues/ 下沒有 hbl-*.json；先跑 fetch-hbl.py。")
    snap = json.loads(pathlib.Path(cands[-1]).read_text(encoding="utf-8"))
    hist_p = ROOT / "leagues" / "hbl-history.json"
    hist = json.loads(hist_p.read_text(encoding="utf-8")) if hist_p.exists() else None

    out_dir = ROOT / "public-basketball" / "hbl"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(build_page(snap, hist), encoding="utf-8")
    print("✅ public-basketball/hbl/index.html")

    sm = ROOT / "public-basketball" / "sitemap.xml"
    keep = ([u for u in re.findall(r"<loc>([^<]+)</loc>", sm.read_text(encoding="utf-8"))
             if "/hbl/" not in u] if sm.exists() else [f"{BASE}/"])
    urls = list(dict.fromkeys(keep + [f"{BASE}/hbl/"]))
    body = "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
    sm.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                  f"{body}</urlset>\n", encoding="utf-8")
    print(f"🗺️  sitemap.xml → {len(urls)} URLs (+/hbl/)")


if __name__ == "__main__":
    main()
