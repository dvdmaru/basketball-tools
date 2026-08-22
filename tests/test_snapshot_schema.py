#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快照欄位契約 — 把 MODEL.md §1 的表變成可執行的（2026-08-18）。

為什麼要有這支：MODEL.md §1 寫著「NBA 快照沒有 division 欄位」。
那句話今天是對的，但**文件不會自己知道資料變了**——哪天 fetch 腳本多帶回一個欄位、
或上游改名拿掉一個欄位，文件就安靜地開始說謊，而且不會有任何東西壞掉。
（本站已經有過一次：文案層寫死賽季事實，開季後會集體說錯話，build 與測試全綠。）

守的不變量：
  1. 每個快照的欄位集合 ⊆ MODEL.md 登記的（必有 ∪ 可有）。出現沒登記的欄位 → 紅燈，
     訊息要求去更新 MODEL.md §1（**不是**要求把欄位刪掉——新增欄位通常是對的，
     只是契約要跟著動）。
  2. 必有欄位不得消失。
  3. ⛔ 明確的負向斷言：NBA standings 每列**不得**出現 division。
     這條有具體事故：寫手寫出「太平洋組第 1」，而快照根本沒有這一欄，
     那個事實來自模型知識、且碰巧正確——沒有任何比對抓得到。詳 MODEL.md §1。

⭐ 本檔含**陽性對照**（`test_gate_itself_catches_injected_field`）：
把一個假欄位注進副本，斷言檢查器會叫。沒有這個，「全綠」可能只代表檢查器沒在跑。

跑法：python3 -m unittest discover -s tests -v
"""
import glob
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODEL_DOC = "MODEL.md §1 資料契約"

# ── MODEL.md §1 的表，逐欄登記 ───────────────────────────────────────────
NBA_TOP_REQUIRED = {"season", "asof", "final", "source", "standings"}
NBA_TOP_OPTIONAL = {"champion_en", "champion_zh", "finals_note"}
NBA_ROW_REQUIRED = {"conference", "seed", "name", "name_zh", "abbr",
                    "wins", "losses", "pct", "games_back", "rank"}
NBA_ROW_OPTIONAL = set()
NBA_ROW_FORBIDDEN = {"division"}  # 見 docstring 第 3 點

TW_TOP_REQUIRED = {"asof_taipei_date", "season", "final", "leagues"}
TW_TOP_OPTIONAL = set()
TW_LEAGUE_REQUIRED = {"name_zh", "standings", "source"}
TW_LEAGUE_OPTIONAL = {"champion_zh", "finals_note", "regular_season_games"}
TW_ROW_REQUIRED = {"rank", "team_name", "win", "lose", "pct", "games_behind"}
TW_ROW_OPTIONAL = set()

HBL_TOP_REQUIRED = {"asof_taipei_date", "season_label", "final", "divisions"}
HBL_TOP_OPTIONAL = set()
HBL_DIV_REQUIRED = {"label", "final_four", "source"}
HBL_DIV_OPTIONAL = {"champion", "final_note"}
HBL_ROW_REQUIRED = {"rank", "school"}
HBL_ROW_OPTIONAL = {"note"}
# HBL＝未成年學生，最細只到學校層。這裡不是列舉禁詞，而是「白名單以外一律擋」，
# 所以任何球員層欄位（姓名、得分、身高…）都會被上面的未登記欄位檢查攔下。詳 MODEL.md §2-1。

HBL_HISTORY_TOP_REQUIRED = {"asof_taipei_date", "note", "seasons"}
HBL_HISTORY_ROW_REQUIRED = {"season", "boys_champion", "girls_champion"}


def check_keys(obj, required, optional, where):
    """回傳問題清單（空＝過）。分開報「少了必有」與「多了沒登記的」。"""
    keys = set(obj)
    problems = []
    missing = required - keys
    if missing:
        problems.append(
            f"{where}：缺少必有欄位 {sorted(missing)}——"
            f"若上游真的拿掉了，請同步修 {MODEL_DOC} 並確認沒有渲染路徑還在讀它")
    unknown = keys - required - optional
    if unknown:
        problems.append(
            f"{where}：出現未登記欄位 {sorted(unknown)}——"
            f"新增欄位通常是對的，但請**同一個 PR** 把它加進 {MODEL_DOC} 的表；"
            f"契約沒跟上，下一個接手的人會以為這一欄不存在")
    return problems


def _load(pattern):
    hits = sorted(glob.glob(str(ROOT / pattern)))
    return [(pathlib.Path(p).name, json.loads(pathlib.Path(p).read_text(encoding="utf-8")))
            for p in hits]


def audit_nba(name, d):
    p = check_keys(d, NBA_TOP_REQUIRED, NBA_TOP_OPTIONAL, f"{name} 頂層")
    for i, row in enumerate(d.get("standings", [])):
        p += check_keys(row, NBA_ROW_REQUIRED, NBA_ROW_OPTIONAL, f"{name} standings[{i}]")
        for bad in NBA_ROW_FORBIDDEN & set(row):
            p.append(
                f"{name} standings[{i}]：出現 `{bad}` 欄位。這一欄過去不存在，"
                f"而正文曾出現過依賴它的敘述（「太平洋組第 1」）＝當時是模型知識。"
                f"若現在真的抓得到，請更新 {MODEL_DOC} 並解除本斷言；"
                f"在那之前，任何分組層敘述都沒有資料支撐")
    return p


def audit_tw(name, d):
    p = check_keys(d, TW_TOP_REQUIRED, TW_TOP_OPTIONAL, f"{name} 頂層")
    leagues = d.get("leagues", {})
    for lg in ("tpbl", "plg"):
        if lg not in leagues:
            p.append(f"{name}：缺少 leagues.{lg}")
            continue
        p += check_keys(leagues[lg], TW_LEAGUE_REQUIRED, TW_LEAGUE_OPTIONAL,
                        f"{name} leagues.{lg}")
        for i, row in enumerate(leagues[lg].get("standings", [])):
            p += check_keys(row, TW_ROW_REQUIRED, TW_ROW_OPTIONAL,
                            f"{name} leagues.{lg}.standings[{i}]")
    return p


def audit_hbl(name, d):
    p = check_keys(d, HBL_TOP_REQUIRED, HBL_TOP_OPTIONAL, f"{name} 頂層")
    for div in ("boys", "girls"):
        node = d.get("divisions", {}).get(div)
        if node is None:
            p.append(f"{name}：缺少 divisions.{div}")
            continue
        p += check_keys(node, HBL_DIV_REQUIRED, HBL_DIV_OPTIONAL, f"{name} divisions.{div}")
        for i, row in enumerate(node.get("final_four", [])):
            p += check_keys(row, HBL_ROW_REQUIRED, HBL_ROW_OPTIONAL,
                            f"{name} divisions.{div}.final_four[{i}]（⛔ 學校層以下不得出現欄位）")
    return p


def audit_hbl_history(name, d):
    p = check_keys(d, HBL_HISTORY_TOP_REQUIRED, set(), f"{name} 頂層")
    for i, row in enumerate(d.get("seasons", [])):
        p += check_keys(row, HBL_HISTORY_ROW_REQUIRED, set(), f"{name} seasons[{i}]")
    return p


class TestSnapshotSchema(unittest.TestCase):
    def _run(self, pattern, auditor):
        files = _load(pattern)
        # ⛔ 空集合不算通過——沒有檔案代表 pattern 錯了或快照被清掉，
        #    那正是「驗了空集合還亮綠」的經典假通過。
        self.assertTrue(files, f"找不到任何符合 {pattern} 的快照——檢查器本身沒在測東西")
        problems = []
        for name, d in files:
            problems += auditor(name, d)
        self.assertEqual(problems, [], "\n  ▸ " + "\n  ▸ ".join(problems) if problems else "")

    def test_nba_standings(self):
        self._run("leagues/nba-standings-*.json", audit_nba)

    def test_tw_hoops(self):
        self._run("leagues/tw-hoops-*.json", audit_tw)

    def test_hbl_season(self):
        self._run("leagues/hbl-1*.json", audit_hbl)

    def test_hbl_history(self):
        self._run("leagues/hbl-history.json", audit_hbl_history)

    def test_no_division_field_in_nba(self):
        """獨立成一條，讓它壞掉時錯誤訊息直指這個具體事故。"""
        for name, d in _load("leagues/nba-standings-*.json"):
            for row in d.get("standings", []):
                self.assertNotIn(
                    "division", row,
                    f"{name}：NBA 快照出現 division 欄位。"
                    f"MODEL.md §1 記載它不存在，且有依賴它的正文事故紀錄；"
                    f"請先更新契約再解除本斷言")

    # ── 陽性對照：檢查器自己會不會叫 ──────────────────────────────
    def test_gate_itself_catches_injected_field(self):
        files = _load("leagues/nba-standings-*.json")
        self.assertTrue(files)
        name, d = files[0]
        mutated = json.loads(json.dumps(d))          # 深拷貝，⛔ 不碰磁碟上的快照
        mutated["standings"][0]["division"] = "Pacific"
        mutated["totally_new_top_level_field"] = 1
        problems = audit_nba(name, mutated)
        self.assertTrue(
            any("division" in p for p in problems),
            "陽性對照失敗：注入 division 之後檢查器沒有叫——這支測試在說謊")
        self.assertTrue(
            any("totally_new_top_level_field" in p for p in problems),
            "陽性對照失敗：注入未登記的頂層欄位之後檢查器沒有叫")

    def test_gate_itself_catches_missing_required(self):
        files = _load("leagues/tw-hoops-*.json")
        self.assertTrue(files)
        name, d = files[0]
        mutated = json.loads(json.dumps(d))
        del mutated["final"]
        problems = audit_tw(name, mutated)
        self.assertTrue(
            any("final" in p and "缺少必有欄位" in p for p in problems),
            "陽性對照失敗：拿掉必有欄位之後檢查器沒有叫")

    def test_model_doc_exists_and_documents_the_contract(self):
        """契約文件被刪或被搬走時要紅燈——否則錯誤訊息會指向不存在的檔案。"""
        doc = ROOT / "MODEL.md"
        self.assertTrue(doc.exists(), "MODEL.md 不見了，但本檔的所有錯誤訊息都指向它")
        text = doc.read_text(encoding="utf-8")
        for anchor in ("資料契約", "division", "final_four"):
            self.assertIn(anchor, text, f"MODEL.md 已不再提到「{anchor}」——契約與本檔脫節")


class TestFaqSchemaEmitted(unittest.TestCase):
    """FAQ 的 H2 寫錯時，`FAQPage` 會靜默消失——頁面照常 render、build 全綠。

    這是 MODEL.md §1「第三種靜默失效」那一節的機械關卡：
    文件寫了規則但沒有東西會叫，等於沒寫（本 repo 記錄有案的失敗模式）。
    """

    def _articles(self):
        pattern = str(ROOT / "public-basketball" / "articles" / "*" / "index.html")
        return sorted(glob.glob(pattern))

    @staticmethod
    def _graph(path):
        import re
        text = pathlib.Path(path).read_text(encoding="utf-8")
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>',
                      text, re.S)
        if not m:
            return None
        return json.loads(m.group(1)).get("@graph", [])

    def test_every_built_article_emits_faqpage(self):
        files = self._articles()
        self.assertTrue(files, "檢查器本身沒在測東西：找不到任何已建置的文章頁")
        missing = []
        for f in files:
            graph = self._graph(f)
            slug = pathlib.Path(f).parent.name
            if graph is None:
                missing.append(f"{slug}（整段 JSON-LD 都不見了）")
            elif not any(n.get("@type") == "FAQPage" for n in graph):
                missing.append(slug)
        self.assertFalse(missing, (
            "下列文章沒有吐出 FAQPage：" + "、".join(missing) +
            "——最常見原因是 FAQ 的 H2 沒有逐字寫成"
            "「常見問題」／「常見問答」／「FAQ」三選一，"
            "或層級誤寫成 H3。頁面看起來完全正常，只有結構化資料消失。"
            f"規則見 {MODEL_DOC} 那一節。"))

    def test_gate_itself_catches_a_stripped_faqpage(self):
        """陽性對照：把 FAQPage 從 @graph 拿掉之後，判定式必須認得出來。

        ⛔ 只在記憶體裡動，不碰磁碟。
        """
        files = self._articles()
        self.assertTrue(files, "檢查器本身沒在測東西")
        graph = self._graph(files[0])
        self.assertIsNotNone(graph, "取樣的那一篇本來就沒有 JSON-LD，對照做不成")
        self.assertTrue(any(n.get("@type") == "FAQPage" for n in graph),
                        "取樣的那一篇本來就沒有 FAQPage，對照做不成")
        stripped = [n for n in graph if n.get("@type") != "FAQPage"]
        self.assertFalse(any(n.get("@type") == "FAQPage" for n in stripped),
                         "陽性對照失敗：拿掉 FAQPage 之後判定式還說它在")


if __name__ == "__main__":
    unittest.main()
