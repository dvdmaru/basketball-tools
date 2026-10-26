#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HBL 進行中學年度（2026-10-26）：115 學年度資格賽 10/27 開打，官網只建了資格賽 division。

舊抓取器只認「總決賽」，找不到就 RuntimeError、fail-soft 沿用 114；11 月起 freshness 門檻又要求
115 快照，每日 job 會轉紅。修法＝沒有總決賽（或總決賽尚無完賽）就寫 final=false 的進行中快照：
四強留空、不推冠軍，附逐階段對戰表 schedule 與上季冠軍 previous_season。
跑法：python3 -m unittest discover -s tests -v
"""
import copy
import importlib.util
import json
import pathlib
import re
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "hbl"


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hbl = _load("fetch_hbl_in_progress", "fetch-hbl.py")
page = _load("gen_hbl_page_in_progress", "gen-hbl-page.py")
ba = _load("build_articles_hbl_in_progress", "build-articles.py")
schema = _load("snapshot_schema_hbl_in_progress", "../tests/test_snapshot_schema.py")


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _game(when, home, away, done=False, hs=None, as_=None, venue="健行科大"):
    g = {"id": 1, "matchedAt": when, "venue": venue, "status": "COMPLETED" if done else "NOT_STARTED",
         "homeSquad": {"id": 1, "name": f"{home}全名", "altName": home},
         "awaySquad": {"id": 2, "name": f"{away}全名", "altName": away},
         "homeSquadScore": hs if done else 0, "awaySquadScore": as_ if done else 0}
    return g


QUAL_BOYS = [_game("2026-10-27T02:00:00.000Z", "高苑工商", "治平高中", done=True, hs=70, as_=65),
             _game("2026-10-27T05:20:00.000Z", "三重商工", "新民高中"),
             _game("2026-10-28T02:00:00.000Z", "中華商海", "滬江高中", venue="中原大學")]
QUAL_GIRLS = [_game("2026-10-27T07:20:00.000Z", "忠明高中", "輔仁中學")]


def navigation_in_progress(finals_without_games=False):
    """以真實 fixture 為底（114 完整、115 空），把 115 注入資格賽 division（可再加一個沒賽果的總決賽）。"""
    nav = copy.deepcopy(fixture("hbl-api-public-navigation-page-76.json"))
    league = hbl._hbl_league(nav)
    s115 = next(s for s in league["seasons"] if str(s.get("name")).startswith("115"))
    for event in s115["events"]:
        if "甲級" not in event["name"]:
            continue
        div_id = 952 if "男" in event["name"] else 953
        event["divisions"] = [{"id": div_id, "name": "資格賽", "status": "IN_PROGRESS"}]
        if finals_without_games:
            event["divisions"].append({"id": div_id + 100, "name": "總決賽", "status": "NOT_STARTED"})
    return nav


def fake_call_factory(nav):
    def fake_call(url):
        if url.endswith("/public-navigation/page/76"):
            return nav
        m = re.search(r"/division-matches/(\d+)$", url)
        if m:
            did = int(m.group(1))
            if did == 952:
                return copy.deepcopy(QUAL_BOYS)
            if did == 953:
                return copy.deepcopy(QUAL_GIRLS)
            if did in (1052, 1053):
                return []  # 總決賽 division 已建、尚無賽事
            path = re.sub(r"^https://hbl\.com\.tw/", "", url).replace("/", "-")
            return fixture(f"hbl-{path}.json")
        raise AssertionError(f"unexpected url {url}")
    return fake_call


class HblInProgressFetchTests(unittest.TestCase):
    def _run_main(self, nav):
        hbl._GAMES_CACHE.clear()
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = pathlib.Path(tmp)
            prev = ROOT / "leagues" / "hbl-114-2026-10-13.json"
            (out_dir / prev.name).write_text(prev.read_text(encoding="utf-8"), encoding="utf-8")
            with mock.patch.object(hbl, "OUT_DIR", out_dir), \
                 mock.patch.object(hbl, "call", side_effect=fake_call_factory(nav)), \
                 mock.patch.object(hbl.datetime, "datetime", wraps=hbl.datetime.datetime) as date_time:
                date_time.now.return_value = hbl.datetime.datetime(2026, 10, 27, 12, tzinfo=hbl.zoneinfo.ZoneInfo("Asia/Taipei"))
                hbl.main()
                files = sorted(out_dir.glob("hbl-115-*.json"))
                self.assertEqual([f.name for f in files], ["hbl-115-2026-10-27.json"])
                return json.loads(files[0].read_text(encoding="utf-8"))

    def test_qualifier_only_season_writes_in_progress_snapshot(self):
        snap = self._run_main(navigation_in_progress())
        self.assertEqual(snap["season_label"], "115學年度")
        self.assertFalse(snap["final"])
        for key in ("boys", "girls"):
            self.assertEqual(snap["divisions"][key]["final_four"], [])
            self.assertNotIn("champion", snap["divisions"][key])
        self.assertEqual(snap["stages"]["boys"]["divisions"][0]["name"], "資格賽")
        self.assertEqual(snap["stages"]["boys"]["divisions"][0]["completed"], 1)
        boys = snap["schedule"]["boys"][0]
        self.assertEqual(boys["name"], "資格賽")
        self.assertEqual(len(boys["games"]), 3)
        self.assertEqual(boys["games"][0]["date"], "2026-10-27")
        self.assertEqual(boys["games"][0]["time"], "10:00")        # UTC 02:00 → 台北 10:00
        self.assertEqual((boys["games"][0]["home_score"], boys["games"][0]["away_score"]), (70, 65))
        self.assertIsNone(boys["games"][1]["home_score"])         # 未完賽比分為 null，不是 0
        self.assertEqual(boys["games"][2]["venue"], "中原大學")
        self.assertEqual(snap["previous_season"]["season_label"], "114學年度")
        self.assertEqual(snap["previous_season"]["divisions"]["boys"]["champion"], "松山高中")
        self.assertNotIn("next_season", snap)
        self.assertEqual(schema.audit_hbl("hbl-115-2026-10-27.json", snap), [])

    def test_finals_division_without_games_is_still_in_progress(self):
        snap = self._run_main(navigation_in_progress(finals_without_games=True))
        self.assertFalse(snap["final"])
        self.assertEqual(snap["divisions"]["boys"]["final_four"], [])
        self.assertEqual([s["name"] for s in snap["schedule"]["boys"]], ["資格賽", "總決賽"])

    def test_one_division_finished_other_not_is_whole_snapshot_in_progress(self):
        """男甲總決賽已 COMPLETED（用 114 的 703 賽果）、女甲總決賽還沒打：整份進行中，男甲也不掛冠軍。"""
        nav = navigation_in_progress()
        league = hbl._hbl_league(nav)
        s115 = next(s for s in league["seasons"] if str(s.get("name")).startswith("115"))
        for event in s115["events"]:
            if "甲級" in event["name"] and "男" in event["name"]:
                event["divisions"].append({"id": 703, "name": "總決賽", "status": "COMPLETED"})
            elif "甲級" in event["name"] and "女" in event["name"]:
                event["divisions"].append({"id": 1053, "name": "總決賽", "status": "IN_PROGRESS"})
        snap = self._run_main(nav)
        self.assertFalse(snap["final"])
        self.assertNotIn("champion", snap["divisions"]["boys"])
        self.assertEqual(snap["divisions"]["boys"]["final_four"], [])
        self.assertEqual(len(snap["results"]["boys"]["finals"]), 4)   # 賽果表仍保留逐場資料
        self.assertEqual(schema.audit_hbl("x", snap), [])

    def test_null_matched_at_does_not_crash_sorting(self):
        hbl._GAMES_CACHE.clear()
        games = [dict(QUAL_BOYS[1], matchedAt=None), QUAL_BOYS[0]]
        with mock.patch.object(hbl, "call", return_value=games):
            rows = hbl._division_games(999)
        self.assertEqual(rows[0]["matchedAt"], None)
        self.assertEqual(hbl._schedule_game(rows[0])["date"], "")

    def test_schema_gate_rejects_champion_on_in_progress_snapshot(self):
        snap = self._run_main(navigation_in_progress())
        mutated = json.loads(json.dumps(snap))
        mutated["divisions"]["boys"]["champion"] = "某校"
        mutated["schedule"]["boys"][0]["games"][0]["top_scorer"] = "某同學"
        problems = schema.audit_hbl("x", mutated)
        self.assertTrue(any("final=false" in p for p in problems))
        self.assertTrue(any("top_scorer" in p for p in problems))


class HblInProgressPageTests(unittest.TestCase):
    def setUp(self):
        hbl._GAMES_CACHE.clear()
        nav = navigation_in_progress()
        season_name, season = hbl.latest_established_season(nav)
        with mock.patch.object(hbl, "call", side_effect=fake_call_factory(nav)):
            self.snap = {
                "asof_taipei_date": "2026-10-27", "season_label": "115學年度", "final": False,
                "divisions": {"boys": {"label": "男子甲級", "final_four": [], "source": "f"},
                              "girls": {"label": "女子甲級", "final_four": [], "source": "f"}},
                "stages": hbl.stage_overview(season), "results": hbl.stage_results(season),
                "schedule": hbl.stage_schedule(season),
                "previous_season": {"season_label": "114學年度",
                                    "divisions": {"boys": {"label": "男子甲級", "champion": "松山高中", "final_note": "冠軍戰 87:71 勝南湖高中"},
                                                  "girls": {"label": "女子甲級", "champion": "陽明高中", "final_note": "冠軍戰 61:53 勝北一女中"}}},
            }

    def test_page_shows_schedule_and_says_no_champion_yet(self):
        html = page.build_page(self.snap, {"seasons": []})
        self.assertIn("115學年度 進行中", html.split("<title>")[1].split("</title>")[0])
        self.assertIn("115學年度逐場對戰與賽果", html)
        self.assertIn("高苑工商 vs 治平高中", html)
        self.assertIn("70：65", html)
        self.assertIn("男子甲級・資格賽（進行中，已完成 1／3 場）", html)
        self.assertIn("本季尚未產生冠軍", html)
        self.assertIn("114學年度男子甲級冠軍", html)
        self.assertNotIn("已完賽，表列為總決賽最終名次", html)
        self.assertNotIn("115學年度男子甲級冠軍", html)      # 不得把進行中季標成有冠軍
        faq_ld = next(n for n in json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))["@graph"]
                      if n.get("@type") == "FAQPage")
        champ_q = next(q for q in faq_ld["mainEntity"] if "冠軍是誰" in q["name"])
        self.assertIn("尚未產生冠軍", champ_q["acceptedAnswer"]["text"])
        self.assertIn("松山高中", champ_q["acceptedAnswer"]["text"])

    def test_completed_season_page_unchanged_shape(self):
        snap = json.loads((ROOT / "leagues" / "hbl-114-2026-10-13.json").read_text(encoding="utf-8"))
        html = page.build_page(snap, {"seasons": []})
        self.assertIn("HBL 高中籃球甲級四強與冠軍（114學年度）", html)
        self.assertIn("已完賽，表列為總決賽最終名次", html)
        self.assertNotIn("逐場對戰與賽果", html)

    def test_homepage_hbl_tab_in_progress_has_no_final_four(self):
        nba = json.loads((ROOT / "leagues" / "nba-standings-2025-26.json").read_text(encoding="utf-8"))
        tw = json.loads((ROOT / "leagues" / "tw-hoops-2026-07-19.json").read_text(encoding="utf-8"))
        def fake(pattern):
            if pattern.startswith("nba-standings"):
                return nba
            if pattern.startswith("tw-hoops"):
                return tw
            if pattern.startswith("hbl-"):
                return self.snap
            return None
        with mock.patch.object(ba, "_dash_latest", fake):
            html = ba.render_sport_index([], ba.SITES["basketball"], "籃球")
        self.assertIn("115學年度 · 進行中", html)
        self.assertIn("已完成 1／3 場", html)
        self.assertIn("上季（114學年度）冠軍：男子甲級 松山高中、女子甲級 陽明高中", html)
        self.assertNotIn("總決賽最終名次", html)
        self.assertIn("看逐場對戰表", html)


if __name__ == "__main__":
    unittest.main()
