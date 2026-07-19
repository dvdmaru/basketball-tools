#!/usr/bin/env python3
"""
build-articles.py — markdown → static HTML + 套 design tokens (同 public/index.html 7 主題)

Input:
    articles/<slug>/index.md + assets (cover.png, table-*.png, etc)

Output:
    public/articles/<slug>/index.html + cp assets
    public/articles/index.html  (article 列表，sorted by date desc)

Frontmatter (per article):
    ---
    slug: <slug>
    type: daily | feature
    date: YYYY-MM-DD
    title: "..."
    subtitle: "..."
    vol: N (daily only)
    lede: "..."   # optional — 40–80 字直接答案（AEO 短答），render 成「重點速答」盒
                  #            + 餵進 meta description / Article.description
    ---

AEO FAQ（optional）：在 markdown body 末段寫一個 FAQ 區段，build 會自動產
FAQPage JSON-LD（可見內容照常 render，schema 文字＝可見文字）：

    ## 常見問題
    ### 問句一？
    答案段落一。
    ### 問句二？
    答案段落二。

接受的區段標題：`## 常見問題` / `## 常見問答` / `## FAQ`。
內容務必由人工／pipeline 依已驗事實撰寫，build 端不生成任何 FAQ 文字。

用法：
    python3 scripts/build-articles.py
"""

import pathlib
import re
import shutil
import sys
import datetime
import json
import glob
import unicodedata
import html as html_lib

import markdown as md_lib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "articles"
OUT = ROOT / "public" / "articles"
SITE = "https://foootball.twtools.cc"
ORG_NAME = "@foootball"

WEEKDAY_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


# ---------- competition registry (multi-competition single source of truth) ----------
# config/competitions.json drives schema.org nodes, cadence, data source and IA per
# competition. Phase 1 holds only wc2026; tournament_node() is now a thin alias over
# competition_node(wc2026) and emits byte-identical JSON-LD to the previous hardcode.
def load_competitions() -> dict:
    p = ROOT / "config" / "competitions.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


COMPETITIONS = load_competitions()


# ---------- draft exclusion (build-side pending-review gate) ----------
# Slugs listed in config/draft-exclude.json are treated as drafts pending review and are
# skipped entirely at discovery -> they never enter any article index, feed, sitemap, sport
# landing, or get an individual page rendered. This keeps unreviewed articles that already
# live in the shared articles/ pool off the public site WITHOUT touching the author's source
# files (frontmatter stays untouched, so the author's later "reviewed" commit won't conflict).
# Remove a slug here once its cross-check passes to publish it. Empty by default -> zero
# effect (output byte-identical), so shipping it dormant is safe.
def load_draft_excludes() -> set:
    p = ROOT / "config" / "draft-exclude.json"
    if not p.exists():
        return set()
    data = json.loads(p.read_text(encoding="utf-8"))
    slugs = data.get("exclude", []) if isinstance(data, dict) else data
    return {str(s) for s in (slugs or [])}


DRAFT_EXCLUDE = load_draft_excludes()


# ---------- per-sport site identity (multi-sport single source of truth) ----------
# config/sites.json carries org/website identity per sport (base URL, org name, sameAs,
# website name). A comp resolves its site via its `sport` field; comps without `sport`
# (every existing soccer comp) fall back to SOCCER_SITE, whose values equal the legacy
# SITE/ORG_NAME constants -> existing soccer pages emit byte-identical JSON-LD.
def load_sites() -> dict:
    p = ROOT / "config" / "sites.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


SITES = load_sites()

# Hardcoded fallback == legacy constants, so a missing/partial sites.json never changes
# the soccer output (the regression contract). sites.json["soccer"] must match this.
SOCCER_SITE = SITES.get("soccer") or {
    "base": SITE,
    "org_name": ORG_NAME,
    "org_same_as": ["https://medium.com/@foootball"],
    "website_name": "@foootball — 2026 世界盃賽程 + 戰報",
    "brand_mark": "@FOOOTBALL",
    "brand_tag": "2026 World Cup · 賽程 + 戰報",
    "title_suffix": "@foootball",
    "feed_title": "@foootball 最新文章",
    "feed_channel_title": "@foootball — 2026 世界盃戰報與專題",
    "feed_channel_desc": "2026 FIFA 世界盃每日戰報、規則解析與專題文章。",
    "default_theme": "grass",
    "nav": [
        {"label": "賽程訂閱", "href": "/", "key": "home"},
        {"label": "戰況", "href": "/standings/", "key": "standings"},
        {"label": "文章", "href": "/articles/", "key": "articles"},
    ],
    "external_link": {"label": "Medium ↗", "href": "https://medium.com/@foootball"},
    "footer_cta": {"label": "👉 訂閱你的球隊賽程", "href": "/"},
    "footer_links": [
        {"label": "所有文章", "href": "/articles/"},
        {"label": "Medium", "href": "https://medium.com/@foootball", "external": True},
        {"label": "賽程訂閱", "href": "/"},
    ],
}


def site_for(comp: dict) -> dict:
    """Resolve a comp to its site-identity dict. Sport read off the comp's top-level
    `sport` (falls back to the schema block, then soccer). Soccer -> SOCCER_SITE."""
    sport = (comp.get("sport") or comp.get("schema", {}).get("sport") or "soccer").lower()
    return SITES.get(sport, SOCCER_SITE)


def effective_status(comp: dict, today: datetime.date = None) -> str:
    """Resolve display status. `status` is authored intent; once past `archive_after`
    the competition is treated as archived (drives index/homepage placement). Data-
    driven so the 2026-07-19 World Cup → archive transition is a no-op rebuild."""
    if today is None:
        today = datetime.date.today()
    aft = comp.get("archive_after")
    if aft:
        try:
            if today > datetime.date.fromisoformat(aft):
                return "archived"
        except ValueError:
            pass
    return comp.get("status", "live")


# ---------- site-wide GA4 (同步 public/index.html) ----------
def ga_snippet(site: dict = None) -> str:
    """Per-site GA4 tag. Defaults to the soccer/world-cup property so legacy
    public/ output stays byte-identical; baseball passes its own ga_id (sites.json)."""
    # 無 ga_id ⇒ 不掛 GA（等 Charlie 開 GA4 property 後把 measurement id 填進
    # sites.json 的 ga_id 再重 build；絕不 fallback 到別站的 id）。
    gid = (site or {}).get("ga_id")
    if not gid:
        return "<!-- GA4: ga_id 未設定（sites.json），暫不掛追蹤 -->"
    return (
        "<!-- Google tag (gtag.js) -->\n"
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>\n'
        "<script>\n"
        "  window.dataLayer = window.dataLayer || [];\n"
        "  function gtag(){dataLayer.push(arguments);}\n"
        "  gtag('js', new Date());\n"
        f"  gtag('config', '{gid}');\n"
        "</script>"
    )


GA_SNIPPET = ga_snippet()


# ---------- shared design tokens (與 public/index.html 同步) ----------

SHARED_TOKENS_CSS = """
:root {
  --radius: 16px;
  --radius-sm: 11px;
  --font-display: 'Anton', 'Noto Sans TC', sans-serif;
  --font-ui: 'Archivo', 'Noto Sans TC', -apple-system, BlinkMacSystemFont, 'PingFang TC', 'Microsoft JhengHei', sans-serif;
  --font-mono: ui-monospace, 'SF Mono', 'Cascadia Mono', Menlo, monospace;
  --surface: #ffffff; --surface-2: #f8faf6; --surface-3: #eef1ec;
  --fg: #1b211e; --fg-soft: #49534d; --dim: #6f7a73; --faint: #9aa39d;
  --line: rgba(20,28,24,0.10); --line-2: rgba(20,28,24,0.17);
  --sheet-shadow: rgba(20,28,24,0.16); --scrim: rgba(20,28,24,0.34);
}
:root[data-theme="grass"]    { --bg:#f1f4ed; --bg-glow:#e2efdc; --accent:#1f9d63; --accent-bright:#23b372; --accent-ink:#ffffff; --accent-soft:rgba(31,157,99,0.10);  --accent-line:rgba(31,157,99,0.30);  --accent-glow:rgba(31,157,99,0.26); }
:root[data-theme="cobalt"]   { --bg:#eef1f7; --bg-glow:#e1e8f7; --accent:#2b5ce0; --accent-bright:#3a6bf0; --accent-ink:#ffffff; --accent-soft:rgba(43,92,224,0.10);  --accent-line:rgba(43,92,224,0.30);  --accent-glow:rgba(43,92,224,0.26); }
:root[data-theme="tangerine"]{ --bg:#f7f1e9; --bg-glow:#f3e6d4; --accent:#d4622a; --accent-bright:#e8743a; --accent-ink:#ffffff; --accent-soft:rgba(212,98,42,0.10);  --accent-line:rgba(212,98,42,0.30);  --accent-glow:rgba(212,98,42,0.26); }
:root[data-theme="berry"]    { --bg:#f6eef2; --bg-glow:#f2e1ea; --accent:#c0356f; --accent-bright:#d44a82; --accent-ink:#ffffff; --accent-soft:rgba(192,53,111,0.10); --accent-line:rgba(192,53,111,0.30); --accent-glow:rgba(192,53,111,0.26); }
:root[data-theme="teal"]     { --bg:#ebf2f1; --bg-glow:#dcecea; --accent:#0f8a8a; --accent-bright:#14a3a0; --accent-ink:#ffffff; --accent-soft:rgba(15,138,138,0.10); --accent-line:rgba(15,138,138,0.30); --accent-glow:rgba(15,138,138,0.26); }
:root[data-theme="plum"]     { --bg:#f1eef6; --bg-glow:#e6e1f3; --accent:#6c4bd1; --accent-bright:#7d5ee0; --accent-ink:#ffffff; --accent-soft:rgba(108,75,209,0.10); --accent-line:rgba(108,75,209,0.30); --accent-glow:rgba(108,75,209,0.26); }
:root[data-theme="dark"] {
  --surface: #143524; --surface-2: #1a4530; --surface-3: #1f4a36;
  --fg: #e8f0e6; --fg-soft: #b8c5bb; --dim: #8a9c8d; --faint: #6a7a6e;
  --line: rgba(232,240,230,0.10); --line-2: rgba(232,240,230,0.18);
  --sheet-shadow: rgba(0,0,0,0.55); --scrim: rgba(0,0,0,0.55);
  --bg: #0d2818; --bg-glow: #143a26; --accent: #d4af37; --accent-bright: #f0c850;
  --accent-ink: #0d2818; --accent-soft: rgba(212,175,55,0.12); --accent-line: rgba(212,175,55,0.35); --accent-glow: rgba(212,175,55,0.30);
}
:root[data-theme="dark"] body::before { mix-blend-mode: screen; opacity: 0.22; }
:root[data-theme="dark"] .theme-switch { box-shadow: 0 6px 22px rgba(0,0,0,0.45); }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  background: var(--bg); color: var(--fg); font-family: var(--font-ui);
  line-height: 1.6; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}
body {
  min-height: 100vh; padding: 0 16px 110px; position: relative;
  background: radial-gradient(130% 72% at 50% -12%, var(--bg-glow) 0%, transparent 56%), var(--bg);
}
body::before {
  content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0; opacity: 0.4;
  mix-blend-mode: multiply;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E");
}
"""

THEME_SWITCH_CSS = """
.theme-switch {
  position: fixed; top: 14px; right: 16px; z-index: 150;
  display: flex; align-items: center; gap: 11px;
  background: color-mix(in srgb, var(--surface) 86%, transparent);
  border: 1px solid var(--line); border-radius: 99px;
  padding: 7px 13px 7px 14px; box-shadow: 0 6px 22px rgba(20,28,24,0.10);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
}
.ts-label { font-family: var(--font-mono); font-size: 10px; letter-spacing: 1.5px; color: var(--dim); text-transform: uppercase; }
.ts-dots { display: flex; gap: 8px; }
.ts-dot {
  width: 19px; height: 19px; border-radius: 50%; padding: 0; cursor: pointer;
  background: var(--sw); border: 2px solid var(--surface);
  box-shadow: 0 0 0 1px var(--line-2);
  transition: transform 0.16s ease, box-shadow 0.16s ease;
}
.ts-dot:hover { transform: scale(1.14); }
.ts-dot.active { box-shadow: 0 0 0 2px var(--sw); transform: scale(1.05); }
@media (max-width: 520px) {
  .theme-switch { top: 10px; right: 10px; padding: 6px 11px; gap: 9px; }
  .ts-label { display: none; }
}
"""

THEME_SWITCH_HTML = """
<div class="theme-switch">
  <span class="ts-label">配色</span>
  <div class="ts-dots">
    <button class="ts-dot" data-theme="grass" onclick="setTheme('grass')" style="--sw:#1f9d63" aria-label="草綠"></button>
    <button class="ts-dot" data-theme="cobalt" onclick="setTheme('cobalt')" style="--sw:#2b5ce0" aria-label="鈷藍"></button>
    <button class="ts-dot" data-theme="tangerine" onclick="setTheme('tangerine')" style="--sw:#d4622a" aria-label="暖橘"></button>
    <button class="ts-dot" data-theme="berry" onclick="setTheme('berry')" style="--sw:#c0356f" aria-label="莓紅"></button>
    <button class="ts-dot" data-theme="teal" onclick="setTheme('teal')" style="--sw:#0f8a8a" aria-label="湖青"></button>
    <button class="ts-dot" data-theme="plum" onclick="setTheme('plum')" style="--sw:#6c4bd1" aria-label="紫"></button>
    <button class="ts-dot" data-theme="dark" onclick="setTheme('dark')" style="--sw:#0d2818" aria-label="深綠（brand）"></button>
  </div>
</div>
"""

THEME_SWITCH_JS = """
const THEMES = ['grass','cobalt','tangerine','berry','teal','plum','dark'];
function setTheme(t) {
  if (!THEMES.includes(t)) t = 'grass';
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem('wc-theme', t); } catch (e) {}
  document.querySelectorAll('.ts-dot').forEach(d => d.classList.toggle('active', d.dataset.theme === t));
}
(function initTheme() {
  let t = 'grass';
  try { t = localStorage.getItem('wc-theme') || 'grass'; } catch (e) {}
  setTheme(t);
})();
"""


# ---------- shared site header (article + index) ----------

SITE_HEADER_CSS = """
.site-header {
  display: flex; justify-content: space-between; align-items: flex-end;
  padding: 36px 0 20px; margin-bottom: 44px;
  border-bottom: 1px solid var(--line);
  gap: 24px; flex-wrap: wrap;
}
.brand-block { display: flex; flex-direction: column; gap: 6px; }
.brand-mark {
  font-family: var(--font-display); font-size: 30px; line-height: 1;
  color: var(--accent); letter-spacing: 1.2px;
  text-decoration: none; transition: color 0.15s ease;
}
.brand-mark:hover { color: var(--accent-bright); }
.brand-tag {
  font-family: var(--font-mono); font-size: 10.5px;
  letter-spacing: 2.5px; color: var(--dim); text-transform: uppercase;
}
.site-nav {
  display: flex; gap: 22px; align-items: center;
  font-family: var(--font-mono); font-size: 11.5px;
  letter-spacing: 2px; text-transform: uppercase;
}
.site-nav a {
  color: var(--dim); text-decoration: none;
  padding: 6px 0; border-bottom: 1.5px solid transparent;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.site-nav a:hover, .site-nav a.active {
  color: var(--accent); border-bottom-color: var(--accent);
}
@media (max-width: 580px) {
  .site-header { padding-top: 22px; gap: 16px; }
  .brand-mark { font-size: 24px; }
  .site-nav { gap: 16px; font-size: 11px; }
}
.site-disclaimer { font-size: 11px; color: var(--faint); line-height: 1.7; text-align: center; max-width: 600px; margin: 18px auto 0; }
.site-disclaimer span { opacity: 0.75; }

/* ---------- v2 header（Claude Design mock；basketball 全站） ---------- */
.container{max-width:1180px;margin:0 auto}
.site-head{position:sticky;top:0;z-index:40;background:var(--bb-header-bg);
  backdrop-filter:saturate(140%) blur(14px);-webkit-backdrop-filter:saturate(140%) blur(14px);
  border-bottom:1px solid var(--line);margin:0 -16px}
.head-in{display:flex;align-items:center;gap:20px;padding:14px 28px;max-width:1180px;margin:0 auto;flex-wrap:wrap}
.brand{display:flex;flex-direction:column;gap:2px;margin-right:auto;text-decoration:none}
.brand .mark{font-family:var(--f-display);font-size:26px;letter-spacing:.5px;color:var(--accent);line-height:1}
.brand .mark b{color:var(--fg);font-weight:400}
.brand .tag{font-family:var(--f-ui);font-size:10.5px;letter-spacing:2.5px;color:var(--fg-mute);text-transform:uppercase}
.nav2{display:flex;gap:4px;font-family:var(--f-ui);font-weight:600;font-size:14px}
.nav2 a{padding:7px 14px;border-radius:999px;color:var(--fg-soft)}
.nav2 a:hover{background:var(--surface-2);color:var(--fg)}
.nav2 a.on{background:var(--accent);color:var(--accent-ink)}
.theme{display:flex;align-items:center;gap:9px;padding-left:16px;border-left:1px solid var(--line)}
.theme .lbl{font-family:var(--f-ui);font-size:10px;letter-spacing:1.5px;color:var(--fg-dim);text-transform:uppercase}
.dots{display:flex;gap:7px}
.dot{width:18px;height:18px;border-radius:50%;border:1.5px solid transparent;cursor:pointer;padding:0;transition:transform .12s}
.dot:hover{transform:scale(1.15)}
.dot[aria-pressed="true"]{border-color:var(--fg)}
@media(max-width:640px){
  .head-in{padding:12px 18px;gap:12px}
  .nav2{order:3;width:100%;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}
  .nav2::-webkit-scrollbar{display:none}
  .theme{padding-left:12px}
  .theme .lbl{display:none}
}
/* ---------- v2 footer ---------- */
.foot{margin-top:80px;border-top:1px solid var(--line);background:var(--bg-deep);margin-left:-16px;margin-right:-16px}
.foot-in{max-width:1180px;margin:0 auto;padding:36px 28px 60px}
.foot .disc{font-size:12px;color:var(--fg-dim);line-height:1.7;text-align:center;max-width:760px;margin:0 auto 20px}
.foot .flinks{display:flex;justify-content:center;gap:8px 22px;flex-wrap:wrap;font-family:var(--f-ui);font-size:13px;margin-bottom:18px}
.sisters{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 20px;font-family:var(--f-ui);font-size:12.5px;color:var(--fg-mute)}
.sisters a{color:var(--fg-soft)}
.sisters b{color:var(--fg-dim);font-weight:600;letter-spacing:1px;text-transform:uppercase;font-size:11px}
"""

# 非官方聲明（全 surface footer）— 降低 false-affiliation 商標風險（nominative fair use 硬化）
DISCLAIMER_HTML = (
    '<div class="site-disclaimer">本站為非官方球迷資訊站，與 FIFA／國際足總無任何關聯或授權；'
    '賽程與比分資料整理自公開來源。<br>'
    '<span>Unofficial fan-made site · Not affiliated with, endorsed by, or sponsored by FIFA.</span></div>'
)

BASKETBALL_DISCLAIMER_HTML = (
    '<div class="site-disclaimer">本站為非官方籃球資訊站，與 NBA、TPBL、P. LEAGUE+、HBL（高中體總）等'
    '聯盟、球團與學校無任何關聯或授權；數據與比分整理自公開來源並標註。<br>'
    '<span>Unofficial fan-made site · Not affiliated with, endorsed by, or sponsored by the NBA, TPBL, P. LEAGUE+ or HBL.</span></div>'
)

# twtools 生態系姊妹站互連（「互連+收錄」計畫）：名稱與定位取自各站現行 title，勿自行改寫。
# 單一資料源，site_footer_html 與 _bb_footer 共用；渲染時排除本站自己。自家站內鏈，不加 nofollow。
SISTER_SITES = [
    ("TWTools — 打工牛馬的線上工具箱", "https://twtools.cc/"),
    ("aire — AI Tool Atlas·AI 工具圖鑑", "https://aire.twtools.cc/"),
    ("樹洞21號 — 匿名 AI 心事平台", "https://tree.twtools.cc/"),
    ("@foootball — 2026 世界盃賽程", "https://foootball.twtools.cc/"),
    ("@baseball — 中職 CPBL＋MLB 深度戰報", "https://baseball.twtools.cc/"),
    ("籃球數據誌 — NBA＋台灣籃球數據", "https://basketball.twtools.cc/"),
    ("Shhhh — 專業短網址管理平台", "https://shhhh.cc/"),
    ("dvdmaru — 把事實和敘事分開來看", "https://dvdmaru.com/"),
]


def sister_sites_html(site: dict) -> str:
    """低調純文字的姊妹站連結列。inline style 以便三種頁面外殼（article / dashboard /
    gen-* _shell）都不需各自補 CSS。"""
    base = site["base"].rstrip("/") + "/"
    links = "　·　".join(
        f'<a href="{u}" style="color:var(--dim);text-decoration:none">{html_lib.escape(n)}</a>'
        for n, u in SISTER_SITES if u != base)
    return ('<div class="sister-sites" style="margin-top:12px;font-size:12px;'
            f'color:var(--dim);line-height:2;text-align:center">姊妹站　{links}</div>')


def site_header_html(active: str, site: dict = None) -> str:
    """active: nav key to mark current ('home'|'data'|'articles'|...).
    Basketball -> v2 sticky 毛玻璃 header（brand + pill nav + 主題 dots，mock 落地）；
    soccer fallback 保留 legacy 版。放在 container 外（頁殼負責）。"""
    site = site or SOCCER_SITE
    if site.get("default_theme", "grass") in BB_THEME_KEYS:
        parts = []
        for n in site.get("nav", []):
            cls = ' class="on"' if n.get("key") == active else ""
            parts.append(f'<a href="{n["href"]}"{cls}>{n["label"]}</a>')
        ext = site.get("external_link")
        if ext:
            parts.append(f'<a href="{ext["href"]}" target="_blank" rel="noopener">{ext["label"]}</a>')
        links = "\n      ".join(parts)
        mark = html_lib.escape(site["brand_mark"])
        if mark.startswith("@"):
            mark = f'@<b>{mark[1:]}</b>'
        dots = "\n        ".join(
            f'<button class="dot" style="background:{acc}" data-set-theme="{k}" '
            f'aria-pressed="{"true" if k == site.get("default_theme") else "false"}" title="{zh}"></button>'
            for k, zh, acc in BB_THEME_DOTS)
        return f"""
<header class="site-head">
  <div class="head-in">
    <a class="brand" href="/">
      <span class="mark">{mark}</span>
      <span class="tag">{html_lib.escape(site["brand_tag"])}</span>
    </a>
    <nav class="nav2">
      {links}
    </nav>
    <div class="theme">
      <span class="lbl">配色</span>
      <div class="dots">
        {dots}
      </div>
    </div>
  </div>
</header>
"""
    parts = []
    for n in site.get("nav", []):
        cls = ' class="active"' if n.get("key") == active else ""
        parts.append(f'<a href="{n["href"]}"{cls}>{n["label"]}</a>')
    ext = site.get("external_link")
    if ext:
        parts.append(f'<a href="{ext["href"]}" target="_blank" rel="noopener">{ext["label"]}</a>')
    links = "\n      ".join(parts)
    return f"""
  <header class="site-header">
    <div class="brand-block">
      <a href="/" class="brand-mark">{site["brand_mark"]}</a>
      <div class="brand-tag">{site["brand_tag"]}</div>
    </div>
    <nav class="site-nav">
      {links}
    </nav>
  </header>
"""


# ---- 籃球數據誌 dark-brand palette v2（Claude Design mock 2026-07-19 落地）----
# ember 預設值採 design-notes token 表（「保留現況值」條目沿用建站日色票）；
# court/slate/jade/violet 變體取自 mock stylesheet（只換 accent 與底色階）。
# 舊代元件（文章頁 ARTICLE_CSS/INDEX_CSS、gen-* 頁 PAGE_CSS）依賴的 legacy 變數
# （--dim/--faint/--accent-soft/--accent-line/--radius/--font-*…）以 alias 併出，
# 一套 token 同時餵新舊兩代版型。分帶/斑馬色刻意用不透明值（手機 sticky 釘欄要實色）。
BB_THEME_KEYS = ["ember", "court", "slate", "jade", "violet"]
BB_THEME_DOTS = [("ember", "ember 炭黑橘", "#ef7d3a"), ("court", "court 木地板金", "#d9a04c"),
                 ("slate", "slate 石墨", "#6f9bd0"), ("jade", "jade 墨玉", "#43b189"),
                 ("violet", "violet 暗紫", "#9b7bd8")]
_BB_ACCENT = {k: acc for k, _z, acc in BB_THEME_DOTS}

_BB_TOKEN_BLOCKS = """
:root[data-theme="ember"]{
  --bg:#14100e; --bg-deep:#0e0b09; --surface:#1c1714; --surface-2:#241d19; --surface-3:#2a221d;
  --fg:#f3ece4; --fg-soft:#d3c8bb; --fg-mute:#94a0b4; --fg-dim:#6d655b;
  --line:rgba(243,236,228,.09); --line-2:rgba(243,236,228,.16);
  --accent:#ef7d3a; --accent-bright:#ff9250; --gold:#d9a04c; --accent-ink:#1a0f07;
  --zebra:#191411; --band-po:#241811; --band-pi:#211a11;
  --accent-weak:rgba(239,125,58,.10); --gold-weak:rgba(217,160,76,.10);
}
:root[data-theme="court"]{
  --bg:#17120c; --bg-deep:#0f0b06; --surface:#211a11; --surface-2:#2a2116; --surface-3:#31271a;
  --fg:#f3ece4; --fg-soft:#d3c8bb; --fg-mute:#94a0b4; --fg-dim:#6d655b;
  --line:rgba(243,236,228,.09); --line-2:rgba(243,236,228,.16);
  --accent:#d9a04c; --accent-bright:#eab863; --gold:#e9c987; --accent-ink:#1a0f07;
  --zebra:#1d160e; --band-po:#271d0f; --band-pi:#241d10;
  --accent-weak:rgba(217,160,76,.10); --gold-weak:rgba(233,201,135,.10);
}
:root[data-theme="slate"]{
  --bg:#111418; --bg-deep:#0b0d10; --surface:#1a1e24; --surface-2:#222831; --surface-3:#293039;
  --fg:#f3ece4; --fg-soft:#d3c8bb; --fg-mute:#8b97a8; --fg-dim:#6d655b;
  --line:rgba(243,236,228,.09); --line-2:rgba(243,236,228,.16);
  --accent:#6f9bd0; --accent-bright:#8bb3e0; --gold:#c9a86a; --accent-ink:#1a0f07;
  --zebra:#161a20; --band-po:#182430; --band-pi:#22201a;
  --accent-weak:rgba(111,155,208,.10); --gold-weak:rgba(201,168,106,.10);
}
:root[data-theme="jade"]{
  --bg:#0f1512; --bg-deep:#0a0f0c; --surface:#16201b; --surface-2:#1d2a23; --surface-3:#24332a;
  --fg:#f3ece4; --fg-soft:#d3c8bb; --fg-mute:#94a0b4; --fg-dim:#6d655b;
  --line:rgba(243,236,228,.09); --line-2:rgba(243,236,228,.16);
  --accent:#43b189; --accent-bright:#5fcfa4; --gold:#cfb069; --accent-ink:#1a0f07;
  --zebra:#131c17; --band-po:#12251c; --band-pi:#20241a;
  --accent-weak:rgba(67,177,137,.10); --gold-weak:rgba(207,176,105,.10);
}
:root[data-theme="violet"]{
  --bg:#15111c; --bg-deep:#0e0b13; --surface:#1e1826; --surface-2:#271f31; --surface-3:#2f263c;
  --fg:#f3ece4; --fg-soft:#d3c8bb; --fg-mute:#94a0b4; --fg-dim:#6d655b;
  --line:rgba(243,236,228,.09); --line-2:rgba(243,236,228,.16);
  --accent:#9b7bd8; --accent-bright:#b79bef; --gold:#cba25f; --accent-ink:#1a0f07;
  --zebra:#191424; --band-po:#241a33; --band-pi:#231d1c;
  --accent-weak:rgba(155,123,216,.10); --gold-weak:rgba(203,162,95,.10);
}
"""


def _hexrgba(h: str, a) -> str:
    h = h.lstrip("#")
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"


def _bb_theme_tokens_css() -> str:
    """v2 token 系統：mock 的 :root[data-theme] 五組 token（_BB_TOKEN_BLOCKS 字面值）
    ＋逐主題 alias 區塊（legacy 變數/字族/圓角/身體背景），讓文章頁與 gen-* 頁零改動續用。"""
    def sel(suffix):
        return ",\n".join(f':root[data-theme="{k}"] {suffix}' for k in BB_THEME_KEYS)

    alias_blocks = []
    for k in BB_THEME_KEYS:
        acc = _BB_ACCENT[k]
        alias_blocks.append(f""":root[data-theme="{k}"] {{
  --dim:var(--fg-mute); --faint:var(--fg-dim);
  --accent-soft:var(--accent-weak); --accent-line:{_hexrgba(acc,0.36)}; --accent-glow:{_hexrgba(acc,0.30)};
  --accent-neg:#d85742; --accent-neg-deep:#c8472f;
  --bg-glow:var(--surface-2); --sheet-shadow:rgba(0,0,0,.5); --scrim:rgba(0,0,0,.5);
  --bb-header-bg:color-mix(in srgb,var(--bg) 82%,transparent);
  --f-display:"Anton",Impact,sans-serif; --f-ui:"Archivo",system-ui,sans-serif;
  --f-text:"Noto Sans TC","PingFang TC",sans-serif;
  --font-display:var(--f-display); --font-ui:var(--f-ui);
  --r-sm:8px; --r-md:12px; --r-lg:16px; --r-xl:22px; --rank-w:46px;
  --radius:var(--r-lg); --radius-sm:var(--r-md);
}}""")

    overrides = f"""{sel('body')} {{ font-family:var(--f-text);
  background-image:
    radial-gradient(1200px 720px at 86% -6%,rgba(239,125,58,.16),transparent 58%),
    radial-gradient(900px 620px at 6% 2%,rgba(217,160,76,.08),transparent 60%),
    radial-gradient(1500px 1000px at 50% 118%,rgba(239,125,58,.06),transparent 62%);
  background-attachment:fixed; }}
{sel('body::before')} {{ display:none; }}
{sel('a')} {{ color:var(--accent); }}
{sel('a:hover')} {{ color:var(--accent-bright); }}"""
    return "\n" + _BB_TOKEN_BLOCKS + "\n" + "\n".join(alias_blocks) + "\n" + overrides + "\n"


# v2：切換器住進 header（site_header_html 的 .theme dots），獨立浮動 widget 廢止。
BB_THEME_SWITCH_HTML = ""
BB_THEME_SWITCH_JS = """
/* minimal theme switcher — persists to localStorage('bk-theme') */
(function(){
  var KEY="bk-theme", root=document.documentElement;
  var saved=localStorage.getItem(KEY);
  if(saved){ root.setAttribute("data-theme",saved); }
  document.addEventListener("click",function(e){
    var b=e.target.closest("[data-set-theme]"); if(!b) return;
    var t=b.getAttribute("data-set-theme");
    root.setAttribute("data-theme",t);
    localStorage.setItem(KEY,t);
    document.querySelectorAll("[data-set-theme]").forEach(function(x){
      x.setAttribute("aria-pressed", x===b ? "true":"false");
    });
  });
  if(saved){ document.querySelectorAll("[data-set-theme]").forEach(function(x){
    x.setAttribute("aria-pressed", x.getAttribute("data-set-theme")===saved ? "true":"false"); }); }
})();
"""


def theme_switch_html(site: dict = None) -> str:
    """Color switcher. Legacy soccer fallback -> light 7-dot palette. Basketball -> 空字串
    （v2 切換器已內建於 site_header_html 的 dots）。"""
    site = site or SOCCER_SITE
    if site.get("default_theme", "grass") not in BB_THEME_KEYS:
        return THEME_SWITCH_HTML
    return BB_THEME_SWITCH_HTML


def theme_switch_js(site: dict = None) -> str:
    """Theme init/persist JS. Legacy soccer fallback -> light palette (key wc-theme).
    Basketball -> dark palette (default ember, key bk-theme)."""
    site = site or SOCCER_SITE
    if site.get("default_theme", "grass") not in BB_THEME_KEYS:
        return THEME_SWITCH_JS
    return BB_THEME_SWITCH_JS


def extra_theme_css(site: dict = None) -> str:
    """Per-sport extra theme rules injected into the page <style>. Empty for the legacy soccer
    fallback. Basketball = a family of DARK themes (ember default + accent variants), all
    var-driven so this single override drives the whole basketball site + the color switcher."""
    site = site or SOCCER_SITE
    if site.get("default_theme", "grass") not in BB_THEME_KEYS:
        return ""
    return _bb_theme_tokens_css()


def bb_footer_v2(site: dict, active: str = "") -> str:
    """v2 全站 footer（mock 落地）：免責＋快速連結＋姊妹站。放在 container 外。"""
    link_parts = []
    for n in site.get("nav", []):
        link_parts.append(f'<a href="{n["href"]}">{n["label"]}</a>')
    ext = site.get("external_link")
    if ext:
        link_parts.append(f'<a href="{ext["href"]}" target="_blank" rel="noopener">{ext["label"]}</a>')
    links = "".join(link_parts)
    base = site["base"].rstrip("/") + "/"
    sisters = "\n      ".join(
        f'<a href="{u}">{html_lib.escape(n)}</a>'
        for n, u in SISTER_SITES if u != base)
    return f"""
<footer class="foot">
  <div class="foot-in">
    <div class="flinks">{links}</div>
    <p class="disc">本站為非官方籃球資訊站，與 NBA、TPBL、P. LEAGUE+、HBL（高中體總）等聯盟、球團與學校無任何關聯或授權；數據與比分整理自公開來源並標註。<br>
    Unofficial fan-made site · Not affiliated with, endorsed by, or sponsored by the NBA, TPBL, P. LEAGUE+ or HBL.</p>
    <div class="sisters">
      <b>姊妹站</b>
      {sisters}
    </div>
  </div>
</footer>"""


def site_footer_html(site: dict = None) -> str:
    """Article-page footer. Soccer -> legacy footer byte-for-byte (CTA + Medium + disclaimer).
    Basketball -> v2 全站 footer（bb_footer_v2）。"""
    site = site or SOCCER_SITE
    if site.get("default_theme", "grass") in BB_THEME_KEYS:
        return bb_footer_v2(site)
    cta = site.get("footer_cta")
    cta_line = f'\n    <a href="{cta["href"]}" class="cta-btn">{cta["label"]}</a>' if cta else ""
    link_parts = []
    for l in site.get("footer_links", []):
        if l.get("external"):
            link_parts.append(f'<a href="{l["href"]}" target="_blank" rel="noopener">{l["label"]}</a>')
        else:
            link_parts.append(f'<a href="{l["href"]}">{l["label"]}</a>')
    links = "\n      ".join(link_parts)
    disclaimer = DISCLAIMER_HTML
    return f"""  <div class="article-footer">{cta_line}
    <div class="foot-links">
      {links}
    </div>
    {disclaimer}
  </div>"""


# ---------- shared JSON-LD helpers (structured data for SEO/GEO/AEO) ----------

def _ld(obj: dict) -> str:
    """Wrap a schema.org node as a <script type=application/ld+json> block."""
    payload = obj if "@context" in obj else {"@context": "https://schema.org", **obj}
    return ('<script type="application/ld+json">'
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            + "</script>")


def graph_ld(nodes: list) -> str:
    """One @graph block holding several linked nodes (Google merges by @id)."""
    nodes = [n for n in nodes if n]
    if not nodes:
        return ""
    return _ld({"@context": "https://schema.org", "@graph": nodes})


def org_node(site: dict = None) -> dict:
    site = site or SOCCER_SITE
    base = site["base"]
    return {
        "@type": "Organization",
        "@id": f"{base}/#org",
        "name": site["org_name"],
        "url": f"{base}/",
        "sameAs": site["org_same_as"],
    }


def website_node(site: dict = None) -> dict:
    site = site or SOCCER_SITE
    base = site["base"]
    return {
        "@type": "WebSite",
        "@id": f"{base}/#website",
        "name": site["website_name"],
        "url": f"{base}/",
        "inLanguage": "zh-Hant",
        "publisher": {"@id": f"{base}/#org"},
    }


def competition_node(comp: dict, site: dict = None) -> dict:
    """schema.org node for one competition, driven by the registry.

    Cups -> SportsEvent (dated, host countries); leagues -> SportsLeague (season org).
    Key insertion order is preserved so the wc2026 SportsEvent serializes byte-identical
    to the previous hardcoded tournament_node() output (json.dumps keeps insertion order).
    """
    base = (site or site_for(comp))["base"]
    s = comp["schema"]
    node = {
        "@type": s["type"],
        "@id": f"{base}/{comp['schema_id']}",
        "name": comp["name_zh"],
        "sport": s.get("sport", "Soccer"),
    }
    if s["type"] == "SportsEvent":
        node["startDate"] = comp["start_date"]
        node["endDate"] = comp["end_date"]
        node["eventStatus"] = s.get("event_status", "https://schema.org/EventScheduled")
        if "location" in s:
            node["location"] = s["location"]
    else:  # SportsLeague (round-robin / playoff leagues): season-scoped org, no dates
        node["url"] = f"{base}{comp['index']['landing']}"
    if "organizer" in s:
        node["organizer"] = {"@type": "Organization", **s["organizer"]}
    return node


def tournament_node() -> dict:
    """Back-compat alias: the 2026 FIFA World Cup SportsEvent.

    Kept (name + signature) for the whole migration because build-standings.py and
    gen-team-pages.py re-export it by name via importlib. Now sourced from the registry.
    """
    comp = COMPETITIONS.get("wc2026") or next(iter(COMPETITIONS.values()))
    return competition_node(comp)


def breadcrumb_node(items: list) -> dict:
    """items: list of (name, url-or-None). Last item usually current page (url ok)."""
    elements = []
    for i, (name, url) in enumerate(items):
        el = {"@type": "ListItem", "position": i + 1, "name": name}
        if url:
            el["item"] = url
        elements.append(el)
    return {"@type": "BreadcrumbList", "itemListElement": elements}


# ---------- article page CSS ----------

ARTICLE_CSS = """
.container { max-width: 720px; margin: 0 auto; position: relative; z-index: 1; padding-top: 0; }

.article-header { margin-bottom: 32px; padding-bottom: 26px; border-bottom: 1px solid var(--line); }
.article-kicker {
  display: inline-flex; align-items: center; gap: 10px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 3px;
  text-transform: uppercase; color: var(--accent); margin-bottom: 18px; font-weight: 600;
}
.article-kicker::before { content: ''; width: 22px; height: 2px; background: var(--accent); }
.article-title { font-family: var(--font-display); font-weight: 400; font-size: clamp(30px, 5.5vw, 46px); line-height: 1.15; color: var(--fg); margin-bottom: 14px; letter-spacing: 0.3px; }
.article-title .tc { font-family: var(--font-ui); font-weight: 900; letter-spacing: -0.3px; }
.article-subtitle { font-size: 17px; color: var(--fg-soft); line-height: 1.55; font-weight: 500; }
.article-meta { font-family: var(--font-mono); font-size: 12px; color: var(--dim); margin-top: 16px; letter-spacing: 1px; }
.article-meta .dot { display: inline-block; width: 4px; height: 4px; border-radius: 50%; background: var(--faint); vertical-align: middle; margin: 0 9px 2px; }

.article-lede {
  background: var(--surface-2); border-left: 2px solid var(--accent);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  padding: 15px 20px; margin: 0 0 34px;
}
.article-lede .lede-label {
  display: block; font-family: var(--font-mono); font-size: 10.5px;
  letter-spacing: 2.5px; text-transform: uppercase; color: var(--accent);
  font-weight: 700; margin-bottom: 7px;
}
.article-lede p { font-size: 16px; color: var(--fg); line-height: 1.7; margin: 0; }

.article-cover { width: 100%; max-width: 100%; height: auto; border-radius: var(--radius-sm); margin: 0 0 36px; box-shadow: 0 10px 30px var(--sheet-shadow); }

.prose { color: var(--fg-soft); font-size: 16.5px; line-height: 1.85; }
.prose h2 { font-family: var(--font-display); font-weight: 400; font-size: 28px; line-height: 1.2; color: var(--fg); margin: 48px 0 18px; letter-spacing: 0.3px; }
.prose h3 { font-size: 21px; font-weight: 700; color: var(--fg); margin: 36px 0 14px; line-height: 1.35; }
.prose h4 { font-size: 17.5px; font-weight: 700; color: var(--fg); margin: 28px 0 12px; }
.prose p { margin: 0 0 18px; }
.prose strong { color: var(--fg); font-weight: 700; }
.prose em { font-style: italic; }
.prose a { color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--accent-line); transition: border-color 0.15s ease; }
.prose a:hover { border-bottom-color: var(--accent); }
.prose img { display: block; width: 100%; height: auto; max-width: 100%; border-radius: var(--radius-sm); margin: 30px 0; box-shadow: 0 6px 22px var(--sheet-shadow); }
.prose blockquote { border-left: 3px solid var(--accent); background: var(--surface-2); padding: 14px 20px; margin: 24px 0; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; color: var(--fg); font-style: normal; }
.prose blockquote p { margin: 0 0 8px; }
.prose blockquote p:last-child { margin: 0; }
.prose ul, .prose ol { padding-left: 24px; margin: 0 0 22px; }
.prose li { margin: 0 0 8px; }
.prose hr { border: none; height: 1px; background: var(--line); margin: 40px 0; }
.prose table {
  width: 100%; border-collapse: collapse; margin: 28px 0;
  font-size: 14.5px; line-height: 1.55; overflow: hidden;
  border-radius: var(--radius-sm); box-shadow: 0 4px 16px var(--sheet-shadow);
}
.prose thead { background: var(--surface-2); }
.prose th {
  padding: 12px 14px; text-align: left; font-weight: 700; color: var(--fg);
  border-bottom: 2px solid var(--accent-line); letter-spacing: 0.4px; font-size: 13.5px;
}
.prose td {
  padding: 11px 14px; border-bottom: 1px solid var(--line);
  vertical-align: top; color: var(--fg-soft);
}
.prose tbody tr:last-child td { border-bottom: none; }
.prose tbody tr:hover td { background: var(--surface-2); }
.prose table strong { color: var(--accent); font-variant-numeric: tabular-nums; }
/* daily 戰報 §1 4-column table: 賽事 / 比分 / 場館 / 焦點 — explicit widths.
   只套 daily：feature/preview 的多欄表（5–6 欄）改走 auto 排版，否則第 4 欄吃滿 45%
   會把後面的欄位擠成一字一行。 */
.prose--daily table th:nth-child(1), .prose--daily table td:nth-child(1) { width: 24%; }
.prose--daily table th:nth-child(2), .prose--daily table td:nth-child(2) { width: 9%; text-align: center; white-space: nowrap; }
.prose--daily table th:nth-child(3), .prose--daily table td:nth-child(3) { width: 22%; }
.prose--daily table th:nth-child(4), .prose--daily table td:nth-child(4) { width: 45%; }
@media (max-width: 640px) {
  .prose table { font-size: 13px; }
  .prose th, .prose td { padding: 9px 10px; }
  .prose--daily table th:nth-child(3), .prose--daily table td:nth-child(3) { font-size: 12px; }
}
.prose code { background: var(--surface-3); padding: 2px 6px; border-radius: 4px; font-family: var(--font-mono); font-size: 0.92em; color: var(--fg); }
.prose pre { background: var(--surface-3); padding: 14px 16px; border-radius: var(--radius-sm); overflow-x: auto; margin: 20px 0; }
.prose pre code { background: transparent; padding: 0; }

.article-footer { margin-top: 60px; padding-top: 28px; border-top: 1px solid var(--line); display: flex; flex-direction: column; align-items: center; gap: 22px; }
.cta-btn {
  display: inline-flex; align-items: center; gap: 9px;
  padding: 16px 28px; border-radius: 13px;
  background-color: var(--accent); color: var(--accent-ink);
  text-decoration: none; font-weight: 800; font-size: 15px; letter-spacing: 0.4px;
  box-shadow: 0 10px 26px var(--accent-glow);
  transition: transform 0.18s cubic-bezier(0.22,1,0.36,1), background-color 0.18s ease;
}
.cta-btn:hover { transform: translateY(-2px); background-color: var(--accent-bright); }
.foot-links { display: flex; gap: 22px; font-family: var(--font-mono); font-size: 12.5px; letter-spacing: 1px; }
.foot-links a { color: var(--dim); text-decoration: none; }
.foot-links a:hover { color: var(--accent); }

/* ---- series nav: 前一日 / 後一日 + 更多每日戰報 ---- */
.post-nav { margin-top: 56px; padding-top: 30px; border-top: 1px solid var(--line); }
.post-nav-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.post-nav-link {
  display: flex; flex-direction: column; gap: 6px;
  padding: 15px 18px; border: 1px solid var(--line); border-radius: var(--radius-sm);
  background: var(--surface); text-decoration: none;
  transition: border-color 0.18s ease, transform 0.18s ease, box-shadow 0.18s ease;
}
.post-nav-link:hover { border-color: var(--accent-line); transform: translateY(-2px); box-shadow: 0 10px 26px var(--sheet-shadow); }
.post-nav-link.next { text-align: right; align-items: flex-end; }
.post-nav-link.empty { border: none; background: transparent; pointer-events: none; }
.post-nav-link.fallback { background: var(--surface-2); border-style: dashed; justify-content: center; }
.post-nav-link.fallback .pn-dir { color: var(--dim); }
.post-nav-link.fallback .pn-title { color: var(--fg-soft); font-weight: 600; }
.pn-dir { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 1.8px; color: var(--accent); text-transform: uppercase; font-weight: 700; }
.pn-title { font-size: 14.5px; font-weight: 700; color: var(--fg); line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.pn-date { font-family: var(--font-mono); font-size: 11px; color: var(--dim); letter-spacing: 1px; }
.more-dailies { margin-top: 30px; }
.md-label { display: flex; align-items: center; gap: 12px; font-family: var(--font-mono); font-size: 11px; letter-spacing: 3px; color: var(--dim); text-transform: uppercase; margin-bottom: 12px; }
.md-label::before { content: ''; width: 20px; height: 2px; background: var(--accent); }
.md-list { display: flex; flex-direction: column; }
.md-list a { display: flex; gap: 14px; align-items: baseline; padding: 12px 4px; border-bottom: 1px solid var(--line); text-decoration: none; color: var(--fg-soft); transition: color 0.15s ease; }
.md-list a:last-child { border-bottom: none; }
.md-list a:hover { color: var(--accent); }
.md-list .md-date { font-family: var(--font-mono); font-size: 11.5px; color: var(--dim); white-space: nowrap; letter-spacing: 0.5px; }
.md-list .md-ttl { font-size: 14px; font-weight: 600; line-height: 1.4; flex: 1;
  display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }
@media (max-width: 560px) {
  .post-nav-pair { grid-template-columns: 1fr; }
  .post-nav-link.next { text-align: left; align-items: flex-start; }
  .post-nav-link.empty { display: none; }
}
"""


# ---------- index page CSS ----------

INDEX_CSS = """
.container { max-width: 1100px; margin: 0 auto; position: relative; z-index: 1; padding-top: 0; }
.idx-h1 {
  font-family: var(--font-display); font-weight: 400;
  font-size: clamp(28px, 4.4vw, 42px); line-height: 1.12;
  color: var(--fg); letter-spacing: 0.4px; margin-bottom: 10px;
}
.idx-intro {
  font-size: 14px; color: var(--fg-soft); letter-spacing: 0.2px;
  margin-bottom: 44px;
}

/* ---- feature article (first / most important) ---- */
.idx-feature {
  display: grid; grid-template-columns: 1.35fr 1fr; gap: 40px;
  align-items: center; margin-bottom: 60px;
  text-decoration: none; color: inherit;
}
.idx-feature-img-wrap { position: relative; overflow: hidden; border-radius: var(--radius); }
.idx-feature-img {
  width: 100%; height: 340px; object-fit: cover; display: block;
  box-shadow: 0 14px 36px var(--sheet-shadow);
  transition: transform 0.32s cubic-bezier(0.22,1,0.36,1);
}
.idx-feature:hover .idx-feature-img { transform: scale(1.03); }
.idx-feature-body { display: flex; flex-direction: column; gap: 16px; }
.idx-feature-kicker {
  display: inline-flex; align-items: center; gap: 8px;
  background: var(--accent); color: var(--accent-ink);
  padding: 6px 14px; border-radius: 99px;
  font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 2.5px;
  text-transform: uppercase; font-weight: 700; align-self: flex-start;
}
.idx-feature-title {
  font-family: var(--font-display); font-weight: 400;
  font-size: clamp(26px, 3.2vw, 36px); line-height: 1.2;
  color: var(--fg); letter-spacing: 0.3px;
}
.idx-feature-excerpt {
  font-size: 16px; color: var(--fg-soft); line-height: 1.7;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical;
  overflow: hidden;
}
.idx-feature-meta {
  font-family: var(--font-mono); font-size: 12px; color: var(--dim);
  letter-spacing: 1px; padding-top: 4px;
}

/* ---- section label ---- */
.idx-section-label {
  display: flex; align-items: center; gap: 13px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 3px;
  color: var(--dim); text-transform: uppercase;
  margin-bottom: 22px;
}
.idx-section-label::before { content: ''; width: 22px; height: 2px; background: var(--accent); }
.idx-section-label .gt-rule { flex: 1; height: 1px; background: var(--line); margin-left: 4px; }

/* ---- 3-col grid ---- */
.idx-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
.idx-card {
  display: flex; flex-direction: column;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); overflow: hidden;
  text-decoration: none; color: inherit;
  transition: transform 0.22s cubic-bezier(0.22,1,0.36,1), border-color 0.2s ease, box-shadow 0.2s ease;
}
.idx-card:hover { transform: translateY(-4px); border-color: var(--accent-line); box-shadow: 0 14px 32px var(--sheet-shadow); }
.idx-card-img-wrap { position: relative; overflow: hidden; }
.idx-card-img { width: 100%; height: 170px; object-fit: cover; display: block; transition: transform 0.32s cubic-bezier(0.22,1,0.36,1); }
.idx-card:hover .idx-card-img { transform: scale(1.04); }
.idx-card-body { padding: 16px 18px 18px; display: flex; flex-direction: column; gap: 9px; flex: 1; }
.idx-card-kicker {
  display: inline-flex; align-items: center; gap: 7px;
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 2.5px;
  text-transform: uppercase; font-weight: 700; color: var(--accent);
  align-self: flex-start;
}
.idx-card-kicker::before { content: ''; width: 12px; height: 2px; background: var(--accent); }
.idx-card-title {
  font-size: 15.5px; font-weight: 700; color: var(--fg); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden; letter-spacing: 0.2px;
}
.idx-card-meta { font-family: var(--font-mono); font-size: 11px; color: var(--dim); margin-top: auto; padding-top: 8px; letter-spacing: 1px; }

/* ---- responsive ---- */
@media (max-width: 900px) {
  .idx-grid { grid-template-columns: repeat(2, 1fr); }
  .idx-feature { grid-template-columns: 1fr; gap: 22px; }
  .idx-feature-img { height: 260px; }
}
@media (max-width: 580px) {
  .container { padding-top: 38px; }
  .idx-grid { grid-template-columns: 1fr; }
  .idx-feature-img { height: 200px; }
  .idx-feature-title { font-size: 24px; }
}
"""


# ---------- frontmatter parser ----------

def parse_frontmatter(text: str):
    """Split YAML-ish frontmatter from markdown body. Returns (meta dict, body str)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    fm = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    meta = {}
    for line in fm.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        elif v.isdigit():
            v = int(v)
        meta[k.strip()] = v
    return meta, body


# ---------- markdown body preprocess ----------

def strip_medium_guide(body: str) -> str:
    """Strip the daily-only "Medium 貼稿指南" blockquote section + its trailing ---."""
    pattern = re.compile(r"> \*\*Medium 貼稿指南\*\*.*?(?:\n---\n)", re.DOTALL)
    return pattern.sub("", body, count=1)


def inject_inline_images(body: str) -> str:
    """Strip [📸 插入 PNG: filename] placeholders. The PNG is a Medium-only
    artifact — on this site we already render the §1/§2 markdown table /
    bullet list as HTML, which is both SEO-/GEO-indexable and visually
    cleaner. Keeping the PNG inline would duplicate the same content twice."""
    return re.sub(r"\[📸 插入 PNG: [^\]]+?\]\s*\n?", "", body)


def strip_h1(body: str) -> str:
    """Drop the first H1 (we render title via the article header)."""
    return re.sub(r"^# .*\n", "", body, count=1).lstrip("\n")


def extract_excerpt(body: str, length: int = 120) -> str:
    """Pull the first prose paragraph (skip headings, images, blockquotes,
    horizontal rules) and truncate. Strips inline markdown markers."""
    for raw in body.split("\n\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("#", "!", ">", "---", "```", "|")):
            continue
        if line.startswith(("- ", "* ", "1.")):
            continue
        # skip a bold-only standfirst / volume marker line (e.g. **... Vol. 004**)
        # — it just duplicates the subtitle and makes a useless excerpt.
        if line.startswith("**") and line.endswith("**") and line.count("**") == 2:
            continue
        # strip inline md: **bold** _em_ `code` [text](url)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"\*(.+?)\*", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = line.replace("\n", " ").strip()
        if len(line) > length:
            return line[:length].rstrip() + "…"
        return line
    return ""


def _strip_inline_md(s: str) -> str:
    """Drop inline markdown markers so schema text matches the rendered plain text."""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s.strip()


FAQ_HEADING_RE = re.compile(r"(?m)^##[ \t]+(?:常見問題|常見問答|FAQ)[ \t]*$")


def parse_faq(body: str):
    """Extract (question, answer) pairs from a '## 常見問題' section so we can emit
    FAQPage schema. The section itself stays in the body and renders as normal
    prose (h2 + h3 + p), so the schema text always matches the visible text.

    Convention: each item is a '### 問句？' heading followed by one or more
    paragraphs of answer, until the next '###' or a new '##' section / EOF.
    We NEVER synthesise FAQ text here — only mirror what the author wrote.
    """
    m = FAQ_HEADING_RE.search(body)
    if not m:
        return []
    section = body[m.end():]
    nxt = re.search(r"(?m)^##[ \t]+\S", section)  # stop at next level-2 heading
    if nxt:
        section = section[:nxt.start()]
    pairs = []
    for part in re.split(r"(?m)^###[ \t]+", section)[1:]:
        head, _, rest = part.partition("\n")
        q = _strip_inline_md(head.strip())
        a = _strip_inline_md(" ".join(
            ln.strip() for ln in rest.splitlines() if ln.strip()))
        if q and a:
            pairs.append((q, a))
    return pairs


def faq_node(pairs, page_url: str):
    """schema.org FAQPage node from (q, a) pairs, or None when empty."""
    if not pairs:
        return None
    return {
        "@type": "FAQPage",
        "@id": f"{page_url}#faq",
        "inLanguage": "zh-Hant",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in pairs
        ],
    }


# ---------- render ----------

def render_article(meta: dict, body_html: str, slug: str, excerpt: str = "",
                   prev_nav=None, next_nav=None, more_dailies=None, nav_kind="daily",
                   faq=None) -> str:
    typ = meta.get("type", "feature")
    if typ == "daily":
        vol = meta.get("vol", "?")
        kicker = f"DAILY · VOL. {int(vol):03d}" if isinstance(vol, int) else f"DAILY · VOL. {vol}"
    else:
        kicker = "FEATURE"
    title_raw = meta.get("title", slug)
    title_safe = html_lib.escape(title_raw)
    # seo_title overrides ONLY the <title> element (SERP headline / ranking
    # signal); visible H1, og/twitter title and JSON-LD headline stay on title.
    seo_title_raw = str(meta.get("seo_title", "")).strip() or title_raw
    seo_title_safe = html_lib.escape(seo_title_raw)
    subtitle_raw = meta.get("subtitle", "")
    subtitle = html_lib.escape(subtitle_raw)
    lede_raw = str(meta.get("lede", "")).strip()
    date_str = str(meta.get("date", ""))
    try:
        d = datetime.date.fromisoformat(date_str)
        date_disp = f"{d.year}/{d.month:02d}/{d.day:02d} · {WEEKDAY_ZH[d.weekday()]}"
    except Exception:
        date_disp = date_str

    # meta description: prefer the subtitle, enrich with the first paragraph when
    # thin (daily subtitles like "Vol. 00x" are too short to be useful for SEO).
    desc_raw = subtitle_raw.strip()
    if len(desc_raw) < 60 and excerpt and excerpt not in desc_raw and desc_raw not in excerpt:
        desc_raw = f"{desc_raw}　{excerpt}".strip("　 ") if desc_raw else excerpt
    if not desc_raw:
        desc_raw = excerpt or title_raw
    if lede_raw:  # purpose-written short answer beats subtitle/excerpt for description
        desc_raw = lede_raw
    desc_raw = desc_raw[:150].rstrip("　 ·，、")
    desc_safe = html_lib.escape(desc_raw)
    cover_alt = html_lib.escape(f"{title_raw}｜封面")

    # structured data: Article + breadcrumb (+ org/website context)
    # competition the article belongs to (this repo defaults to nba)
    comp = COMPETITIONS.get(meta.get("competition", "nba")) or COMPETITIONS.get("nba")
    # site identity follows the comp's sport; soccer comps -> SOCCER_SITE (base == SITE)
    # so every SITE-derived URL below stays byte-identical for existing articles.
    site = site_for(comp)
    base = site["base"]
    art_type = "NewsArticle" if typ == "daily" else "Article"
    page_url = f"{base}/articles/{slug}/"
    article_ld = {
        "@type": art_type,
        "headline": title_raw,
        "description": desc_raw,
        "image": f"{base}/articles/{slug}/cover.png",
        "inLanguage": "zh-Hant",
        "url": page_url,
        "mainEntityOfPage": page_url,
        "author": {"@id": f"{base}/#org"},
        "publisher": {"@id": f"{base}/#org"},
        "isPartOf": {"@id": f"{base}/{comp['schema_id']}"},
    }
    if date_str:
        article_ld["datePublished"] = date_str
        article_ld["dateModified"] = date_str
    crumb = breadcrumb_node([
        ("首頁", f"{base}/"),
        ("文章", f"{base}/articles/"),
        (title_raw, page_url),
    ])
    jsonld = graph_ld([org_node(site), website_node(site), competition_node(comp, site),
                       article_ld, crumb, faq_node(faq, page_url)])

    # ----- prev/next nav + 更多每日戰報 (internal linking for SEO/engagement) -----
    # daily 走「前一日/後一日戰報」(daily 連載)；feature 走「前一篇/後一篇」(feature 之間，
    # 例如 AI 圓桌三部曲)。邊界缺一側時補「所有文章」連結，不留白。
    def _dl(a):
        return (a["slug"],
                html_lib.escape(str(a["meta"].get("title", a["slug"]))),
                _date_disp(str(a["meta"].get("date", ""))))
    prev_lbl, next_lbl = ("前一篇", "後一篇") if nav_kind == "feature" else ("前一日戰報", "後一日戰報")
    FALLBACK_TITLE = "瀏覽全部戰報與文章"

    head_rels = ""
    if prev_nav:
        head_rels += f'\n<link rel="prev" href="{base}/articles/{prev_nav["slug"]}/">'
    if next_nav:
        head_rels += f'\n<link rel="next" href="{base}/articles/{next_nav["slug"]}/">'

    if prev_nav:
        s, t, dt = _dl(prev_nav)
        prev_link = (f'<a class="post-nav-link prev" href="/articles/{s}/">'
                     f'<span class="pn-dir">← {prev_lbl}</span>'
                     f'<span class="pn-title">{t}</span><span class="pn-date">{dt}</span></a>')
    else:
        prev_link = ('<a class="post-nav-link prev fallback" href="/articles/">'
                     '<span class="pn-dir">← 所有文章</span>'
                     f'<span class="pn-title">{FALLBACK_TITLE}</span></a>')
    if next_nav:
        s, t, dt = _dl(next_nav)
        next_link = (f'<a class="post-nav-link next" href="/articles/{s}/">'
                     f'<span class="pn-dir">{next_lbl} →</span>'
                     f'<span class="pn-title">{t}</span><span class="pn-date">{dt}</span></a>')
    else:
        next_link = ('<a class="post-nav-link next fallback" href="/articles/">'
                     '<span class="pn-dir">所有文章 →</span>'
                     f'<span class="pn-title">{FALLBACK_TITLE}</span></a>')

    more = more_dailies or []
    if more:
        rows = ""
        for a in more:
            s, t, dt = _dl(a)
            rows += (f'<a href="/articles/{s}/"><span class="md-date">{dt}</span>'
                     f'<span class="md-ttl">{t}</span></a>')
        more_block = ('<div class="more-dailies"><div class="md-label">更多每日戰報</div>'
                      f'<div class="md-list">{rows}</div></div>')
    else:
        more_block = ""

    series_nav = (f'<nav class="post-nav" aria-label="文章導覽">'
                  f'<div class="post-nav-pair">{prev_link}{next_link}</div>'
                  f'{more_block}</nav>')

    # ----- short-answer lede (AEO 短答；早於封面、DOM 高位) -----
    lede_html = ""
    if lede_raw:
        lede_html = ('\n    <div class="article-lede"><span class="lede-label">重點速答</span>'
                     f'<p>{html_lib.escape(lede_raw)}</p></div>')

    return f"""<!DOCTYPE html>
<html lang="zh-Hant" data-theme="{site['default_theme']}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{seo_title_safe} | {site['title_suffix']}</title>
<meta name="description" content="{desc_safe}">
<meta property="og:title" content="{title_safe}">
<meta property="og:description" content="{desc_safe}">
<meta property="og:image" content="{base}/articles/{slug}/cover.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:type" content="article">
<meta property="og:url" content="{base}/articles/{slug}/">
<meta property="og:site_name" content="{site['org_name']}">
<meta property="og:locale" content="zh_TW">
<meta property="article:published_time" content="{date_str}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title_safe}">
<meta name="twitter:description" content="{desc_safe}">
<meta name="twitter:image" content="{base}/articles/{slug}/cover.png">
<link rel="canonical" href="{base}/articles/{slug}/">{head_rels}
<link rel="alternate" type="application/rss+xml" title="{site['feed_title']}" href="{base}/feed.xml">
{jsonld}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Archivo:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap" rel="stylesheet">
{ga_snippet(site)}
<style>
{SHARED_TOKENS_CSS}{extra_theme_css(site)}
{THEME_SWITCH_CSS}
{SITE_HEADER_CSS}
{ARTICLE_CSS}
</style>
</head>
<body>
{theme_switch_html(site)}{site_header_html("articles", site) if site.get("default_theme", "grass") in BB_THEME_KEYS else ""}
<div class="container">{site_header_html("articles", site) if site.get("default_theme", "grass") not in BB_THEME_KEYS else ""}
  <article>
    <header class="article-header">
      <div class="article-kicker">{kicker}</div>
      <h1 class="article-title">{title_safe}</h1>
      <div class="article-subtitle">{subtitle}</div>
      <div class="article-meta">{date_disp}</div>
    </header>{lede_html}
    <img class="article-cover" src="cover.png" alt="{cover_alt}">
    <div class="prose{' prose--daily' if typ == 'daily' else ''}">
{body_html}
    </div>
  </article>
  {series_nav}
</div>
{site_footer_html(site)}
<script>{theme_switch_js(site)}</script>
</body>
</html>
"""


def _kicker_label(meta: dict) -> str:
    if meta.get("type") == "daily":
        vol = meta.get("vol", "?")
        return f"DAILY · VOL. {int(vol):03d}" if isinstance(vol, int) else f"DAILY · VOL. {vol}"
    return "FEATURE"


def _date_disp(date_str: str) -> str:
    try:
        d = datetime.date.fromisoformat(date_str)
        return f"{d.year}/{d.month:02d}/{d.day:02d} · {WEEKDAY_ZH[d.weekday()]}"
    except Exception:
        return date_str


def render_index(articles: list) -> str:
    if not articles:
        feature_html = ""
        grid_html = ""
    else:
        feat = articles[0]
        feat_kicker = _kicker_label(feat["meta"])
        feat_title = html_lib.escape(feat["meta"].get("title", feat["slug"]))
        feat_excerpt = html_lib.escape(feat.get("excerpt") or feat["meta"].get("subtitle", ""))
        feat_meta = _date_disp(str(feat["meta"].get("date", "")))
        feature_html = f"""
  <a class="idx-feature" href="/articles/{feat['slug']}/">
    <div class="idx-feature-img-wrap"><img class="idx-feature-img" src="/articles/{feat['slug']}/cover.png" alt="{feat_title}｜封面"></div>
    <div class="idx-feature-body">
      <span class="idx-feature-kicker">{feat_kicker}</span>
      <h2 class="idx-feature-title">{feat_title}</h2>
      <div class="idx-feature-excerpt">{feat_excerpt}</div>
      <div class="idx-feature-meta">{feat_meta}</div>
    </div>
  </a>"""

        cards = ""
        for a in articles[1:]:
            kicker = _kicker_label(a["meta"])
            title = html_lib.escape(a["meta"].get("title", a["slug"]))
            date_disp = _date_disp(str(a["meta"].get("date", "")))
            cards += f"""
      <a class="idx-card" href="/articles/{a['slug']}/">
        <div class="idx-card-img-wrap"><img class="idx-card-img" src="/articles/{a['slug']}/cover.png" alt="{title}｜封面"></div>
        <div class="idx-card-body">
          <span class="idx-card-kicker">{kicker}</span>
          <div class="idx-card-title">{title}</div>
          <div class="idx-card-meta">{date_disp}</div>
        </div>
      </a>"""

        grid_html = f"""
  <div class="idx-section-label">更多文章 <span class="gt-rule"></span></div>
  <div class="idx-grid">{cards}
  </div>""" if cards else ""

    # structured data: CollectionPage + ItemList of all articles + breadcrumb
    item_list = {
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1,
             "url": f"{SITE}/articles/{a['slug']}/",
             "name": a["meta"].get("title", a["slug"])}
            for i, a in enumerate(articles)
        ],
    }
    collection = {
        "@type": "CollectionPage",
        "@id": f"{SITE}/articles/",
        "url": f"{SITE}/articles/",
        "name": "文章 — 2026 世界盃每日戰報與焦點觀察",
        "inLanguage": "zh-Hant",
        "isPartOf": {"@id": f"{SITE}/#website"},
        "mainEntity": item_list,
    }
    idx_crumb = breadcrumb_node([("首頁", f"{SITE}/"), ("文章", f"{SITE}/articles/")])
    idx_jsonld = graph_ld([org_node(), website_node(), collection, idx_crumb])

    return f"""<!DOCTYPE html>
<html lang="zh-Hant" data-theme="grass">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>文章 — 2026 世界盃每日戰報 + 焦點觀察 | @foootball</title>
<meta name="description" content="2026 世界盃每日戰報、焦點觀察、規則解讀。台北時間，繁體中文。">
<meta property="og:title" content="文章 — @foootball 世界盃">
<meta property="og:description" content="每日戰報、規則解讀、焦點觀察。">
<meta property="og:type" content="website">
<meta property="og:url" content="https://foootball.twtools.cc/articles/">
<meta property="og:image" content="https://foootball.twtools.cc/og-home.png">
<meta property="og:image:width" content="2400">
<meta property="og:image:height" content="1260">
<meta property="og:site_name" content="@foootball">
<meta property="og:locale" content="zh_TW">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="文章 — @foootball 世界盃">
<meta name="twitter:description" content="每日戰報、規則解讀、焦點觀察。">
<meta name="twitter:image" content="https://foootball.twtools.cc/og-home.png">
<link rel="canonical" href="https://foootball.twtools.cc/articles/">
<link rel="alternate" type="application/rss+xml" title="@foootball 最新文章" href="https://foootball.twtools.cc/feed.xml">
{idx_jsonld}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Archivo:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap" rel="stylesheet">
{GA_SNIPPET}
<style>
{SHARED_TOKENS_CSS}
{THEME_SWITCH_CSS}
{SITE_HEADER_CSS}
{INDEX_CSS}
</style>
</head>
<body>
{THEME_SWITCH_HTML}
<div class="container">{site_header_html("articles")}
  <h1 class="idx-h1">文章 — 2026 世界盃每日戰報與焦點觀察</h1>
  <div class="idx-intro">每日戰報 · 焦點觀察 · 規則解讀 — 全部繁體中文 / 台北時間</div>
{feature_html}
{grid_html}
  <footer style="margin-top:56px;padding-top:26px;border-top:1px solid var(--line);">{DISCLAIMER_HTML}</footer>
</div>
<script>{THEME_SWITCH_JS}</script>
</body>
</html>
"""


# ---------- RSS feed ----------
# RFC-822 date 用固定英文縮寫（build 環境 locale 不定，不靠 strftime("%a")）。
_RFC822_DAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_RFC822_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FEED_MAX = 30  # feed 只收最近 N 篇


def _rfc822(date_str: str) -> str:
    """YYYY-MM-DD → 'Sun, 08 Jun 2026 08:00:00 +0800'（固定台北早上 8 點）。"""
    try:
        d = datetime.date.fromisoformat(date_str)
    except Exception:
        return ""
    return (f"{_RFC822_DAY[d.weekday()]}, {d.day:02d} {_RFC822_MON[d.month - 1]} "
            f"{d.year} 08:00:00 +0800")


def render_feed(articles: list, site: dict = None) -> str:
    """RSS 2.0 feed（<site>/feed.xml）。收最近 FEED_MAX 篇 daily+feature；
    description 優先用 lede（重點速答）→ excerpt → subtitle，全為已可見文字。
    site=None -> soccer（byte-identical 合約）。"""
    site = site or SOCCER_SITE
    base = site["base"]
    items = articles[:FEED_MAX]
    last_build = _rfc822(str(items[0]["meta"].get("date", ""))) if items else ""

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{site['feed_channel_title']}</title>",
        f"    <link>{base}/articles/</link>",
        f'    <atom:link href="{base}/feed.xml" rel="self" type="application/rss+xml" />',
        f"    <description>{site['feed_channel_desc']}</description>",
        "    <language>zh-Hant</language>",
    ]
    if last_build:
        lines.append(f"    <lastBuildDate>{last_build}</lastBuildDate>")
    for a in items:
        meta = a["meta"]
        url = f"{base}/articles/{a['slug']}/"
        title = html_lib.escape(str(meta.get("title", a["slug"])))
        desc_src = (str(meta.get("lede", "")).strip()
                    or a.get("excerpt") or str(meta.get("subtitle", "")))
        desc = html_lib.escape(_strip_inline_md(desc_src))
        cat = "每日戰報" if meta.get("type") == "daily" else "專題"
        pub = _rfc822(str(meta.get("date", "")))
        lines.append("    <item>")
        lines.append(f"      <title>{title}</title>")
        lines.append(f"      <link>{url}</link>")
        lines.append(f'      <guid isPermaLink="true">{url}</guid>')
        if pub:
            lines.append(f"      <pubDate>{pub}</pubDate>")
        lines.append(f"      <category>{html_lib.escape(cat)}</category>")
        lines.append(f"      <description>{desc}</description>")
        lines.append("    </item>")
    lines.append("  </channel>")
    lines.append("</rss>")
    lines.append("")
    return "\n".join(lines)


# ---------- per-sport site routing (multi-site build) ----------
# A comp's sport decides which static site it builds into. Soccer -> public/ (the existing
# foootball site, untouched / byte-identical). Non-soccer sports -> public-<sport>/ with their
# own landing + sitemap and their own base URL (baseball.twtools.cc). render_index/render_feed
# stay soccer-only so the foootball output never changes.
PUB_SOCCER = ROOT / "public"


def _comp_of(meta: dict) -> dict:
    return COMPETITIONS.get(meta.get("competition", "nba")) or COMPETITIONS["nba"]


def _sport_of(meta: dict) -> str:
    comp = _comp_of(meta)
    return (comp.get("sport") or comp.get("schema", {}).get("sport") or "soccer").lower()


def pub_root_for(meta: dict) -> pathlib.Path:
    sport = _sport_of(meta)
    return PUB_SOCCER if sport == "soccer" else ROOT / f"public-{sport}"


# Landing + article-index card CSS for non-soccer sites. Var-driven → inherits the dark navy
# tokens from extra_theme_css(navy), so the landing/list match the article & team pages exactly.
BB_LANDING_CSS = """
.bb-shell{max-width:1060px;margin:0 auto}
.bb-hero{padding:30px 2px 26px}
.bb-hero h1{font-family:var(--font-display);font-size:clamp(30px,5vw,48px);line-height:1.08;letter-spacing:.5px;color:var(--fg)}
.bb-hero p{font-size:16.5px;color:var(--fg-soft);line-height:1.75;max-width:64ch;margin-top:14px}
.bb-sec{display:flex;align-items:baseline;gap:12px;margin:36px 2px 16px}
.bb-sec h2{font-family:var(--font-mono);font-size:12px;letter-spacing:2.5px;text-transform:uppercase;color:var(--dim);font-weight:700}
.bb-sec .ln{flex:1;height:1px;background:var(--line)}
.bb-teams{display:flex;align-items:center;gap:16px;text-decoration:none;color:inherit;
  background:var(--accent-soft);border:1px solid var(--accent-line);border-radius:var(--radius-sm);
  padding:16px 22px;margin:8px 0 4px;transition:border-color .15s,transform .15s}
.bb-teams:hover{border-color:var(--accent);transform:translateY(-2px)}
.bb-teams .ic{font-size:26px}
.bb-teams .t{font-size:17px;font-weight:800;color:var(--fg)}
.bb-teams .d{font-size:12.5px;color:var(--dim);margin-top:2px}
.bb-teams .go{margin-left:auto;color:var(--accent);font-weight:800;font-size:14px}
.cov{position:relative;overflow:hidden;background:var(--surface-2)}
.cov img{display:block;width:100%;height:100%;object-fit:cover}
.card-lead{display:block;text-decoration:none;color:inherit;background:var(--surface);
  border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;margin-bottom:6px;transition:border-color .15s,transform .15s}
.card-lead:hover{border-color:var(--accent-line);transform:translateY(-2px)}
.card-lead .cov{aspect-ratio:1200/470}
.card-lead .body{padding:22px 26px}
.card-lead .kk{font-family:var(--font-mono);font-size:11px;letter-spacing:2px;color:var(--accent);font-weight:700;text-transform:uppercase}
.card-lead .tt{font-size:27px;font-weight:900;line-height:1.3;margin:9px 0;color:var(--fg)}
.card-lead .dd{font-size:14.5px;color:var(--fg-soft);line-height:1.65;max-width:62ch}
.card-lead .mm{font-size:12.5px;color:var(--faint);margin-top:12px;font-variant-numeric:tabular-nums}
.bb-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px}
.card{display:grid;grid-template-columns:165px 1fr;text-decoration:none;color:inherit;background:var(--surface);
  border:1px solid var(--line);border-radius:var(--radius-sm);overflow:hidden;transition:border-color .15s,transform .15s}
.card:hover{border-color:var(--accent-line);transform:translateY(-2px)}
.card .body{padding:15px 17px;display:flex;flex-direction:column;justify-content:center}
.card .kk{font-family:var(--font-mono);font-size:10.5px;letter-spacing:1.5px;color:var(--accent);font-weight:700;text-transform:uppercase}
.card .tt{font-size:16px;font-weight:900;line-height:1.36;margin:6px 0 0;color:var(--fg)}
.card .mm{font-size:11.5px;color:var(--faint);margin-top:9px;font-variant-numeric:tabular-nums}
.bb-faq{margin-top:14px;display:grid;gap:12px}
.bb-faq .qa{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);padding:16px 20px}
.bb-faq .faq-q{font-size:16px;font-weight:800;color:var(--fg);margin:0 0 6px;line-height:1.45}
.bb-faq .faq-a{font-size:14px;color:var(--fg-soft);line-height:1.72;margin:0}
.bb-foot{margin-top:52px;padding-top:24px;border-top:1px solid var(--line);font-size:12px;color:var(--faint);line-height:1.85}
@media(max-width:680px){.bb-grid{grid-template-columns:1fr}.card{grid-template-columns:120px 1fr}}
"""

# Dashboard-specific CSS for the baseball homepage (今日賽事 / 戰績 / 領先者 / 數據總覽).
# Var-driven (navy theme) + CSS-only tabs (radio + :checked ~ .panel) so every league's data is
# in the DOM (GEO/AEO-safe, no JS data fetch). Reuses the component vocabulary from the standings
# generators (.std-table / .lb-grid).
BB_DASH_CSS = """
.dash-asof{display:inline-flex;align-items:center;gap:8px;margin-top:16px;font-family:var(--font-mono);
  font-size:12px;color:var(--dim);border:1px solid var(--line-2);border-radius:999px;padding:6px 14px}
.dash-asof b{color:var(--accent);font-weight:700}
.bb-sec .tg{font-family:var(--font-mono);font-size:11px;color:var(--faint);letter-spacing:1px}
.tabs>input{position:absolute;opacity:0;width:0;height:0;pointer-events:none}
.tablabels{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px;border-bottom:1px solid var(--line)}
.tablabels label{cursor:pointer;padding:9px 16px;font-size:14px;font-weight:700;color:var(--dim);
  border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .15s,border-color .15s}
.tablabels label:hover{color:var(--fg)}
.tabs .panel{display:none}
.gc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(218px,1fr));gap:10px}
.gc{border:1px solid var(--line);border-radius:10px;padding:10px 14px;background:var(--surface)}
.gc-row{display:flex;justify-content:space-between;align-items:center;padding:3px 0;color:var(--fg-soft);font-size:14.5px}
.gc-row.win{color:var(--fg);font-weight:800}
.gc-row.win .gc-s{color:var(--accent)}
.gc-s{font-family:var(--font-mono);font-weight:700}
.dv-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 28px}
.div-name{font-family:var(--font-mono);font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--accent);margin:14px 0 6px}
.std-table{width:100%;border-collapse:collapse;font-size:13.5px}
.std-table th,.std-table td{padding:7px 6px;text-align:center;border-bottom:1px solid var(--line);white-space:nowrap}
.std-table th{color:var(--faint);font-size:11px;font-weight:700}
.std-table td.l,.std-table th.l{text-align:left}
.std-table td.rk{color:var(--dim);font-family:var(--font-mono)}
.std-table tr.lead td.tm{font-weight:800;color:var(--fg)}
.std-pts{color:var(--accent);font-weight:800;font-family:var(--font-mono)}
.rd-pos,.stk-pos{color:#5fb878}.rd-neg,.stk-neg{color:#d98a8a}
.lb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(248px,1fr));gap:10px 22px}
.lb-card{border:1px solid var(--line);border-radius:12px;padding:12px 14px 8px;background:var(--surface)}
.lb-card h3{font-size:14px;color:var(--accent);margin-bottom:6px;font-weight:800;letter-spacing:1px}
.lb-card table{width:100%;border-collapse:collapse}
.lb-card td{padding:4px 2px;font-size:13.5px;border-bottom:1px solid var(--line)}
.lb-card td.rk{color:var(--dim);font-family:var(--font-mono);width:20px}
.lb-card td.nm{text-align:left}
.lb-card td.tm{color:var(--faint);font-size:11px;text-align:right}
.lb-card td.vl{text-align:right;color:var(--accent);font-weight:800;font-family:var(--font-mono);width:52px}
.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.tile{display:flex;align-items:center;gap:14px;background:var(--accent-soft);border:1px solid var(--accent-line);
  border-radius:var(--radius-sm);padding:16px 20px;text-decoration:none;color:var(--fg);transition:border-color .15s,transform .15s}
.tile:hover{border-color:var(--accent);transform:translateY(-2px)}
.tile .ic{font-size:24px}
.tile .tt{font-weight:800;font-size:15px}
.tile .ds{color:var(--dim);font-size:12px;margin-top:2px;display:block}
.tile .go{margin-left:auto;color:var(--accent);font-weight:800}
.dash-note{color:var(--faint);font-size:12px;margin-top:10px;line-height:1.6}
.stale-badge{display:inline-block;font-family:var(--font-mono);font-size:11px;color:#d98a8a;
  border:1px solid #d98a8a;border-radius:6px;padding:1px 8px;margin-left:8px}
@media(max-width:680px){.dv-grid{grid-template-columns:1fr}.tiles{grid-template-columns:1fr}}
"""


def _bb_lead_card(a: dict) -> str:
    title = html_lib.escape(a["meta"].get("title", a["slug"]))
    desc = html_lib.escape(a.get("excerpt") or a["meta"].get("subtitle", ""))[:150]
    return f"""<a class="card-lead" href="/articles/{a['slug']}/">
    <div class="cov"><img src="/articles/{a['slug']}/cover.png" alt="{title}｜封面" loading="lazy"></div>
    <div class="body"><span class="kk">{_kicker_label(a['meta'])} · {_date_disp(str(a['meta'].get('date','')))}</span>
      <div class="tt">{title}</div><div class="dd">{desc}</div></div></a>"""


def _bb_grid_card(a: dict) -> str:
    title = html_lib.escape(a["meta"].get("title", a["slug"]))
    return f"""<a class="card" href="/articles/{a['slug']}/">
      <div class="cov"><img src="/articles/{a['slug']}/cover.png" alt="{title}｜封面" loading="lazy"></div>
      <div class="body"><span class="kk">{_kicker_label(a['meta'])}</span>
        <div class="tt">{title}</div><div class="mm">{_date_disp(str(a['meta'].get('date','')))}</div></div></a>"""


# Image-forward magazine cards for /articles/ — same idx-* markup as the @foootball article
# index, auto-themed navy/gold because every rule is var-driven (INDEX_CSS is injected into the
# page head via _bb_head's extra_css). Cover on top, kicker/title/meta below.
def _bb_feature_card(a: dict) -> str:
    title = html_lib.escape(a["meta"].get("title", a["slug"]))
    excerpt = html_lib.escape(a.get("excerpt") or a["meta"].get("subtitle", ""))
    return f"""
  <a class="idx-feature" href="/articles/{a['slug']}/">
    <div class="idx-feature-img-wrap"><img class="idx-feature-img" src="/articles/{a['slug']}/cover.png" alt="{title}｜封面"></div>
    <div class="idx-feature-body">
      <span class="idx-feature-kicker">{_kicker_label(a['meta'])}</span>
      <h2 class="idx-feature-title">{title}</h2>
      <div class="idx-feature-excerpt">{excerpt}</div>
      <div class="idx-feature-meta">{_date_disp(str(a['meta'].get('date','')))}</div>
    </div>
  </a>"""


def _bb_idx_card(a: dict) -> str:
    title = html_lib.escape(a["meta"].get("title", a["slug"]))
    return f"""
      <a class="idx-card" href="/articles/{a['slug']}/">
        <div class="idx-card-img-wrap"><img class="idx-card-img" src="/articles/{a['slug']}/cover.png" alt="{title}｜封面" loading="lazy"></div>
        <div class="idx-card-body">
          <span class="idx-card-kicker">{_kicker_label(a['meta'])}</span>
          <div class="idx-card-title">{title}</div>
          <div class="idx-card-meta">{_date_disp(str(a['meta'].get('date','')))}</div>
        </div>
      </a>"""


# ---------- v2 首頁 CSS（Claude Design mock 落地；header/footer/token 另在共用區） ----------
BB_HOME_CSS = """
.tnum{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1}
.wrap{max-width:1180px;margin:0 auto;padding:0 12px}
/* section label (editorial rule) */
.slabel{display:flex;align-items:center;gap:16px;margin:0 0 20px;font-family:var(--f-ui)}
.slabel .k{font-size:12px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:var(--fg);white-space:nowrap}
.slabel .k em{color:var(--accent);font-style:normal}
.slabel .rule{flex:1;height:1px;background:var(--line-2)}
.slabel .r{font-size:11px;letter-spacing:2px;color:var(--fg-dim);text-transform:uppercase;white-space:nowrap}
/* hero */
.hero{padding:64px 0 30px}
.hero h1{font-family:var(--f-text);font-weight:900;font-size:clamp(38px,6vw,72px);line-height:1.04;letter-spacing:-.5px;text-wrap:balance}
.hero h1 .en{font-family:var(--f-display);font-weight:400;color:var(--accent);letter-spacing:1px}
.hero .lead{max-width:640px;margin-top:20px;font-size:clamp(15px,1.5vw,18px);color:var(--fg-soft);text-wrap:pretty}
.status{display:flex;flex-wrap:wrap;align-items:center;gap:8px 10px;margin-top:28px;font-family:var(--f-ui);font-size:13px}
.status .seg{display:inline-flex;align-items:center;gap:7px;padding:7px 13px;background:var(--surface);border:1px solid var(--line);border-radius:999px;color:var(--fg-soft)}
.status .seg b{color:var(--fg);font-variant-numeric:tabular-nums}
.status .seg.live{border-color:color-mix(in srgb,var(--accent) 45%,transparent);color:var(--fg)}
.pdot{width:8px;height:8px;border-radius:50%;background:var(--accent)}
.pdot.pulse{box-shadow:0 0 0 0 var(--accent);animation:pulse 1.8s infinite}
@keyframes pulse{70%{box-shadow:0 0 0 7px transparent}100%{box-shadow:0 0 0 0 transparent}}
/* dashboard blocks */
.dash{display:flex;flex-direction:column;gap:56px;margin-top:26px}
.block{scroll-margin-top:90px}
.live-badge{display:inline-flex;align-items:center;gap:7px;font-family:var(--f-ui);font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--accent);padding:4px 10px;border:1px solid color-mix(in srgb,var(--accent) 40%,transparent);border-radius:999px}
/* champion cards */
.champ-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.cc{position:relative;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);padding:22px 20px 20px;overflow:hidden;transition:.18s;display:flex;flex-direction:column;min-height:150px}
.cc::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:linear-gradient(90deg,var(--accent),var(--gold))}
.cc:hover{transform:translateY(-3px);border-color:var(--line-2);background:var(--surface-2)}
.cc .eyebrow{display:flex;align-items:center;gap:8px;font-family:var(--f-ui);font-weight:700;font-size:12px;letter-spacing:1.5px;color:var(--accent);text-transform:uppercase}
.cc .eyebrow .sub{color:var(--fg-dim);font-weight:600;letter-spacing:1px}
.cc .team{font-weight:900;font-size:26px;line-height:1.1;margin-top:14px;color:var(--fg);letter-spacing:-.3px}
.cc .series{margin-top:auto;padding-top:12px;font-size:13px;color:var(--fg-mute);font-variant-numeric:tabular-nums}
.cc .seal{position:absolute;top:16px;right:16px;width:34px;height:34px;border-radius:50%;border:1.5px solid color-mix(in srgb,var(--gold) 60%,transparent);display:grid;place-items:center;font-family:var(--f-text);font-weight:900;font-size:15px;color:var(--gold)}
.cc.lead{grid-column:span 2;background:linear-gradient(150deg,var(--surface-2),var(--surface));padding:28px}
.cc.lead .team{font-size:clamp(34px,4vw,48px)}
.cc.lead .ghost{position:absolute;right:-14px;bottom:-30px;font-family:var(--f-display);font-size:150px;line-height:1;color:var(--fg);opacity:.035;pointer-events:none}
.cc.lead .runnerup{font-size:13px;color:var(--fg-mute);margin-top:6px}
/* tabs (CSS-only radio) */
.tabwrap{margin-top:2px}
.tabs input{position:absolute;opacity:0;pointer-events:none}
.tablist{display:flex;gap:4px;border-bottom:1px solid var(--line-2);overflow-x:auto;scrollbar-width:none}
.tablist::-webkit-scrollbar{display:none}
.tablist label{font-family:var(--f-ui);font-weight:600;font-size:14.5px;color:var(--fg-mute);padding:12px 18px;cursor:pointer;white-space:nowrap;border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .15s}
.tablist label:hover{color:var(--fg-soft)}
.panel{display:none;padding-top:26px}
#t-nba:checked~.tablist label[for=t-nba],
#t-tpbl:checked~.tablist label[for=t-tpbl],
#t-plg:checked~.tablist label[for=t-plg],
#t-hbl:checked~.tablist label[for=t-hbl]{color:var(--fg);border-bottom-color:var(--accent)}
#t-nba:checked~#p-nba,#t-tpbl:checked~#p-tpbl,#t-plg:checked~#p-plg,#t-hbl:checked~#p-hbl{display:block}
/* standings table */
.conf-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.conf h3{font-family:var(--f-ui);font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--fg-mute);margin-bottom:10px;font-weight:700}
.tbl-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface)}
table.std{width:100%;border-collapse:separate;border-spacing:0;font-size:14px}
table.std th,table.std td{padding:11px 12px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap;background:var(--surface)}
table.std thead th{font-family:var(--f-ui);font-weight:600;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--fg-mute);background:var(--surface-3);border-bottom:1px solid var(--line-2)}
table.std tbody tr:last-child td{border-bottom:none}
table.std .c-rank{text-align:center;width:var(--rank-w)}
table.std .c-team{text-align:left}
table.std td.c-team{font-weight:500;color:var(--fg)}
table.std tbody tr:nth-child(even) td{background:var(--zebra)}
table.std tbody tr.po td{background:var(--band-po)}
table.std tbody tr.pi td{background:var(--band-pi)}
table.std tbody tr.po td.c-rank{box-shadow:inset 3px 0 0 var(--accent)}
table.std tbody tr.pi td.c-rank{box-shadow:inset 3px 0 0 var(--gold)}
.seed{display:inline-grid;place-items:center;min-width:24px;height:24px;border-radius:7px;font-family:var(--f-ui);font-weight:700;font-size:12.5px;color:var(--fg-mute);font-variant-numeric:tabular-nums}
tr.po .seed{background:color-mix(in srgb,var(--accent) 20%,transparent);color:var(--accent-bright)}
tr.pi .seed{background:color-mix(in srgb,var(--gold) 18%,transparent);color:var(--gold)}
.win{color:var(--accent-bright);font-weight:700;font-variant-numeric:tabular-nums}
.pct{font-variant-numeric:tabular-nums;color:var(--fg-soft)}
.gb{color:var(--fg-mute);font-variant-numeric:tabular-nums}
.divider-row td{border-bottom:2px solid var(--line-2) !important}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin-top:12px;font-family:var(--f-ui);font-size:12px;color:var(--fg-mute)}
.legend span{display:inline-flex;align-items:center;gap:7px}
.legend i{width:10px;height:10px;border-radius:3px;display:inline-block}
.legend i.po{background:var(--accent)}.legend i.pi{background:var(--gold)}
.tbl-cap{font-size:12px;color:var(--fg-dim);margin-top:14px;letter-spacing:.3px}
.scroll-hint{display:none}
/* mini four-teams (HBL) */
.four-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.four{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden}
.four h4{font-family:var(--f-ui);font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--fg-mute);padding:14px 16px 10px;font-weight:700}
.four .row{display:flex;align-items:center;gap:12px;padding:12px 16px;border-top:1px solid var(--line);font-size:14px}
.four .row .pl{font-family:var(--f-ui);font-weight:700;font-size:12px;letter-spacing:1px;color:var(--fg-mute);min-width:34px}
.four .row.champ .pl{color:var(--accent)}
.four .row .nm{font-weight:500;color:var(--fg)}
.four .row.champ .nm{font-weight:700}
.four .row .note{margin-left:auto;font-size:12px;color:var(--fg-dim);font-variant-numeric:tabular-nums}
/* tiles */
.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.tile{display:flex;align-items:center;gap:18px;padding:22px 24px;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);transition:.18s;position:relative;overflow:hidden}
.tile:hover{background:var(--surface-2);border-color:color-mix(in srgb,var(--accent) 35%,transparent);transform:translateY(-2px)}
.tile .idx{font-family:var(--f-display);font-size:34px;color:var(--accent);opacity:.85;line-height:1;min-width:44px}
.tile .body h4{font-size:17px;font-weight:700;color:var(--fg)}
.tile .body p{font-size:13px;color:var(--fg-mute);margin-top:3px}
.tile .arw{margin-left:auto;font-family:var(--f-ui);font-size:20px;color:var(--fg-dim);transition:.18s}
.tile:hover .arw{color:var(--accent);transform:translateX(4px)}
/* articles */
.art-grid{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:16px}
.art{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);overflow:hidden;transition:.18s;display:flex;flex-direction:column}
.art:hover{border-color:var(--line-2);transform:translateY(-2px)}
.art .cover{aspect-ratio:16/9;background:linear-gradient(135deg,var(--surface-3),var(--surface-2));position:relative;overflow:hidden}
.art.lead .cover{aspect-ratio:16/10}
.art .cover img{width:100%;height:100%;object-fit:cover;display:block}
.art .txt{padding:16px 18px 18px;display:flex;flex-direction:column;gap:8px;flex:1}
.art .kick{font-family:var(--f-ui);font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--accent)}
.art h4{font-size:16px;font-weight:700;line-height:1.35;color:var(--fg)}
.art.lead h4{font-size:22px}
.art p{font-size:13px;color:var(--fg-mute);text-wrap:pretty}
.art .meta{margin-top:auto;font-size:11.5px;color:var(--fg-dim);font-variant-numeric:tabular-nums;letter-spacing:.3px}
/* FAQ */
.faq{display:flex;flex-direction:column;gap:10px}
.faq details{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden}
.faq details[open]{border-color:var(--line-2)}
.faq summary{list-style:none;cursor:pointer;padding:18px 20px;font-weight:700;font-size:15px;color:var(--fg);display:flex;align-items:center;gap:14px}
.faq summary::-webkit-details-marker{display:none}
.faq summary .chev{margin-left:auto;color:var(--fg-mute);transition:transform .2s;font-family:var(--f-ui);flex:none}
.faq details[open] summary .chev{transform:rotate(45deg);color:var(--accent)}
.faq .ans{padding:0 20px 18px;color:var(--fg-soft);font-size:14px;line-height:1.7;text-wrap:pretty}
section.blk{padding-top:8px}
.sp{height:56px}
/* responsive */
@media(max-width:900px){
  .champ-grid{grid-template-columns:repeat(2,1fr)}
  .cc.lead{grid-column:span 2}
  .conf-grid{grid-template-columns:1fr;gap:32px}
  .art-grid{grid-template-columns:1fr 1fr}
  .art.lead{grid-column:span 2}
}
@media(max-width:640px){
  .wrap{padding:0 2px}
  .hero{padding:40px 0 22px}
  .champ-grid{grid-template-columns:1fr;gap:12px}
  .cc.lead{grid-column:span 1}
  .cc.lead .ghost{display:none}
  .tiles{grid-template-columns:1fr}
  .art-grid{grid-template-columns:1fr}
  .art.lead{grid-column:span 1}
  .four-grid{grid-template-columns:1fr}
  .dash{gap:44px}
  table.std{min-width:520px}
  table.std th,table.std td{padding:10px 10px;font-size:13px}
  table.std .c-rank{position:sticky;left:0;z-index:3}
  table.std .c-team{position:sticky;left:var(--rank-w);z-index:3;box-shadow:8px 0 8px -8px rgba(0,0,0,.5)}
  .scroll-hint{display:flex;align-items:center;gap:6px;justify-content:flex-end;font-family:var(--f-ui);font-size:11px;color:var(--fg-dim);margin-bottom:8px;letter-spacing:.5px}
}
"""


def _bb_head(site: dict, title: str, desc: str, url: str, jsonld: str, extra_css: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-Hant" data-theme="{site['default_theme']}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_lib.escape(title)}</title>
<meta name="description" content="{html_lib.escape(desc)}">
<meta property="og:title" content="{html_lib.escape(title)}">
<meta property="og:description" content="{html_lib.escape(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{site['base']}/og-home.png">
<meta property="og:image:width" content="2400">
<meta property="og:image:height" content="1260">
<meta property="og:site_name" content="{html_lib.escape(site['org_name'])}">
<meta property="og:locale" content="zh_TW">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html_lib.escape(title)}">
<meta name="twitter:description" content="{html_lib.escape(desc)}">
<meta name="twitter:image" content="{site['base']}/og-home.png">
<meta name="theme-color" content="#14100e">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="canonical" href="{url}">
<link rel="alternate" type="application/rss+xml" title="{site['feed_title']}" href="{site['base']}/feed.xml">
{jsonld}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Archivo:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap" rel="stylesheet">
{ga_snippet(site)}
<style>
{SHARED_TOKENS_CSS}{extra_theme_css(site)}
{THEME_SWITCH_CSS}
{SITE_HEADER_CSS}
{BB_LANDING_CSS}
{BB_DASH_CSS}
{extra_css}
</style>
</head>"""


def _bb_footer(site: dict) -> str:
    """v2：dashboard／gen-* 頁共用 footer，委派 bb_footer_v2（放 container 外）。"""
    return bb_footer_v2(site)


# 首頁可見 FAQ（＝站台事實，非杜撰；同時餵 FAQPage schema 與可見問句式標題，
# 對應測評 AEO 的「FAQ 結構 / 問句式標題 / PAA 友善」三項）。問句一律以「？」收尾。
BB_HOME_FAQ = [
    ("籃球數據誌涵蓋哪些聯盟？",
     "美國職籃 NBA（30 隊）、台灣職籃兩聯盟——TPBL（台灣職業籃球大聯盟，7 隊）與 P. LEAGUE+（4 隊），以及 HBL 高中籃球甲級聯賽（男甲、女甲）。首頁提供各聯盟戰績速覽，數據頁可深入查詢。"),
    ("籃球數據誌的數據多久更新一次？",
     "目前為休賽季模式：頁面顯示 2025-26 賽季（HBL 為 114 學年度）的終局數據，並標註資料截至日期。2026 年 10 月各聯盟新賽季開打後，NBA 戰績改為每日自動更新、台灣職籃與 HBL 為每週更新；每篇文章的數字也都標註來源與截止日期。"),
    ("這個網站和 NBA、TPBL、P. LEAGUE+ 或 HBL 官方有關係嗎？",
     "沒有。籃球數據誌是獨立的繁體中文數據內容站，與 NBA、TPBL、P. LEAGUE+、HBL（中華民國高級中等學校體育總會）及各球團、學校均無任何官方關聯；所有數據整理自公開來源並於頁面標註。"),
    ("文章的數據可信嗎？要怎麼查證？",
     "每篇深度文以結構化事實（facts pack）為基礎撰寫，數字逐筆對照公開來源，並經獨立第二來源交叉核對後才發佈。文中關鍵數據附截止日期與來源說明，方便讀者自行查證。"),
    ("為什麼看籃球數據誌，而不是直接查比分？",
     "即時比分各家都有；籃球數據誌專注「看門道」——用戰績結構、賽制脈絡與長期數據把數字背後的故事說清楚，並把 NBA、台灣職籃與 HBL 放在同一個座標系裡看，為深度理解而非即時速報而寫。"),
]


def _bb_faq_html() -> str:
    qa = "\n".join(
        f'    <div class="qa"><h3 class="faq-q">{html_lib.escape(q)}</h3>'
        f'<p class="faq-a">{html_lib.escape(a)}</p></div>'
        for q, a in BB_HOME_FAQ)
    return ('<div class="bb-sec"><h2>常見問題</h2><span class="ln"></span></div>\n'
            f'  <section class="bb-faq">\n{qa}\n  </section>')


# ---------- baseball homepage dashboard ----------

def _dash_norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.casefold().strip()


_DASH_TEAM_ZH = None


def _dash_zh(name):
    """team-zh.json fuzzy lookup (NFKD + casefold), mirrors build-standings._norm_name."""
    global _DASH_TEAM_ZH
    if _DASH_TEAM_ZH is None:
        p = ROOT / "scripts" / "team-zh.json"
        raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        _DASH_TEAM_ZH = {_dash_norm(k): v for k, v in raw.items() if not k.startswith("_")}
    return _DASH_TEAM_ZH.get(_dash_norm(name), name)


def _dash_latest(pattern):
    files = sorted(glob.glob(str(ROOT / "leagues" / pattern)))
    return json.loads(pathlib.Path(files[-1]).read_text(encoding="utf-8")) if files else None


def _dash_json(name):
    p = ROOT / "leagues" / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _dash_slate_from_games(games):
    """api-baseball games[] -> (latest_date, [{away,home,ar,hr}]) for finished games only."""
    scored = [g for g in (games or []) if "home_score" in g and "away_score" in g]
    if not scored:
        return "", []
    scored.sort(key=lambda g: g.get("date", ""))
    latest = scored[-1]["date"]
    return latest, [{"away": g["away_name"], "home": g["home_name"],
                     "ar": g["away_score"], "hr": g["home_score"]}
                    for g in scored if g["date"] == latest]


_CAT_ZH_DASH = {"homeRuns": "全壘打", "runsBattedIn": "打點", "battingAverage": "打擊率",
                "stolenBases": "盜壘", "onBasePlusSlugging": "OPS", "hits": "安打",
                "earnedRunAverage": "防禦率", "strikeouts": "三振", "wins": "勝投", "saves": "救援"}


def _dash_game_cards(games, zh=True):
    def card(a, h, ar, hr):
        az = _dash_zh(a) if zh else a
        hz = _dash_zh(h) if zh else h
        aw = "win" if (ar is not None and hr is not None and ar > hr) else ""
        hw = "win" if (ar is not None and hr is not None and hr > ar) else ""
        return (f'<div class="gc"><div class="gc-row {aw}"><span>{html_lib.escape(az)}</span>'
                f'<span class="gc-s">{ar if ar is not None else "–"}</span></div>'
                f'<div class="gc-row {hw}"><span>{html_lib.escape(hz)}</span>'
                f'<span class="gc-s">{hr if hr is not None else "–"}</span></div></div>')
    cells = "".join(card(g["away"], g["home"], g["ar"], g["hr"]) for g in games[:12])
    return f'<div class="gc-grid">{cells}</div>'


def _dash_nba_conferences(standings):
    """NBA 東／西區兩張表（fetch-nba.py 產物：conference/rank/name_zh/wins/losses/pct/games_back）。"""
    order = [("Eastern", "東區"), ("Western", "西區")]
    by = {}
    for t in standings:
        by.setdefault(t.get("conference", ""), []).append(t)
    blocks = []
    for key, zh in order:
        rows = sorted(by.get(key, []), key=lambda r: int(r["rank"]))
        if not rows:
            continue
        trs = ""
        for r in rows:
            lead = ' class="lead"' if str(r["rank"]) == "1" else ""
            nm = r.get("name_zh") or r.get("name", "")
            pct = str(r.get("pct", "")).lstrip("0") or "0"
            trs += (f'<tr{lead}><td class="rk">{r["rank"]}</td>'
                    f'<td class="l tm">{html_lib.escape(nm)}</td>'
                    f'<td class="std-pts">{r["wins"]}</td><td>{r["losses"]}</td>'
                    f'<td>{pct}</td><td>{r.get("games_back", "—")}</td></tr>')
        blocks.append(f'<div class="dv"><div class="div-name">{zh}</div>'
                      f'<table class="std-table"><thead><tr><th>#</th><th class="l">球隊</th>'
                      f'<th>勝</th><th>敗</th><th>勝率</th><th>勝差</th></tr></thead>'
                      f'<tbody>{trs}</tbody></table></div>')
    return f'<div class="dv-grid">{"".join(blocks)}</div>'


def _dash_simple_standings(rows):
    trs = ""
    for r in rows:
        lead = ' class="lead"' if r.get("rank") == 1 else ""
        nm = _dash_zh(r.get("team_name", ""))
        pct = str(r.get("pct", "")).lstrip("0") or "0"
        trs += (f'<tr{lead}><td class="rk">{r.get("rank")}</td>'
                f'<td class="l tm">{html_lib.escape(nm)}</td>'
                f'<td class="std-pts">{r.get("win")}</td><td>{r.get("lose")}</td>'
                f'<td>{pct}</td><td>{r.get("games_behind")}</td></tr>')
    return ('<table class="std-table"><thead><tr><th>#</th><th class="l">球隊</th><th>勝</th>'
            f'<th>敗</th><th>勝率</th><th>勝差</th></tr></thead><tbody>{trs}</tbody></table>')


def _dash_hbl_division(div):
    """HBL 甲級單一組別（男甲／女甲）→ 四強最終名次表＋冠軍戰註記。div 來自 fetch-hbl.py：
    {label, champion, final_note, final_four:[{rank, school, note}]}。"""
    trs = ""
    for r in div.get("final_four", []):
        lead = ' class="lead"' if r.get("rank") == 1 else ""
        trs += (f'<tr{lead}><td class="rk">{r.get("rank")}</td>'
                f'<td class="l tm">{html_lib.escape(r.get("school", ""))}</td>'
                f'<td class="l">{html_lib.escape(r.get("note", ""))}</td></tr>')
    cap = html_lib.escape(div.get("final_note", ""))
    return (f'<div class="dv"><div class="div-name">{html_lib.escape(div.get("label", ""))}</div>'
            '<table class="std-table"><thead><tr><th>#</th><th class="l">學校</th>'
            f'<th class="l">附註</th></tr></thead><tbody>{trs}</tbody></table>'
            + (f'<div class="dash-note">{cap}</div>' if cap else "") + '</div>')


def _dash_champions(cards):
    """cards = [(聯盟標籤, 冠軍隊, 附註)] → 冠軍卡列（復用 .lb-card 詞彙）。"""
    cells = "".join(
        f'<div class="lb-card"><h3>{html_lib.escape(lg)}</h3>'
        f'<div style="font-size:18px;font-weight:900;color:var(--fg);margin:2px 0 4px">{html_lib.escape(ch)}</div>'
        f'<div style="font-size:12.5px;color:var(--dim);line-height:1.6">{html_lib.escape(note)}</div></div>'
        for lg, ch, note in cards if ch)
    return f'<div class="lb-grid">{cells}</div>'


def _dash_tabgroup(group, tabs):
    """tabs = [(id, label, body_html, note_html_or_empty)]; first is the default-checked panel.
    Emits CSS-only tabs (radio + general-sibling :checked) — all panels are in the DOM (GEO-safe)."""
    inputs = "".join(
        f'<input type="radio" name="{group}" id="{group}-{tid}"{" checked" if i == 0 else ""}>'
        for i, (tid, _, _, _) in enumerate(tabs))
    labels = "".join(f'<label for="{group}-{tid}">{lbl}</label>' for tid, lbl, _, _ in tabs)
    rules = "".join(
        f'#{group}-{tid}:checked~.tablabels label[for="{group}-{tid}"]'
        '{color:var(--accent);border-bottom-color:var(--accent)}'
        f'#{group}-{tid}:checked~.panel-{group}-{tid}{{display:block}}'
        for tid, _, _, _ in tabs)
    panels = "".join(
        f'<div class="panel panel-{group}-{tid}">{body}'
        f'{("<div class=" + chr(34) + "dash-note" + chr(34) + ">" + note + "</div>") if note else ""}</div>'
        for tid, _, body, note in tabs)
    return f'<style>{rules}</style><div class="tabs">{inputs}<div class="tablabels">{labels}</div>{panels}</div>'


def _dash_build_date(*objs):
    cands = []
    for o in objs:
        if not o:
            continue
        for k in ("asof", "asof_taipei_date", "date"):
            if o.get(k):
                cands.append(str(o[k]))
    return max(cands) if cands else ""


def _cjk_count(html_text: str) -> int:
    """body_html 純 CJK 字數（文章卡 meta 用）。"""
    text = re.sub(r"<[^>]+>", "", html_text or "")
    return len([c for c in text if "一" <= c <= "鿿"])


def _std_table_v2(rows, key_map, po_max=0, pi_max=0, abbr_key=None):
    """v2 戰績表（mock .std）：斑馬紋＋（可選）季後賽/附加賽分帶＋seed 晶片＋手機釘欄。
    rows 依 key_map 取值：key_map=(rank, team, win, lose, pct, gb) 的欄位名 tuple。
    po_max/pi_max=0 表示不畫分帶（TPBL/PLG 晉級門檻未驗證，不標）；
    abbr_key 給了就多一欄縮寫（/standings/ 桌機版用）。"""
    rk, tk, wk, lk, pk, gk = key_map
    trs = ""
    n = len(rows)
    for r in rows:
        rank = int(r.get(rk) or 0)
        cls = []
        if po_max and rank <= po_max:
            cls.append("po")
        elif pi_max and rank <= pi_max:
            cls.append("pi")
        if (po_max and rank == po_max and n > po_max) or (pi_max and rank == pi_max and n > pi_max):
            cls.append("divider-row")
        cls_attr = f' class="{" ".join(cls)}"' if cls else ""
        team = r.get(tk) or r.get("name") or ""
        pct = str(r.get(pk, "")).lstrip("0") or "0"
        gb = html_lib.escape(str(r.get(gk, "—")))
        abbr_td = (f'<td class="c-abbr"><span class="abbr">{html_lib.escape(str(r.get(abbr_key, "")))}</span></td>'
                   if abbr_key else "")
        trs += (f'<tr{cls_attr}><td class="c-rank"><span class="seed">{rank}</span></td>'
                f'<td class="c-team">{html_lib.escape(team)}</td>{abbr_td}'
                f'<td class="win">{r.get(wk)}</td><td>{r.get(lk)}</td>'
                f'<td class="pct">{pct}</td><td class="gb">{gb}</td></tr>')
    abbr_th = '<th class="c-abbr">縮寫</th>' if abbr_key else ""
    return ('<div class="tbl-scroll"><table class="std">'
            f'<thead><tr><th class="c-rank">#</th><th class="c-team">球隊</th>{abbr_th}'
            '<th>勝</th><th>敗</th><th>勝率</th><th>勝差</th></tr></thead>'
            f'<tbody>{trs}</tbody></table></div>')


# ---------- v2 內頁共用（/standings/ /tw/ /hbl/：page-hero＋champ-band＋FAQ details） ----------
BB_PAGE_EXTRA_CSS = """
.page-hero{padding:52px 0 30px}
.page-hero h1{font-family:var(--f-text);font-weight:900;font-size:clamp(30px,4.5vw,50px);line-height:1.08;letter-spacing:-.5px}
.page-hero h1 .en{font-family:var(--f-display);font-weight:400;color:var(--accent);letter-spacing:1px}
.page-hero .sub{margin-top:14px;color:var(--fg-soft);font-size:clamp(14px,1.4vw,16px);max-width:640px;text-wrap:pretty}
.champ-band{display:flex;align-items:center;gap:20px;background:linear-gradient(120deg,var(--surface-2),var(--surface));border:1px solid color-mix(in srgb,var(--gold) 32%,transparent);border-radius:var(--r-lg);padding:22px 26px;position:relative;overflow:hidden;margin-bottom:30px}
.champ-band::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:linear-gradient(90deg,var(--accent),var(--gold))}
.champ-band .bseal{flex:none;width:56px;height:56px;border-radius:50%;border:2px solid color-mix(in srgb,var(--gold) 55%,transparent);display:grid;place-items:center;font-weight:900;font-size:24px;color:var(--gold)}
.champ-band .bt .lbl{font-family:var(--f-ui);font-weight:700;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--accent)}
.champ-band .bt .nm{font-weight:900;font-size:clamp(22px,3vw,30px);line-height:1.1;margin:4px 0 5px;color:var(--fg)}
.champ-band .bt .sr{font-size:13.5px;color:var(--fg-mute);font-variant-numeric:tabular-nums}
table.std .c-abbr{text-align:center}
.abbr{font-family:ui-monospace,"SF Mono",monospace;font-size:11.5px;color:var(--fg-dim);letter-spacing:.5px}
@media(max-width:640px){table.std .c-abbr{display:none}}
"""


def bb_slabel(k_html: str, r_text: str) -> str:
    """v2 節標（editorial rule）。k_html 可含 <em>。"""
    return (f'<div class="slabel"><span class="k">{k_html}</span><span class="rule"></span>'
            f'<span class="r">{html_lib.escape(r_text)}</span></div>')


def bb_faq_details_html(pairs) -> str:
    """v2 FAQ（details 折疊；內容全在 DOM，faq_node schema 照舊鏡射同一組 pairs）。"""
    items = "".join(
        f'<details{" open" if i == 0 else ""}><summary>{html_lib.escape(q)}<span class="chev">＋</span></summary>'
        f'<div class="ans">{html_lib.escape(a)}</div></details>'
        for i, (q, a) in enumerate(pairs))
    return ('<section class="blk"><div class="sp"></div>'
            + bb_slabel('常見 <em>問題</em>', 'FAQ')
            + f'<div class="faq">{items}</div></section>')


_SCROLL_HINT = '<div class="scroll-hint">← 左右滑動看完整欄位 →</div>'


def _hbl_four_html(div):
    """HBL 四強卡（mock .four）。div = fetch-hbl divisions[boys|girls]。"""
    rank_zh = {1: "冠軍", 2: "亞軍", 3: "季軍", 4: "殿軍"}
    rows = ""
    for r in div.get("final_four", []):
        champ = ' champ' if r.get("rank") == 1 else ""
        note = r.get("note", "")
        note_html = f'<span class="note">{html_lib.escape(note)}</span>' if note else ""
        rows += (f'<div class="row{champ}"><span class="pl">{rank_zh.get(r.get("rank"), r.get("rank"))}</span>'
                 f'<span class="nm">{html_lib.escape(r.get("school", ""))}</span>{note_html}</div>')
    return (f'<div class="four"><h4>{html_lib.escape(div.get("label", ""))} · 四強</h4>{rows}</div>')


def render_sport_index(articles: list, site: dict, sport_label: str) -> str:
    """v2 首頁 dashboard（Claude Design mock 2026-07-19 落地，保留 controller 套皮）：
    hero＋status segs → 冠軍卡列（休賽季門面／開季後收合）→ 戰績速覽 CSS-only tabs
    （NBA 分帶＋seed 晶片＋手機釘欄）→ 編號 tiles → 文章 art-grid（真封面）→ details FAQ。
    全部 server-rendered 自 leagues/*.json；mock 的「phase toggle」改為 build-time
    offseason 旗標決定版序；mock 占位數據一律不用（資料層走真快照）。"""
    base = site["base"]
    # ----- data -----
    nba = _dash_latest("nba-standings-*.json")
    tw = _dash_latest("tw-hoops-*.json")
    hbl = _dash_latest("hbl-[0-9]*.json")  # 排除 hbl-history.json
    tw_lg = (tw or {}).get("leagues", {})
    tpbl, plg = tw_lg.get("tpbl"), tw_lg.get("plg")
    build_date = _dash_build_date(nba, tw, hbl)
    offseason = bool((nba or {}).get("final"))
    season_tag = (nba or {}).get("season") or (tw or {}).get("season") or ""

    # ----- 冠軍卡列 -----
    cards = []
    if nba and nba.get("champion_zh"):
        if offseason:
            cards.append(
                '<article class="cc lead"><span class="ghost">01</span>'
                '<div class="eyebrow">NBA <span class="sub">TOTAL CHAMPION</span></div>'
                f'<div class="team">{html_lib.escape(nba["champion_zh"])}</div>'
                f'<div class="runnerup">{html_lib.escape(nba.get("finals_note", ""))}</div>'
                f'<div class="series">{html_lib.escape(nba.get("champion_en", ""))} · {season_tag} champion</div>'
                '<div class="seal">冠</div></article>')
        else:
            cards.append(
                '<article class="cc"><div class="eyebrow">NBA</div>'
                f'<div class="team">{html_lib.escape(nba["champion_zh"])}</div>'
                f'<div class="series">{html_lib.escape(nba.get("finals_note", ""))}</div>'
                '<div class="seal">冠</div></article>')
    if tpbl and tpbl.get("champion_zh"):
        cards.append('<article class="cc"><div class="eyebrow">TPBL</div>'
                     f'<div class="team">{html_lib.escape(tpbl["champion_zh"])}</div>'
                     f'<div class="series">{html_lib.escape(tpbl.get("finals_note", ""))}</div>'
                     '<div class="seal">冠</div></article>')
    if plg and plg.get("champion_zh"):
        cards.append('<article class="cc"><div class="eyebrow">PLG</div>'
                     f'<div class="team">{html_lib.escape(plg["champion_zh"])}</div>'
                     f'<div class="series">{html_lib.escape(plg.get("finals_note", ""))}</div>'
                     '<div class="seal">冠</div></article>')
    for k, lbl in (("boys", "男甲"), ("girls", "女甲")):
        d = ((hbl or {}).get("divisions", {}) or {}).get(k) or {}
        if d.get("champion"):
            cards.append(f'<article class="cc"><div class="eyebrow">HBL <span class="sub">{lbl}</span></div>'
                         f'<div class="team">{html_lib.escape(d["champion"])}</div>'
                         f'<div class="series">{html_lib.escape(d.get("final_note", ""))}</div>'
                         '<div class="seal">冠</div></article>')
    champ_label = (f'{season_tag} <em>冠軍</em>' if offseason else '上季 <em>冠軍</em> 回顧')
    champ_sec = ""
    if cards:
        champ_sec = (f'<section class="block" id="champ"><div class="slabel">'
                     f'<span class="k">{champ_label}</span><span class="rule"></span>'
                     '<span class="r">賽季終局</span></div>'
                     f'<div class="champ-grid">{"".join(cards)}</div></section>')

    # ----- 戰績速覽 tabs -----
    tabs = []  # (id, label, panel_html)
    if nba and nba.get("standings"):
        east = sorted([r for r in nba["standings"] if r["conference"] == "Eastern"], key=lambda r: r["rank"])
        west = sorted([r for r in nba["standings"] if r["conference"] == "Western"], key=lambda r: r["rank"])
        km = ("rank", "name_zh", "wins", "losses", "pct", "games_back")
        nba_panel = (
            '<div class="conf-grid">'
            f'<div class="conf"><h3>東區 Eastern</h3>{_SCROLL_HINT}{_std_table_v2(east, km, po_max=6, pi_max=10)}</div>'
            f'<div class="conf"><h3>西區 Western</h3>{_SCROLL_HINT}{_std_table_v2(west, km, po_max=6, pi_max=10)}</div>'
            '</div>'
            '<div class="legend"><span><i class="po"></i>直接晉級季後賽（第 1–6 名）</span>'
            '<span><i class="pi"></i>附加賽區（第 7–10 名）</span></div>'
            f'<div class="tbl-cap">{season_tag} 例行賽終局名次 · 截至 {nba.get("asof", "")} · '
            f'整理自 ESPN 公開資料。<a href="/standings/">看完整東西區排名 →</a></div>')
        tabs.append(("nba", "NBA 東西區", nba_panel))
    km_tw = ("rank", "team_name", "win", "lose", "pct", "games_behind")
    if tpbl and tpbl.get("standings"):
        tabs.append(("tpbl", "TPBL",
                     f'{_SCROLL_HINT}{_std_table_v2(tpbl["standings"], km_tw)}'
                     f'<div class="tbl-cap">{tw.get("season", "")} 例行賽終局 · 快照 {tw.get("asof_taipei_date", "")} · '
                     f'整理自 TPBL 官網公開資料。<a href="/tw/">看兩聯盟對照 →</a></div>'))
    if plg and plg.get("standings"):
        tabs.append(("plg", "PLG",
                     f'{_SCROLL_HINT}{_std_table_v2(plg["standings"], km_tw)}'
                     f'<div class="tbl-cap">{tw.get("season", "")} 例行賽終局 · 快照 {tw.get("asof_taipei_date", "")} · '
                     f'整理自 PLG 官網公開資料。<a href="/tw/">看兩聯盟對照 →</a></div>'))
    if hbl and hbl.get("divisions"):
        dvs = hbl["divisions"]
        four = "".join(_hbl_four_html(dvs[k]) for k in ("boys", "girls") if dvs.get(k))
        tabs.append(("hbl", "HBL 甲級",
                     f'<div class="four-grid">{four}</div>'
                     f'<div class="tbl-cap">{hbl.get("season_label", "")}總決賽最終名次 · '
                     f'整理自 HBL 官網公開賽果。<a href="/hbl/">看歷屆冠軍 →</a></div>'))
    stand_sec = ""
    if tabs:
        inputs = "".join(f'<input type="radio" name="lg" id="t-{tid}"{" checked" if i == 0 else ""}>'
                         for i, (tid, _l, _p) in enumerate(tabs))
        labels = "".join(f'<label for="t-{tid}">{lbl}</label>' for tid, lbl, _p in tabs)
        panels = "".join(f'<div class="panel" id="p-{tid}">{p}</div>' for tid, _l, p in tabs)
        live_badge = ('' if offseason else
                      '<span class="live-badge"><span class="pdot pulse"></span>進行中</span>')
        stand_sec = ('<section class="block" id="standings"><div class="slabel">'
                     f'<span class="k">戰績 <em>速覽</em></span>{live_badge}<span class="rule"></span>'
                     '<span class="r">排名 / 名次</span></div>'
                     f'<div class="tabwrap tabs">{inputs}<div class="tablist">{labels}</div>{panels}</div>'
                     '</section>')

    dash_blocks = (champ_sec + stand_sec) if offseason else (stand_sec + champ_sec)

    # ----- tiles -----
    tiles = ('<section class="blk"><div class="sp"></div>'
             '<div class="slabel"><span class="k">數據 <em>總覽</em></span><span class="rule"></span>'
             '<span class="r">深入查詢</span></div>'
             '<div class="tiles">'
             '<a class="tile" href="/standings/"><span class="idx">01</span><div class="body">'
             f'<h4>NBA 戰績</h4><p>東西區完整排名 · {season_tag} 賽季</p></div><span class="arw">→</span></a>'
             '<a class="tile" href="/tw/"><span class="idx">02</span><div class="body">'
             '<h4>台灣職籃</h4><p>TPBL · PLG 兩聯盟戰績對照</p></div><span class="arw">→</span></a>'
             '<a class="tile" href="/hbl/"><span class="idx">03</span><div class="body">'
             '<h4>HBL 高中籃球</h4><p>男甲 · 女甲 四強與歷屆冠軍</p></div><span class="arw">→</span></a>'
             '<a class="tile" href="/data/"><span class="idx">04</span><div class="body">'
             '<h4>數據總覽</h4><p>所有數據頁入口</p></div><span class="arw">→</span></a>'
             '</div></section>')

    # ----- 最新文章（真封面 art-grid）-----
    art_sec = ""
    if articles:
        def art_card(a, lead=False):
            title = html_lib.escape(a["meta"].get("title", a["slug"]))
            excerpt = html_lib.escape((a.get("excerpt") or a["meta"].get("subtitle", ""))[:80])
            wc = _cjk_count(a.get("body_html", ""))
            meta = _date_disp(str(a["meta"].get("date", "")))
            if wc:
                meta += f" · {wc:,} 字"
            cls = "art lead" if lead else "art"
            desc = f'<p>{excerpt}</p>' if lead and excerpt else ""
            return (f'<a class="{cls}" href="/articles/{a["slug"]}/">'
                    f'<div class="cover"><img src="/articles/{a["slug"]}/cover.png" alt="{title}｜封面" loading="lazy"></div>'
                    f'<div class="txt"><span class="kick">{_kicker_label(a["meta"])}</span>'
                    f'<h4>{title}</h4>{desc}<div class="meta">{meta}</div></div></a>')
        cards_html = art_card(articles[0], lead=True) + "".join(art_card(a) for a in articles[1:5])
        art_sec = ('<section class="blk"><div class="sp"></div>'
                   '<div class="slabel"><span class="k">最新 <em>文章</em></span><span class="rule"></span>'
                   '<a class="r" href="/articles/" style="text-decoration:none">全部文章 →</a></div>'
                   f'<div class="art-grid">{cards_html}</div></section>')

    # ----- FAQ（details 折疊；內容全在 DOM，schema 照舊鏡射）-----
    faq_items = "".join(
        f'<details{" open" if i == 0 else ""}><summary>{html_lib.escape(q)}<span class="chev">＋</span></summary>'
        f'<div class="ans">{html_lib.escape(a)}</div></details>'
        for i, (q, a) in enumerate(BB_HOME_FAQ))
    faq_sec = ('<section class="blk"><div class="sp"></div>'
               '<div class="slabel"><span class="k">常見 <em>問題</em></span><span class="rule"></span>'
               '<span class="r">FAQ</span></div>'
               f'<div class="faq">{faq_items}</div></section>')

    # ----- hero status -----
    mode_seg = ('<span class="seg">休賽季模式 · 顯示 ' + season_tag + ' 終局數據</span>' if offseason else
                '<span class="seg live"><span class="pdot pulse"></span>開季中 · 每日自動更新</span>')
    asof_seg = (f'<span class="seg"><span class="pdot"></span>資料截至 <b>{build_date}</b></span>'
                if build_date else "")

    # ----- JSON-LD -----
    item_list = {"@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": f"{base}/articles/{a['slug']}/",
         "name": a["meta"].get("title", a["slug"])} for i, a in enumerate(articles)]}
    collection = {"@type": "CollectionPage", "@id": f"{base}/", "url": f"{base}/",
                  "name": site["website_name"], "inLanguage": "zh-Hant",
                  "isPartOf": {"@id": f"{base}/#website"}, "mainEntity": item_list}
    jsonld = graph_ld([org_node(site), website_node(site), collection,
                       breadcrumb_node([("首頁", f"{base}/")]),
                       faq_node(BB_HOME_FAQ, f"{base}/")])
    desc = "NBA × 台灣職籃（TPBL／PLG）× HBL 高中籃球的戰績與數據儀表板：東西區排名、台灣職籃戰績、HBL 四強與冠軍，以及數據導向的深度特刊。繁體中文 / 台北時間。"
    return f"""{_bb_head(site, site['website_name'], desc, f"{base}/", jsonld, extra_css=BB_HOME_CSS)}
<body>
{site_header_html("home", site)}
<main class="wrap">
  <section class="hero">
    <h1><span class="en">NBA</span> × 台灣籃球，<br>用數據看門道。</h1>
    <p class="lead">美國職籃 NBA × 台灣職籃 TPBL／PLG × HBL 高中籃球 —— 戰績、名次與冠軍脈絡，一頁掌握。深度特刊在「文章」。</p>
    <div class="status">
      {asof_seg}
      {mode_seg}
      <span class="seg">整理自公開來源</span>
    </div>
  </section>
  <div class="dash">
  {dash_blocks}
  </div>
  {tiles}
  {art_sec}
  {faq_sec}
</main>
{bb_footer_v2(site)}
<script>{theme_switch_js(site)}</script>
</body>
</html>
"""


def render_sport_articles_index(articles: list, site: dict, sport_label: str) -> str:
    """The real /articles/ index (distinct from home — no teams hero, article-focused list).
    Fixes the earlier hole where /articles/ was a byte-identical clone of the homepage."""
    base = site["base"]
    feature = _bb_feature_card(articles[0]) if articles else ""
    cards = "".join(_bb_idx_card(a) for a in articles[1:])
    grid_block = (f"""
  <div class="idx-section-label">更多文章 <span class="gt-rule"></span></div>
  <div class="idx-grid">{cards}
  </div>""" if cards else "")
    item_list = {"@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": f"{base}/articles/{a['slug']}/",
         "name": a["meta"].get("title", a["slug"])} for i, a in enumerate(articles)]}
    coll = {"@type": "CollectionPage", "@id": f"{base}/articles/", "url": f"{base}/articles/",
            "name": f"{site['org_name']} 深度文章", "inLanguage": "zh-Hant",
            "isPartOf": {"@id": f"{base}/#website"}, "mainEntity": item_list}
    jsonld = graph_ld([org_node(site), website_node(site), coll,
                       breadcrumb_node([("首頁", f"{base}/"), ("文章", f"{base}/articles/")])])
    return f"""{_bb_head(site, f"深度文章 ｜ {site['org_name']}", f"NBA 與台灣籃球（TPBL／PLG／HBL）的數據深度分析、聯盟指南與專題特刊，共 {len(articles)} 篇。", f"{base}/articles/", jsonld, extra_css=INDEX_CSS)}
<body>
{site_header_html("articles", site)}
<div class="bb-shell">
  <main>
  <h1 class="idx-h1">深度文章 — NBA 與台灣籃球</h1>
  <div class="idx-intro">數據深度分析 · 聯盟指南 · 專題特刊 — 每篇附數據表格、每個數字標註來源與截止日期 · 共 {len(articles)} 篇、最新在前</div>
{feature}{grid_block}
  </main>
</div>
{_bb_footer(site)}
<script>{theme_switch_js(site)}</script>
</body>
</html>
"""


def render_sport_sitemap(articles: list, site: dict) -> str:
    base = site["base"]
    urls = [f"{base}/", f"{base}/articles/"] + [f"{base}/articles/{a['slug']}/" for a in articles]
    body = "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}</urlset>\n")


def render_bb_llms_txt(articles: list, site: dict) -> str:
    """llms.txt for basketball — build-time generated so the article list never goes stale
    (a hand-written static file is a staleness bomb; this regenerates on every daily build).
    Site facts up top are what AI answer engines quote — keep them honest and dated."""
    base = site["base"]
    art_lines = "\n".join(
        f"- [{a['meta'].get('title', a['slug'])}]({base}/articles/{a['slug']}/)"
        + (f"（{a['meta']['date']}）" if a["meta"].get("date") else "")
        for a in articles[:10])
    return f"""# 籃球數據誌（basketball.twtools.cc）— NBA・台灣職籃・HBL 戰績與數據

> 非官方的繁體中文籃球數據與內容站。提供美國職籃 NBA、台灣職籃兩聯盟（TPBL／P. LEAGUE+）與 HBL 高中籃球甲級聯賽的戰績儀表板（排名、名次、冠軍脈絡），以及數據導向的深度特刊文章。內容以繁體中文撰寫、台北時間標示，面向台灣球迷。

本站為獨立經營的資訊站，與 NBA、TPBL、P. LEAGUE+、HBL（中華民國高級中等學校體育總會）及各球團、學校均無任何官方關係，不使用官方標誌，非商業性質。數據整理自公開來源並逐頁標註（NBA 整理自 ESPN 公開資料；台灣職籃整理自 TPBL／PLG 官網；HBL 整理自 hbl.com.tw），頁面標注資料截至日期；休賽季顯示 2025-26 賽季（HBL 為 114 學年度）終局數據，開季後恢復自動更新。

## 重點頁面

- [籃球數據儀表板（首頁）]({base}/)：NBA 東西區排名、台灣職籃戰績、HBL 四強與各聯盟冠軍，一頁掌握。
- [NBA 戰績]({base}/standings/)：東西區完整排名（2025-26 賽季）。
- [台灣職籃戰績]({base}/tw/)：TPBL 與 P. LEAGUE+ 兩聯盟戰績與冠軍。
- [HBL 高中籃球]({base}/hbl/)：男甲、女甲四強最終名次與冠軍戰。
- [數據總覽]({base}/data/)：所有數據頁入口。
- [文章總覽]({base}/articles/)：深度特刊列表——以可查證數據為底的長文分析，每篇附統計表格。

## 最新文章

{art_lines}

## 文章與更新

- [RSS feed]({base}/feed.xml)：最新深度特刊。
- 深度特刊：數據導向長文，所有數字對照公開來源查證後發布，附截止日期。

## 使用說明

- 引用本站資料時，請註明資料為非官方整理、並以各聯盟官方公告為準。
- 內容僅供資訊參考；時間以台北時間（UTC+8）標示。
"""


def _build_sport_site(articles: list, sport: str):
    """Render a non-soccer site's landing + sitemap. Articles already rendered to their out_dir
    by build(). `articles` here are that sport's articles, newest-first."""
    site = SITES.get(sport, SOCCER_SITE)
    label = {"basketball": "籃球"}.get(sport, sport)
    pub = ROOT / f"public-{sport}"
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "index.html").write_text(render_sport_index(articles, site, label), encoding="utf-8")
    if sport == "basketball":
        (pub / "llms.txt").write_text(render_bb_llms_txt(articles, site), encoding="utf-8")
    # 真正的文章列表頁（nav「文章」→ /articles/），與首頁區隔、文章導向，非首頁克隆
    (pub / "articles").mkdir(parents=True, exist_ok=True)
    (pub / "articles" / "index.html").write_text(
        render_sport_articles_index(articles, site, label), encoding="utf-8")
    (pub / "sitemap.xml").write_text(render_sport_sitemap(articles, site), encoding="utf-8")
    (pub / "feed.xml").write_text(render_feed(articles, site), encoding="utf-8")
    print(f"🏀 {sport} site: index + sitemap + feed ({len(articles)} articles) → {pub}/")


# ---------- main build ----------

def build():
    # articles/ 不存在＝零文章（git 不追蹤空目錄；.gitkeep 已補，這裡再防一層）
    SRC.mkdir(parents=True, exist_ok=True)

    articles = []
    for d in sorted(SRC.iterdir()):
        if not d.is_dir():
            continue
        md_path = d / "index.md"
        if not md_path.exists():
            continue
        text = md_path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        meta.setdefault("slug", d.name)
        # this repo is basketball-only; articles without an explicit competition
        # default to nba (authors should still set it per article).
        meta.setdefault("competition", "nba")
        slug = meta["slug"]

        # build-side draft gate: slugs in config/draft-exclude.json are pending review and
        # excluded from ALL output (index/feed/sitemap/landing/page). Empty list -> no-op.
        if slug in DRAFT_EXCLUDE:
            print(f"⏭  skip draft (pending review, excluded): {slug}")
            continue

        if meta.get("type") == "daily":
            body = strip_medium_guide(body)
        body = inject_inline_images(body)
        body = strip_h1(body)

        excerpt = extract_excerpt(body)
        faq = parse_faq(body)  # mirror author-written FAQ section into FAQPage schema
        body_html = md_lib.markdown(body, extensions=["extra", "sane_lists"])

        # route to the comp's sport site: soccer -> public/articles (unchanged),
        # baseball -> public-baseball/articles. Soccer path == OUT/slug (byte-identical).
        out_dir = pub_root_for(meta) / "articles" / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        # cp all non-md assets
        for asset in d.iterdir():
            if asset.is_file() and asset.suffix != ".md":
                shutil.copy2(asset, out_dir / asset.name)

        articles.append({"slug": slug, "meta": meta, "excerpt": excerpt,
                         "faq": faq, "body_html": body_html, "out_dir": out_dir})

    # ----- 真下架：草稿 gate 只是 `continue` 跳過，既有輸出目錄仍留在 public-*/articles/，
    # 從首頁/列表/RSS/sitemap 消失但網址照樣打得開（＝沒有真的撤下）。這裡清掉本次未產出的目錄。
    # ⚠️ 只清理「本次確實有產出文章」的站根：多站共用本腳本，若某站這次一篇都沒產出，
    # 代表它不在本次建置範圍內，絕不能把它整個 articles/ 清空。 -----
    produced = {}  # pub_root/articles -> {slug}
    for a in articles:
        produced.setdefault(a["out_dir"].parent, set()).add(a["slug"])
    for art_root, keep_slugs in produced.items():
        for child in sorted(art_root.iterdir()):
            if child.is_dir() and child.name not in keep_slugs:
                shutil.rmtree(child)
                print(f"   🧹 removed stale article output: {child.name}（草稿或已下架）")

    # ----- prev/next neighbors computed PER SITE (sport) so each site's daily/feature rails
    # are independent. Soccer's group == all WC/soccer articles, so its neighbors (and thus
    # output) stay byte-identical; baseball features never enter soccer's rail. -----
    groups = {}  # sport -> [article dicts]
    for a in articles:
        groups.setdefault(_sport_of(a["meta"]), []).append(a)

    nav_for = {}  # slug -> (prev_nav, next_nav, more_dailies, kind)
    for group in groups.values():
        dailies_asc = sorted(
            [a for a in group if a["meta"].get("type") == "daily"],
            key=lambda a: str(a["meta"].get("date", "")),
        )
        features_asc = sorted(
            [a for a in group if a["meta"].get("type") != "daily"],
            key=lambda a: (str(a["meta"].get("date", "")), a["slug"]),
        )
        recent_dailies = list(reversed(dailies_asc))[:3]
        n = len(dailies_asc)
        for i, a in enumerate(dailies_asc):
            prev_nav = dailies_asc[i - 1] if i > 0 else None        # older date → 前一日戰報
            next_nav = dailies_asc[i + 1] if i < n - 1 else None    # newer date → 後一日戰報
            skip = {a["slug"]}
            if prev_nav:
                skip.add(prev_nav["slug"])
            if next_nav:
                skip.add(next_nav["slug"])
            more = [d for d in reversed(dailies_asc) if d["slug"] not in skip][:3]
            nav_for[a["slug"]] = (prev_nav, next_nav, more, "daily")
        m = len(features_asc)
        for i, a in enumerate(features_asc):
            prev_nav = features_asc[i - 1] if i > 0 else None        # earlier feature → 前一篇
            next_nav = features_asc[i + 1] if i < m - 1 else None    # later feature → 後一篇
            nav_for[a["slug"]] = (prev_nav, next_nav, recent_dailies, "feature")

    # ----- render every article now that neighbors are known (out_dir already per-site) -----
    for a in articles:
        prev_nav, next_nav, more, kind = nav_for.get(a["slug"], (None, None, [], "daily"))
        html_out = render_article(a["meta"], a["body_html"], a["slug"], a["excerpt"],
                                  prev_nav=prev_nav, next_nav=next_nav,
                                  more_dailies=more, nav_kind=kind, faq=a["faq"])
        (a["out_dir"] / "index.html").write_text(html_out, encoding="utf-8")
        print(f"✅ {a['slug']}")

    # ----- per-site index / feed / sitemap (sort by date desc; feature > daily on tie) -----
    type_rank = {"feature": 0, "daily": 1}

    def _sorted(lst):
        return sorted(lst, key=lambda a: (str(a["meta"].get("date", "")),
                      -type_rank.get(a["meta"].get("type", "daily"), 9)), reverse=True)

    # soccer (foootball): unchanged path -> public/ (byte-identical)
    soccer_sorted = _sorted(groups.get("soccer", []))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(render_index(soccer_sorted), encoding="utf-8")
    print(f"📚 index.html ({len(soccer_sorted)} articles) → {OUT}/index.html")
    feed_path = ROOT / "public" / "feed.xml"
    feed_path.write_text(render_feed(soccer_sorted), encoding="utf-8")
    print(f"📡 feed.xml ({min(len(soccer_sorted), FEED_MAX)} items) → {feed_path}")

    # non-soccer sports (basketball.twtools.cc ...): own landing + sitemap under public-<sport>/.
    # sites.json 註冊的 sport 一定建站（零文章也要有首頁/llms/sitemap/feed——建站初期常態）。
    for sport in SITES:
        if sport != "soccer":
            groups.setdefault(sport, [])
    for sport, group in groups.items():
        if sport == "soccer":
            continue
        _build_sport_site(_sorted(group), sport)


if __name__ == "__main__":
    build()
