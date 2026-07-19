# basketball.twtools.cc 建站（clone baseball-tools 架構）

**Task 起手日**：2026-07-19
**完工硬性條件**：所有 story 全部 ✅（文章 story 例外：PR 開好停等 Charlie cross-check 即算此階段完成）

## Story 1: Repo 骨架
- [ ] 引擎移植完成：`python3 scripts/update-basketball.py --skip-fetch` 全綠、`public-basketball/` 產出首頁+llms.txt+sitemap+feed
- [ ] 零密鑰：`grep -riE "(api[_-]?key|token|secret).{0,4}[:=]" scripts config *.jsonc` 無密鑰值命中
- [ ] git init + initial commit 進 main（僅此一次；之後全走 PR）

## Story 2: 數據管線
- [ ] `fetch-nba.py`／`fetch-tw-hoops.py`／`fetch-hbl.py` 實跑成功，`leagues/*.json` 落地
- [ ] 數字抽驗：NBA 冠軍（尼克 4:1 馬刺）自 ESPN 賽果計算；TPBL 冠軍（夢想家 4:3 國王）自官網 API 賽果計算；HBL 冠軍戰比分（松山 87:71／陽明 61:53）與獨立查證來源吻合
- [ ] `fetch-hbl.py --history` 產出 106-114 學年度歷屆冠軍 9/9

## Story 3: Dashboard 頁
- [ ] 首頁：冠軍榜＋NBA/TPBL/PLG/HBL 戰績 tabs＋tiles＋FAQ，全 server-rendered、CSS-only tabs
- [ ] `/standings/`（NBA 東西區）、`/tw/`（TPBL×PLG）、`/hbl/`（四強+歷屆冠軍）、`/data/` hub 四頁生成
- [ ] 休賽季誠實標示：as-of chip＋「休賽季模式」字樣出現在首頁

## Story 4: 長青文（PR 停等人工 cross-check，不自動發）
- [ ] `nba-league-guide` NBA 完全指南
- [ ] `taiwan-hoops-two-leagues` 台灣職籃雙聯盟格局
- [ ] `hbl-league-guide` HBL 完全指南
- [ ] `nba-2026-offseason` 2026 休賽季全景
- [ ] 每篇：facts pack → 寫稿 → 查核 → humanizer 去 AI 味 → 全形標點/簡體=0/港式詞=0 掃描 → PR

## Story 5: SEO/GEO 基建
- [ ] llms.txt（build-time 生成）、robots.txt（歡迎 AI bots＋Sitemap 指向本站）
- [ ] 新 IndexNow key 檔在站根、indexnow-ping.mjs 指向 basketball host
- [ ] 姊妹站互連 footer 出現在全站（含 baseball／foootball 回鏈）
- [ ] JSON-LD @graph＋FAQPage 鏡射可見文字（首頁+三數據頁）
- [ ] og-home.png 2400×1260＋favicon/icons/webmanifest

## Story 6: 自動化+部署
- [ ] `gh repo create dvdmaru/basketball-tools --public` + push main
- [ ] secrets 設好並 `gh secret list` 驗證（CLOUDFLARE_API_TOKEN／CLOUDFLARE_ACCOUNT_ID）
- [ ] `wrangler deploy` 上線，live 驗證（cache-bust）：首頁/standings/tw/hbl/data/llms.txt/robots.txt/sitemap.xml 全 200＋內容 token
- [ ] `gh workflow run basketball-daily.yml` 一次真跑：run log 有 Version ID（不信綠燈）

## Story 7: 收尾
- [ ] PUBLIC 終掃（含 git 歷史零密鑰）
- [ ] 記憶同步：CoWork L0 專案表＋L2、per-project `project_basketball_twtools.md`
- [ ] Charlie 手動待辦清單（🔴粗體）：GA4 property／GSC／sites-dashboard sites.json／topic-desk
