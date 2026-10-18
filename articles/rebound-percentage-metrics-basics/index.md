---
title: "籃板一樣多，REB Chance% 和 Adjusted 為什麼不同？"
subtitle: "NBA 的 REB%、REB Chance%、Adjusted 指標怎麼分？"
lede: "假設一名球員搶下 6 個籃板（REB），有 10 次 rebound chance，其中 2 次把籃板讓給隊友。依 NBA.com 詞彙表的公式，REB Chance% 是 6/10，Adjusted 是 6/(10 − 2)，換成百分比是 60% 與 75%。分子相同，分母不同。"
slug: rebound-percentage-metrics-basics
date: "2026-10-05"
competition: nba
topic: nba-stats
topic_ref: "manual"
type: "feature"
---

# 籃板一樣多，REB Chance% 和 Adjusted 為什麼不同？

**新手村｜數據入門・籃板類指標 REB%、Rebound Chance%、Adjusted 系列**

## 同樣 6 個籃板，為什麼是 60% 還是 75%？

假設一名球員 REB 6、REB Chances 10、Deferred REB Chances 2。

| 指標 | 詞彙表公式 | 代入假設數字 | 換成百分比 |
|---|---|---|---|
| REB Chance%（Rebound Chance Percentage） | `(REB)/(REB Chances)` | 6/10 = 0.6 | 60% |
| Adjusted REB Chance %（Adjusted Rebound Chance Percentage） | `(REB)/(REB Chances - Deferred REB Chances)` | 6/(10 − 2) = 0.75 | 75% |

公式本身沒有乘 100，百分比是本文換算的。

兩個百分比的分子都是 6，差在分母。

所以 75% 不是這名球員多搶了球，是分母少算了 2 次。

## Rebound Chance 怎麼認定？

分母的 10，要先知道怎麼數。

REB Chances（Rebound Chances）的認定條件是：球越過籃框下方之後、被完整抓下之前，球員只要在任一時點是離球最近的球員，就有一次 rebound chance。

REB Chance% 用球員或球隊取得的籃板數，去比 rebounding chances 的次數。

## Adjusted 版扣掉的 2 次是什麼？

扣掉的是 Deferred REB Chances。條目的定義是：球員有 rebound chance，卻 defers the rebound to a teammate 的次數。中文可以讀成把籃板讓給隊友。

回到假設數字。10 次 chance 裡有 2 次讓給隊友，這 2 次留在 REB Chance% 的分母裡，Adjusted 把它們拿掉。

## REB% 可以拿 Chance% 頂替嗎？

REB%（Rebounding Percentage）的定義是：球員或球隊在場上時取得的 available rebounds 百分比。照定義句的讀法，分子是搶下的籃板，分母是 available rebounds。

available rebounds 和 rebounding chances 是兩個詞。詞彙表沒有把其中一個定義成另一個，也沒有給換算。所以 REB Chances 不能直接填進 REB% 的分母。

## Contested REB% 又在比什麼？

Contested 與 Uncontested 換了一個問題：取得籃板時，附近有沒有對手？

Contested REB 是搶板者 3.5 呎以內有對手的籃板。

Uncontested REB 是球員或球隊在沒有對手於 3.5 呎以內時取得的籃板數。

Contested REB% 的公式是 `(Contested REB)/(REB)`。分母是 REB，公式裡沒有 Chances。

## 看到一個籃板百分比，先問分母是什麼

比較兩個百分比之前，先確認兩邊的分母是同一種。分母不同，高低就不能直接比。

籃板數本身怎麼出現在 box score 上，可先讀[如何讀 Box Score](/articles/read-box-score/)。同系列還有[失誤率類指標入門](/articles/turnover-rate-metrics-basics/)，以及[Usage Rate 與 PIE 入門](/articles/usage-rate-pie-basics/)。

## 常見問題

### REB% 有公式嗎？

詞彙表的 REB%、OREB%、DREB% 條目只有定義句，沒有 Formula 欄。REB% 的定義句是球員或球隊在場上時取得的 available rebounds 百分比，OREB% 與 DREB% 同型，各限進攻與防守。沒列公式，不表示 NBA 沒有算法。

### REB Chance% 的分母是什麼？

分母是 REB Chances，公式是 `(REB)/(REB Chances)`。球員在球越過籃框下方到被完整抓下之間，任一時點是離球最近的球員，就有 rebound chance。一次投籃未進會產生幾個 chance，以及這些 chance 是否互斥，REB Chances 條目沒有說明。

### Adjusted REB Chance % 與 REB Chance% 差在哪裡？

差在分母。Adjusted 的公式是 `(REB)/(REB Chances - Deferred REB Chances)`，扣掉球員有 rebound chance 卻把籃板讓給隊友的次數。OREB 與 DREB 各有對應的 Adjusted 條目，分別扣 Deferred OREB Chances 與 Deferred DREB Chances。

### Contested 籃板與 Uncontested 籃板怎麼分？

看 3.5 呎以內有沒有對手。Contested REB 是搶板者 3.5 呎以內有對手的籃板，Uncontested REB 是沒有對手在 3.5 呎以內時取得的籃板數。Contested REB%、Contested OREB%、Contested DREB% 的分母分別是 REB、OREB、DREB。詞彙表的條目清單裡，Uncontested 只有 REB、OREB、DREB 三條計數條目，沒有百分比條目。

## 範圍與版本

- 本文依 NBA.com 詞彙表在 2026 年 9 月 25 日的版本。詞彙表條目沒有標示賽季，條目之後可能改動，以官方頁面為準。
- 文中的 REB 6、REB Chances 10、Deferred REB Chances 2 都是假設數字，不是任何球員或賽季的實測。
- 「沒有 Formula 欄」只指這個版本裡的 REB%、OREB%、DREB% 條目。

## 資料來源

- NBA.com Stats：[Stat Glossary](https://www.nba.com/stats/help/glossary)，2026 年 9 月 25 日版本。引用條目：REB、REB%、OREB%、DREB%、REB Chance%、REB Chances、Adjusted REB Chance %、Adjusted OREB Chance %、Adjusted DREB Chance %、Deferred REB Chances、Deferred OREB Chances、Deferred DREB Chances、Contested REB、Contested REB%、Contested OREB%、Contested DREB%、Uncontested REB、Uncontested OREB、Uncontested DREB 與條目清單（Jump To）。
