#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-nba-cup.py — NBA Cup（季中錦標賽）小組賽戰績頁（public-basketball/nba-cup/）。

吃 leagues/nba-cup-<season>.json（fetch-nba-cup.py）：六組 standings（勝敗、淨勝分、總得分，
本站依官方同分規則前三層自算）＋各組逐場（台北時間）＋外卡（本站自算）＋淘汰賽日程（config）。
⚠️ 晉級、種子與淘汰賽對戰以 NBA 官方公告為準，頁面每處都標。

用法：python3 scripts/gen-nba-cup.py
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
ARTICLE = "/articles/nba-cup-2026-format-guide/"

PAGE_CSS = """
.cup-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;margin:14px 0}
.cup-group h3{margin:0 0 6px;font-size:1.05rem}
.cup-group .tie{font-size:12px;color:var(--fg-mute);margin:6px 0 0}
table.cup{width:100%;border-collapse:separate;border-spacing:0;font-size:14px;border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden;background:var(--surface)}
table.cup th,table.cup td{padding:9px 10px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
table.cup th.l,table.cup td.l{text-align:left}
table.cup thead th{font-family:var(--f-ui);font-weight:600;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--fg-mute);background:var(--surface-3)}
table.cup tbody tr:last-child td{border-bottom:none}
table.cup tbody tr.lead td{color:var(--accent);font-weight:700}
table.games{width:100%;border-collapse:separate;border-spacing:0;font-size:13px;border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden;background:var(--surface);margin-top:8px}
table.games td,table.games th{padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:left}
table.games thead th{font-family:var(--f-ui);font-weight:600;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--fg-mute);background:var(--surface-3)}
table.games tbody tr:last-child td{border-bottom:none}
"""


def _shell(title, desc, canonical, jsonld, body):
    return f"""<!DOCTYPE html>
<html lang="zh-Hant" data-theme="{SITE['default_theme']}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="{ba._BB_BG.get(SITE.get('default_theme'), '#14100e')}">
<script>{ba.theme_preload_js(SITE)}</script>
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
{ba.site_header_html('nba-cup', SITE)}
<main class="wrap">
{body}
</main>
{ba.site_footer_html(SITE)}
<script>{ba.theme_switch_js(SITE)}</script>
</body>
</html>
"""


def _signed(n):
    return f"+{n}" if n > 0 else str(n)


def group_block(group):
    rows = ""
    for i, r in enumerate(group.get("standings", [])):
        lead = ' class="lead"' if i == 0 and r.get("played") else ""
        rows += (f'<tr{lead}><td class="l">{i + 1}</td><td class="l">{html_lib.escape(r.get("name_zh", ""))}'
                 f' <span class="abbr">{html_lib.escape(r.get("abbr", ""))}</span></td>'
                 f'<td>{r.get("wins", 0)}</td><td>{r.get("losses", 0)}</td>'
                 f'<td>{_signed(int(r.get("diff", 0)))}</td><td>{r.get("points", 0)}</td></tr>')
    games = ""
    for g in group.get("games", []):
        if g.get("status") == "FINAL" and g.get("home_score") is not None:
            mid = f'{g.get("away_score")}：{g.get("home_score")}' + ("（OT）" if g.get("ot") else "")
        elif g.get("status") in ("LIVE", "POSTPONED", "CANCELLED"):
            mid = {"LIVE": "進行中", "POSTPONED": "延期", "CANCELLED": "取消"}[g["status"]]
        else:
            mid = html_lib.escape(g.get("time", "")) + " 開賽"
        games += (f'<tr><td>{html_lib.escape(g.get("date", ""))}</td>'
                  f'<td>{html_lib.escape(g.get("away_zh", ""))} @ {html_lib.escape(g.get("home_zh", ""))}</td>'
                  f'<td>{mid}</td></tr>')
    tie = (f'<p class="tie">{html_lib.escape(group["tie_note"])}</p>' if group.get("tie_note") else "")
    return (f'<div class="cup-group"><h3>{html_lib.escape(group.get("name", ""))}</h3>'
            '<div class="tbl-scroll"><table class="cup"><thead><tr><th class="l">#</th><th class="l">球隊</th>'
            '<th>勝</th><th>敗</th><th>淨勝分</th><th>總得分</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>{tie}'
            '<details><summary class="tbl-cap">各場（台北時間）</summary>'
            '<div class="tbl-scroll"><table class="games"><thead><tr><th>日期</th><th>對戰（客 @ 主）</th><th>比分／開賽</th></tr></thead>'
            f'<tbody>{games}</tbody></table></div></details></div>')


def _page_faq(snap):
    label = snap.get("label", "NBA Cup")
    season = snap.get("season", "")
    done = sum(1 for g in snap.get("groups", []) for x in g.get("games", []) if x.get("status") == "FINAL")
    total = 10 * len(snap.get("groups", []))  # 賽制常數：每組 5 隊各打 4 場＝10 場；不用抓到的場數（ESPN 可能只出一部分）
    tb = snap.get("tiebreak") or []
    ko = snap.get("knockout") or {}
    wc = snap.get("wildcards") or {}
    wc_txt = "；".join(f'{"東區" if k == "Eastern" else "西區"}外卡目前為{v["name_zh"]}'
                      for k, v in wc.items() if v)
    return [
        (f"{label} 是什麼？什麼時候打？",
         f"NBA 季中錦標賽（{label}）的小組賽共 {total} 場，排在 {snap.get('group_play', {}).get('note', '')}；"
         "30 隊分成東西區各 3 組、每組 5 隊，每隊打 4 場，小組賽計入例行賽戰績。"
         f"完整賽制與分組由來見本站的 {label} 賽制指南（{ARTICLE}）。"),
        ("怎麼晉級淘汰賽？",
         "8 隊：6 個小組第一，加上東西區各 1 張外卡。外卡是該區 3 個小組第二名中小組賽戰績最好的一隊，"
         f"只在同區內比。{wc_txt + '（本站自算，以官方公告為準）。' if wc_txt else '小組賽開打後本頁會顯示本站自算的外卡現況，以官方公告為準。'}"),
        ("組內同分怎麼排？本頁的名次是官方名次嗎？",
         "官方同分規則依序為：" + "→".join(tb) + "。"
         "本頁只自算前三層（對戰成績只在恰兩隊同分時算；淨勝分與總得分不含延長賽，進延長賽的場次淨勝分記 0），"
         "三隊以上同分或需要第四層以後的情況會標註，名次以 NBA 官方公告為準。"),
        ("淘汰賽在哪裡打？",
         f"八強賽 {ko.get('quarterfinals', '')}；四強賽 {ko.get('semifinals', '')}；冠軍戰 {ko.get('final', '')}。"
         "冠軍戰是唯一的中立場地，且不計入例行賽戰績。"),
        ("這個頁面的資料來源是什麼？多久更新？",
         f"賽程與比分整理自 ESPN 公開資料（scoreboard 標記 NBA Cup 的場次），分組依 NBA 官方 2026 年 6 月 30 日公告；"
         f"快照 {snap.get('asof_taipei_date', '')}，每日自動更新（小組賽已完成 {done}／{total} 場）。"
         "本站與 NBA 及各球團無任何官方關聯，引用請以官方公告為準。"),
    ]


def build_page(snap):
    label = snap.get("label", "NBA Cup")
    season = snap.get("season", "")
    asof = snap.get("asof_taipei_date", "")
    canonical = f"{BASE}/nba-cup/"
    groups = snap.get("groups", [])
    done = sum(1 for g in groups for x in g.get("games", []) if x.get("status") == "FINAL")
    total = 10 * len(groups)
    west = [g for g in groups if g.get("conference") == "Western"]
    east = [g for g in groups if g.get("conference") == "Eastern"]
    wc = snap.get("wildcards") or {}
    wc_html = ""
    if any(wc.values()):
        parts = [f'{"東區" if k == "Eastern" else "西區"}：{html_lib.escape(v["name_zh"])}'
                 for k, v in wc.items() if v]
        wc_html = ('<div class="tbl-cap">外卡現況（本站自算，各區小組第二名中戰績最佳者；以官方公告為準）：'
                   + "、".join(parts) + '</div>')
    sections = ""
    for conf_label, lst in (("西區 West", west), ("東區 East", east)):
        if not lst:
            continue
        sections += (f'<section class="blk"><div class="sp"></div>'
                     + ba.bb_slabel(f'{conf_label.split()[0]} <em>{conf_label.split()[1]}</em>', "小組賽")
                     + '<div class="cup-grid">' + "".join(group_block(g) for g in lst) + '</div></section>')
    unassigned = snap.get("unassigned") or []
    warn = (f'<div class="tbl-cap">⚠️ 有 {len(unassigned)} 場 ESPN 標為 Cup 但兩隊不在同一組，未計入上表：'
            f'{html_lib.escape("、".join(unassigned))}。</div>' if unassigned else "")
    ko = snap.get("knockout") or {}
    ko_html = ('<section class="blk"><div class="sp"></div>' + ba.bb_slabel('淘汰賽 <em>日程</em>', "官方公告")
               + '<div class="tbl-scroll"><table class="cup"><thead><tr><th class="l">輪次</th><th class="l">日期與場地</th></tr></thead><tbody>'
               + "".join(f'<tr><td class="l">{lbl}</td><td class="l">{html_lib.escape(str(ko.get(k, "")))}</td></tr>'
                         for k, lbl in (("quarterfinals", "八強賽"), ("semifinals", "四強賽"), ("final", "冠軍戰")) if ko.get(k))
               + '</tbody></table></div></section>') if ko else ""
    cap = (f'<div class="tbl-cap">{label} 小組賽：已完成 {done}／{total} 場 · 快照 {asof}（台北） · '
           '名次依官方同分規則前三層自算（對戰、淨勝分、總得分，皆不含延長賽），晉級與種子以 NBA 官方公告為準。'
           '整理自 ESPN 公開資料，分組依 NBA 官方公告；本站與 NBA 及各球團無任何官方關聯。</div>')
    faq = _page_faq(snap)
    body = (
        '<section class="page-hero">'
        f'<h1><span class="en">{html_lib.escape(label)}</span> 小組賽戰績與分組</h1>'
        f'<p class="sub">NBA {season} 季中錦標賽六個小組的勝敗、淨勝分與逐場賽程（台北時間，截至 {asof}），'
        f'附外卡現況與淘汰賽日程。賽制說明見<a href="{ARTICLE}">{html_lib.escape(label)} 賽制指南</a>。</p>'
        '</section>' + wc_html + sections + warn + cap + ko_html + ba.bb_faq_details_html(faq))
    title = f"{label} 小組賽戰績與分組（{season}）"
    coll = {"@type": "CollectionPage", "@id": canonical, "url": canonical, "name": title,
            "inLanguage": "zh-Hant", "isPartOf": {"@id": f"{BASE}/#website"}}
    jsonld = ba.graph_ld([ba.org_node(SITE), ba.website_node(SITE), coll,
                          ba.breadcrumb_node([("首頁", f"{BASE}/"), ("NBA Cup", canonical)]),
                          ba.faq_node(faq, canonical)])
    desc = (f"{label} 六個小組戰績（截至 {asof}，已完成 {done}／{total} 場）：各組勝敗、淨勝分、總得分與逐場賽程（台北時間），"
            "外卡現況與八強、四強、冠軍戰日程。整理自 ESPN 公開資料與 NBA 官方分組公告的非官方數據頁。")
    return _shell(title, desc, canonical, jsonld, body)


def main():
    cands = sorted(glob.glob(str(ROOT / "leagues" / "nba-cup-*.json")))
    if not cands:
        print("⏭️ leagues/ 下沒有 nba-cup-*.json（本季分組未登記或尚未抓取）→ 不產 /nba-cup/")
        return
    snap = json.loads(pathlib.Path(cands[-1]).read_text(encoding="utf-8"))
    out_dir = ROOT / "public-basketball" / "nba-cup"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(build_page(snap), encoding="utf-8")
    print("✅ public-basketball/nba-cup/index.html")

    sm = ROOT / "public-basketball" / "sitemap.xml"
    keep = ([u for u in re.findall(r"<loc>([^<]+)</loc>", sm.read_text(encoding="utf-8"))
             if "/nba-cup/" not in u] if sm.exists() else [f"{BASE}/"])
    urls = list(dict.fromkeys(keep + [f"{BASE}/nba-cup/"]))
    body = "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
    sm.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                  f"{body}</urlset>\n", encoding="utf-8")
    print(f"🗺️  sitemap.xml → {len(urls)} URLs (+/nba-cup/)")


if __name__ == "__main__":
    main()
