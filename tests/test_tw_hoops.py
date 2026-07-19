#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fixture-based 測試——2026-07-19 外部審查 P0/P1 的回歸保護。

不打網路：只測 fetch-tw-hoops.py / fetch-nba.py 的純函式。
跑法：python3 -m unittest discover -s tests -v
"""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


tw = _load("fetch_tw_hoops", "fetch-tw-hoops.py")


def _game(div, date, home, hs, away, as_):
    return {"division_id": div, "game_date": date,
            "home_team": {"name": home, "won_score": hs},
            "away_team": {"name": away, "won_score": as_}}


class TestStandingsSort(unittest.TestCase):
    def test_win_pct_beats_raw_wins_when_games_uneven(self):
        # 出賽數不齊：10-2（.833）必須排在 11-10（.524）前面
        rows = tw._standings_rows({"多打隊": [11, 10], "少打隊": [10, 2]})
        self.assertEqual([r["team_name"] for r in rows], ["少打隊", "多打隊"])
        self.assertEqual(rows[0]["rank"], 1)

    def test_equal_pct_falls_back_to_more_wins(self):
        rows = tw._standings_rows({"甲": [5, 5], "乙": [10, 10]})
        self.assertEqual(rows[0]["team_name"], "乙")


class TestTpblFinalsGuard(unittest.TestCase):
    def test_regular_only_division_never_yields_champion(self):
        # 開季初只有例行賽 division：即使有隊已 4 勝也不得判冠軍
        games = [_game(1, f"2026-11-0{i}", "A", 90, "B", 80) for i in range(1, 6)]
        by_div = {1: games}
        champ, note = tw._tpbl_finals(by_div, reg_div=1)
        self.assertIsNone(champ)
        self.assertEqual(note, "")

    def test_finals_under_four_wins_no_champion(self):
        by_div = {1: [_game(1, "2026-11-01", "A", 90, "B", 80)] * 20,
                  2: [_game(2, "2027-06-01", "A", 90, "B", 80),
                      _game(2, "2027-06-03", "B", 95, "A", 90)]}
        champ, _ = tw._tpbl_finals(by_div, reg_div=1)
        self.assertIsNone(champ)

    def test_valid_finals_series_yields_champion(self):
        finals = ([_game(2, f"2027-06-0{i}", "A", 90, "B", 80) for i in (1, 3, 5, 9)]
                  + [_game(2, "2027-06-07", "B", 88, "A", 70)] * 3)
        by_div = {1: [_game(1, "2026-11-01", "A", 90, "B", 80)] * 20, 2: finals}
        champ, note = tw._tpbl_finals(by_div, reg_div=1)
        self.assertEqual(champ, "A")
        self.assertEqual(note, "總冠軍賽 4:3 勝B")

    def test_multi_team_division_is_not_finals(self):
        by_div = {1: [_game(1, "2026-11-01", "A", 90, "B", 80)] * 20,
                  2: [_game(2, "2027-06-01", "A", 90, "B", 80),
                      _game(2, "2027-06-02", "C", 90, "A", 80),
                      _game(2, "2027-06-03", "A", 90, "C", 80),
                      _game(2, "2027-06-04", "A", 90, "B", 80)]}
        champ, _ = tw._tpbl_finals(by_div, reg_div=1)
        self.assertIsNone(champ)


class TestSeasonFactsGuard(unittest.TestCase):
    FACTS = {"season": "2025-26", "champion_zh": "桃園璞園領航猿"}

    def test_matching_season_applies(self):
        self.assertEqual(tw._guard_season_facts(dict(self.FACTS), "2025-26")
                         .get("champion_zh"), "桃園璞園領航猿")

    def test_mismatched_season_drops_champion(self):
        self.assertEqual(tw._guard_season_facts(dict(self.FACTS), "2026-27"), {})

    def test_empty_facts_pass_through(self):
        self.assertEqual(tw._guard_season_facts({}, "2026-27"), {})


class TestNbaDefaultSeason(unittest.TestCase):
    def test_default_season_by_month(self):
        nba = _load("fetch_nba", "fetch-nba.py")
        import datetime as real_dt

        class FakeDate(real_dt.date):
            _today = None

            @classmethod
            def today(cls):
                return cls._today

        orig = nba.datetime.date
        try:
            nba.datetime.date = FakeDate
            FakeDate._today = real_dt.date(2026, 7, 19)
            self.assertEqual(nba.default_season(), 2026)  # 休賽季 → 剛結束的 2025-26
            FakeDate._today = real_dt.date(2026, 10, 25)
            self.assertEqual(nba.default_season(), 2027)  # 開季後 → 2026-27
        finally:
            nba.datetime.date = orig


if __name__ == "__main__":
    unittest.main()
