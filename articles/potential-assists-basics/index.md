---
title: "Potential Assists 比 AST 多的那截，能讀成隊友投丟嗎？"
subtitle: "Potential Assists 的條件是隊友接球後 1 dribble 內出手，定義沒寫投進或投失；NBA 詞彙表沒有給兩欄相減的等式"
lede: "Potential Assists 的定義是：任何傳給隊友、隊友接球後 1 dribble 內出手的傳球。條件是出手，定義沒寫投進或投失。AST 的定義寫直接導致投進，兩條條件不同，詞彙表也沒給兩欄的等式。因此 Potential AST 減 AST 的差額，不能直接讀成隊友投丟的次數。"
slug: potential-assists-basics
competition: nba
topic: nba-stats
type: "feature"
date: "2026-10-13"
topic_ref: "manual"
---

# Potential Assists 比 AST 多的那截，能讀成隊友投丟嗎？

**新手村｜數據入門・Potential Assists**

## Potential Assists 要求隊友投進嗎？

Potential AST（Potential Assists）的條件有兩個。傳球要給隊友。隊友接球後，要在 1 dribble 內出手（shoots）。

條件設在出手，不在結果。

「1 dribble 內」可以讀成包含 0 次與 1 次運球：接球後直接出手，或運一次球再出手。這是對 within 1 dribble 的讀法，詞彙表沒有另外解釋。

## Potential Assists 和 AST 的定義，看得出誰包含誰嗎？

把兩條定義並排：

| 條目 | 定義 |
|---|---|
| AST（Assists） | 球員的助攻數，也就是直接導致投進的傳球（passes that lead directly to a made basket） |
| Potential AST（Potential Assists） | 任何傳給隊友、隊友接球後 1 dribble 內出手的傳球 |

AST 的定義沒有列運球次數，也沒有說 directly 怎麼判斷。兩句湊在一起，不足以確認一欄包含另一欄。

詞彙表沒有把任何欄位寫成 Potential AST 的組成。AST 在 box score 上怎麼讀，可以先看[怎麼讀 box score](/articles/read-box-score/)。

## 假設 Potential AST 是 10、AST 是 6，差的 4 是投丟嗎？

先做算術。假設一名球員的 Potential AST 是 10，AST 是 6。10 減 6 是 4。

要把這個 4 讀成「4 次隊友投丟」，需要兩件事同時成立：每一筆 AST 都落在 Potential AST 裡，而且多出來的每一筆都是投丟。詞彙表兩條定義都沒有寫這兩件事。

再看一個假設的球。隊友接球後運了 3 次球才投進。3 次超過「1 dribble 內」，照字面不符合 Potential Assists。這一球算不算 AST，詞彙表沒有寫。

差額裡混了哪些情況，單靠詞彙表分不清。所以這個 4 只能讀成「兩欄相差 4」，不能直接讀成「投丟 4 次」。

其他幾個跟助攻有關的指標，另見[助攻指標入門](/articles/assist-metrics-basics/)。

## 常見問題

### Potential Assists 是不是「隊友出手但沒投進」的次數？

不能這樣讀。定義寫的是傳給隊友、隊友接球後 1 dribble 內出手的傳球，沒有寫投進或投失。Potential AST 減 AST 的差額，詞彙表沒有給等式，不足以證明是投丟次數。

### 隊友接球後運了 3 次球才投進，算不算 Potential Assists？

照字面不算。3 次運球超過「1 dribble 內」。這一球算不算 AST，詞彙表沒有寫。

### Potential Assists 和 Free Throw Assists、Secondary Assist 是同一類嗎？

三條都列在 Tracking 類型下，但各有各的條件。Potential Assists 是傳給隊友，隊友接球後 1 dribble 內出手。Free Throw Assists 是傳給一名接球後 one dribble 內造成投籃犯規的球員。Secondary Assist 是傳給一名在 1 second 內且沒有運球，就被記錄一次助攻的球員。

## 範圍與版本

- 本文依據 NBA.com 統計詞彙表 2026-09-25 的快照；頁面之後若有更動，以官方頁面為準。
- 詞彙表條目沒有標示賽季。
- Potential AST 與 AST 兩個條目都沒有 Formula 欄。沒寫公式，不等於 NBA 沒有算法。
- Potential AST 條目的 Contexts 列 Tracking、Player、Passing，沒有列 Team。快照沒有說明球隊層級的 Potential Assists 有沒有。
- 文中的 10、6、3 次運球都是假設，用來對照定義字面，不是實測數據。

## 資料來源

- [NBA.com Stats Glossary（統計詞彙表）](https://www.nba.com/stats/help/glossary)：Potential AST（Potential Assists）、AST（Assists）、FT Assists（Free Throw Assists）、Secondary Assist 各條目
- 站內延伸閱讀：[怎麼讀 box score](/articles/read-box-score/)、[助攻指標入門](/articles/assist-metrics-basics/)
