#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站群自有版位（scripts/adslots.py）回歸測試。

釘住 Charlie 2026-11-07 的裁定：
- 首頁主推位＋原生版位，原生每頁最多 2 則；不做彈窗。
- 「零 client fetch」站規的版位例外只限首頁、/articles/、文章頁；數據頁
  （/standings/、/tw/、/hbl/、/nba-cup/、/data/）一律不放版位、不載版位程式。
- 平常隱藏（HTML 帶 hidden）；首頁「最新文章」照舊 5 篇，第 5 篇帶 data-ad-yield。
- 預設卡標「推廣」、連結帶 noopener；版位程式不准用 innerHTML 類寫法（設定檔內容一律當純文字）。
- 曝光＝一半以上進畫面且停留 1 秒（GA4 view_promotion），點擊＝select_promotion；預覽不送 GA。

⚠️ 本測試**不跑產生器、不寫任何檔**：頁面一律呼叫 render 函式／各 gen-* 的 build_page 在記憶體裡產生
（MODEL.md「測試會不會偷寫版控產物」）。版位程式檔只在 build-articles.py 的 _build_sport_site 寫出，
render 函式只拿 ads.SCRIPT_HREF 組標籤。

跑法：python3 -m unittest discover -s tests -v
"""
import glob
import importlib.util
import json
import pathlib
import re
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUB = ROOT / "public-basketball"


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ads = _load("adslots_t", "adslots.py")
ba = _load("build_articles_adslots_t", "build-articles.py")
gen_std = _load("gen_nba_standings_adslots_t", "gen-nba-standings.py")
gen_cup = _load("gen_nba_cup_adslots_t", "gen-nba-cup.py")
gen_tw = _load("gen_tw_standings_adslots_t", "gen-tw-standings.py")
gen_hbl = _load("gen_hbl_page_adslots_t", "gen-hbl-page.py")
gen_hub = _load("gen_data_hub_adslots_t", "gen-basketball-data-hub.py")

SITE = ba.SITES["basketball"]
SLOT_RE = re.compile(r'<a class="ad-slot[^"]*" data-ad-slot="([a-z_]+)"[^>]*>')
SCRIPT_RE = re.compile(r'<script src="/assets/ad-[0-9a-f]{10}\.js" defer></script>')
# 任何一個出現在數據頁都算「放了版位」：外殼、讓位標記、版位 CSS、版位程式、設定檔網址
AD_MARKERS = ("ad-slot", "data-ad-", ".ad-label", "/assets/ad-", "ad-slots.json")

_TMP = tempfile.TemporaryDirectory()   # out_dir 佔位（_card_src 只看檔案在不在），不寫任何東西


def _articles():
    """跟 build() 一樣讀 articles/*/index.md 組出文章清單，但不寫檔、不轉 markdown。"""
    out = []
    for md in sorted((ROOT / "articles").glob("*/index.md")):
        meta, body = ba.parse_frontmatter(md.read_text(encoding="utf-8"))
        meta.setdefault("slug", md.parent.name)
        meta.setdefault("competition", "nba")
        if meta["slug"] in ba.DRAFT_EXCLUDE:
            continue
        out.append({"slug": meta["slug"], "meta": meta, "excerpt": ba.extract_excerpt(body),
                    "faq": [], "body_html": "<p>本文</p>", "out_dir": pathlib.Path(_TMP.name) / meta["slug"]})
    out.sort(key=lambda a: str(a["meta"].get("date", "")), reverse=True)
    return out


ARTICLES = _articles()


def _slots(html):
    return SLOT_RE.findall(html)


def _home():
    return ba.render_sport_index(ARTICLES, SITE, "籃球")


def _articles_index():
    return ba.render_sport_articles_index(ARTICLES, SITE, "籃球")


def _article_pages():
    for a in ARTICLES:
        yield a["slug"], ba.render_article(a["meta"], a["body_html"], a["slug"], a["excerpt"],
                                           related_candidates=ARTICLES)


def _json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _data_pages():
    """數據頁：各 gen-* 的 build_page，用 repo 裡**每一份**可用的快照／fixture 各產一次。
    回傳 [(標籤, html)]。"""
    pages = []
    games = sorted(glob.glob(str(ROOT / "leagues" / "nba-games-*.json"))) + \
        sorted(glob.glob(str(ROOT / "tests" / "fixtures" / "nba" / "nba-games-*.json")))
    for f in sorted(glob.glob(str(ROOT / "leagues" / "nba-standings-*.json"))):
        snap = _json(f)
        pages.append((f"standings:{pathlib.Path(f).name}", gen_std.build_page(snap)))
        for g in games:
            pages.append((f"standings:{pathlib.Path(f).name}+{pathlib.Path(g).name}",
                          gen_std.build_page(snap, _json(g))))
    for f in sorted(glob.glob(str(ROOT / "leagues" / "nba-cup-*.json"))) + \
            sorted(glob.glob(str(ROOT / "tests" / "fixtures" / "nba" / "nba-cup-*.json"))):
        pages.append((f"nba-cup:{pathlib.Path(f).name}", gen_cup.build_page(_json(f))))
    for f in sorted(glob.glob(str(ROOT / "leagues" / "tw-hoops-*.json"))):
        pages.append((f"tw:{pathlib.Path(f).name}", gen_tw.build_page(_json(f))))
    hist_f = ROOT / "leagues" / "hbl-history.json"
    hist = _json(hist_f) if hist_f.exists() else {"seasons": []}
    for f in sorted(glob.glob(str(ROOT / "leagues" / "hbl-[0-9]*.json"))):
        pages.append((f"hbl:{pathlib.Path(f).name}", gen_hbl.build_page(_json(f), hist)))
    pages.append(("data-hub", gen_hub.build_page()))
    return pages


class PlacementTests(unittest.TestCase):
    def test_home_has_one_hero_and_one_native(self):
        self.assertEqual(sorted(_slots(_home())), ["home_hero", "native_list"])

    def test_articles_index_has_one_native(self):
        self.assertEqual(_slots(_articles_index()), ["native_list"])

    def test_every_article_has_exactly_one_end_slot(self):
        n = 0
        for slug, html in _article_pages():
            with self.subTest(page=slug):
                self.assertEqual(_slots(html), ["native_end"])
                self.assertIsNotNone(SCRIPT_RE.search(html))
            n += 1
        self.assertGreater(n, 50, "應該掃到全部文章頁")

    def test_native_at_most_two_per_page(self):
        pages = [("home", _home()), ("articles", _articles_index())] + list(_article_pages())
        for name, html in pages:
            n = sum(1 for s in _slots(html) if s.startswith("native"))
            self.assertLessEqual(n, 2, name)

    def test_hero_is_after_h1_and_before_dashboard(self):
        html = _home()
        hero = html.index('data-ad-slot="home_hero"')
        self.assertLess(html.index("</h1>"), hero, "主推位不能包住 H1")
        self.assertLess(html.index('<section class="hero">'), hero)
        self.assertLess(hero, html.index('<div class="dash">'), "主推位要在第一屏（儀表板之前）")

    def test_native_list_is_third_card_on_home(self):
        html = _home()
        grid = html[html.index('<div class="art-grid">'):]
        grid = grid[:grid.index("</section>")]
        cards = re.findall(r'<a (?:data-ad-yield="native_list" )?class="(art[^"]*|ad-slot[^"]*)"', grid)
        self.assertEqual(cards[2].split()[0], "ad-slot")
        self.assertTrue(all(c.startswith("art") for c in cards[:2] + cards[3:]))

    def test_native_list_is_third_card_on_articles_index(self):
        html = _articles_index()
        i = html.index('data-ad-slot="native_list"')
        grid = html[html.rfind('<div class="idx-grid">', 0, i):]
        cards = re.findall(r'<a class="(idx-card|ad-slot[^"]*)"', grid)
        self.assertEqual(cards[:3], ["idx-card", "idx-card", "ad-slot ad-native"])

    def test_article_end_slot_between_related_and_post_nav(self):
        _slug, html = next(_article_pages())
        end = html.index('data-ad-slot="native_end"')
        self.assertLess(html.index("</article>"), end, "內文結束之後")
        self.assertLess(end, html.index('<nav class="post-nav"'), "上下篇導覽之前")


class NormalLookTests(unittest.TestCase):
    """沒有檔期時網站要跟原本一樣：版位隱藏、首頁照舊 5 篇、/articles/ 篇數不變。"""

    def test_all_slots_hidden_in_html(self):
        pages = [("home", _home()), ("articles", _articles_index())] + list(_article_pages())[:5]
        for name, html in pages:
            tags = re.findall(r'<a class="ad-slot[^>]*>', html)
            self.assertTrue(tags, name)
            for tag in tags:
                self.assertTrue(tag.endswith(" hidden>"), (name, tag))

    def test_home_keeps_five_articles_with_one_yield_card(self):
        self.assertGreaterEqual(len(ARTICLES), 5)
        html = _home()
        grid = html[html.index('<div class="art-grid">'):]
        grid = grid[:grid.index("</section>")]
        arts = re.findall(r'<a (?:data-ad-yield="native_list" )?class="art[ "]', grid)
        self.assertEqual(len(arts), 5)
        self.assertEqual(grid.count('data-ad-yield="native_list"'), 1)
        last = re.findall(r'<a [^>]*class="art[^"]*"[^>]*>', grid)[-1]
        self.assertIn('data-ad-yield="native_list"', last, "讓位的是最後一篇")

    def test_articles_index_lists_every_article_once(self):
        html = _articles_index()
        hrefs = re.findall(r'<a class="idx-(?:card|feature)" href="/articles/([^/]+)/"', html)
        self.assertEqual(sorted(hrefs), sorted(a["slug"] for a in ARTICLES))

    def test_yield_and_hidden_css_present(self):
        self.assertIn(".ad-slot[hidden],[data-ad-yield][hidden]{display:none!important}", ads.AD_CSS)
        for html in (_home(), _articles_index(), next(_article_pages())[1]):
            self.assertIn(ads.AD_CSS, html)

    def test_preview_skips_ga_and_time_window(self):
        js = ads.JS_TEXT
        self.assertIn("ad-preview=1", js)
        self.assertIn("if(PREVIEW||typeof window.gtag!=='function')return;", js)
        self.assertIn("return PREVIEW||(a<=now&&now<b);", js)


class ScopeTests(unittest.TestCase):
    """版位例外只限首頁、/articles/、文章頁：數據頁不放版位、不載版位程式。

    ⚠️ 反向對照（2026-11-07 實測）：在 gen-nba-standings.py 的 build_page 結果裡塞進
    ads.slot_html("home_hero")＋ads.script_tag()，test_data_pages_have_no_ads 會紅；還原後綠。
    """

    def test_data_pages_have_no_ads(self):
        pages = _data_pages()
        kinds = {name.split(":")[0] for name, _ in pages}
        self.assertTrue({"standings", "tw", "hbl", "data-hub"} <= kinds, kinds)
        for name, html in pages:
            with self.subTest(page=name):
                for m in AD_MARKERS:
                    self.assertNotIn(m, html)
                self.assertIsNone(SCRIPT_RE.search(html))
        self.assertGreaterEqual(len(pages), 6, "應該掃到每一種數據頁、每份快照")

    def test_built_data_pages_have_no_ads(self):
        """已建好的產物（repo 內 committed 的、或本機剛 build 的）：除了首頁、/articles/、
        文章頁之外，所有 HTML 都不准有版位。"""
        allowed = {PUB / "index.html", PUB / "articles" / "index.html"}
        checked = 0
        for p in PUB.rglob("*.html"):
            if p in allowed or (p.parent.parent == PUB / "articles" and p.name == "index.html"):
                continue
            html = p.read_text(encoding="utf-8")
            with self.subTest(page=str(p.relative_to(PUB))):
                for m in AD_MARKERS:
                    self.assertNotIn(m, html)
            checked += 1
        self.assertGreaterEqual(checked, 4, "standings／tw／hbl／data 至少要掃到")

    def test_data_generators_never_reference_ads(self):
        for f in ("gen-nba-standings.py", "gen-nba-cup.py", "gen-tw-standings.py",
                  "gen-hbl-page.py", "gen-basketball-data-hub.py"):
            src = (ROOT / "scripts" / f).read_text(encoding="utf-8")
            with self.subTest(gen=f):
                self.assertIsNone(re.search(r"\bads\.", src))
                self.assertNotIn("adslots", src)
                self.assertNotIn("slot_html", src)

    def test_shared_head_carries_no_ad_css(self):
        """數據頁共用 _bb_head；版位 CSS 只能經 extra_css 由首頁／列表自己帶。"""
        head = ba._bb_head(SITE, "t", "d", SITE["base"] + "/", "")
        self.assertNotIn(".ad-slot", head)

    def test_csp_allows_config_origin(self):
        """本站 _headers 有 CSP：沒放行 twtools.cc，版位程式讀不到設定檔（版位永遠不出現，而且不會報錯）。"""
        csp = next(l for l in (PUB / "_headers").read_text(encoding="utf-8").splitlines()
                   if "Content-Security-Policy:" in l)
        directives = {d.split()[0]: d.split()[1:] for d in csp.split(":", 1)[1].split(";") if d.strip()}
        self.assertIn("https://twtools.cc", directives["connect-src"])
        for h in ads.IMG_HOSTS:
            self.assertIn(f"https://{h}", directives["img-src"])
        self.assertTrue(ads.CONFIG_URL.startswith("https://twtools.cc/"))


class MarkupTests(unittest.TestCase):
    def test_fallback_card_label_and_rel(self):
        for slot in ("home_hero", "native_list", "native_end"):
            h = ads.slot_html(slot)
            with self.subTest(slot=slot):
                self.assertIn('<span class="ad-label">推廣</span>', h)
                self.assertIn(' hidden>', h, "平常要隱藏：沒有檔期時網站維持原本的樣子")
                self.assertIn('rel="noopener"', h)
                self.assertIn('href="https://', h)
                self.assertNotIn("<h1", h)

    def test_fallback_text_comes_from_sister_sites(self):
        sister = set(ba.SISTER_SITES)
        for slot, (title, url) in ads.FALLBACK.items():
            with self.subTest(slot=slot):
                self.assertIn((title, url), sister)
                self.assertNotEqual(url, SITE["base"] + "/", "預設卡不推自己")

    def test_unknown_slot_rejected(self):
        with self.assertRaises(ValueError):
            ads.slot_html("popup")

    def test_render_does_not_write_script_file(self):
        """render 函式只組標籤，不寫檔（測試才不會改到版控目錄）。"""
        src = (ROOT / "scripts" / "build-articles.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("ads.write_script("), 1)
        self.assertIn('if sport == "basketball":\n        ads.write_script(pub)', src)

    def test_write_script_keeps_current_and_previous(self):
        with tempfile.TemporaryDirectory() as d:
            assets = pathlib.Path(d) / "assets"
            assets.mkdir()
            for i, name in enumerate(("ad-0000000001.js", "ad-0000000002.js")):
                (assets / name).write_text("old", encoding="utf-8")
            p = ads.write_script(pathlib.Path(d))
            self.assertEqual(p.read_text(encoding="utf-8"), ads.JS_TEXT)
            self.assertEqual(len(list(assets.glob("ad-*.js"))), 2)
            self.assertEqual("/assets/" + p.name, ads.SCRIPT_HREF)


class ScriptTests(unittest.TestCase):
    JS = ads.JS_TEXT

    def test_never_writes_html_from_config(self):
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(",
                       "new Function", "createContextualFragment", "DOMParser"):
            self.assertNotIn(banned, self.JS)

    def test_reads_only_central_config(self):
        self.assertEqual(self.JS.count("fetch("), 1)
        self.assertIn('"https://twtools.cc/ad-slots.json"', self.JS)
        self.assertIn("credentials:'omit'", self.JS)

    def test_site_key(self):
        self.assertEqual(ads.SITE_KEY, "basketball")
        self.assertIn('SITE="basketball"', self.JS)

    def test_viewability_rule(self):
        self.assertIn("IntersectionObserver", self.JS)
        self.assertIn("intersectionRatio>=0.5", self.JS)
        self.assertIn(",1000)", self.JS)
        self.assertIn("'view_promotion'", self.JS)
        self.assertIn("'select_promotion'", self.JS)

    def test_paid_links_marked_sponsored(self):
        self.assertIn("c.tier==='paid'?'sponsored noopener'", self.JS)
        self.assertIn("c.tier==='paid'?'贊助':'推廣'", self.JS)

    def test_https_only_and_utm(self):
        self.assertIn("x.protocol==='https:'", self.JS)
        for k in ("utm_source", "utm_medium", "utm_campaign"):
            self.assertIn(f"'{k}'", self.JS)

    def test_images_limited_to_csp_hosts(self):
        self.assertIn('IMG_HOSTS=["twtools.cc"]', self.JS)
        self.assertIn("var img=c.image?okImg(c.image):null;", self.JS)


if __name__ == "__main__":
    unittest.main()
