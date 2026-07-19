# basketball-tools — 籃球數據誌（basketball.twtools.cc）

非官方繁體中文籃球數據與內容站：**NBA × 台灣職籃（TPBL／PLG）× HBL 高中籃球**。
100% 靜態、server-rendered、零 client fetch（為被 AI 引用設計，GEO/AEO）。
架構 clone 自姊妹站 [dvdmaru/baseball-tools](https://github.com/dvdmaru/baseball-tools)（棒球數據誌）。

- Live：https://basketball.twtools.cc/
- 部署：Cloudflare Workers static assets，worker `basketball-tools`，帳號 charlie.chien2019
  （account id `2f123fdee05d453c8a077b6ba541c45d`，非機密；token 走環境變數，永不入 repo）

## 三層架構

1. **數據自動更新**：`scripts/fetch-*.py` 抓公開資料 → `leagues/*.json` 快照
2. **文章管線**:`articles/<slug>/index.md` + `cover.png` → `build-articles.py` → 靜態頁
   （FAQ「### 問句？」自動鏡射 FAQPage JSON-LD；`config/draft-exclude.json` 草稿 gate）
3. **Worker 部署**：`public-basketball/` 整包上 CF Workers；每日 GH Actions
   （`.github/workflows/basketball-daily.yml`，`workflow_dispatch` 可手動觸發）

## 資料源（2026-07-19 實測選型，全部免金鑰）

| 聯盟 | 源 | 性質 |
|---|---|---|
| NBA | ESPN 公開 JSON（site.api.espn.com） | 未文件化私有 API；datacenter IP 可直通。官方 stats.nba.com／cdn.nba.com 已上 TLS 指紋+Referer 判定，僅作輔助 |
| TPBL | api.tpbl.basketball（官網未文件化 API） | 例行賽戰績與總冠軍由賽果自算 |
| PLG | pleagueofficial.com/standings（server-rendered HTML） | 戰績表直接 parse；總冠軍為 editorial fact（`config/season-facts.json`，附來源） |
| HBL | hbl.com.tw `/rest/*`（官網未文件化 API） | 總決賽名次由賽果推導；歷屆冠軍 `fetch-hbl.py --history`（回溯至 106 學年度） |

所有未文件化介面：UA＋指數退避＋fail-soft（斷源沿用 repo 內快照，頁面 as-of 誠實標示）。
**basketball-reference 條款明文禁爬，永不使用。**

## 紅線

- **IP guardrails**：封面／頁面純文字，無隊徽、球員照、聯盟 logo；全站非官方 disclaimer；文章結尾無 CTA。
- **HBL＝未成年學生**：只整理隊伍層賽果與名次，不建個別球員數據；負面題材永不進自動管線；
  影音為 Hami Video 獨家授權，不嵌入不觸碰。
- **PUBLIC repo 零密鑰**：token 全走 GH Secrets／本機 `~/.config/cloudflare/`。

## 建置與部署

```bash
# 重建（不部署）
python3 scripts/update-basketball.py            # 抓資料 + 重生
python3 scripts/update-basketball.py --skip-fetch   # 只重生（用既有快照）

# 手動部署（本機；token 從檔案讀，勿貼明文）
CLOUDFLARE_API_TOKEN=$(cat ~/.config/cloudflare/foootball-tools-2019.token) \
CLOUDFLARE_ACCOUNT_ID=2f123fdee05d453c8a077b6ba541c45d \
npx wrangler deploy -c wrangler-basketball.jsonc </dev/null

# 雲端隨選重建+部署（不需本機 token）
gh workflow run basketball-daily.yml --ref main
```

跑序鐵則（sitemap 覆寫坑）：`build-articles.py` 會整個覆寫 `sitemap.xml` → 必須先跑它，
再跑各 generator（`gen-nba-standings` / `gen-tw-standings` / `gen-hbl-page` /
`gen-basketball-data-hub`，各自 re-merge 自己的 path）。`update-basketball.py` 已按此編排。

## 品牌

深色 ember 主題（炭黑 `#14100e` ＋ 暖白 `#f3ece4` ＋ 籃球橘 `#ef7d3a` ＋ 木地板金 `#d9a04c`），
與 baseball（navy／金）、foootball（森林綠）區隔。變體：court／slate／jade／violet
（`build-articles.py` 的 `BB_THEMES`，localStorage key `bk-theme`）。
封面與品牌資產：`gen-basketball-cover.py`／`gen-basketball-brand-assets.py`（HTML→Chrome headless PNG）。
