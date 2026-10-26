#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NBA 近三日賽程（台北時間）與 NBA Cup 小組賽戰績（2026-10-26 新增）。

不打網路：fetch 端用 ESPN 形狀的 fixture；頁面端用 tests/fixtures/nba/ 的實抓樣本。
跑法：python3 -m unittest discover -s tests -v
"""
import copy
import datetime
import importlib.util
import json
import pathlib
import re
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "nba"


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


games_mod = _load("fetch_nba_games_t", "fetch-nba-games.py")
cup_mod = _load("fetch_nba_cup_t", "fetch-nba-cup.py")
gen_cup = _load("gen_nba_cup_t", "gen-nba-cup.py")
gen_std = _load("gen_nba_standings_t", "gen-nba-standings.py")
ub = _load("update_basketball_t", "update-basketball.py")
ba = gen_std.ba

CUP_CFG = json.loads((ROOT / "config" / "nba-cup-2026.json").read_text(encoding="utf-8"))
ZH = {"Denver Nuggets": "丹佛金塊", "Houston Rockets": "休士頓火箭", "Phoenix Suns": "鳳凰城太陽",
      "Dallas Mavericks": "達拉斯獨行俠", "Utah Jazz": "猶他爵士"}
NAMES = {"DEN": "Denver Nuggets", "HOU": "Houston Rockets", "PHX": "Phoenix Suns",
         "DAL": "Dallas Mavericks", "UTAH": "Utah Jazz"}


def espn_event(eid, when_utc, home, away, hs=None, as_=None, periods=4, cup=True, home_ls=None, away_ls=None):
    done = hs is not None

    def comp(abbr, score, ha, ls):
        return {"homeAway": ha, "score": str(score) if score is not None else "0",
                "team": {"abbreviation": abbr, "displayName": NAMES.get(abbr, abbr)},
                "linescores": [{"value": float(v)} for v in (ls or [])]}
    return {"id": str(eid), "date": when_utc, "shortName": f"{away} @ {home}",
            "competitions": [{
                "competitors": [comp(home, hs, "home", home_ls), comp(away, as_, "away", away_ls)],
                "status": {"period": periods if done else 0,
                           "type": {"completed": done, "state": "post" if done else "pre", "name": "STATUS_FINAL" if done else "STATUS_SCHEDULED"}},
                "notes": [{"headline": "NBA Cup - Group Play"}] if cup else [],
                "venue": {"fullName": "Arena"},
            }]}


class CupStandingsTests(unittest.TestCase):
    def _groups(self, events):
        rows = [cup_mod.game_row(e, ZH) for e in events]
        zh_by = {}
        for r in rows:
            zh_by[r["home_abbr"]] = r["home_zh"]
            zh_by[r["away_abbr"]] = r["away_zh"]
        return cup_mod.build_groups(CUP_CFG, rows, zh_by)

    def test_config_is_six_groups_of_five_unique_teams(self):
        abbrs = [t for g in CUP_CFG["groups"] for t in g["teams"]]
        self.assertEqual(len(CUP_CFG["groups"]), 6)
        self.assertEqual(len(abbrs), 30)
        self.assertEqual(len(set(abbrs)), 30)

    def test_live_fixture_has_every_cup_game_inside_one_group(self):
        snap = json.loads((FIX / "nba-cup-2026-27.json").read_text(encoding="utf-8"))
        self.assertEqual(snap["unassigned"], [])
        self.assertEqual([len(g["games"]) for g in snap["groups"]], [10] * 6)
        self.assertEqual(sum(len(g["games"]) for g in snap["groups"]), 60)

    def test_regulation_diff_and_ot_rule(self):
        # DEN 勝 HOU 110-100（正規）；PHX 勝 DAL 120-118（OT：前四節 108-108）→ 淨勝分記 0、得分只算前四節
        events = [espn_event(1, "2026-10-30T23:00Z", "DEN", "HOU", 110, 100, home_ls=[30, 30, 25, 25], away_ls=[25, 25, 25, 25]),
                  espn_event(2, "2026-10-31T02:00Z", "PHX", "DAL", 120, 118, periods=5,
                             home_ls=[27, 27, 27, 27, 12], away_ls=[27, 27, 27, 27, 10])]
        groups, unassigned = self._groups(events)
        self.assertEqual(unassigned, [])
        wa = next(g for g in groups if g["name"] == "West A")
        rec = {r["abbr"]: r for r in wa["standings"]}
        self.assertEqual((rec["DEN"]["wins"], rec["DEN"]["diff"], rec["DEN"]["points"]), (1, 10, 110))
        self.assertEqual((rec["HOU"]["losses"], rec["HOU"]["diff"]), (1, -10))
        self.assertEqual((rec["PHX"]["wins"], rec["PHX"]["diff"], rec["PHX"]["points"]), (1, 0, 108))
        self.assertEqual((rec["DAL"]["losses"], rec["DAL"]["diff"], rec["DAL"]["points"]), (1, 0, 108))
        self.assertEqual(wa["standings"][0]["abbr"], "DEN")   # 同 1 勝，淨勝分 10 > 0
        self.assertTrue(wa["games"][1]["ot"])
        self.assertEqual(rec["UTAH"]["played"], 0)
        self.assertEqual(wa["tie_note"], "")   # 0-0、0-1 混在一起不是真同分

    def test_two_way_tie_uses_head_to_head_before_diff(self):
        # HOU 淨勝分高，但 DEN 對 HOU 直接對戰贏 → DEN 在前
        events = [espn_event(1, "2026-10-30T23:00Z", "DEN", "HOU", 101, 100, home_ls=[25, 25, 25, 26], away_ls=[25, 25, 25, 25]),
                  espn_event(2, "2026-11-06T23:00Z", "HOU", "PHX", 130, 100, home_ls=[32, 33, 32, 33], away_ls=[25, 25, 25, 25]),
                  espn_event(3, "2026-11-06T23:30Z", "DEN", "DAL", 100, 99, home_ls=[25, 25, 25, 25], away_ls=[25, 25, 25, 24])]
        groups, _ = self._groups(events)
        wa = next(g for g in groups if g["name"] == "West A")
        self.assertEqual([r["abbr"] for r in wa["standings"][:2]], ["DEN", "HOU"])
        self.assertEqual(wa["tie_note"], "")

    def test_in_progress_ranking_uses_win_pct_not_raw_wins(self):
        # UTAH 1-0（+20）、PHX 1-1（+10）、DEN 1-0（+1）：1-0 的兩隊都要排在 1-1 前面；DEN 與 UTAH 同 1-0 看淨勝分
        events = [espn_event(1, "2026-10-30T23:00Z", "UTAH", "HOU", 120, 100, home_ls=[30] * 4, away_ls=[25] * 4),
                  espn_event(2, "2026-11-06T23:00Z", "PHX", "DAL", 110, 100, home_ls=[28, 28, 27, 27], away_ls=[25] * 4),
                  espn_event(3, "2026-11-13T23:00Z", "DEN", "PHX", 101, 100, home_ls=[25, 25, 25, 26], away_ls=[25] * 4)]
        groups, _ = self._groups(events)
        wa = next(g for g in groups if g["name"] == "West A")
        self.assertEqual([r["abbr"] for r in wa["standings"][:3]], ["UTAH", "DEN", "PHX"])
        self.assertEqual(wa["tie_note"], "")  # UTAH/DEN 同 1-0 恰兩隊、無對戰 → 不標

    def test_ot_without_linescores_is_not_counted_into_points(self):
        events = [espn_event(1, "2026-10-30T23:00Z", "DEN", "HOU", 110, 108, periods=5)]  # 沒有 linescores
        groups, _ = self._groups(events)
        wa = next(g for g in groups if g["name"] == "West A")
        rec = {r["abbr"]: r for r in wa["standings"]}
        self.assertEqual((rec["DEN"]["wins"], rec["DEN"]["diff"], rec["DEN"]["points"]), (1, 0, 0))
        self.assertIn("缺分節資料", wa["tie_note"])

    def test_knockout_games_and_out_of_window_games_are_not_group_play(self):
        ev = espn_event(1, "2026-12-05T00:00Z", "DEN", "HOU")
        ev["competitions"][0]["notes"] = [{"headline": "NBA Cup - Quarterfinals"}]
        self.assertFalse(cup_mod.is_cup(ev, CUP_CFG))
        ev2 = espn_event(2, "2026-10-31T00:00Z", "DEN", "HOU")      # 美東 10/30 晚 → 窗內
        self.assertTrue(cup_mod.is_cup(ev2, CUP_CFG))
        ev3 = espn_event(3, "2026-12-01T00:00Z", "DEN", "HOU")      # 美東 11/30 → 窗外
        self.assertFalse(cup_mod.is_cup(ev3, CUP_CFG))

    def test_postponed_game_is_not_scheduled(self):
        ev = espn_event(1, "2026-10-31T00:00Z", "DEN", "HOU")
        ev["competitions"][0]["status"]["type"].update({"name": "STATUS_POSTPONED", "state": "post"})
        self.assertEqual(cup_mod.game_row(ev, ZH)["status"], "POSTPONED")
        self.assertEqual(games_mod.game_row(ev, ZH)["status"], "POSTPONED")
        self.assertIsNone(games_mod.game_row(ev, ZH)["home_score"])

    def test_three_way_tie_is_flagged_not_resolved(self):
        events = [espn_event(1, "2026-10-30T23:00Z", "DEN", "HOU", 100, 90, home_ls=[25] * 4, away_ls=[22, 22, 23, 23]),
                  espn_event(2, "2026-11-06T23:00Z", "HOU", "PHX", 100, 90, home_ls=[25] * 4, away_ls=[22, 22, 23, 23]),
                  espn_event(3, "2026-11-13T23:00Z", "PHX", "DEN", 100, 90, home_ls=[25] * 4, away_ls=[22, 22, 23, 23])]
        groups, _ = self._groups(events)
        wa = next(g for g in groups if g["name"] == "West A")
        self.assertIn("三隊以上同勝率", wa["tie_note"])

    def test_cross_group_cup_game_goes_to_unassigned(self):
        events = [espn_event(1, "2026-10-30T23:00Z", "DEN", "OKC", 100, 90, home_ls=[25] * 4, away_ls=[22, 22, 23, 23])]
        groups, unassigned = self._groups(events)
        self.assertEqual(unassigned, ["OKC @ DEN"])
        self.assertTrue(all(r["played"] == 0 for g in groups for r in g["standings"]))

    def test_wildcard_is_best_second_place_per_conference(self):
        groups = [{"conference": "Western", "name": "A", "standings": [
                       {"abbr": "X", "name_zh": "X", "wins": 3, "losses": 0, "played": 3, "diff": 30, "points": 300},
                       {"abbr": "Y", "name_zh": "Y", "wins": 2, "losses": 1, "played": 3, "diff": 5, "points": 300}]},
                  {"conference": "Western", "name": "B", "standings": [
                       {"abbr": "P", "name_zh": "P", "wins": 3, "losses": 0, "played": 3, "diff": 30, "points": 300},
                       {"abbr": "Q", "name_zh": "Q", "wins": 2, "losses": 1, "played": 3, "diff": 9, "points": 300}]},
                  {"conference": "Eastern", "name": "C", "standings": [
                       {"abbr": "E", "name_zh": "E", "wins": 0, "losses": 0, "played": 0, "diff": 0, "points": 0},
                       {"abbr": "F", "name_zh": "F", "wins": 0, "losses": 0, "played": 0, "diff": 0, "points": 0}]}]
        wc = cup_mod.wildcards(groups)
        self.assertEqual(wc["Western"]["abbr"], "Q")
        self.assertIsNone(wc["Eastern"])  # 還沒開打不猜

    def test_scheduled_game_has_null_scores_and_taipei_time(self):
        row = cup_mod.game_row(espn_event(9, "2026-10-31T02:00Z", "DEN", "PHX"), ZH)
        self.assertEqual((row["date"], row["time"], row["status"]), ("2026-10-31", "10:00", "SCHEDULED"))
        self.assertIsNone(row["home_score"])
        self.assertEqual(row["home_zh"], "丹佛金塊")


class GamesFetchTests(unittest.TestCase):
    def test_days_are_bucketed_by_taipei_date(self):
        today = datetime.date(2026, 10, 26)
        # 美東 10/25 晚（UTC 10/26 00:00）→ 台北 10/26 08:00；美東 10/26 晚（UTC 10/27 00:00）→ 台北 10/27
        by_et = {
            "20261024": [espn_event(1, "2026-10-25T00:00Z", "DEN", "HOU", 100, 90, cup=False, home_ls=[25] * 4, away_ls=[22, 22, 23, 23])],
            "20261025": [espn_event(2, "2026-10-26T00:00Z", "PHX", "DAL", 99, 98, cup=False, home_ls=[25] * 4, away_ls=[25, 25, 24, 24])],
            "20261026": [espn_event(3, "2026-10-27T00:00Z", "UTAH", "DEN", cup=False),
                         espn_event(4, "2026-10-27T03:00Z", "HOU", "PHX", cup=False)],
        }

        def fake_call(url):
            key = re.search(r"dates=(\d{8})", url).group(1)
            return {"events": by_et[key]}
        with mock.patch.object(games_mod, "call", side_effect=fake_call):
            days = games_mod.fetch_days(today, ZH)
        self.assertEqual([d["date"] for d in days], ["2026-10-25", "2026-10-26", "2026-10-27"])
        self.assertEqual([len(d["games"]) for d in days], [1, 1, 2])
        g = days[1]["games"][0]
        self.assertEqual((g["time"], g["status"], g["home_score"], g["away_score"]), ("08:00", "FINAL", 99, 98))
        self.assertEqual(days[2]["games"][0]["time"], "08:00")
        self.assertIsNone(days[2]["games"][0]["home_score"])
        self.assertFalse(g["cup"])

    def test_main_writes_even_when_every_day_is_empty(self):
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(games_mod, "OUT_DIR", pathlib.Path(d)), \
             mock.patch.object(games_mod, "call", return_value={"events": []}):
            games_mod.main()
            files = list(pathlib.Path(d).glob("nba-games-*.json"))
        self.assertEqual(len(files), 1)


class PagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cup = json.loads((FIX / "nba-cup-2026-27.json").read_text(encoding="utf-8"))
        cls.games = json.loads((FIX / "nba-games-2026-10-26.json").read_text(encoding="utf-8"))
        cls.nba = json.loads((ROOT / "leagues" / "nba-standings-2025-26.json").read_text(encoding="utf-8"))

    def test_cup_page_lists_six_groups_and_official_disclaimer(self):
        html = gen_cup.build_page(self.cup)
        for name in ("West A", "West B", "West C", "East A", "East B", "East C"):
            self.assertIn(f"<h3>{name}</h3>", html)
        self.assertIn("以 NBA 官方公告為準", html)
        self.assertIn("/articles/nba-cup-2026-format-guide/", html)
        self.assertIn("已完成 0／60 場", html)
        self.assertIn("Hinkle Fieldhouse", html)
        graph = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))["@graph"]
        faq = next(n for n in graph if n.get("@type") == "FAQPage")
        self.assertEqual(len(faq["mainEntity"]), 5)
        self.assertNotIn("<a ", json.dumps(faq, ensure_ascii=False))

    def test_standings_page_has_games_section_when_snapshot_present(self):
        html = gen_std.build_page(self.nba, self.games)
        self.assertIn('id="games"', html)
        self.assertIn("近三日", html)
        self.assertIn("邁阿密熱火 @ 夏洛特黃蜂", html)
        self.assertIn("110：115", html)          # 客：主
        self.assertIn("07:00 開賽", html)
        self.assertIn('href="/nba-cup/"', html)
        self.assertNotIn('id="games"', gen_std.build_page(self.nba, None))

    def test_homepage_nba_tab_shows_today_games(self):
        tw = json.loads((ROOT / "leagues" / "tw-hoops-2026-07-19.json").read_text(encoding="utf-8"))
        hbl = json.loads((ROOT / "leagues" / "hbl-114-2026-10-13.json").read_text(encoding="utf-8"))

        def fake(pattern):
            return {"nba-standings-*.json": self.nba, "tw-hoops-*.json": tw,
                    "hbl-[0-9]*.json": hbl, "nba-games-*.json": self.games}.get(pattern)
        with mock.patch.object(ba, "_dash_latest", fake):
            html = ba.render_sport_index([], ba.SITES["basketball"], "籃球")
        self.assertIn("今日／昨日賽程", html)
        self.assertNotIn("2026-10-27<span", html)   # 首頁 compact 只列前兩桶（fixture 第三桶是 10-27）
        self.assertIn("2026-10-26<span", html)
        self.assertIn('href="/nba-cup/"', html)

    def test_nav_has_nba_cup_entry(self):
        nav = [n["href"] for n in ba.SITES["basketball"]["nav"]]
        self.assertIn("/nba-cup/", nav)
        html = ba.site_header_html("nba-cup", ba.SITES["basketball"])
        self.assertIn("/nba-cup/", html)


class FreshnessTests(unittest.TestCase):
    def test_games_snapshot_missing_in_season_is_red(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "nba-standings-2026-27.json").write_text(json.dumps({"season": "2026-27", "asof": "2026-11-15"}), encoding="utf-8")
            failures = ub.freshness_failures(datetime.date(2026, 11, 15), p)
            self.assertTrue(any("賽程快照" in x for x in failures))
            (p / "nba-games-2026-11-14.json").write_text(json.dumps({"asof_taipei_date": "2026-11-14"}), encoding="utf-8")
            failures = ub.freshness_failures(datetime.date(2026, 11, 15), p)
            self.assertFalse(any("賽程快照" in x for x in failures))


if __name__ == "__main__":
    unittest.main()
