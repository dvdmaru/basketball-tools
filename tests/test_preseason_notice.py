#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""開季前提示（2026-10-13）：戰績頁快照仍是上季終局時，標題與頁首要告訴讀者下一季哪天開打。

守的不變量：
  1. 快照 final=True 且 config/season-openers.json 的 season 比快照新 → 標題帶「開打」與下一季標籤，
     頁內有提示段；開打日之前寫「預定」，之後寫「已於」。
  2. 快照 final=False（賽季進行中）→ 完全不出現提示。
  3. config 的 season 不比快照新（開季後快照已換季、或 config 過期）→ 不出現提示；
     config 缺檔或壞檔 → 不出現提示、不報錯。
  4. 提示文字全部由 config 與快照衍生，生成器原始碼不寫死日期（由 test_season_rollover 的字面值掃描兜底）。

跑法：python3 -m unittest discover -s tests -v
"""
import copy
import datetime
import glob
import importlib.util
import json
import pathlib
import re
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ba = _load("build_articles", "build-articles.py")
gnba = _load("gen_nba_standings", "gen-nba-standings.py")
gtw = _load("gen_tw_standings", "gen-tw-standings.py")

OPENERS = {
    "nba": {"season": "2099-00", "opens": "2099-10-21", "label": "NBA 2099-00 賽季例行賽"},
    "tpbl": {"season": "2099-00", "opens": "2099-10-17", "label": "TPBL 2099-00 例行賽"},
    "plg": {"season": "2099-00", "opens": "2099-10-24", "label": "P. LEAGUE+ 2099-00 例行賽"},
}
OLD_SEASON = "2098-99"


def _real(pattern):
    files = sorted(glob.glob(str(ROOT / "leagues" / pattern)))
    if not files:
        raise unittest.SkipTest(f"leagues/ 缺少 {pattern} 快照")
    return json.loads(pathlib.Path(files[-1]).read_text(encoding="utf-8"))


def _title(html):
    return re.search(r"<title>(.*?)</title>", html, re.S).group(1)


class NoticeHelperTests(unittest.TestCase):
    def test_before_opening_says_scheduled(self):
        with mock.patch.object(ba, "bb_season_openers", return_value=OPENERS):
            n = ba.bb_preseason_notice("nba", OLD_SEASON, True, today=datetime.date(2099, 10, 1))
        self.assertIsNotNone(n)
        self.assertIn("預定 2099-10-21 開打", n["text"])
        self.assertIn(OLD_SEASON, n["text"])
        self.assertEqual(n["title_tag"], "2099-00 賽季 10/21 開打")

    def test_after_opening_says_already_opened(self):
        with mock.patch.object(ba, "bb_season_openers", return_value=OPENERS):
            n = ba.bb_preseason_notice("nba", OLD_SEASON, True, today=datetime.date(2099, 10, 25))
        self.assertIn("已於 2099-10-21 開打", n["text"])

    def test_in_season_snapshot_has_no_notice(self):
        with mock.patch.object(ba, "bb_season_openers", return_value=OPENERS):
            self.assertIsNone(ba.bb_preseason_notice("nba", OLD_SEASON, False))

    def test_config_not_newer_than_snapshot_has_no_notice(self):
        with mock.patch.object(ba, "bb_season_openers", return_value=OPENERS):
            self.assertIsNone(ba.bb_preseason_notice("nba", "2099-00", True))   # 快照已換季
            self.assertIsNone(ba.bb_preseason_notice("nba", "2100-01", True))   # config 過期

    def test_missing_or_broken_config_is_silent(self):
        with mock.patch.object(ba, "bb_season_openers", return_value={}):
            self.assertIsNone(ba.bb_preseason_notice("nba", OLD_SEASON, True))
        with mock.patch.object(ba, "bb_season_openers", return_value={"nba": {"season": "2099-00", "opens": "not-a-date"}}):
            self.assertIsNone(ba.bb_preseason_notice("nba", OLD_SEASON, True))
        with mock.patch.object(ba, "bb_season_openers", return_value={"nba": {"season": "2099-00"}}):
            self.assertIsNone(ba.bb_preseason_notice("nba", OLD_SEASON, True))

    def test_real_config_parses(self):
        cfg = ba.bb_season_openers()
        self.assertTrue(cfg, "config/season-openers.json 讀不到")
        for key in ("nba", "tpbl", "plg"):
            self.assertIn(key, cfg)
            datetime.date.fromisoformat(cfg[key]["opens"])
            self.assertRegex(cfg[key]["season"], r"^\d{4}-\d{2}$")


class StandingsPageTests(unittest.TestCase):
    # ⚠️ 各產生器用 importlib 各自載入一份 build-articles，要 patch 它們手上的那份（gnba.ba／gtw.ba），
    #    patch 本檔的 ba 對頁面沒有作用。
    def _nba(self, final):
        snap = copy.deepcopy(_real("nba-standings-*.json"))
        snap["season"] = OLD_SEASON
        snap["final"] = final
        with mock.patch.object(gnba.ba, "bb_season_openers", return_value=OPENERS):
            return gnba.build_page(snap)

    def _tw(self, final):
        snap = copy.deepcopy(_real("tw-hoops-*.json"))
        snap["season"] = OLD_SEASON
        snap["final"] = final
        with mock.patch.object(gtw.ba, "bb_season_openers", return_value=OPENERS):
            return gtw.build_page(snap)

    def test_nba_offseason_title_and_notice(self):
        html = self._nba(True)
        self.assertIn("2099-00 賽季 10/21 開打", _title(html))
        self.assertIn(OLD_SEASON + " 終局", _title(html))
        self.assertIn('class="tbl-cap preseason"', html)
        self.assertIn("2099-10-21", html)

    def test_nba_in_season_has_no_notice(self):
        html = self._nba(False)
        self.assertNotIn("開打", _title(html))
        self.assertNotIn('preseason"', html)
        self.assertNotIn("2099-10-21", html)

    def test_tw_offseason_title_uses_earliest_league_and_each_panel_has_own_date(self):
        html = self._tw(True)
        self.assertIn("2099-00 賽季 10/17 開打起", _title(html))
        self.assertIn("2099-10-17", html)   # TPBL 面板
        self.assertIn("2099-10-24", html)   # PLG 面板
        self.assertEqual(html.count('class="tbl-cap preseason"'), 2)

    def test_tw_in_season_has_no_notice(self):
        html = self._tw(False)
        self.assertNotIn("開打", _title(html))
        self.assertNotIn('preseason"', html)

    def test_jsonld_name_matches_title(self):
        html = self._nba(True)
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        names = [n.get("name") for b in blocks for n in json.loads(b).get("@graph", [])
                 if n.get("@type") == "CollectionPage"]
        self.assertEqual(names, [_title(html).split(" | ")[0]])


if __name__ == "__main__":
    unittest.main()
