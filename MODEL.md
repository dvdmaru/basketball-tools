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

### ☠️ 兩個靜默預設：欄位沒寫不會報錯，只會被歸錯地方（2026-08-21 稽核）

`build-articles.py` 有兩個 fallback，**沒寫就套預設、不警告、build 全綠**：

| 位置 | 欄位 | 沒寫的話 | 後果 |
|---|---|---|---|
| 文章 frontmatter | `competition` | 落回 `"nba"` | 非 NBA 的文章會被當成 NBA 那一組 |
| `config/competitions.json` 的一筆 comp | `sport`（或 `schema.sport`） | `site_for()` 落回 `"soccer"` | 該賽事整組拿到**足球站**的站台識別 |

**截至 2026-08-21 兩個預設都沒有被踩到**：`competitions.json` 的 4 筆（nba／tpbl／plg／hbl）
都自己寫了 `sport: basketball`，`articles/` 的 13 篇也都寫了 `competition`。
⇒ 所以這不是待修的 bug，是**新增賽事或新增文章時要當成必填的兩個欄位**。

⚠️ **姊妹站判例（同一種缺陷真的會炸）**：foootball-tools 的 `article_section()` 預設是
`worldcup-2026`。2026-08-21 一篇英超文章沒有宣告 `section`，就被靜默收進世界盃專區——
專區篇數 +1、該文排到專區清單第 1 位、專區 description 與 ItemList schema 一起被改寫，
**build 全綠、零警告**，是人去讀 diff 才發現的（該站 PR #128）。
⚠️ 依姊妹站禁自動同步的原則，**這裡只記事實，不搬對方的程式**。

⭐ 這條與上面「沒有 `division`」同一族：**沒有東西可以拿來比對的錯，不會有任何 gate 叫**。
差別是 `division` 那次是模型知識填空，這次是**程式自己填的預設值**。

### ☠️ 第三種靜默失效：FAQ 的 H2 寫錯，`FAQPage` 整段不吐（2026-08-22 補）

`build-articles.py` 的 `FAQ_HEADING_RE` **只認三個字串**——H2 必須逐字是
`常見問題`／`常見問答`／`FAQ`，三選一。

多一個字、少一個字、或層級寫成 H3，`parse_faq()` 就找不到區段、回傳空 list，
`faq_node()` 收到空 list 回 `None` ⇒ **`FAQPage` 的 JSON-LD 整段不會輸出**。

☠️ **但頁面照常 render、問答內容照常顯示、build 全綠、零警告。**
肉眼看網頁完全正常，只有結構化資料悄悄消失。

⇒ 新文章寫完**一定要對建置產物驗一次**，不要只看網頁：

```
python3 -c "import re,json;t=open('public-basketball/articles/<slug>/index.html',encoding='utf-8').read();\
d=json.loads(re.search(r'<script type=\"application/ld\+json\">(.*?)</script>',t,re.S).group(1));\
print([n['@type'] for n in d['@graph']])"
```

`@graph` 裡看不到 `FAQPage` 就是中了。⭐ 與上面兩個同族：**輸出少了東西，沒有任何 gate 會叫**。

**截至 2026-08-22，14 篇文章全部都有吐出 `FAQPage`**（逐檔掃過）。
⇒ 同樣不是待修的 bug，是**寫新文章時 H2 要當成逐字比對的欄位**。


### ☠️ 第四種靜默失效：錯的陰性測試把真洞鎖成「預期行為」（2026-08-24 racing 實例補）

racing PR #59 加了一條陰性測試斷言「`race-zh.json` 不被任何百科頁群渲染」——前提是錯的
（賽季線就印站名譯名），測試卻綠了整整一批，還**擋住**下一批的正確修法（PR #60 要把那張表切進指紋，
它就紅）。錯的陰性測試比沒有測試更糟：它把洞登記成規格。

⇒ 寫「X 永遠不會 Y」型陰性斷言前，**逐頁群 grep 生成器實際讀了什麼**（不是憑「我記得沒印」），
並在測試註解寫下查證方法；範圍越全稱（never／any）越要逐一列舉查過的頁群。本站百科線與 racing 同架構，
指紋切片（譯名表 sha）若日後補上，同一條陰性測試型別會再出現。

### 人工維護的欄位（不是抓來的；改要附 source）

- `config/season-facts.json` → **只有 PLG 總冠軍**。
  PLG 官網冠軍賽頁是 JS 動態渲染、難以穩定 scrape，故記在這裡。
  **TPBL／HBL／NBA 的冠軍由 fetch 腳本從官網賽果自算，不要寫進這個檔。**
- 每筆必附 `sources` 與 `verified`（人工 cross-check 的說明）。

### 會到期失效的事實（時間到要回來改；不改**不會有任何東西告訴你**）

| 事實 | 到期點 | 動作 |
|---|---|---|
| `articles/lakers-sale-iger-kushner/` 的「尚待 NBA 批准」與 8 條 FAQ | 2026 年 9 月 NBA 董事會表決 | 依 `articles/lebron-james-76ers-24th-season/` 的 pattern：正文開頭補一段 `> **YYYY 年 M 月 D 日更新**：…` 引文區塊，**保留原查證狀態與判準不改寫** |
| `articles/wolves-lynx-sale-stad/` 的「尚待 NBA 董事會核准」與 8 條 FAQ | **同一場**董事會（ESPN 報導排定 2026-09-15、16 開會） | 同上 pattern。⚠️ 本篇對該狀態的敘述**刻意寫成可一次改掉的形狀**，不要散落改 |
| `articles/kevin-garnett-wolves-21-jersey-retirement/` 全篇未來式（「將是第二件」「將於…退休」）與 FAQ 的「儀式尚未舉行」 | 儀式日：美國時間 2027-02-28（台灣 2027-03-01），灰狼主場對塞爾提克賽後 | 同上 pattern（開頭補「更新」引文區塊）。⚠️ 標題、subtitle、lede、H1、正文、FAQ 的未來式**散在多處**，改時逐一掃「將」「會是」「尚未」；封面副標（`gen-basketball-cover.py`）也要一併改並重產 PNG |
| 同篇「六項隊史第一」表與「現有 30 隊唯一」 | 每個 NBA 賽季結束（現役球員仍在累積，任何一格可能被改寫；快照基準 2026-08-23） | 重跑該文查核用的 30 隊比對後決定要不要加更新註記；**基準日句（截至 2026-08-23）不可默默改日期不改數據** |
| `season-facts.json` 的 PLG 冠軍 | 2026-27 PLG 總冠軍賽結束 | 人工 cross-check 後更新 |
| 各聯盟 2026-27 開季日 | 官方公告時 | 見 §2-2——**公告前不准填** |

☠️ **上面前兩列是同一顆到期點：湖人篇與灰狼篇卡在同一場董事會。**
表決結果出來時**兩篇要一起改**——只改其中一篇，站上會同時存在「已核准」與「尚待核准」兩種說法，
而且兩篇互相內鏈，讀者一點就看到矛盾。

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
5. ⭐ **寫手會用中文數詞繞數字 gate**（2026-08-24 racing 兩批實證：「四站冠軍」「三人爭冠」）——
   派工單明寫「統計值一律阿拉伯數字＋claim」，驗收掃描要抓「[一二三四五六七八九十]＋站／人／勝」。
   「N 強爭冠」這類常識敘事要用**末站前的積分數學可能性**驗（1981 Jones 末站前已無機會，
   季末第三≠爭冠者），不是看季末前三名。
   （8/24 續）racing 已把這條做進 checker 本體（C4：default-deny＋具名成語白名單＋爭冠人數
   數學重算），**首批 12 篇寫手端零中文數詞違規**——gate 放進寫手自檢迴路才有威懾力，
   驗收端事後掃描只能抓漏。本站要做同型 gate 時照抄 racing 的 C4 形狀。
6. **修正輪後 grep 整份事實包**（含 `_comment`／`external_history`／note 欄），不只正文——
   查核桌連兩批都在 facts pack 註記裡抓到修正前的舊句殘留，雙 sha256 會把殘留一併核准。
7. ☠️ **語境語意主張不能用全域字串掃描判罪**（2026-08-24 racing：「緊追在後」在 2 分差成立、
   在 290 分差不成立；指揮位對同一詞全域 grep 誤傷 2 例合法用法）——掃描產出的是**候選清單**，
   判決要逐例帶語境（分差、順位、賽況）；反向也成立：別因一例誤用就把這類詞塞進禁字表。

---

## 4. 本檔維護規則

- **快照欄位增減 → 同一個 PR 更新 §1 的表。**
  `tests/test_snapshot_schema.py` 會擋：出現未登記的欄位、或必有欄位消失，
  就是紅燈，錯誤訊息會指回本檔。**文件與現實的漂移由 CI 抓，不靠誰記得同步。**
- 新增聯盟／新增人工維護欄位／新增紅線 → 同 PR 更新本檔。
- ⛔ 其餘一律不要動本檔。改得愈頻繁，愈沒有人信它。
