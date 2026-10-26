#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NBA 近三日賽程的桶標題只放絕對日期＋星期，不寫「今天／昨天」（2026-10-27）。

為什麼：頁面一天只 build 一次（台北 12:00）。相對標籤在 build 當下是對的，
過了午夜到下一次 build 之間就全錯——而那正是 NBA 台北早上開打、最多人看比分的時段。
10/27 00:10 首頁寫著「今天 2026-10-26」。改絕對日期後，頁面上沒有任何會隨時鐘過期的字。
跑法：python3 -m unittest discover -s tests -v
"""
import datetime
import importlib.util
import json
import pathlib
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "nba"


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ba = _load("build_articles_date_labels", "build-articles.py")
SNAP = json.loads((FIX / "nba-games-2026-10-26.json").read_text(encoding="utf-8"))


class GamesDateLabelTests(unittest.TestCase):
    def test_bucket_titles_are_absolute_dates_with_weekday(self):
        html = ba.bb_nba_games_html(SNAP)
        # fixture 三桶＝10/25（日）、10/26（一）、10/27（二）
        self.assertIn("<h4>2026-10-25（日）<span", html)
        self.assertIn("<h4>2026-10-26（一）<span", html)
        self.assertIn("<h4>2026-10-27（二）<span", html)

    def test_no_relative_day_words_anywhere(self):
        for compact in (False, True):
            html = ba.bb_nba_games_html(SNAP, compact=compact)
            for word in ("今天", "昨天", "明天", "今日", "昨日"):
                self.assertNotIn(word, html, f"compact={compact} 仍含「{word}」")

    def test_labels_do_not_depend_on_wall_clock(self):
        """同一份快照，不管 build 在哪一天跑，輸出一個字都不能變。"""
        class _FakeDT(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 27, 0, 10, tzinfo=tz)
        with mock.patch.object(ba.datetime, "datetime", _FakeDT):
            after_midnight = ba.bb_nba_games_html(SNAP)
        self.assertEqual(after_midnight, ba.bb_nba_games_html(SNAP))

    def test_caption_states_update_cadence(self):
        html = ba.bb_nba_games_html(SNAP)
        self.assertIn("每日約 12:00 更新一次", html)
        self.assertIn("不是即時比分", html)
        self.assertIn("快照後才打完的比賽要等下一次更新", html)
        self.assertIn("快照 2026-10-26", html)

    def test_unparseable_date_falls_back_to_raw_text(self):
        snap = {"days": [{"date": "n/a", "games": []}], "asof_taipei_date": "2026-10-26", "asof_taipei_time": "12:05"}
        html = ba.bb_nba_games_html(snap)
        self.assertIn("<h4>n/a<span", html)
        self.assertIn("沒有比賽", html)


if __name__ == "__main__":
    unittest.main()
