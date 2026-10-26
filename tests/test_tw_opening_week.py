#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""台職開季週回歸（2026-10-26）。

實況：TPBL 10/17、PLG 10/24 開打後十天，fetch-tw-hoops 只替「打過球的隊」產列，
開季 4 場完賽只有 5 隊有紀錄，加上 PLG 回 0 列，合計 5 列對上季終局 11 列跌破 50%，
snapshot_guard 天天拒寫、頁面停在 2025-26 終局（CI run 40301716855 日誌）。

修法三件：①例行賽列由「排定場次」的隊伍集合鋪 0-0 再疊賽果；②同季某源回空表沿用前一份該聯盟資料，
跨季不沿用（上季終局表與冠軍不得掛進新賽季）；③保留近期賽果／賽程（隊伍層）。
跑法：python3 -m unittest discover -s tests -v
"""
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


tw = _load("fetch_tw_hoops_opening", "fetch-tw-hoops.py")
gtw = _load("gen_tw_standings_opening", "gen-tw-standings.py")


def _sched(div, date, home, away, done=False, hs=None, as_=None, time="19:00:00"):
    return {"division_id": div, "game_date": date, "game_time": time,
            "status": "COMPLETED" if done else "NOT_STARTED",
            "venue": {"name": "場館"},
            "home_team": {"name": home, "won_score": hs if done else None},
            "away_team": {"name": away, "won_score": as_ if done else None}}


ROW = {"rank": 1, "team_name": "T", "win": 1, "lose": 0, "pct": "1.000", "games_behind": "—"}
GAME_KEYS = {"date", "time", "home", "away", "home_score", "away_score", "venue", "status"}


class TpblOpeningWeekTests(unittest.TestCase):
    TEAMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚"]

    def _games(self):
        games = [_sched(655, "2026-10-10", "甲", "乙", done=True, hs=90, as_=80)]  # 開季前盃賽 division
        d = 0
        for i, h in enumerate(self.TEAMS):
            for a in self.TEAMS[i + 1:]:
                for _ in range(3):
                    games.append(_sched(656, f"2026-12-{(d % 28) + 1:02d}", h, a))
                    d += 1
        games[1] = _sched(656, "2026-10-17", "甲", "乙", done=True, hs=100, as_=90)
        games[2] = _sched(656, "2026-10-25", "丙", "丁", done=True, hs=70, as_=75)
        games[3] = _sched(656, "2026-10-24", "戊", "己")           # 已過日期但 API 仍未標完賽（實測延遲）
        games[4] = _sched(656, "2026-10-27", "甲", "丙")           # 明天
        games[5] = _sched(656, "2026-11-09", "乙", "丁")           # 7 天外
        return games

    def _fetch(self, today="2026-10-26"):
        games = self._games()

        def fake_curl(url):
            if url.endswith("/seasons"):
                return json.dumps([{"id": 3, "name": "2026-2027 賽季", "started_at": "2026-10-17"}])
            return json.dumps(games)
        with mock.patch.object(tw, "curl", side_effect=fake_curl):
            return tw.fetch_tpbl(today)

    def test_all_scheduled_teams_get_a_row_from_day_one(self):
        season, league, final = self._fetch()
        self.assertEqual(season, "2026-27")
        self.assertFalse(final)
        rows = league["standings"]
        self.assertEqual(len(rows), 7)
        self.assertEqual({r["team_name"] for r in rows[:2]}, {"甲", "丁"})  # 兩個 1-0
        self.assertEqual(sum(1 for r in rows if r["win"] == 0 and r["lose"] == 0), 3)
        self.assertEqual(rows[-1]["pct"], "0.000")
        self.assertEqual(league["regular_season_games"], 2)
        self.assertIsNone(league["champion_zh"])

    def test_recent_and_upcoming_are_team_level_and_windowed(self):
        _, league, _ = self._fetch()
        recent = league["recent_results"]
        # 近 7 天（10/19–10/26）：只有 10/25 那場；10/17 在窗外
        self.assertEqual([(r["home"], r["home_score"], r["away_score"]) for r in recent], [("丙", 70, 75)])
        self.assertEqual([r["date"] for r in league["upcoming"]], ["2026-10-27"])
        for r in recent + league["upcoming"]:
            self.assertEqual(set(r), GAME_KEYS)
            self.assertEqual(r["venue"], "場館")
        lagging = [r for r in recent + league["upcoming"] if r["date"] == "2026-10-24"]
        self.assertEqual(lagging, [])  # 已過日期但未完賽：不列賽果也不列賽程

    def test_games_helper_without_today_is_empty(self):
        self.assertEqual(tw._tpbl_games(self._games(), None), {"recent_results": [], "upcoming": []})

    def test_preseason_only_still_returns_empty_table(self):
        """例行賽一場都沒完賽（只有盃賽完賽）仍是「尚未開打」：不鋪 0-0 列，既有行為不變。"""
        games = [g for g in self._games() if g["status"] != "COMPLETED" or g["division_id"] == 655]

        def fake_curl(url):
            if url.endswith("/seasons"):
                return json.dumps([{"id": 3, "name": "2026-2027 賽季", "started_at": "2026-10-17"}])
            return json.dumps(games)
        with mock.patch.object(tw, "curl", side_effect=fake_curl):
            _, league, _ = tw.fetch_tpbl("2026-10-16")
        self.assertEqual(league["standings"], [])


class TwCarryOverTests(unittest.TestCase):
    def _run(self, previous, tpbl_result, plg_result):
        with tempfile.TemporaryDirectory() as d:
            out_dir = pathlib.Path(d)
            (out_dir / "tw-hoops-2026-10-20.json").write_text(json.dumps(previous), encoding="utf-8")
            old_out = tw.OUT_DIR
            tw.OUT_DIR = out_dir
            try:
                kw_t = ({"side_effect": tpbl_result} if isinstance(tpbl_result, Exception)
                        else {"return_value": tpbl_result})
                kw_p = ({"side_effect": plg_result} if isinstance(plg_result, Exception)
                        else {"return_value": plg_result})
                with mock.patch.object(tw, "fetch_tpbl", **kw_t), \
                     mock.patch.object(tw, "fetch_plg", **kw_p), \
                     mock.patch.object(sys, "argv", ["fetch-tw-hoops.py"]):
                    tw.main()
                files = sorted(out_dir.glob("tw-hoops-*.json"))
                self.assertEqual(len(files), 2, "新快照應已寫入")
                return json.loads(files[-1].read_text(encoding="utf-8"))
            finally:
                tw.OUT_DIR = old_out

    @staticmethod
    def _prev(season, final, plg_rows):
        return {"asof_taipei_date": "2026-10-20", "season": season, "final": final,
                "leagues": {"tpbl": {"name_zh": "TPBL", "standings": [ROW] * 7, "source": "old"},
                            "plg": {"name_zh": "PLG", "champion_zh": "舊冠軍" if final else None,
                                    "standings": plg_rows, "source": "old"}}}

    GOOD_TPBL = ("2026-27", {"name_zh": "TPBL", "standings": [ROW] * 7, "regular_season_games": 3,
                             "recent_results": [], "upcoming": [], "source": "fixture"}, False)
    EMPTY_PLG = {"name_zh": "PLG", "champion_zh": None, "finals_note": "", "standings": [], "source": "尚未刊出"}

    def test_same_season_empty_source_carries_prior_league(self):
        out = self._run(self._prev("2026-27", False, [ROW] * 4), self.GOOD_TPBL, self.EMPTY_PLG)
        self.assertEqual(len(out["leagues"]["plg"]["standings"]), 4)
        self.assertEqual(out["leagues"]["plg"]["carried_from"], "2026-10-20")
        self.assertNotIn("carried_from", out["leagues"]["tpbl"])

    def test_same_season_failed_source_carries_prior_league(self):
        out = self._run(self._prev("2026-27", False, [ROW] * 4), self.GOOD_TPBL, RuntimeError("PLG 403"))
        self.assertEqual(len(out["leagues"]["plg"]["standings"]), 4)
        self.assertEqual(out["leagues"]["plg"]["carried_from"], "2026-10-20")  # 失敗路徑也要揭露

    def test_consecutive_carry_keeps_original_data_date_and_drops_game_lists(self):
        prev = self._prev("2026-27", False, [ROW] * 4)
        prev["leagues"]["plg"]["carried_from"] = "2026-10-18"      # 前一份本身已是沿用品
        prev["leagues"]["tpbl"]["upcoming"] = [{"date": "2026-10-19"}]
        prev["leagues"]["tpbl"]["recent_results"] = []
        out = self._run(prev, RuntimeError("TPBL 逾時"), self.EMPTY_PLG)
        self.assertEqual(out["leagues"]["plg"]["carried_from"], "2026-10-18")   # 不是 10-20
        self.assertEqual(out["leagues"]["tpbl"]["carried_from"], "2026-10-20")
        self.assertNotIn("upcoming", out["leagues"]["tpbl"])      # 過期賽程不帶
        self.assertNotIn("recent_results", out["leagues"]["tpbl"])

    def test_both_sources_down_without_same_season_snapshot_raises(self):
        with tempfile.TemporaryDirectory() as d:
            out_dir = pathlib.Path(d)
            (out_dir / "tw-hoops-2026-07-19.json").write_text(
                json.dumps(self._prev("2025-26", True, [ROW] * 4)), encoding="utf-8")
            old_out = tw.OUT_DIR
            tw.OUT_DIR = out_dir
            try:
                with mock.patch.object(tw, "fetch_tpbl", side_effect=RuntimeError("TPBL 逾時")), \
                     mock.patch.object(tw, "fetch_plg", side_effect=RuntimeError("PLG 403")), \
                     mock.patch.object(sys, "argv", ["fetch-tw-hoops.py"]):
                    with self.assertRaises(RuntimeError):
                        tw.main()
                self.assertEqual(len(list(out_dir.glob("tw-hoops-*.json"))), 1)
            finally:
                tw.OUT_DIR = old_out

    def test_new_season_does_not_inherit_last_season_table_or_champion(self):
        """前一份是上季終局（含冠軍）：新賽季某源失敗或回空，不得把上季表與冠軍掛進新賽季。"""
        for plg_result in (RuntimeError("PLG 403"), self.EMPTY_PLG):
            with self.subTest(plg=type(plg_result).__name__):
                out = self._run(self._prev("2025-26", True, [ROW] * 4), self.GOOD_TPBL, plg_result)
                self.assertEqual(out["season"], "2026-27")
                self.assertEqual(out["leagues"]["plg"]["standings"], [])
                self.assertIsNone(out["leagues"]["plg"].get("champion_zh"))
                self.assertNotIn("carried_from", out["leagues"]["plg"])
                self.assertEqual(len(out["leagues"]["tpbl"]["standings"]), 7)  # 7 ≥ 11×50%，守門放行


class TwPageGamesTests(unittest.TestCase):
    OPENERS = {"tpbl": {"season": "2026-27", "opens": "2026-10-17", "label": "TPBL 2026-27 例行賽"},
               "plg": {"season": "2026-27", "opens": "2026-10-24", "label": "P. LEAGUE+ 2026-27 例行賽"}}

    def test_panel_renders_recent_results_and_upcoming(self):
        g = {"date": "2026-10-25", "time": "17:00", "home": "甲", "away": "乙",
             "home_score": 81, "away_score": 89, "venue": "新莊體育館", "status": "COMPLETED"}
        u = dict(g, date="2026-10-31", home_score=None, away_score=None, status="SCHEDULED")
        panel = gtw.league_panel({"standings": [ROW], "recent_results": [g], "upcoming": [u]},
                                 "2026-27", "2026-10-26", "fixture")
        for needle in ("近期賽果", "81：89", "近期賽程", "2026-10-31", "新莊體育館"):
            self.assertIn(needle, panel)

    def test_panel_without_games_has_no_game_tables(self):
        panel = gtw.league_panel({"standings": [ROW]}, "2026-27", "2026-10-26", "fixture")
        self.assertNotIn("近期賽果", panel)
        self.assertNotIn("近期賽程", panel)

    def test_carried_from_is_disclosed(self):
        panel = gtw.league_panel({"standings": [ROW], "carried_from": "2026-10-20"},
                                 "2026-27", "2026-10-26", "fixture")
        self.assertIn("沿用 2026-10-20", panel)

    def test_started_notice_only_after_opening_day_of_same_season(self):
        import datetime as dt
        with mock.patch.object(gtw.ba, "bb_season_openers", return_value=self.OPENERS):
            self.assertIsNone(gtw.started_notice("plg", "2026-27", dt.date(2026, 10, 23)))
            text = gtw.started_notice("plg", "2026-27", dt.date(2026, 10, 26))
            self.assertIn("已於 2026-10-24 開打", text)
            self.assertIsNone(gtw.started_notice("plg", "2025-26", dt.date(2026, 10, 26)))
        panel = gtw.league_panel({"standings": []}, "2026-27", "2026-10-26", "fixture", started=text)
        self.assertIn("已於 2026-10-24 開打", panel)
        self.assertNotIn("尚未開打", panel)

    def test_tab_label_team_count_derives_from_snapshot(self):
        snap = {"season": "2026-27", "asof_taipei_date": "2026-10-26", "final": False,
                "leagues": {"tpbl": {"name_zh": "TPBL", "standings": [ROW] * 8, "source": "f"},
                            "plg": {"name_zh": "PLG", "standings": [], "source": "f"}}}
        with mock.patch.object(gtw.ba, "bb_season_openers", return_value=self.OPENERS):
            html = gtw.build_page(snap)
        self.assertIn("TPBL（8 隊）", html)
        self.assertIn(">P. LEAGUE+</label>", html)
        self.assertNotIn("4 隊", html.split("<main")[1].split("常見")[0])


if __name__ == "__main__":
    unittest.main()
