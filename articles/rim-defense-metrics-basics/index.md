---
slug: rim-defense-metrics-basics
competition: nba
topic: nba-stats
type: "feature"
date: "2026-10-13"
title: "NBA.com 詞彙表裡，籃下防守的 DFG% 和一般防守的對手命中率共用同一個縮寫"
subtitle: "依 2026 年 9 月 25 日的詞彙表頁面，籃下防守的對手出手數、命中數、命中率各有一條定義；只看 DFG% 這個百分比，也讀不出對手在籃下投了幾球。"
lede: "NBA.com 統計詞彙表（2026 年 9 月 25 日的頁面內容）把籃下防守（defending the rim）的對手出手數、命中數和命中率各列一條，縮寫是 DFGA、DFGM、DFG%。詞彙表另有一般防守（defending the shot）的三條，縮寫相同，公式欄寫的字也相同。只看縮寫，讀不出一個 DFG% 屬於哪一組；只看百分比，也讀不出對手在籃下投了幾球。"
topic_ref: "manual"
---

# NBA.com 詞彙表裡，籃下防守的 DFG% 和一般防守的對手命中率共用同一個縮寫

**新手村｜數據入門・籃下防守 DFGA、DFGM、DFG%**

逛 NBA.com 的球員防守數據，會碰到一排縮寫：DFGA、DFGM、DFG%。其中一組標的是對手在籃下的出手，看起來很像「護框數據」。

本文依據的是 NBA.com 統計詞彙表（NBA Stats Glossary）2026 年 9 月 25 日取得的頁面內容，以下說「詞彙表」都指這一版。「籃下防守」是本文對原文 defending the rim 的中文稱呼，詞彙表自己沒有用這個中文詞。本文不寫任何真實球員或球隊的數字，示範一律用標明「假設」的練習。

讀完之後，看到一個 DFG% 數字，你可以自己問三件事：這是詞彙表的哪一條、對手出手了幾次、「籃下」兩個字有沒有距離。

## 籃下防守的三欄，各回答對手的一件事

詞彙表為籃下防守列了三條，名稱都以 Field Goals Defended at Rim 開頭。

| 詞彙表條目 | 縮寫 | 中文意思 | 公式欄 |
|---|---|---|---|
| Field Goals Defended at Rim Attempted | DFGA | 球員或球隊在籃下防守時，對手的投籃出手數 | 無 |
| Field Goals Defended at Rim Made | DFGM | 同一情境下，對手的投籃命中數 | 無 |
| Field Goals Defended at Rim Percent | DFG% | 同一情境下，對手出手的命中百分比 | (DFGM)/(DFGA) |

三條的類型欄（Type）都標 Tracking，也就是追蹤數據。命中率那一條的定義是：球員或球隊在防守籃框（defending the rim）時，對手出手中命中的百分比。出手數與命中數兩條的句型相同。

三欄的關係是一條除法。DFGM 除以 DFGA，得到 DFG%。DFGA 在公式裡是分母，它告訴你這個百分比建立在幾次出手上。

## 一般防守的三條也叫 DFGA、DFGM、DFG%

詞彙表裡還有另一組條目，縮寫和籃下那組一模一樣，定義的情境換成防守出手（defending the shot），類型欄標 Defense（防守）。

| 縮寫 | 籃下防守那條（defending the rim） | 一般防守那條（defending the shot） |
|---|---|---|
| DFGA | Field Goals Defended at Rim Attempted | Defended Field Goals Attempted |
| DFGM | Field Goals Defended at Rim Made | Defended Field Goals Made |
| DFG% | Field Goals Defended at Rim Percent | Defended Field Goal Percentage |

一般防守的命中率那一條，公式欄也寫 (DFGM)/(DFGA)，和籃下那條的字一樣。兩條的算法是否相同，條目沒有說明。

本文的讀法是：一張表上如果只寫 DFG%、沒有寫 at Rim，單看這個縮寫，分不出它屬於哪一組。實際的 NBA.com 資料頁可能用表名或欄名標明了歸屬，詞彙表頁面本身看不出來，這一點本文無法判定。

## 詞彙表沒有替籃下防守寫幾英尺

讀者最容易做的事，是替「籃下」補一個距離，例如以為它指離籃框幾英尺內。籃下防守的三條定義都只寫「球員或球隊在防守籃框時」，沒有距離數字，也沒有英尺這類單位。怎樣算在防守籃框、由哪位防守者承接，三條也都沒有寫。

詞彙表裡另有一條 Shot At Rim（籃下出手）寫了距離：離籃框 5 英尺以內的任何出手。它和籃下防守三條是各自並列的條目，三條的定義沒有引用它，詞彙表也沒有說兩者的範圍相同。

## 籃下防守旁邊另列的三條防守欄位

詞彙表裡還有三條常被放在一起讀的防守欄位，各有各的定義。

**阻攻（Blocks）。** 進攻球員出手，防守球員把球撥掉，擋下他得分的機會。BLK 欄的讀法見[技術統計表](/articles/read-box-score/)。

**命中率差（Percentage Points Difference）。** 射手整季的一般命中率，與防守球員或球隊盯防（guarding）該射手時的命中率，兩者之差，公式是 FG% - DFG%。詞彙表寫，好的防守數字會是負數。公式裡的 DFG% 是籃下那條還是一般防守那條，條目沒有寫。

**Deterrent Factor。** 球員在某個特定對位中每回合的出手數，占他整季平均每回合出手數的百分比。它比的是出手頻率，不是命中率。

同為防守欄位的另一篇新手村文章，可接著讀[contested shot 入門](/articles/contested-shots-basics/)。

## 假設甲的 DFG% 是 25%、乙是 50%，兩人的出手數差了 10 倍

下面用兩名假設的防守者練習。數字都是假設，不屬於任何真實球員。

- 甲：籃下防守的 DFGA 是 4，DFGM 是 1。
- 乙：籃下防守的 DFGA 是 40，DFGM 是 20。

照詞彙表籃下 DFG% 那一條的公式 (DFGM)/(DFGA) 算：

- 甲：1 除以 4，得 0.25。
- 乙：20 除以 40，得 0.50。

換成百分比，甲是 25%，乙是 50%。這個換算是本文做的，詞彙表公式欄只寫了除法。

接著回答三個問題。

**問題一：只給 25% 與 50% 兩個數字，少了哪一欄的資訊？** 少了 DFGA。甲的 25% 建立在 4 次出手上，乙的 50% 建立在 40 次出手上，後者的出手數是前者的 10 倍。

**問題二：如果一張表只寫 DFG%，沒有寫 at Rim，這一欄可能是詞彙表的哪幾條？** 可能是籃下防守那條，也可能是一般防守那條。兩條都掛著 DFG%，公式欄寫的字也一樣。要分辨，得看表名、欄名，或欄位旁的說明。

**問題三：這兩人「在籃下」的範圍，詞彙表給了距離嗎？** 沒有，理由見〈詞彙表沒有替籃下防守寫幾英尺〉那一節。

比較兩個人的 DFG% 之前，可以先比兩人的 DFGA。甲乙的命中率不同，兩人的出手數也差很多；單看百分比，看不出分母有多大，也看不出這個比較有多穩定。

## 範圍與版本

本文只讀 NBA.com 統計詞彙表 2026 年 9 月 25 日的頁面內容。詞彙表會更新，之後請以官方最新版為準。這幾個欄位的名稱，在 NBA 2025-26 規則書、FIBA 2026 版規則書（2026 年 10 月 1 日生效）與 NBA 2023 CBA 的本機全文文字檔裡都查無。

## 常見問題

### 籃下防守的 DFG% 怎麼算？

依 NBA.com 統計詞彙表 2026 年 9 月 25 日的頁面內容，籃下防守（defending the rim）那條 DFG% 的公式是 (DFGM)/(DFGA)，也就是對手的命中數除以出手數。詳見〈籃下防守的三欄，各回答對手的一件事〉。

### 籃下防守的 DFG% 和一般防守的 DFG% 是同一個數字嗎？

NBA.com 統計詞彙表 2026 年 9 月 25 日的頁面內容裡，兩條都掛 DFG%，公式欄的字也相同，但情境不同：一條寫 defending the rim，一條寫 defending the shot。兩條的算法是否相同，條目沒有說明。詳見〈一般防守的三條也叫 DFGA、DFGM、DFG%〉。

### 詞彙表有說籃下是離籃框幾英尺嗎？

NBA.com 統計詞彙表 2026 年 9 月 25 日的頁面內容裡，籃下防守三條的定義沒有寫距離。另一條 Shot At Rim 寫的是 5 英尺以內的出手，三條沒有引用它。詳見〈詞彙表沒有替籃下防守寫幾英尺〉。

## 資料來源

- NBA.com Stats Glossary（取得日 2026 年 9 月 25 日）：[NBA.com 詞彙表](https://www.nba.com/stats/help/glossary)。用到的條目：Field Goals Defended at Rim Attempted／Made／Percent、Defended Field Goals Attempted／Made、Defended Field Goal Percentage、Shot At Rim、Blocks、Percentage Points Difference、Deterrent Factor。
- NBA 2025-26 規則書、FIBA 2026 版規則書（2026 年 10 月 1 日生效）、NBA 2023 CBA：本機保存的全文文字檔，取得日 2026 年 10 月 4 日，無可點擊網址。
