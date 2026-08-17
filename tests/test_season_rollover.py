#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""season-state rollover 回歸保護（2026-08-18）。

守的不變量（一條涵蓋全站）：
  1. 餵 final=False（賽季進行中）的假快照 → 產出的頁面不得出現「休賽季」「終局」，
     也不得出現任何寫死的賽季字面值（舊賽季 2025-26／114學年度）。
  2. 餵 final=True 的假快照 → 休賽季文案要正常出現，且賽季標籤仍取自快照
     （把快照 season 改成別的值，輸出就要跟著改；舊字面值一個都不許漏出來）。

涵蓋產物：首頁（含 FAQPage JSON-LD）、/tw/（含 FAQPage JSON-LD）、/data/、llms.txt。

做法：把 leagues/ 的真實快照 deep-copy 後改寫 season／final，再 monkeypatch 各腳本的
_dash_latest，直接呼叫 render/build 函式取 HTML；⛔ 不寫任何檔案進 leagues/。

跑法：python3 -m unittest discover -s tests -v
"""
import copy
import glob
import importlib.util
import json
import pathlib
import re
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 舊賽季字面值——任何產出裡出現這些字串，就代表某處把賽季寫死了。
STALE_LITERALS = ("2025-26", "114學年度", "114 學年度", "2026 年 10 月")
# 測試用的「新賽季」標籤（僅存在於假快照，repo 內任何原始碼都不該出現）。
NEW_SEASON = "2026-27"
NEW_HBL_SEASON = "115學年度"
OFFSEASON_WORDS = ("休賽季", "終局")


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ba = _load("build_articles", "build-articles.py")
gtw = _load("gen_tw_standings", "gen-tw-standings.py")
hub = _load("gen_data_hub", "gen-basketball-data-hub.py")
SITE = ba.SITES["basketball"]


def _real(pattern):
    files = sorted(glob.glob(str(ROOT / "leagues" / pattern)))
    if not files:
        raise unittest.SkipTest(f"leagues/ 缺少 {pattern} 快照")
    return json.loads(pathlib.Path(files[-1]).read_text(encoding="utf-8"))


def snapshots(final):
    """回傳 (nba, tw, hbl) 三份假快照：賽季標籤一律換成 NEW_SEASON，final 依參數。"""
    nba = copy.deepcopy(_real("nba-standings-*.json"))
    tw = copy.deepcopy(_real("tw-hoops-*.json"))
    hbl = copy.deepcopy(_real("hbl-[0-9]*.json"))
    nba["season"] = NEW_SEASON
    nba["final"] = final
    tw["season"] = NEW_SEASON
    tw["final"] = final
    hbl["season_label"] = NEW_HBL_SEASON
    hbl["final"] = final
    if not final:
        # 賽季進行中卻仍殘留舊冠軍卡＝B1 #7 指出的邊界情況，刻意保留以驗標籤不會誤說「賽季終局」。
        for lg in tw["leagues"].values():
            lg.pop("champion_zh", None)
            lg.pop("finals_note", None)
    return nba, tw, hbl


def _patch(module, nba, tw, hbl):
    def fake(pattern):
        if pattern.startswith("nba-standings"):
            return nba
        if pattern.startswith("tw-hoops"):
            return tw
        if pattern.startswith("hbl-"):
            return hbl
        return None
    return mock.patch.object(module, "_dash_latest", fake)


def _faq_ld(html):
    """從頁面抽出 FAQPage 節點的 (question, answer) 清單。"""
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    for b in blocks:
        data = json.loads(b)
        for node in data.get("@graph", []):
            if node.get("@type") == "FAQPage":
                return [(q["name"], q["acceptedAnswer"]["text"]) for q in node["mainEntity"]]
    return []


class RolloverAssertMixin:
    def assertNoStale(self, text, where):
        for lit in STALE_LITERALS:
            self.assertNotIn(lit, text, f"{where}：出現寫死的賽季字面值「{lit}」")

    def assertInSeasonClean(self, text, where):
        """賽季進行中的產出：不得有休賽季字樣，也不得有寫死賽季字面值。"""
        self.assertNoStale(text, where)
        for w in OFFSEASON_WORDS:
            self.assertNotIn(w, text, f"{where}：賽季進行中卻出現休賽季字樣「{w}」")
        self.assertIn(NEW_SEASON, text, f"{where}：賽季標籤沒有跟著快照走")


# ---------- 首頁（含 FAQPage JSON-LD）----------

class HomePageRolloverTests(RolloverAssertMixin, unittest.TestCase):
    def _render(self, final):
        nba, tw, hbl = snapshots(final)
        with _patch(ba, nba, tw, hbl):
            return ba.render_sport_index([], SITE, "籃球")

    def test_in_season_home_has_no_offseason_language(self):
        self.assertInSeasonClean(self._render(False), "首頁（賽季進行中）")

    def test_in_season_home_faq_jsonld_has_no_offseason_language(self):
        pairs = _faq_ld(self._render(False))
        self.assertTrue(pairs, "首頁 FAQPage JSON-LD 不見了")
        blob = " ".join(q + a for q, a in pairs)
        self.assertInSeasonClean(blob, "首頁 FAQPage JSON-LD（賽季進行中）")

    def test_in_season_home_faq_jsonld_mirrors_visible_faq(self):
        html = self._render(False)
        for q, a in _faq_ld(html):
            self.assertIn(ba.html_lib.escape(q), html, "FAQ 問句沒鏡射到可見 DOM")
            self.assertIn(ba.html_lib.escape(a), html, "FAQ 答案沒鏡射到可見 DOM")

    def test_in_season_home_status_labels_say_in_progress(self):
        html = self._render(False)
        self.assertIn("例行賽進行中", html, "首頁戰績表 caption 沒改成進行中")
        self.assertIn("賽季進行中", html, "首頁冠軍卡列標籤沒改成進行中")
        self.assertIn("開季中", html, "首頁 hero 狀態列沒進開季模式")

    def test_offseason_home_keeps_offseason_copy(self):
        html = self._render(True)
        self.assertIn("休賽季", html, "休賽季文案消失了")
        self.assertIn("例行賽終局", html, "休賽季戰績表 caption 不見「終局」")
        self.assertIn("賽季終局", html, "休賽季冠軍卡列標籤不見「終局」")
        self.assertIn(NEW_SEASON, html)
        self.assertNoStale(html, "首頁（休賽季）")

    def test_offseason_home_faq_jsonld_is_data_derived(self):
        pairs = _faq_ld(self._render(True))
        blob = " ".join(q + a for q, a in pairs)
        self.assertIn("休賽季", blob)
        self.assertIn(NEW_HBL_SEASON, blob, "FAQ 沒有取用快照的 HBL 學年度標籤")
        self.assertNoStale(blob, "首頁 FAQPage JSON-LD（休賽季）")


# ---------- llms.txt ----------

class LlmsTxtRolloverTests(RolloverAssertMixin, unittest.TestCase):
    def _render(self, final):
        nba, tw, hbl = snapshots(final)
        with _patch(ba, nba, tw, hbl):
            return ba.render_bb_llms_txt([], SITE)

    def test_in_season_llms_txt_has_no_offseason_claim(self):
        self.assertInSeasonClean(self._render(False), "llms.txt（賽季進行中）")

    def test_offseason_llms_txt_keeps_offseason_claim(self):
        txt = self._render(True)
        self.assertIn("休賽季", txt)
        self.assertIn(NEW_SEASON, txt)
        self.assertIn(NEW_HBL_SEASON, txt, "llms.txt 沒有取用快照的 HBL 學年度標籤")
        self.assertNoStale(txt, "llms.txt（休賽季）")

    def test_standings_link_line_follows_snapshot_season(self):
        txt = self._render(False)
        line = next(ln for ln in txt.splitlines() if "/standings/)" in ln)
        self.assertIn(NEW_SEASON, line, "llms.txt 的 NBA 戰績行沒跟著快照賽季走")
        self.assertNoStale(line, "llms.txt NBA 戰績行")


# ---------- /data/ 數據總覽 ----------

class DataHubRolloverTests(RolloverAssertMixin, unittest.TestCase):
    def _render(self, final):
        nba, tw, hbl = snapshots(final)
        with _patch(hub.ba, nba, tw, hbl):
            return hub.build_page()

    def test_in_season_data_hub_card_has_no_offseason_claim(self):
        self.assertInSeasonClean(self._render(False), "/data/（賽季進行中）")

    def test_offseason_data_hub_card_keeps_offseason_claim(self):
        html = self._render(True)
        self.assertIn("休賽季", html)
        self.assertIn(NEW_SEASON, html)
        self.assertNoStale(html, "/data/（休賽季）")


# ---------- /tw/ 台灣職籃戰績頁 ----------

class TwStandingsRolloverTests(RolloverAssertMixin, unittest.TestCase):
    def _render(self, final):
        _nba, tw, _hbl = snapshots(final)
        return gtw.build_page(tw)

    def test_page_faq_signature_takes_final(self):
        """B1 #5 結構性缺陷：_page_faq 當初根本沒收 final，比照 NBA 版補上。"""
        import inspect
        params = inspect.signature(gtw._page_faq).parameters
        self.assertIn("final", params, "gen-tw-standings._page_faq 又沒有 final 參數了")

    def test_in_season_tw_page_has_no_offseason_language(self):
        self.assertInSeasonClean(self._render(False), "/tw/（賽季進行中）")

    def test_in_season_tw_faq_jsonld_has_no_offseason_language(self):
        pairs = _faq_ld(self._render(False))
        self.assertTrue(pairs, "/tw/ FAQPage JSON-LD 不見了")
        blob = " ".join(q + a for q, a in pairs)
        self.assertInSeasonClean(blob, "/tw/ FAQPage JSON-LD（賽季進行中）")

    def test_in_season_tw_table_caption_says_in_progress(self):
        self.assertIn("例行賽進行中", self._render(False), "/tw/ 戰績表 caption 沒改成進行中")

    def test_in_season_tw_faq_does_not_name_stale_champions(self):
        """賽季進行中不得沿用舊賽季冠軍名字（原本 Q&A 把冠軍寫死在字串裡）。"""
        blob = " ".join(q + a for q, a in _faq_ld(self._render(False)))
        for name in ("福爾摩沙夢想家", "桃園璞園領航猿"):
            self.assertNotIn(name, blob, f"/tw/ FAQ 在賽季進行中仍宣稱冠軍是{name}")

    def test_offseason_tw_page_keeps_offseason_copy(self):
        html = self._render(True)
        self.assertIn("休賽季", html)
        self.assertIn("例行賽終局", html)
        self.assertIn(NEW_SEASON, html)
        self.assertNoStale(html, "/tw/（休賽季）")

    def test_offseason_tw_faq_champions_come_from_snapshot(self):
        _nba, tw, _hbl = snapshots(True)
        tw["leagues"]["tpbl"]["champion_zh"] = "測試冠軍隊"
        tw["leagues"]["tpbl"]["finals_note"] = "總冠軍賽 4:0 勝測試對手"
        blob = " ".join(q + a for q, a in _faq_ld(gtw.build_page(tw)))
        self.assertIn("測試冠軍隊", blob, "/tw/ FAQ 的冠軍沒有取自快照")
        self.assertNotIn("福爾摩沙夢想家", blob, "/tw/ FAQ 仍寫死舊冠軍")

    def test_tw_page_champion_absent_is_stated_honestly(self):
        _nba, tw, _hbl = snapshots(True)
        for lg in tw["leagues"].values():
            lg.pop("champion_zh", None)
        blob = " ".join(q + a for q, a in _faq_ld(gtw.build_page(tw)))
        self.assertIn("尚未產生", blob, "冠軍缺漏時應誠實說尚未產生，而非沿用舊資料")


# ---------- 原始碼層：不得再有寫死的賽季字面值 ----------

class NoHardcodedSeasonInGeneratorsTests(unittest.TestCase):
    """守生成器原始碼本身：本次修過的四支腳本裡不得再出現舊賽季字面值。
    （封面標題／文章 slug 屬「該篇文章的主題」，不在這四支腳本內，故不受影響。）"""
    FILES = ("build-articles.py", "gen-tw-standings.py",
             "gen-basketball-data-hub.py", "gen-nba-standings.py")

    def test_no_stale_season_literal_in_generator_sources(self):
        for fname in self.FILES:
            src = (ROOT / "scripts" / fname).read_text(encoding="utf-8")
            for lit in ("2025-26", "114學年度"):
                self.assertNotIn(lit, src, f"scripts/{fname} 又把賽季 {lit} 寫死了")


if __name__ == "__main__":
    unittest.main()
