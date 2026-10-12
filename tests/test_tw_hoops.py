#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fixture-based 測試——2026-07-19 外部審查 P0/P1 的回歸保護。

不打網路：只測 fetch-tw-hoops.py / fetch-nba.py 的純函式。
跑法：python3 -m unittest discover -s tests -v
"""
import importlib.util
import gzip
import json
import pathlib
import subprocess
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


tw = _load("fetch_tw_hoops", "fetch-tw-hoops.py")
nba = _load("fetch_nba", "fetch-nba.py")
hbl = _load("fetch_hbl", "fetch-hbl.py")
gtw = _load("gen_tw_standings_for_empty", "gen-tw-standings.py")


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


def _nba_standings(season_type, wins=0, losses=0):
    children = []
    for conference, prefix in (("Eastern Conference", "E"), ("Western Conference", "W")):
        entries = []
        for i in range(15):
            entries.append({"team": {"displayName": f"{prefix}{i}", "abbreviation": f"{prefix}{i}"},
                            "stats": [{"name": "playoffSeed", "displayValue": str(i + 1)},
                                      {"name": "wins", "displayValue": str(wins if i == 0 else 0)},
                                      {"name": "losses", "displayValue": str(losses if i == 0 else 0)},
                                      {"name": "winPercent", "displayValue": ".000"},
                                      {"name": "gamesBehind", "displayValue": "-"}]})
        children.append({"name": conference, "standings": {"seasonType": season_type, "entries": entries}})
    return {"children": children}


class TestNbaFetchGuards(unittest.TestCase):
    def test_call_decodes_gzip_body_even_if_curl_leaves_it_compressed(self):
        raw = gzip.compress(json.dumps({"ok": True}).encode("utf-8"))
        with mock.patch.object(nba.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, stdout=raw)):
            self.assertEqual(nba.call("https://example.test", tries=1), {"ok": True})

    def test_preseason_type_one_is_not_regular_season(self):
        fixture = _nba_standings(1, wins=2, losses=0)
        self.assertFalse(nba.regular_season_has_completed_game(fixture))
        with tempfile.TemporaryDirectory() as d:
            old_out = nba.OUT_DIR
            nba.OUT_DIR = pathlib.Path(d)
            try:
                with mock.patch.object(nba, "call", return_value=fixture), \
                     mock.patch.object(sys, "argv", ["fetch-nba.py", "--season", "2027"]):
                    nba.main()
                self.assertFalse(list(pathlib.Path(d).glob("nba-standings-*.json")))
            finally:
                nba.OUT_DIR = old_out

    def test_regular_season_type_two_with_completed_game_writes(self):
        fixture = _nba_standings(2, wins=1, losses=0)
        self.assertTrue(nba.regular_season_has_completed_game(fixture))
        with tempfile.TemporaryDirectory() as d:
            old_out = nba.OUT_DIR
            nba.OUT_DIR = pathlib.Path(d)
            try:
                with mock.patch.object(nba, "call", side_effect=[fixture, {"events": []}]), \
                     mock.patch.object(sys, "argv", ["fetch-nba.py", "--season", "2027"]):
                    nba.main()
                self.assertTrue((pathlib.Path(d) / "nba-standings-2026-27.json").exists())
            finally:
                nba.OUT_DIR = old_out


class TestTwPreseasonAndIsolation(unittest.TestCase):
    def test_empty_league_panel_says_not_started_not_in_progress(self):
        panel = gtw.league_panel({"standings": []}, "2026-27", "2026-10-12", "fixture", final=False)
        self.assertIn("尚未開打", panel)
        self.assertNotIn("例行賽進行中", panel)

    def test_tpbl_zero_games_is_a_valid_not_started_snapshot(self):
        def fake_curl(url):
            if url.endswith("/seasons"):
                return json.dumps([{"id": 3, "name": "2026-2027 賽季", "started_at": "2026-10-01"}])
            return "[]"
        with mock.patch.object(tw, "curl", side_effect=fake_curl):
            season, league, final = tw.fetch_tpbl()
        self.assertEqual(season, "2026-27")
        self.assertFalse(final)
        self.assertEqual(league["regular_season_games"], 0)
        self.assertEqual(league["standings"], [])

    def test_plg_zero_rows_is_a_valid_not_started_snapshot(self):
        with mock.patch.object(tw, "curl", return_value="<table><tr><th>排行</th></tr></table>"):
            league = tw.fetch_plg("2026-27")
        self.assertEqual(league["standings"], [])
        self.assertIn("尚未刊出", league["source"])

    def test_plg_all_zero_table_is_not_published_as_standings(self):
        row = "<tr><td>1</td><td>領航猿</td><td>0</td><td>0</td><td>0</td></tr>"
        html = "<table>" + row * 4 + "</table>"
        with mock.patch.object(tw, "curl", return_value=html) as curl:
            league = tw.fetch_plg("2026-27")
        self.assertIn("/standings/2026-27", curl.call_args.args[0])
        self.assertEqual(league["standings"], [])
        self.assertIn("尚無已完成", league["source"])

    def test_one_source_failure_does_not_prevent_other_source_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            out_dir = pathlib.Path(d)
            previous = {
                "asof_taipei_date": "2026-10-11", "season": "2026-27", "final": False,
                "leagues": {
                    "tpbl": {"name_zh": "TPBL", "standings": [], "source": "old"},
                    "plg": {"name_zh": "PLG", "standings": [], "source": "old"},
                },
            }
            (out_dir / "tw-hoops-2026-10-11.json").write_text(json.dumps(previous), encoding="utf-8")
            old_out = tw.OUT_DIR
            tw.OUT_DIR = out_dir
            try:
                # 成功的那一源要有實際戰績列：雙方都空表時 main() 會視為「開季前」略過不寫，
                # 那是另一個案例（見 tw_skip 註解）；這裡測的是「一源失敗不拖垮另一源」。
                row = {"rank": 1, "team_name": "T", "win": 1, "lose": 0, "pct": "1.000", "games_behind": "—"}
                good_tpbl = ("2026-27", {"name_zh": "TPBL", "standings": [row],
                                           "regular_season_games": 1, "source": "fixture"}, False)
                good_plg = {"name_zh": "PLG", "standings": [row], "source": "fixture"}
                with self.subTest(source="TPBL"), \
                     mock.patch.object(tw, "fetch_tpbl", side_effect=RuntimeError("TPBL 逾時")), \
                     mock.patch.object(tw, "fetch_plg", return_value=good_plg), \
                     mock.patch.object(sys, "argv", ["fetch-tw-hoops.py"]):
                    tw.main()
                with self.subTest(source="PLG"), \
                     mock.patch.object(tw, "fetch_tpbl", return_value=good_tpbl), \
                     mock.patch.object(tw, "fetch_plg", side_effect=RuntimeError("PLG 改版")), \
                     mock.patch.object(sys, "argv", ["fetch-tw-hoops.py"]):
                    tw.main()
                self.assertGreaterEqual(len(list(out_dir.glob("tw-hoops-*.json"))), 2)
            finally:
                tw.OUT_DIR = old_out


class TestHblNewApi(unittest.TestCase):
    def test_new_navigation_api_finds_115_and_allows_no_division_yet(self):
        fixture = {"site": {"additional": {"leagues": [{"id": 1, "seasons": [
            {"name": "114學年度", "events": []},
            {"name": "115學年度", "events": [{"name": "高中籃球甲級聯賽男生組", "divisions": []}]},
        ]}]}}}
        name, season = hbl.latest_season(fixture)
        self.assertEqual(name, 115)
        self.assertEqual(hbl.finals_stage_sns(season), {})

    def test_new_division_match_shape_produces_final_four(self):
        games = [
            {"status": "COMPLETED", "matchedAt": "2026-03-21T01:00:00Z", "homeSquad": {"name": "A"}, "awaySquad": {"name": "B"}, "homeScore": 80, "awayScore": 70},
            {"status": "COMPLETED", "matchedAt": "2026-03-21T03:00:00Z", "homeSquad": {"name": "C"}, "awaySquad": {"name": "D"}, "homeScore": 75, "awayScore": 65},
            {"status": "COMPLETED", "matchedAt": "2026-03-22T01:00:00Z", "homeSquad": {"name": "B"}, "awaySquad": {"name": "D"}, "homeScore": 77, "awayScore": 70},
            {"status": "COMPLETED", "matchedAt": "2026-03-22T03:00:00Z", "homeSquad": {"name": "A"}, "awaySquad": {"name": "C"}, "homeScore": 88, "awayScore": 82},
        ]
        with mock.patch.object(hbl, "call", return_value=games) as call:
            result = hbl.rank_division(703, "男子甲級")
        call.assert_called_once_with(f"{hbl.BASE}/api/division-matches/703")
        self.assertEqual(result["champion"], "A")
        self.assertEqual([x["school"] for x in result["final_four"]], ["A", "C", "B", "D"])


if __name__ == "__main__":
    unittest.main()

class TpblPreseasonDivisionTests(unittest.TestCase):
    def test_completed_preseason_division_is_not_published_as_regular_season(self):
        """2026-27 實況：division 655 有 7 場 10/9–10/11 已完賽（熱身／盃賽），
        division 656 排定 126 場但一場都還沒打。例行賽要用排定場次最多的 division 判，
        不能用已完成場次最多的——否則熱身賽戰績會被當例行賽貼上線。"""
        def game(gid, div, done):
            g = {"id": gid, "division_id": div, "status": "COMPLETED" if done else "SCHEDULED",
                 "game_date": "2026-10-10" if done else "2026-10-17",
                 "home_team": {"name": f"H{gid % 7}", "won_score": 90 if done else None},
                 "away_team": {"name": f"A{gid % 7}", "won_score": 80 if done else None}}
            return g
        games = [game(i, 655, True) for i in range(7)] + [game(100 + i, 656, False) for i in range(126)]
        def fake_curl(url):
            if url.endswith("/seasons"):
                return json.dumps([{"id": 3, "name": "2026-2027 賽季", "started_at": "2026-10-01"}])
            return json.dumps(games)
        with mock.patch.object(tw, "curl", side_effect=fake_curl):
            season, league, final = tw.fetch_tpbl()
        self.assertEqual(season, "2026-27")
        self.assertFalse(final)
        self.assertEqual(league["standings"], [])
        self.assertEqual(league["regular_season_games"], 0)
