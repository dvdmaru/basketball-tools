---
slug: rim-defense-metrics-basics
competition: nba
topic: nba-stats
type: "feature"
date: "2026-10-13"
title: "籃下 DFG% 只有 25%，就比 50% 防得好嗎？"
subtitle: "對手 4 投 1 中是 25%，40 投 20 中是 50%。先看哪一組出手，再看出手數，才能知道 DFG% 這個百分比背後裝了什麼。"
lede: "籃下 DFG% 是防守籃框時，對手的命中數除以出手數。比較之前，得先確認欄位確實是籃下那組，再看 DFGA 有幾次；25% 可能只來自 4 次出手，單看百分比不足以判定誰防得更好。"
topic_ref: "manual"
---

# 籃下 DFG% 只有 25%，就比 50% 防得好嗎？

**新手村｜數據入門・籃下防守 DFGA、DFGM、DFG%**

假設兩名防守者，甲在籃下防守時讓對手 4 投 1 中，乙讓對手 40 投 20 中。甲的對手命中率是 25%，乙是 50%。只看百分比，甲漂亮得多。

現在再給兩人各加一次對手投籃，而且都進了。甲變成 2 ÷ 5 = 40%，乙則是 21 ÷ 41，約 51.2%。同樣多被進一球，甲跳了 15 個百分點，乙只動了約 1.2 個百分點。

這組假設算例沒有告訴你誰防得比較好，卻說明了少看一欄的代價：DFG% 旁邊的出手數，不能省。

## DFG% 記的是對手，DFGA 才看得出出手多少

NBA 詞彙表的籃下防守三欄，都以球員或球隊防守籃框（defending the rim）為條件，計的是對手的出手與命中。

| 縮寫 | 完整名稱 | 記的是什麼 |
|---|---|---|
| DFGA | Field Goals Defended at Rim Attempted | 球員或球隊在籃下防守時，對手出手幾次 |
| DFGM | Field Goals Defended at Rim Made | 球員或球隊在籃下防守時，對手投進幾球 |
| DFG% | Field Goals Defended at Rim Percent | 球員或球隊在籃下防守時，對手出手的命中百分比 |

公式是 **DFG% = DFGM ÷ DFGA**，用百分比表示。

甲的 25% 建立在 4 次出手上，乙的 50% 建立在 40 次出手上。乙的分母是甲的 10 倍，這個差別不會出現在百分比本身。

DFGM、DFGA 這種「命中數配出手數」的讀法，也可以搭配[技術統計表](/articles/read-box-score/) 練習。先看兩欄原始數字，才知道命中率從哪裡來。

## 同樣寫 DFG%，不保證是同一組出手

NBA 詞彙表另有 Defended Field Goal Percentage，也縮寫成 DFG%。這條寫的是球員防守對方出手（defending the shot）時，對手的命中率；籃下那條則明寫球員或球隊防守籃框。

| 同為 DFG% 的兩條 | 定義的情境 | 詞彙表分類 |
|---|---|---|
| Field Goals Defended at Rim Percent | 球員或球隊防守籃框 | Tracking |
| Defended Field Goal Percentage | 球員防守對方出手 | Defense |

兩條公式都寫 DFGM ÷ DFGA，但這不能證明分子、分母取自同一組出手。

所以比較兩個 DFG% 之前，先看表名與完整欄名。把籃下防守和一般防守混在一起，連比較的對象都可能換了。防守出手的另一個常見名詞，可以接著讀[contested shot 入門](/articles/contested-shots-basics/)。

## Shot At Rim 的 5 英呎，不能直接搬來當防守門檻

「籃下」很容易讓人想補上一個距離。詞彙表確實有 Shot At Rim 這個條目，定義是離籃框 5 英呎內的任何出手。

但籃下防守的 DFGA、DFGM、DFG% 三條定義，沒有寫距離，也沒有引用 Shot At Rim。不能只因兩個名字都有 Rim，就把 5 英呎直接套進防守欄位。這三條定義也沒有說明怎樣把一球歸給某名防守者，不能拿它們還原完整的記錄流程。

看見 25%，先問「哪一組出手、總共有幾次」，比急著替防守者排名更有用。百分比相同或較低，都還沒有交代這兩件事。

## 常見問題

### 籃下防守的 DFG% 怎麼算？

它是球員或球隊防守籃框時，對手的命中數 DFGM 除以出手數 DFGA，再以百分比表示。例如對手 4 投 1 中，就是 25%；比較時也要一起看 DFGA。

### 籃下防守的 DFG% 和一般防守的 DFG% 是同一個數字嗎？

不能只看縮寫認定。NBA 詞彙表把它們列成兩條：籃下那條寫球員或球隊防守籃框，一般那條寫球員防守對方出手。兩條公式文字相同，不表示取的是同一組出手；請看表名與完整欄名。

### 詞彙表有說籃下是離籃框幾英尺嗎？

籃下防守的 DFGA、DFGM、DFG% 三條定義沒有寫距離。另一條 Shot At Rim 寫的是離籃框 5 英呎內的出手，但三條沒有引用它，不能直接套用這個門檻。

## 資料來源

- [NBA Stats Glossary](https://www.nba.com/stats/help/glossary)：Field Goals Defended at Rim Attempted／Made／Percent、Defended Field Goal Percentage、Shot At Rim，採 2026 年 9 月 25 日保存的無版次頁面。「未寫距離」只指所列三條定義，不代表 NBA 其他文件從未公布相關門檻。
- 甲、乙與全部數字都是說明用的假設；百分比由公式換算，除法以 DFGA 大於 0 為前提。「籃下防守」是本文對 defending the rim 的中文稱呼。
