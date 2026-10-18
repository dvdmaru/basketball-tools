---
title: "名字都叫助攻，AST%、Assist Ratio、AST/TO 比的東西不一樣"
subtitle: "AST%、Assist Ratio、AST/TO 各在比什麼？同一個假設的 AST 6，代入兩條公式為什麼得到不同數字？"
lede: "NBA.com 統計詞彙表裡，AST%、Assist Ratio、AST/TO 都和助攻有關，比較對象卻不同：AST% 是球員在場時，他助攻的隊友進球所占的百分比；Assist Ratio 是球員每 100 個 possessions used 平均的助攻數；AST/TO 比較球員或球隊的助攻與失誤。"
slug: assist-metrics-basics
competition: nba
topic: nba-stats
type: "feature"
date: "2026-09-30"
topic_ref: "manual"
---

# 名字都叫助攻，AST%、Assist Ratio、AST/TO 比的東西不一樣

**新手村｜數據入門・助攻進階指標 AST%、Assist Ratio、AST/TO**

假設一名球員這場記了 6 次助攻（AST）。進階數據頁上，他同時掛著 AST%、Assist Ratio 和 AST/TO 三個數字，看起來完全不同。

三個名字都帶助攻，所以很容易拿來互比。但 [NBA.com 詞彙表](https://www.nba.com/stats/help/glossary)給它們的比較對象各不相同。box score 的基本欄位不熟的話，可以先看[怎麼讀 box score](/articles/read-box-score/)。

下面用同一組假設數字：AST 6、TmFGM 34、FGM 4、POSS 60。它們只是示範，不是任何球員的實測。

## AST% 在比什麼？

詞彙表對 AST%（Assist Percentage）的定義是：球員在場時，他助攻的隊友進球所占的百分比。英文原句是 "teammate field goals a player assisted on while they were on the floor"。公式是 AST / (TmFGM - FGM)。

FGM（Field Goals Made）有自己的條目：球員或球隊投進的 field goal 數，包含兩分球與三分球。TmFGM 只出現在這條公式裡，沒有條目。照定義句的讀法，TmFGM 是球員在場時的球隊進球數，TmFGM 減 FGM 就是他在場時隊友的進球數。不能把 TmFGM 直接當成全場或整季的球隊進球數。

代入假設數字：34 減 4 是 30，AST% 是 6 除以 30，等於 0.2。公式沒有乘 100，換成百分比是 20%，這是本文的換算。

## 同一個假設的 AST 6，Assist Ratio 為什麼是 10？

Assist Ratio 的定義是：球員每 100 個 possessions used 平均的助攻數。公式是 (AST * 100) / (POSS)。

乘 100 已經寫在公式裡，結果直接就是「每 100 個」的尺度。假設 POSS 是 60：6 乘 100 是 600，除以 60，等於 10。

助攻數同樣是 6，AST% 的假設值是 20%，Assist Ratio 是 10。差別在分母：一個放球員在場時隊友的進球，一個放 POSS。兩個數字的單位不同，不能比大小。

詞彙表沒有句子把 POSS 和 possessions used 畫上等號，所以 60 只是代入公式的假設值。公式分母同樣寫 POSS 的還有使用率 USG%，可以看[使用率與 PIE 入門](/articles/usage-rate-pie-basics/)。

## AST/TO 拿球員或球隊的助攻去比失誤

AST/TO（Assist to Turnover Ratio）的定義是：球員或球隊的助攻數，與其失誤數相比。

## 只改 POSS 或 TmFGM，AST% 和 Assist Ratio 哪個會動？

把基準組拿來，每次只改一個數字：

| 假設的改動 | AST% | Assist Ratio |
|---|---|---|
| 基準：AST 6、TmFGM 34、FGM 4、POSS 60 | 6 / 30 = 0.2（20%） | 600 / 60 = 10 |
| 只把 POSS 改成 75 | 不變，0.2 | 600 / 75 = 8 |
| 只把 TmFGM 改成 44 | 6 / 40 = 0.15（15%） | 不變，10 |

這兩條公式裡，POSS 只出現在 Assist Ratio，TmFGM 只出現在 AST%，所以各改各的。助攻數不變時，分母變大，結果就變小。

表裡的數字全是假設代入的算術，沒有哪一格代表好或壞。

看到名字裡有助攻的數字，先問它把助攻放在誰旁邊：球員在場時隊友的進球、公式中的 POSS，還是失誤。放的東西不同，數字就不能互換，也不能直接比高低。

## 常見問題

### AST% 與 Assist Ratio 是同一個指標嗎？

不是。AST% 是球員在場時，他助攻的隊友進球所占的百分比，公式 AST / (TmFGM - FGM)。Assist Ratio 是球員每 100 個 possessions used 平均的助攻數，公式 (AST * 100) / (POSS)。兩條的分母不同，數字不能互比。

### AST/TO 的公式是什麼？

詞彙表的 AST/TO 條目只有定義句：球員或球隊的助攻數，與其失誤數相比。條目沒有列出算式。要知道實際算法，以使用這個數字的頁面說明為準。

### TmFGM 是什麼？可以直接當成球隊進球數嗎？

TmFGM 只出現在 AST% 的公式裡，詞彙表沒有它自己的條目。照 AST% 定義句的讀法，它是球員在場時的球隊進球數，不能直接當成全場或整季的球隊進球數。FGM 有條目，是球員或球隊投進的 field goal 數。

### %AST 與 AST% 是同一個條目嗎？

不是。%AST（Percent of Team's Assists）是球員在場時，他的助攻占球隊助攻的百分比。AST% 是球員在場時，他助攻的隊友進球所占的百分比。前者拿他的助攻去比球隊的助攻，後者去比隊友的進球。

## 範圍與版本

- 本文依 2026 年 9 月 25 日存檔的 NBA.com 詞彙表頁面寫成。詞彙表條目沒有標示賽季。之後頁面若有更動，以官方頁面為準。
- AST/TO 沒有列出算式，只限這份存檔。這不表示 NBA 其他地方沒有它的算法。
- 文中的 AST 6、TmFGM 34、FGM 4、POSS 60，以及改成 75 與 44 的版本，全是假設。

## 資料來源

- NBA.com Stats：[Stat Glossary](https://www.nba.com/stats/help/glossary)，條目 AST%、AST Ratio、AST/TO、%AST、FGM、USG%
- 延伸閱讀：[怎麼讀 box score](/articles/read-box-score/)；[使用率與 PIE 入門](/articles/usage-rate-pie-basics/)
