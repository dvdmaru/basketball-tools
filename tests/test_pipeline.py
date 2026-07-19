#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管線回歸測試——鎖 2026-07-19 站群共病修正的行為，防回歸。

三個缺陷（racing-tools 外部稽核抓到，實查確認本站同樣中招）：
  1. 建置失敗仍部署 → 部署前 hard gate（fetch 類 fail-soft 不受影響）
  2. 草稿假下架 → build 後清掉未產出的文章目錄
  3. 上游回空值洗掉好資料 → 快照寫入前驗證，拒寫並保留 last-known-good

⚠️ 本站快照多為「日期序列檔」（tw-hoops-<date>.json），生成端取 sorted(glob)[-1]，
所以空值的傷害不是覆寫、是新檔排序在後 shadow 掉昨天的好資料——baseline 參數就是為此。

跑法：python3 -m unittest discover -s tests -v
"""
import importlib.util
import json
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sg = _load("snapshot_guard", "snapshot_guard.py")


def snap(n):
    """模擬 tw-hoops 形狀：兩聯盟各 n/2 隊。"""
    half = [{"team": i} for i in range(n // 2)]
    return {"leagues": {"tpbl": {"standings": list(half)}, "plg": {"standings": list(half)}}}


def count_teams(d):
    return sum(len(lg.get("standings", [])) for lg in (d or {}).get("leagues", {}).values())


class DatedSnapshotGuardTests(unittest.TestCase):
    """日期序列快照：空的新檔不得寫入、昨天的好資料必須續任 sorted()[-1]。"""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.pattern = str(self.tmp / "tw-hoops-*.json")
        (self.tmp / "tw-hoops-2026-07-19.json").write_text(
            json.dumps(snap(24)), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_newest_picks_latest_by_name(self):
        (self.tmp / "tw-hoops-2026-07-18.json").write_text(json.dumps(snap(24)), encoding="utf-8")
        self.assertEqual(sg.newest(self.pattern).name, "tw-hoops-2026-07-19.json")

    def test_empty_new_day_refused_and_does_not_shadow(self):
        newp = self.tmp / "tw-hoops-2026-07-20.json"
        ok = sg.guarded_write(newp, snap(0), count_teams, label="tw-hoops",
                              baseline=sg.newest(self.pattern))
        self.assertFalse(ok)
        self.assertFalse(newp.exists())  # 空檔沒被建立
        # 生效快照仍是昨天那份好資料
        self.assertEqual(sg.newest(self.pattern).name, "tw-hoops-2026-07-19.json")
        self.assertEqual(count_teams(json.loads(sg.newest(self.pattern).read_text())), 24)

    def test_sharp_drop_new_day_refused(self):
        newp = self.tmp / "tw-hoops-2026-07-20.json"
        self.assertFalse(sg.guarded_write(newp, snap(4), count_teams, label="tw-hoops",
                                          baseline=sg.newest(self.pattern)))
        self.assertFalse(newp.exists())

    def test_healthy_new_day_written_and_becomes_newest(self):
        newp = self.tmp / "tw-hoops-2026-07-20.json"
        self.assertTrue(sg.guarded_write(newp, snap(24), count_teams, label="tw-hoops",
                                         baseline=sg.newest(self.pattern)))
        self.assertEqual(sg.newest(self.pattern).name, "tw-hoops-2026-07-20.json")

    def test_baseline_none_falls_back_to_target_path(self):
        """覆寫同一檔的快照（nba-standings-<season>.json）走預設路徑語意。"""
        p = self.tmp / "nba-standings-2025-26.json"
        self.assertTrue(sg.guarded_write(p, snap(30), count_teams, label="nba"))
        self.assertFalse(sg.guarded_write(p, snap(0), count_teams, label="nba"))
        self.assertEqual(count_teams(json.loads(p.read_text(encoding="utf-8"))), 30)


class PruneStaleArticlesTests(unittest.TestCase):
    """複製 build-articles 的 prune 語意（該檔 import 重量級依賴，這裡驗行為契約）。"""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @staticmethod
    def prune(produced):
        for art_root, keep in produced.items():
            for child in sorted(art_root.iterdir()):
                if child.is_dir() and child.name not in keep:
                    shutil.rmtree(child)

    def _mk(self, root, names):
        root.mkdir(parents=True, exist_ok=True)
        for n in names:
            (root / n).mkdir()
            (root / n / "index.html").write_text("x", encoding="utf-8")
        (root / "index.html").write_text("list", encoding="utf-8")

    def test_reverted_draft_output_removed(self):
        art = self.tmp / "public-basketball" / "articles"
        self._mk(art, ["nba-league-guide", "reverted-draft"])
        self.prune({art: {"nba-league-guide"}})
        self.assertTrue((art / "nba-league-guide").exists())
        self.assertFalse((art / "reverted-draft").exists())
        self.assertTrue((art / "index.html").exists())  # 列表頁不是文章目錄

    def test_untouched_site_root_never_pruned(self):
        """本次沒產出任何文章的站根＝不在建置範圍，整個不得清空（多站共用腳本的地雷）。"""
        bk = self.tmp / "public-basketball" / "articles"
        other = self.tmp / "public" / "articles"
        self._mk(bk, ["kept"])
        self._mk(other, ["someone-elses-article"])
        self.prune({bk: {"kept"}})
        self.assertTrue((other / "someone-elses-article").exists())


class DeployGateTests(unittest.TestCase):
    """hard gate 語意：fetch 類 fail-soft 不進 FAILED，build 類進 → 擋部署。"""

    def setUp(self):
        self.ub = _load("update_basketball", "update-basketball.py")
        self.ub.FAILED.clear()

    def tearDown(self):
        self.ub.FAILED.clear()

    def test_soft_failure_does_not_block(self):
        rc = self.ub.run(["python3", "-c", "import sys; sys.exit(2)"], "fetch NBA", soft=True)
        self.assertEqual(rc, 2)
        self.assertEqual(self.ub.FAILED, [])  # 斷源不擋部署

    def test_hard_failure_blocks(self):
        rc = self.ub.run(["python3", "-c", "import sys; sys.exit(1)"], "build-articles")
        self.assertEqual(rc, 1)
        self.assertEqual(self.ub.FAILED, ["build-articles"])  # 壞產物不上線

    def test_success_records_nothing(self):
        self.assertEqual(self.ub.run(["python3", "-c", "pass"], "gen NBA standings"), 0)
        self.assertEqual(self.ub.FAILED, [])


if __name__ == "__main__":
    unittest.main()
