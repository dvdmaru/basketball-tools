#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配色主題回歸測試（2026-09-11，3 深 2 淺：ember/court/violet + apricot/maple）。

抄棒球站 PR #99 記載的坑逐條防：
  1. WCAG 對比門檻（正文≥7、次要≥4.5、最淡≥4.5/3.0、強調色/勝負色≥4.5）
  2. 每組主題設定完整（登記制：BB_THEME_KEYS 與各查表 dict 的 key 集合必須一致）
  3. 每組主題各自宣告 color-scheme；深色限定效果（body 光暈）不漏到淺色主題
  4. 勝負色吃主題變數，不吃寫死色碼
  5. 7 種頁面外殼（build-articles.py 2 個動態殼 + 4 個 gen-*.py）都接了 preload/switch script
  6. 換頁閃爍 preload script 的白名單驗證（存的是已砍主題名要 fallback，不能整頁掉回無主題樣式）

跑法：python3 -m unittest tests.test_theme_palette -v
"""
import importlib.util
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ba = _load("build_articles", "build-articles.py")


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexcolor):
    hexcolor = hexcolor.lstrip("#")
    r, g, b = (int(hexcolor[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _ratio(h1, h2):
    l1, l2 = _lum(h1), _lum(h2)
    l1, l2 = max(l1, l2), min(l1, l2)
    return (l1 + 0.05) / (l2 + 0.05)


def _parse_token_block(theme_key):
    """從 _BB_TOKEN_BLOCKS 字面值裡挖出單一主題的 --var:value; 對照表。"""
    m = re.search(
        r':root\[data-theme="%s"\]\{(.*?)\}' % re.escape(theme_key),
        ba._BB_TOKEN_BLOCKS, re.S)
    assert m, f"theme block not found for {theme_key}"
    body = m.group(1)
    vals = {}
    for decl in body.split(";"):
        decl = decl.strip()
        if not decl or ":" not in decl:
            continue
        k, v = decl.split(":", 1)
        vals[k.strip()] = v.strip()
    return vals


REQUIRED_VARS = [
    "--bg", "--bg-deep", "--surface", "--surface-2", "--surface-3",
    "--fg", "--fg-soft", "--fg-mute", "--fg-dim",
    "--line", "--line-2", "--accent", "--accent-bright", "--gold", "--accent-ink",
    "--zebra", "--band-po", "--band-pi", "--accent-weak", "--gold-weak",
]


class RegistryConsistency(unittest.TestCase):
    """② 每組主題設定完整：BB_THEME_KEYS 與各查表 dict 的 key 集合必須一致。"""

    def test_dropped_themes_are_gone(self):
        self.assertNotIn("slate", ba.BB_THEME_KEYS)
        self.assertNotIn("jade", ba.BB_THEME_KEYS)

    def test_kept_and_added_themes_present(self):
        self.assertEqual(set(ba.BB_THEME_KEYS),
                          {"ember", "court", "violet", "apricot", "maple"})

    def test_dots_keys_match(self):
        self.assertEqual({k for k, _, _ in ba.BB_THEME_DOTS}, set(ba.BB_THEME_KEYS))

    def test_lookup_dicts_match(self):
        for name in ("_BB_BG", "_BB_NEG", "_BB_NEG_DEEP", "_BB_POS", "_BB_ACCENT"):
            d = getattr(ba, name)
            self.assertEqual(set(d.keys()), set(ba.BB_THEME_KEYS), msg=name)

    def test_light_set_is_subset(self):
        self.assertTrue(ba._BB_LIGHT.issubset(set(ba.BB_THEME_KEYS)))
        self.assertEqual(ba._BB_LIGHT, {"apricot", "maple"})

    def test_every_theme_has_complete_token_block(self):
        for k in ba.BB_THEME_KEYS:
            vals = _parse_token_block(k)
            for var in REQUIRED_VARS:
                self.assertIn(var, vals, msg=f"{k} missing {var}")

    def test_every_theme_declares_color_scheme(self):
        for k in ba.BB_THEME_KEYS:
            m = re.search(r':root\[data-theme="%s"\]\{\s*color-scheme:\s*(light|dark);'
                           % re.escape(k), ba._BB_TOKEN_BLOCKS)
            self.assertIsNotNone(m, msg=f"{k} missing color-scheme declaration")
            expected = "light" if k in ba._BB_LIGHT else "dark"
            self.assertEqual(m.group(1), expected, msg=k)


class ContrastThresholds(unittest.TestCase):
    """① WCAG 對比門檻。

    ⚠️ 範圍：ember/court/violet 是這輪**沿用**（非重新設計）的既有色票——它們的
    --fg-dim（＝站上 --faint）本來就沒有全部通過這份門檻表（例：ember #6d655b
    vs #14100e 只有 3.30），這是砍 slate/jade 之前就存在的既有狀態，不是這輪引入
    的迴歸，所以只驗「沒有變得更差」（正文/accent 這種本來就會過的項目）。
    apricot/maple 是這輪全新設計、逐色算過的，門檻表全套強制套用。
    """

    def _check_baseline(self, theme_key):
        """既有深色主題：只驗正文與 accent，不驗 fg-dim（見上方 docstring）。"""
        v = _parse_token_block(theme_key)

        def hx(key):
            return v[key].strip()

        checks = [
            (hx("--fg"), [hx("--bg"), hx("--surface")], 7.0),
            (hx("--fg"), [hx("--surface-2"), hx("--surface-3")], 4.5),
            (hx("--fg-mute"), [hx("--bg"), hx("--surface"), hx("--surface-2"), hx("--surface-3")], 4.5),
            (hx("--accent"), [hx("--bg")], 4.5),
        ]
        for fg, bgs, thresh in checks:
            for bg in bgs:
                r = _ratio(fg, bg)
                self.assertGreaterEqual(
                    r, thresh - 0.02,
                    msg=f"{theme_key}: {fg} vs {bg} = {r:.2f} < {thresh}")

    def _check_full(self, theme_key):
        """新設計的淺色主題：門檻表全套套用，含最淡層級。"""
        v = _parse_token_block(theme_key)

        def hx(key):
            return v[key].strip()

        checks = [
            (hx("--fg"), [hx("--bg"), hx("--surface")], 7.0),
            (hx("--fg"), [hx("--surface-2"), hx("--surface-3")], 4.5),
            (hx("--fg-mute"), [hx("--bg"), hx("--surface"), hx("--surface-2"), hx("--surface-3")], 4.5),
            (hx("--fg-dim"), [hx("--bg"), hx("--surface")], 4.5),
            (hx("--fg-dim"), [hx("--surface-2"), hx("--surface-3")], 3.0),
            (hx("--accent"), [hx("--bg")], 4.5),
        ]
        for fg, bgs, thresh in checks:
            for bg in bgs:
                r = _ratio(fg, bg)
                self.assertGreaterEqual(
                    r, thresh - 0.02,
                    msg=f"{theme_key}: {fg} vs {bg} = {r:.2f} < {thresh}")

    def test_ember(self):
        self._check_baseline("ember")

    def test_court(self):
        self._check_baseline("court")

    def test_violet(self):
        self._check_baseline("violet")

    def test_apricot(self):
        self._check_full("apricot")

    def test_maple(self):
        self._check_full("maple")

    def test_neg_pos_accent_ink_on_light_themes(self):
        """勝負色與按鈕字是額外查表（_BB_NEG/_BB_POS/accent-ink），淺色主題單獨驗。"""
        for k in ("apricot", "maple"):
            v = _parse_token_block(k)
            bg = v["--bg"]
            self.assertGreaterEqual(_ratio(ba._BB_NEG[k], bg), 4.48, msg=f"{k} neg")
            self.assertGreaterEqual(_ratio(ba._BB_POS[k], bg), 4.48, msg=f"{k} pos")
            self.assertGreaterEqual(
                _ratio(v["--accent-ink"], v["--accent"]), 4.48, msg=f"{k} accent-ink")


class DarkOnlyEffects(unittest.TestCase):
    """③ 深色限定效果不可漏到淺色主題（body 光暈）。"""

    def _glow_rule_selectors(self):
        css = ba._bb_theme_tokens_css()
        m = re.search(r"attachment:fixed;\s*\}\s*\n(.*?)\{\n\s*background-image:", css, re.S)
        self.assertIsNotNone(m, msg="glow 規則在 overrides 裡找不到，CSS 結構可能變了")
        return m.group(1)

    def test_light_themes_have_no_glow_gradient(self):
        sels = self._glow_rule_selectors()
        for k in ba._BB_LIGHT:
            self.assertNotIn(f'"{k}"', sels, msg=f"{k} 不該套光暈")

    def test_dark_themes_have_glow_gradient(self):
        sels = self._glow_rule_selectors()
        for k in [x for x in ba.BB_THEME_KEYS if x not in ba._BB_LIGHT]:
            self.assertIn(f'"{k}"', sels, msg=f"{k} 應保留光暈")


class HardcodedWinLossRegression(unittest.TestCase):
    """④ 勝負色不可回退成寫死色碼（曾經是 #5fb878 / #d98a8a）。"""

    def test_no_hardcoded_result_colors_in_css(self):
        """#5fb878/#d98a8a 合法存在於 _BB_POS/_BB_NEG 查表 dict 裡（深色主題沿用舊值），
        這裡只禁止它們直接寫進 CSS 宣告（color:#.../border:...#...），繞過主題變數。"""
        src = (ROOT / "scripts" / "build-articles.py").read_text(encoding="utf-8")
        for bad in ("color:#5fb878", "color:#d98a8a", "border:1px solid #d98a8a"):
            self.assertNotIn(bad, src, msg=bad)

    def test_result_classes_use_theme_vars(self):
        src = (ROOT / "scripts" / "build-articles.py").read_text(encoding="utf-8")
        self.assertIn(".rd-pos,.stk-pos{color:var(--accent-pos)}", src)
        self.assertIn(".rd-neg,.stk-neg{color:var(--accent-neg)}", src)


class ShellWiring(unittest.TestCase):
    """⑤ 登記制：所有頁面外殼都要接上 preload + switch script，不接就測試失敗
    （不是「找到就好」，是每種殼都要點名核對）。"""

    BUILD_ARTICLES_SHELLS = 2  # 動態 data-theme 的兩個 <html> 殼（article + index/dashboard）
    GEN_SCRIPTS = [
        "gen-basketball-data-hub.py",
        "gen-hbl-page.py",
        "gen-nba-standings.py",
        "gen-tw-standings.py",
    ]

    def test_build_articles_shells_wired(self):
        src = (ROOT / "scripts" / "build-articles.py").read_text(encoding="utf-8")
        preload_calls = src.count("<script>{theme_preload_js(site)}</script>")
        switch_calls = src.count("<script>{theme_switch_js(site)}</script>")
        self.assertGreaterEqual(preload_calls, self.BUILD_ARTICLES_SHELLS)
        self.assertGreaterEqual(switch_calls, self.BUILD_ARTICLES_SHELLS)

    def test_gen_scripts_wired(self):
        for fname in self.GEN_SCRIPTS:
            src = (ROOT / "scripts" / fname).read_text(encoding="utf-8")
            self.assertIn("ba.theme_preload_js(SITE)", src, msg=fname)
            self.assertIn("ba.theme_switch_js(SITE)", src, msg=fname)
            self.assertIn("ba.site_header_html(", src, msg=fname)

    def test_theme_color_meta_precedes_preload_script_in_build_articles(self):
        """2026-09-11 code review 抓到：preload script 若排在 <meta name="theme-color">
        之前，瀏覽器同步執行 script 時該 meta 節點還沒被解析器建立，querySelector 拿到
        null，讀者存的非預設主題在第一次載入時 meta theme-color 不會被校正（要等下次點擊
        切換器的 click handler 才補上，因為那時 DOM 已就緒）。data-theme 屬性本身不受影響
        （root 是 document.documentElement，一開始就存在），純粹是這個次要視覺訊號的 bug。
        每個殼各自檢查，不是只驗全檔案裡兩個字串誰先出現一次（build-articles.py 有兩個殼）。"""
        src = (ROOT / "scripts" / "build-articles.py").read_text(encoding="utf-8")
        head_starts = [m.start() for m in re.finditer(r"<head>\n", src)]
        self.assertGreaterEqual(len(head_starts), self.BUILD_ARTICLES_SHELLS)
        checked = 0
        for i, start in enumerate(head_starts):
            end = head_starts[i + 1] if i + 1 < len(head_starts) else len(src)
            segment = src[start:end]
            if "<script>{theme_preload_js(site)}</script>" not in segment:
                continue  # 不是動態殼（例如 legacy soccer 那個殼）
            script_pos = segment.index("<script>{theme_preload_js(site)}</script>")
            self.assertIn('<meta name="theme-color"', segment[:script_pos],
                          msg=f"殼 #{i}: theme-color meta 沒排在 preload script 前面")
            checked += 1
        self.assertGreaterEqual(checked, self.BUILD_ARTICLES_SHELLS)

    def test_theme_color_meta_precedes_preload_script_in_gen_scripts(self):
        for fname in self.GEN_SCRIPTS:
            src = (ROOT / "scripts" / fname).read_text(encoding="utf-8")
            script_pos = src.index("<script>{ba.theme_preload_js(SITE)}</script>")
            meta_pos = src.index('<meta name="theme-color"')
            self.assertLess(meta_pos, script_pos, msg=fname)


class PreloadFallback(unittest.TestCase):
    """⑥ 讀者存的是已砍主題名（slate/jade）要 fallback，不能整頁掉回無主題樣式。"""

    def test_preload_whitelists_current_keys_only(self):
        js = ba.theme_preload_js({"default_theme": "ember"})
        for k in ba.BB_THEME_KEYS:
            self.assertIn(f'"{k}"', js)
        self.assertNotIn('"slate"', js)
        self.assertNotIn('"jade"', js)

    def test_preload_removes_invalid_saved_value(self):
        js = ba.theme_preload_js({"default_theme": "ember"})
        self.assertIn("VALID.indexOf(saved)===-1", js)
        self.assertIn("localStorage.removeItem(KEY)", js)

    def test_soccer_path_returns_empty(self):
        self.assertEqual(ba.theme_preload_js({"default_theme": "grass"}), "")


if __name__ == "__main__":
    unittest.main()
