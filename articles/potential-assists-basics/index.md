---
slug: potential-assists-basics
competition: nba
topic: nba-stats
type: "feature"
date: "2026-10-13"
title: "NBA.com 的 Potential Assists：隊友接球後 1 dribble 內出手，定義沒寫投進"
subtitle: "助攻（AST）的定義寫明傳球直接導致投進，Potential Assists 寫的是隊友出手；兩欄是兩種條件，詞彙表沒有給兩欄相減的等式。"
lede: "NBA.com 官方統計詞彙表（2026 年 9 月 25 日的頁面內容）對 Potential Assists 的定義是：傳給隊友、而且隊友在接球後 1 dribble 之內出手的傳球。定義寫的是出手，沒有寫投進；助攻（AST）的定義則寫明傳球直接導致投進。下面用 5 次假設的傳球，讓你自己對一次兩條定義。"
topic_ref: "manual"
---

# NBA.com 的 Potential Assists：隊友接球後 1 dribble 內出手，定義沒寫投進

**新手村｜數據入門・Potential Assists**

在 NBA.com 的數據頁上翻到傳球相關的欄位，有時會看到一欄叫 Potential Assists，縮寫 Potential AST。它的名字很像助攻，詞彙表給它的卻是另一條定義。這篇依據的是 NBA.com 官方統計詞彙表（NBA Stats Glossary）2026 年 9 月 25 日的頁面內容。讀完之後，你可以拿一次傳球對照詞彙表的字面，判斷它符合哪一條定義，也知道哪幾種情況詞彙表沒有寫。

## 一句定義、兩個條件：傳給隊友，隊友接球後 1 dribble 內出手

詞彙表給 Potential Assists 的定義只有一句：

> Any pass to a teammate who shoots within 1 dribble of receiving the ball

意思是：任何一次傳給隊友的傳球，只要那名隊友在接球後 1 dribble 之內出手，就符合這一條。第一個條件是傳球的對象是隊友；第二個條件是接球的人在接球後 1 dribble 之內出手。「1 dribble」是詞彙表的原字，指接球後運球的次數：0 次運球直接出手，或運 1 次球再出手，字面上都落在 1 dribble 之內。

這個條目的其他欄位如下：

| 欄位 | Potential Assists 條目寫的內容 |
|---|---|
| 名稱（Name） | Potential Assists（縮寫 Potential AST） |
| 定義（Definition） | 上面那一句 |
| 公式（Formula） | 沒有這一欄；定義之後直接是類型 |
| 類型（Type） | Tracking |
| 情境標籤（Contexts） | Tracking、Player、Passing |

要知道一次傳球算不算，能依據的就是那一句定義。

## 定義句裡有「出手」，沒有「投進」

再讀一次定義句：shoots 是出手，句子裡沒有投進（made），也沒有投失（missed）。隊友要做的只有一件事，就是在接球後 1 dribble 內出手。

照這個字面往下讀一步（這是本文的讀法）：某名球員的 Potential Assists 是一個數字，它告訴你的是「有這麼多次傳球，接球的隊友在 1 dribble 內出手」。這些出手投進了幾球，單看這一欄讀不出來。

## 助攻（AST）和 Potential Assists 寫的是兩種條件

助攻在同一份詞彙表裡有自己的條目，定義寫的是「passes that lead directly to a made basket」，也就是直接導致投進的傳球。兩個條目並排如下：

| 欄位 | 助攻（AST） | Potential Assists |
|---|---|---|
| 定義裡寫的事件 | 傳球直接導致投進 | 隊友接球後 1 dribble 內出手 |
| 類型 | Traditional | Tracking |
| 情境標籤 | Player、Clutch、Play Type、Passing、Box Score | Tracking、Player、Passing |

AST 的條件裡有投進這件事，Potential Assists 的條件寫的是出手。兩個條目的類型也不同；這是詞彙表的分類，本文只轉述，不從分類推論兩者的關係。

AST 的定義沒有運球次數的上限，1 dribble 只寫在 Potential Assists 自己的定義裡。兩者是詞彙表分別寫的兩個條目，不是同一條規則的寬鬆版與嚴格版。

AST 在表上的位置，[技術統計表入門](/articles/read-box-score/) 已經拆過；助攻相關的比率欄位，在 [助攻相關指標入門](/articles/assist-metrics-basics/) 裡有對照。這篇只處理 Potential Assists。

## 常見誤讀：把兩欄相減，當成「隊友沒投進的球」

看到兩個數字並排，很自然會想做減法：Potential Assists 減掉 AST，差額是不是「隊友出手但沒投進的球」？

詞彙表沒有寫這條等式。能對到的字面有這幾件：

- 詞彙表沒有把任何其他欄位寫成 Potential Assists 的組成。
- AST 的定義寫的是直接導致投進的傳球，沒有寫運球數上限。接球的人運了好幾次球才投進，那次傳球算不算 AST，詞彙表沒有說。
- Potential Assists 的定義沒有寫被犯規、罰球的情境。接球的人在 1 dribble 內被犯規而去罰球，這次傳球算不算 Potential Assists，詞彙表沒有說。

這幾件事都沒有答案，兩欄的差額裡混了哪些情況，單靠這份詞彙表分不清楚。能說的是「兩個條目寫的條件不同」；把差額叫做「隊友沒投進的球」，需要詞彙表沒有給的等式。

## 詞彙表裡另外四個助攻相關條目，各有自己的條件

同一份詞彙表裡，還有四個和助攻有關的條目，以下是中文轉述：

| 條目 | 詞彙表定義的重點 |
|---|---|
| Free Throw Assists | 傳球給一名在接球後 one dribble 內造成投籃犯規（shooting foul）的球員 |
| Secondary Assist | 傳球給一名在 1 second 內、而且沒有運球就記錄一次助攻的球員 |
| Assists Adjusted | 球員或球隊的 assists、free throw assists、secondary assists 三者總和 |
| Assist to Pass Percentage Adjusted | 球員或球隊的傳球中，屬於上面三者之一的百分比；公式欄寫 (Adjusted Assists)/(Passes Made) |

Free Throw Assists 的條件裡有投籃犯規，Potential Assists 的定義裡沒有。Secondary Assist 的條件是時間（1 second）加上沒有運球，起點是接球的人記錄了一次助攻。Assists Adjusted 加總的三項裡沒有 Potential Assists。分母 Passes Made 是球員或球隊每場的傳球總數，這一組在 [助攻相關指標入門](/articles/assist-metrics-basics/) 已有說明，這裡不展開。

## 自己對一次：5 次假設的傳球，各符合哪幾條字面？

下面是一組完全假設的情境。某名後衛（假設）在一節比賽裡有 5 次傳球，每一次的結果如下。

| 編號 | 假設的傳球經過 |
|---|---|
| ① | 隊友接球後 0 次運球出手，投進 |
| ② | 隊友接球後運 1 次球出手，投失 |
| ③ | 隊友接球後運 3 次球出手，投進 |
| ④ | 隊友接球後 0 次運球，被犯規（shooting foul），之後罰球 |
| ⑤ | 隊友接球後沒有出手，不運球、1 second 內再傳給另一名隊友，第二人接球後 0 次運球投進（假設第一名隊友因此被記一次 assist） |

逐筆對照詞彙表的字面：

- ①：接球後 0 次運球出手，落在 Potential Assists 的 1 dribble 之內。這次傳球也直接導致投進，符合 AST 的字面。
- ②：接球後運 1 次球出手，也落在 1 dribble 之內，符合 Potential Assists 的字面。出手沒有投進，AST 的定義要求投進，這筆不符合。
- ③：接球後運了 3 次球，超過 1 dribble，Potential Assists 的字面不符合。這次傳球最後換到投進；AST 的定義寫「直接」導致投進，卻沒寫「直接」的門檻，也沒有運球上限，這筆算不算 AST，詞彙表沒有寫。
- ④：接球後 0 次運球，被吹的是投籃犯規，落在 Free Throw Assists 的 one dribble 範圍之內，符合它的字面。Potential Assists 的定義沒有寫犯規與罰球，這一筆詞彙表沒有說。
- ⑤：這名後衛傳球的對象沒有出手，Potential Assists 的字面（隊友接球後出手）不符合。第一名隊友在 1 second 內、沒有運球就傳出一次助攻，符合 Secondary Assist 對這名後衛的字面。1 second 要從哪一刻開始算（接球、傳球還是其他時點），詞彙表沒有寫清楚。

這 5 次傳球沒有一個「標準答案總數」：③算不算 AST、④算不算 Potential Assists、⑤的 1 second 從哪一刻起算，詞彙表都沒有說明。

下次在 NBA.com 的數據頁看到 Potential Assists，你可以做三件事：

1. 先確認欄位名稱與類型：Potential Assists 是 Tracking，AST 是 Traditional。
2. 回到定義句，看它的條件是出手，還是投進。
3. 記得這一欄本身沒有寫出手的結果，不要拿它減掉 AST 去猜投進幾球。

## 範圍與版本

本文的定義句都出自 NBA.com 官方統計詞彙表 2026 年 9 月 25 日的頁面內容；詞彙表會更新，之後以 NBA.com 最新的頁面為準。球員與球隊的實際數字不在討論範圍，示範一律是標明「假設」的情境。

這一版詞彙表的 Potential Assists 條目沒有公式欄。NBA.com 的實際資料怎麼處理投失的球、怎麼處理被犯規罰球的情況，詞彙表沒有另外說明，本文也不替它下結論。情境標籤列 Tracking、Player、Passing，沒有列 Team；有沒有球隊層級的 Potential Assists，詞彙表也沒有說明。若之後的詞彙表替這一條補上公式或結果條件，本文的讀法要跟著重看。

## 常見問題

### Potential Assists 是不是「隊友出手但沒投進」的次數？

NBA.com 詞彙表（2026 年 9 月 25 日的頁面內容）沒有這樣寫。它的定義是傳給接球後 1 dribble 內出手的隊友，沒有寫投進或投失；拿它減掉 AST 當作「沒投進的球」，需要詞彙表沒有給的等式，見〈常見誤讀〉一節。

### 隊友接球後運了 3 次球才投進，算不算 Potential Assists？

照 NBA.com 詞彙表（2026 年 9 月 25 日的頁面內容）的字面，運 3 次球超過了 1 dribble，不符合。那次傳球算不算 AST，詞彙表沒有寫；見〈自己對一次〉的③。

### Potential Assists 和 Free Throw Assists、Secondary Assist 是同一類嗎？

NBA.com 詞彙表（2026 年 9 月 25 日的頁面內容）把它們寫成三個各有條件的條目：Potential Assists 寫隊友 1 dribble 內出手，Free Throw Assists 寫 one dribble 內造成投籃犯規，Secondary Assist 寫 1 second 內、沒有運球就記錄一次助攻。對照見〈詞彙表裡另外四個助攻相關條目〉一節。

## 資料來源

- NBA.com Stats Glossary（取得日 2026 年 9 月 25 日）：[NBA.com 統計詞彙表](https://www.nba.com/stats/help/glossary)。本文引用的條目：Potential Assists、Assists、Free Throw Assists、Secondary Assist、Assists Adjusted、Assist to Pass Percentage Adjusted、Passes Made。
