#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HBL 各階段快照：官方 API fixture 的結構與 rollover 回歸保護。"""
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


hbl = _load("fetch_hbl_stages", "fetch-hbl.py")
page = _load("gen_hbl_page_stages", "gen-hbl-page.py")


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fixture_call(url):
    path = re.sub(r"^https://hbl\.com\.tw/", "", url).replace("/", "-")
    return fixture(f"hbl-{path}.json")


class HblStageSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.navigation = fixture("hbl-api-public-navigation-page-76.json")
        cls.season_name, cls.season = hbl.latest_established_season(cls.navigation)

    def test_latest_established_season_skips_newer_empty_divisions(self):
        latest_name, _latest = hbl.latest_season(self.navigation)
        self.assertGreater(latest_name, self.season_name)
        self.assertEqual(hbl.finals_stage_sns(_latest), {})

    def test_taipei_date_conversion(self):
        self.assertEqual(hbl._taipei_date("2025-10-12T16:30:00Z"), "2025-10-13")

    def test_stages_include_completed_counts_and_taipei_dates(self):
        with mock.patch.object(hbl, "call", side_effect=fixture_call):
            stages = hbl.stage_overview(self.season)
        boys_qualifying = stages["boys"]["divisions"][0]
        self.assertEqual(boys_qualifying["name"], "資格賽")
        self.assertEqual(boys_qualifying["games"], 55)
        self.assertEqual(boys_qualifying["completed"], 55)
        self.assertEqual(boys_qualifying["first_date"], "2025-10-13")
        self.assertEqual(boys_qualifying["last_date"], "2025-10-17")
        self.assertEqual(stages["boys_b"]["divisions"][0]["name"], "全國決賽")
        self.assertEqual(stages["girls_b"]["divisions"][0]["teams"], 8)

    def test_results_take_advancers_from_next_division(self):
        with mock.patch.object(hbl, "call", side_effect=fixture_call):
            results = hbl.stage_results(self.season)
        expected = []
        for game in sorted(fixture("hbl-api-division-matches-698.json"), key=lambda row: row["matchedAt"]):
            for side in ("homeSquad", "awaySquad"):
                name = game[side].get("altName") or game[side]["name"]
                if name not in expected:
                    expected.append(name)
        self.assertEqual(results["boys"]["advancers"]["資格賽"], expected)
        self.assertEqual(len(results["boys"]["semifinals"]), 28)
        self.assertEqual(len(results["girls"]["finals"]), 4)
        self.assertEqual(len(results["girls"]["advancers"]["複賽"]), 4)
        self.assertEqual(results["boys"]["finals"][0]["round_label"], "")

    def test_next_season_uses_official_squad_counts_when_divisions_absent(self):
        latest_name, latest = hbl.latest_season(self.navigation)
        with mock.patch.object(hbl, "call", side_effect=fixture_call):
            upcoming = hbl.next_season_squads(latest_name, latest, "2026-10-13")
        counts = {event["name"]: event["squad_count"] for event in upcoming["events"]}
        self.assertEqual(sorted(counts.values()), [9, 15, 23, 35])
        self.assertTrue(all("squads" in event for event in upcoming["events"] if "甲級" in event["name"]))

    def test_existing_final_four_is_unchanged(self):
        old = json.loads((ROOT / "leagues" / "hbl-114-2026-07-19.json").read_text(encoding="utf-8"))
        with mock.patch.object(hbl, "call", side_effect=fixture_call):
            current = {
                "boys": hbl.rank_division(703, "男子甲級"),
                "girls": hbl.rank_division(704, "女子甲級"),
            }
        for key in ("boys", "girls"):
            self.assertEqual(current[key]["final_four"], old["divisions"][key]["final_four"])
            self.assertEqual(current[key]["champion"], old["divisions"][key]["champion"])

    def test_page_renders_the_three_data_sections_without_stale_literals(self):
        latest_name, latest = hbl.latest_season(self.navigation)
        with mock.patch.object(hbl, "call", side_effect=fixture_call):
            snap = copy.deepcopy(json.loads(
                (ROOT / "leagues" / "hbl-114-2026-07-19.json").read_text(encoding="utf-8")))
            snap["stages"] = hbl.stage_overview(self.season)
            snap["results"] = hbl.stage_results(self.season)
            snap["next_season"] = hbl.next_season_squads(latest_name, latest, "2026-10-13")
        snap["season_label"] = "測試學年度"
        snap["next_season"]["label"] = "下一學年度"
        html = page.build_page(snap, {"seasons": []})
        for heading in ("下一學年度報名隊數", "測試學年度各階段一覽", "準決賽與總決賽賽果"):
            self.assertIn(f"<h2>{heading}</h2>", html)
        self.assertIn("下一學年度有幾隊報名？", html)
        self.assertIn("測試學年度各階段在哪裡打？", html)
        source = (ROOT / "scripts" / "gen-hbl-page.py").read_text(encoding="utf-8")
        for stale in ("114學年度", "2025-26"):
            self.assertNotIn(stale, source)

    def test_main_writes_previous_finished_season_and_next_season_together(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(hbl, "OUT_DIR", pathlib.Path(tmp)), \
             mock.patch.object(hbl, "call", side_effect=fixture_call), \
             mock.patch.object(hbl.datetime, "datetime", wraps=hbl.datetime.datetime) as date_time:
            date_time.now.return_value = hbl.datetime.datetime(2026, 10, 13, tzinfo=hbl.zoneinfo.ZoneInfo("Asia/Taipei"))
            hbl.main()
            files = list(pathlib.Path(tmp).glob("hbl-*.json"))
            self.assertEqual(len(files), 1)
            snap = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(snap["season_label"], "114學年度")
        self.assertEqual(snap["next_season"]["label"], "115學年度")
        self.assertIn("results", snap)


if __name__ == "__main__":
    unittest.main()
