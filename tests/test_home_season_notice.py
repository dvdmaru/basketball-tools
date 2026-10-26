#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""首頁戰績分頁的「已開打仍為上季名次」提示（2026-10-26）。

/tw/ 與 /standings/ 自 PR #76 起，在快照仍是上季終局、config/season-openers.json 登記了新一季時，
會標出「預定 X 開打」或「已於 X 開打；本頁目前仍是上季終局名次」。首頁分頁沒有這一列——
CI 抓取失敗或 snapshot_guard 拒寫時，首頁會把上季終局表安靜地當成本季名次（2026-10-26 審視發現）。

本檔驗三件：①上季終局快照＋已過開季日 → TPBL／PLG／NBA 分頁頂端都有「已於…開打；仍是…終局名次」；
②開季日未到 → 寫「預定…開打」；③新賽季快照裡某聯盟標 carried_from → 註明沿用日期，沒標的聯盟不出現，
正常新賽季快照兩種提示都不得出現。
跑法：python3 -m unittest discover -s tests -v
"""
import copy
import datetime
import functools
import glob
import importlib.util
import json
import pathlib
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ba = _load("build_articles_home_notice", "build-articles.py")
SITE = ba.SITES["basketball"]

OPENERS = {
    "nba": {"season": "2026-27", "opens": "2026-10-21", "label": "NBA 2026-27 賽季例行賽"},
    "tpbl": {"season": "2026-27", "opens": "2026-10-17", "label": "TPBL 2026-27 例行賽"},
    "plg": {"season": "2026-27", "opens": "2026-10-24", "label": "P. LEAGUE+ 2026-27 例行賽"},
}


def _real(pattern):
    files = sorted(glob.glob(str(ROOT / "leagues" / pattern)))
    if not files:
        raise unittest.SkipTest(f"leagues/ 缺少 {pattern} 快照")
    return json.loads(pathlib.Path(files[-1]).read_text(encoding="utf-8"))


def _final_snapshots():
    """上季（2025-26）終局的真實快照 deep-copy；season／final 維持原樣。"""
    nba, tw, hbl = _real("nba-standings-*.json"), _real("tw-hoops-*.json"), _real("hbl-[0-9]*.json")
    nba, tw, hbl = copy.deepcopy(nba), copy.deepcopy(tw), copy.deepcopy(hbl)
    for s in (nba, tw):
        s["season"] = "2025-26"
        s["final"] = True
    return nba, tw, hbl


def _patch(nba, tw, hbl, today):
    def fake(pattern):
        if pattern.startswith("nba-standings"):
            return nba
        if pattern.startswith("tw-hoops"):
            return tw
        if pattern.startswith("hbl-"):
            return hbl
        return None
    fixed = functools.partial(ba.bb_preseason_notice, today=today)
    return (mock.patch.object(ba, "_dash_latest", fake),
            mock.patch.object(ba, "bb_season_openers", lambda: OPENERS),
            mock.patch.object(ba, "bb_preseason_notice", fixed))


def _render(nba, tw, hbl, today):
    p1, p2, p3 = _patch(nba, tw, hbl, today)
    with p1, p2, p3:
        return ba.render_sport_index([], SITE, "籃球")


def _panel(html, tid):
    """取出 id="p-<tid>" 分頁的內文（到下一個 panel 或 section 結束為止）。"""
    start = html.index(f'<div class="panel" id="p-{tid}">')
    nxt = html.find('<div class="panel" id="p-', start + 10)
    end = nxt if nxt != -1 else html.index("</section>", start)
    return html[start:end]


class StaleFinalSnapshotTests(unittest.TestCase):
    def test_started_notice_on_every_tab_when_season_opened(self):
        nba, tw, hbl = _final_snapshots()
        html = _render(nba, tw, hbl, datetime.date(2026, 10, 26))
        self.assertIn("TPBL 2026-27 例行賽已於 2026-10-17 開打；本頁目前仍是 2025-26 賽季終局名次", _panel(html, "tpbl"))
        self.assertIn("P. LEAGUE+ 2026-27 例行賽已於 2026-10-24 開打；本頁目前仍是 2025-26 賽季終局名次", _panel(html, "plg"))
        self.assertIn("NBA 2026-27 賽季例行賽已於 2026-10-21 開打；本頁目前仍是 2025-26 賽季終局名次", _panel(html, "nba"))

    def test_notice_sits_above_the_table(self):
        nba, tw, hbl = _final_snapshots()
        html = _render(nba, tw, hbl, datetime.date(2026, 10, 26))
        panel = _panel(html, "tpbl")
        self.assertLess(panel.index('class="tbl-cap preseason"'), panel.index("<table"))

    def test_pre_opener_notice_says_scheduled(self):
        nba, tw, hbl = _final_snapshots()
        html = _render(nba, tw, hbl, datetime.date(2026, 10, 10))
        self.assertIn("TPBL 2026-27 例行賽預定 2026-10-17 開打；本頁目前仍是 2025-26 賽季終局名次", _panel(html, "tpbl"))
        self.assertNotIn("已於", _panel(html, "tpbl"))

    def test_no_notice_when_openers_not_newer_than_snapshot(self):
        nba, tw, hbl = _final_snapshots()
        for s in (nba, tw):
            s["season"] = "2026-27"  # 快照已是登記的那一季：提示必須消失
        html = _render(nba, tw, hbl, datetime.date(2026, 10, 26))
        self.assertNotIn("本頁目前仍是", html)


class NewSeasonSnapshotTests(unittest.TestCase):
    def _new_season(self):
        nba, tw, hbl = _final_snapshots()
        for s in (nba, tw):
            s["season"] = "2026-27"
            s["final"] = False
            s.pop("champion_zh", None)
            s.pop("champion_en", None)
            s.pop("finals_note", None)
        for lg in tw["leagues"].values():
            lg.pop("champion_zh", None)
            lg.pop("finals_note", None)
        return nba, tw, hbl

    def test_carried_from_is_disclosed_only_on_that_league(self):
        nba, tw, hbl = self._new_season()
        tw["leagues"]["tpbl"]["carried_from"] = "2026-10-25"
        html = _render(nba, tw, hbl, datetime.date(2026, 10, 26))
        self.assertIn("本季戰績沿用 2026-10-25 的快照（本次未自官網取得新資料）", _panel(html, "tpbl"))
        self.assertNotIn("沿用", _panel(html, "plg"))
        self.assertNotIn("本頁目前仍是", html)

    def test_clean_new_season_has_no_notice(self):
        nba, tw, hbl = self._new_season()
        html = _render(nba, tw, hbl, datetime.date(2026, 10, 26))
        self.assertNotIn("本頁目前仍是", html)
        self.assertNotIn("本季戰績沿用", html)
        self.assertNotIn('class="tbl-cap preseason"', html)


if __name__ == "__main__":
    unittest.main()
