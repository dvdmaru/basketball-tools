# MODEL.md — basketball-tools 模型層

> 給任何接手的 agent（Claude Code／Codex／headless pipeline）的**單一版本真相**。
>
> 分工：`README.md` 講**三層架構、資料源、建置與部署、驗證**——「指令怎麼跑」。
> **本檔只講程式擋不住的那半：你操作的是什麼資料、哪些欄位不存在、
> 哪些事實不准自己補、哪些線不能碰。**
>
> ⛔ **刻意不寫**：build／部署指令、PR 歷史、站上有幾篇文章、功能清單。
> 本檔只放**不隨每次 PR 變動的契約**。會隨改動變的敘事搬進來，它就會變成
> 第四份會漂移的副本（現有三份：README、CoWork `projects/basketball-tools.md`、
> Claude Code store `project_basketball_twtools.md`）。
> **本檔的價值在於它幾乎不需要改。**

---

## 1. 資料契約 — 快照有什麼、**沒有什麼**

事實的真相來源一律是 `leagues/*.json` 快照。
頁面上的賽季標籤與賽季狀態取自快照的 `season` / `season_label` / `final`，
**不是** `config/competitions.json`——該檔的 `season` / `start_date` / `end_date` / `status`
四欄目前**沒有任何渲染路徑在讀**（唯一會讀 `status` 的 `effective_status()` 全庫無呼叫點＝死碼），
詳該檔 `_comment`。

| 快照 | 必有 | 可有（缺席是合法狀態） | ⛔ 沒有 |
|---|---|---|---|
| `nba-standings-<season>.json` | `season`／`asof`／`final`／`source`／`standings[]` | `champion_en`／`champion_zh`／`finals_note`（賽季未結束時不存在） | — |
| └ `standings[]` 每一列 | `conference`／`seed`／`name`／`name_zh`／`abbr`／`wins`／`losses`／`pct`／`games_back`／`rank` | — | **`division`** |
| `tw-hoops-<date>.json` | `asof_taipei_date`／`season`／`final`／`leagues.tpbl`／`leagues.plg` | 各聯盟 `champion_zh`／`finals_note`／`regular_season_games`（僅 tpbl 有） | — |
| └ `standings[]` 每一列 | `rank`／`team_name`／`win`／`lose`／`pct`／`games_behind` | — | — |
| `hbl-<season>-<date>.json` | `asof_taipei_date`／`season_label`／`final`／`divisions.boys`／`divisions.girls` | 各組 `champion`／`final_note` | **任何球員層欄位**（見 §2-1） |
| └ `final_four[]` 每一列 | `rank`／`school`／`note` | — | **球員姓名／個人數據** |

### ☠️ 「沒有 `division`」這件事已經出過事（2026-08-18）

寫手在文章裡寫出「**太平洋組第 1**」。NBA 快照**只有 `conference`（東／西區），
沒有 `division`（分組）**——那個事實來自它的模型知識。
湖人 53 勝 29 敗確實是該分組最佳，**所以它是對的**，也**所以它更危險**：
沒有任何比對會叫，因為**沒有東西可以拿來比對**。已砍。
⇒ 這就是 §3-2 那條交接條款的由來。

### 人工維護的欄位（不是抓來的；改要附 source）

- `config/season-facts.json` → **只有 PLG 總冠軍**。
  PLG 官網冠軍賽頁是 JS 動態渲染、難以穩定 scrape，故記在這裡。
  **TPBL／HBL／NBA 的冠軍由 fetch 腳本從官網賽果自算，不要寫進這個檔。**
- 每筆必附 `sources` 與 `verified`（人工 cross-check 的說明）。

### 會到期失效的事實（時間到要回來改；不改**不會有任何東西告訴你**）

| 事實 | 到期點 | 動作 |
|---|---|---|
| `articles/lakers-sale-iger-kushner/` 的「尚待 NBA 批准」與 8 條 FAQ | 2026 年 9 月 NBA 董事會表決 | 依 `articles/lebron-james-76ers-24th-season/` 的 pattern：正文開頭補一段 `> **YYYY 年 M 月 D 日更新**：…` 引文區塊，**保留原查證狀態與判準不改寫** |
| `season-facts.json` 的 PLG 冠軍 | 2026-27 PLG 總冠軍賽結束 | 人工 cross-check 後更新 |
| 各聯盟 2026-27 開季日 | 官方公告時 | 見 §2-2——**公告前不准填** |

---

## 2. 紅線

1. **HBL ＝未成年學生。** README「紅線」節已列規則，本檔記**資料形狀上的後果**：
   快照裡**刻意沒有任何球員層欄位**，最細只到 `final_four[].school`（學校層）。
   哪天 fetch 開始帶回球員姓名或個人數據，那是**紅線被破，不是新功能**。
   負面題材永不進自動管線。
2. **官方未公告的日期不准填。** 台灣兩聯盟 2026-27 開季日至今未公告；
   `competitions.json` 的 `start_date` 停在 2025-26 是**刻意的，不是漏更新**。
   文案一律寫「開季日以各聯盟官方公告為準」，⛔ 不要寫「依往例約 10 月」——
   那是沒有依據的斷言（2026-08-18 已從 `/tw/` FAQ 移除）。
3. **查無時說「尚未產生」，不沿用舊賽季。**
   冠軍敘述一律由快照衍生；`final` 為 false 時輸出「本季尚未產生總冠軍」。
   ⚠️ 這條最陰的破口在 **FAQPage JSON-LD**：問句裡的賽季是動態的，
   答案若寫死冠軍，開季後會對搜尋引擎與 LLM **宣布一個還沒打完的賽季的冠軍**，
   而且頁面照樣 200、測試照樣綠。回歸保護在 `tests/test_season_rollover.py`。
4. **basketball-reference 禁用**（ToS 明文禁止），任何情況都不抓。

---

## 3. 交接條款 — 派工給寫手（subagent／Codex／任何非本人）時必須講死

1. 派工單要同時給「事實包」與「**快照有哪些欄位**」。
   只給事實、不給欄位表，寫手會拿模型知識補洞——而且補得很像真的。
2. ⭐ **驗收判準：正文裡每一個欄位級事實，都要指得出來源欄位。指不出來就是模型知識 → 砍。**
   ⚠️ 判準**不是**「這句話對不對」。**碰巧正確的模型知識照樣要砍**，
   因為它下一次就不對了，而且不會留下任何痕跡讓人發現這個習慣。
3. 派工單與事實包走**檔案傳遞**，不要塞進 shell 引數（CJK 必炸）。
4. 執行 agent **不做 git 操作**；git 留在指揮位。

---

## 4. 本檔維護規則

- **快照欄位增減 → 同一個 PR 更新 §1 的表。**
  `tests/test_snapshot_schema.py` 會擋：出現未登記的欄位、或必有欄位消失，
  就是紅燈，錯誤訊息會指回本檔。**文件與現實的漂移由 CI 抓，不靠誰記得同步。**
- 新增聯盟／新增人工維護欄位／新增紅線 → 同 PR 更新本檔。
- ⛔ 其餘一律不要動本檔。改得愈頻繁，愈沒有人信它。
