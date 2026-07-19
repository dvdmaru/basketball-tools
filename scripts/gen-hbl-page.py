#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-hbl-page.py — HBL 高中籃球頁（public-basketball/hbl/）v2。

Claude Design 元件落地：page-hero＋男甲/女甲 champ-band＋四強 .four 卡（mock 版式）
＋歷屆冠軍 v2 .std 風格表（zebra）＋details FAQ。
歷屆冠軍榜吃 leagues/hbl-history.json（fetch-hbl.py --history；API 僅回溯至 106 學年度）。

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
table.hist{width:100%;border-collapse:separate;border-spacing:0;font-size:14px;border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden;background:var(--surface)}
table.hist th,table.hist td{padding:11px 14px;text-align:left;border-bottom:1px solid var(--line);background:var(--surface)}
table.hist thead th{font-family:var(--f-ui);font-weight:600;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--fg-mute);background:var(--surface-3);border-bottom:1px solid var(--line-2)}
table.hist tbody tr:last-child td{border-bottom:none}
table.hist tbody tr:nth-child(even) td{background:var(--zebra)}
table.hist td.yr{font-family:var(--f-ui);font-weight:700;color:var(--accent);white-space:nowrap}
.four-grid{grid-template-columns:minmax(0,680px)}
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
{ba.SITE_HEADER_CSS}
{ba.BB_HOME_CSS}
{ba.BB_PAGE_EXTRA_CSS}
{PAGE_CSS}
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


def division_block(div, season_label):
    band = ('<div class="champ-band"><div class="bseal">冠</div><div class="bt">'
            f'<div class="lbl">{html_lib.escape(season_label)}{html_lib.escape(div["label"])}冠軍</div>'
            f'<div class="nm">{html_lib.escape(div["champion"])}</div>'
            f'<div class="sr">{html_lib.escape(div.get("final_note", ""))}</div>'
            '</div></div>')
    rank_zh = {1: "冠軍", 2: "亞軍", 3: "季軍", 4: "殿軍"}
    rows = ""
    for r in div.get("final_four", []):
        champ = ' champ' if r.get("rank") == 1 else ""
        note = r.get("note", "")
        note_html = f'<span class="note">{html_lib.escape(note)}</span>' if note else ""
        rows += (f'<div class="row{champ}"><span class="pl">{rank_zh.get(r.get("rank"), r.get("rank"))}</span>'
                 f'<span class="nm">{html_lib.escape(r.get("school", ""))}</span>{note_html}</div>')
    four = f'<div class="four"><h4>{html_lib.escape(div.get("label", ""))} · 四強</h4>{rows}</div>'
    return band, four


def history_table(hist):
    rows = sorted(hist.get("seasons", []), key=lambda r: -int(r["season"]))
    trs = ""
    for r in rows:
        trs += (f'<tr><td class="yr">{r["season"]}學年度</td>'
                f'<td>{html_lib.escape(r.get("boys_champion") or "—")}</td>'
                f'<td>{html_lib.escape(r.get("girls_champion") or "—")}</td></tr>')
    return ('<section class="blk"><div class="sp"></div>'
            + ba.bb_slabel('歷屆 <em>冠軍</em>', '106 學年度起')
            + '<div class="tbl-cap" style="margin:0 0 14px">官網公開賽果可回溯至 106 學年度（2017-18）；更早屆次不在此列。</div>'
            '<table class="hist"><thead><tr><th>學年度</th>'
            '<th>男子甲級冠軍</th><th>女子甲級冠軍</th></tr></thead>'
            f'<tbody>{trs}</tbody></table></section>')


def _page_faq(season_label, divisions):
    b = divisions.get("boys", {})
    g = divisions.get("girls", {})
    return [
        ("HBL 是什麼？",
         "HBL（高級中等學校籃球聯賽）是由中華民國高級中等學校體育總會主辦的全國高中籃球賽事，"
         "本頁聚焦最高層級的甲級聯賽（男子組與女子組）。賽季約從 10 月打到隔年 3 月，"
         "四強決賽自 103 學年度重返臺北小巨蛋後，近年都在此舉行。"),
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


def build_page(snap, hist):
    season_label = snap.get("season_label", "")
    asof = snap.get("asof_taipei_date", "")
    canonical = f"{BASE}/hbl/"
    dvs = snap.get("divisions", {})
    blocks = ""
    for k in ("boys", "girls"):
        if not dvs.get(k):
            continue
        band, four = division_block(dvs[k], season_label)
        blocks += (f'<section class="blk"><div class="sp"></div>'
                   + ba.bb_slabel(f'{"男子" if k == "boys" else "女子"} <em>甲級</em>', season_label)
                   + band + f'<div class="four-grid">{four}</div></section>')
    cap = (f'<div class="tbl-cap">{season_label}賽事已完賽，表列為總決賽最終名次（快照 {asof}）；'
           '本頁僅整理隊伍層賽果，不列個別球員數據。'
           '本站與中華民國高級中等學校體育總會及各校無任何關聯或授權，引用請以官方公告為準。</div>')
    hist_sec = history_table(hist) if hist else ""
    faq = _page_faq(season_label, dvs)
    body = (
        '<section class="page-hero">'
        '<h1><span class="en">HBL</span> 高中籃球 — 甲級四強與冠軍</h1>'
        f'<p class="sub">{season_label} HBL 高中籃球甲級聯賽男子組、女子組總決賽結果，'
        '與可回溯的歷屆冠軍榜。</p>'
        '</section>'
        + blocks + cap + hist_sec + ba.bb_faq_details_html(faq))
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
