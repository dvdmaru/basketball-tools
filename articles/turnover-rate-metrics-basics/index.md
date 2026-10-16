---
slug: turnover-rate-metrics-basics
competition: nba
topic: nba-stats
topic_ref: "manual"
type: "feature"
date: "2026-09-30"
title: "NBA 詞彙表四個失誤條目的分母有三種寫法，只有 TO Ratio 附公式"
subtitle: "TOV%、TO Ratio、TO Freq、OPP TOV% 在 NBA.com 詞彙表是四個獨立條目；名字帶 Percentage 的 OPP TOV%，定義句用的是 per 100"
lede: "NBA.com 統計詞彙表的四個失誤條目，定義句的分母有 plays、possessions used、their own possessions 三種寫法，只有 TO Ratio 附 Formula 欄。看到失誤數字，先查它屬於哪個條目、分母怎麼寫。"
---

# NBA 詞彙表四個失誤條目的分母有三種寫法，只有 TO Ratio 附公式

**新手村｜數據入門・失誤指標 TOV%、TO Ratio、TO Freq、OPP TOV%**

假設你在兩個地方看到同一個詞：失誤率。一個地方把它寫成百分比，另一個寫成每 100 個。你很自然會以為，這是同一件事換了單位。

打開 NBA.com 的統計詞彙表（Stat Glossary），TOV%、TO Ratio、TO Freq、OPP TOV% 是四個各自獨立的條目。本文用「失誤率」泛稱這四個條目，條目一律寫英文原名。

所以看到一個「失誤率」數字，先問它屬於哪個條目、分母怎麼寫，再看它多大。

## 四個條目的分母有三種寫法：plays、possessions used、their own possessions

以下都以本文採用的 NBA.com 詞彙表快照為準。下表把四個條目的定義句、Formula 欄、Type（類別）和 Contexts（情境）排在一起；定義句附中文大意，其餘欄位照原文抄錄。

| 條目（全名） | 定義句（原文與中文大意） | Formula 欄 | Type | Contexts |
|---|---|---|---|---|
| TO Ratio（Turnover Ratio） | The number of turnovers a player or team averages per 100 possessions used。球員或球隊平均每 100 個 possessions used 的失誤數 | `(TO * 100) / (POSS)` | Advanced | Player、Clutch |
| TOV%（Turnover Percentage） | Percentage of plays that end in a player or team's turnover。以球員或球隊失誤作結的 plays 所佔的百分比 | 無此欄 | Advanced | Player、Four Factors、Clutch |
| TO Freq（Turnover Frequency） | The percentage of plays where a player or team commits a turnover。球員或球隊發生失誤的 plays 所佔的百分比 | 無此欄 | Play Type | Play Type、Player |
| OPP TOV%（Opponent Turnover Percentage） | The number of turnovers an opponent averages per 100 of their own possessions。對手平均每 100 個 their own possessions 的失誤數 | 無此欄 | Four Factors | Four Factors、Team |

TOV% 和 TO Freq 寫 plays，TO Ratio 寫 possessions used，OPP TOV% 寫 their own possessions。這是用字的比對，不是定義的比對：三種寫法指的是不是同一件事，本文不下判斷。

## OPP TOV% 名字帶 Percentage，定義句卻寫 per 100

TOV% 和 TO Freq 的定義句寫 percentage of plays，單位是百分比；TO Ratio 和 OPP TOV% 寫 per 100。OPP TOV% 的全名是 Opponent Turnover Percentage，光看名字，猜不出定義句用哪一種單位。

their own 指的是誰？定義句的主詞是 an opponent，本文的讀法是：their own 指對手自己的 possessions。

OffRtg、DEFRTG、NetRtg 的定義句也寫 per 100 possessions，站內另有 [進攻效率與節奏入門](/articles/offensive-rating-pace-basics/)。

## 只有 TO Ratio 附算式，算式的 POSS 和定義句的 possessions used 沒有連起來

想直接代數字，四個條目裡只有 TO Ratio 辦得到。它的 Formula 欄是 `(TO * 100) / (POSS)`，夾在 Definition 和 Type 之間。TOV%、TO Freq、OPP TOV% 在這個位置沒有 Formula 欄，要替它們寫算式，得自己外加。

代數字之前，先看分母的用字。算式寫 POSS，定義句寫 possessions used。詞彙表另有 Poss 條目，全名 Possessions，首句是 The number of possessions played by a player or team.。possessions used 沒有自己的條目，整份詞彙表只有 AST Ratio 和 TO Ratio 的定義句用到它。

這三個相近的詞，詞彙表沒有一句話寫它們相等。TO Ratio 把定義句和 Formula 放在同一個條目裡，有人會把這種並列當成連結。本文的讀法是並列不等於寫明，所以不替它們畫等號，也不說它們有別。

照這個讀法，代進算式的就是 POSS。假設，數字是編的：TO 是 3，POSS 是 60，代進去是 `(3 * 100) / 60`，得 5.0。這個 60 是 POSS 的數字，不能直接說成 possessions used 的個數。

AST Ratio（Assist Ratio）的情形一樣：定義句寫每 100 個 possessions used 平均的助攻數，Formula 是 `(AST * 100) / (POSS)`。站內另有 [助攻指標入門](/articles/assist-metrics-basics/)。

## TOV% 和 TO Freq 的分母都寫 plays，措辭和 Type 卻不一樣

兩個定義句並排看。TOV% 是 plays that end in a player or team's turnover 所佔的百分比；TO Freq 是 plays where a player or team commits a turnover 所佔的百分比。措辭一個是 end in，一個是 commits；Type 一個是 Advanced，一個是 Play Type。

詞彙表沒有寫這兩個條目相等，也沒有寫不同，本文只並排引用。

plays 沒有獨立條目，這兩個定義句也沒有說明 plays 怎麼數，例如犯規、罰球算不算；TO Freq 條目同樣沒有寫算法。這份快照查不到，不等於 NBA 沒有規則。

## %TOV、TOV、Opp TOV 名字很像，在詞彙表是另外三個條目

縮寫相近，條目各自獨立：

| 條目 | 全名 | 定義句大意 | Type |
|---|---|---|---|
| %TOV | Percent of Team's Turnovers | 球員在場時，他的失誤占球隊失誤的百分比 | Usage |
| TOV | Turnovers | 進攻方的球員或球隊把球丟給防守方，算一次失誤 | Traditional |
| Opp TOV | Opponent Turnovers | 進攻中的對手把球丟給防守方的次數 | Opponent |

%TOV 的定義句寫 a team's turnovers，和 TOV% 的 plays 字樣不同。Opp TOV 數的是次數，OPP TOV% 的定義句則是每 100 個 their own possessions 平均的失誤數。延伸閱讀：[怎麼讀 box score](/articles/read-box-score/)、[使用率與 PIE 入門](/articles/usage-rate-pie-basics/)。

## TO Ratio 和 TOV% 的 Type 都是 Advanced，分母寫法卻不同

所以單看 Type，判斷不出分母。看到一個失誤數字，在詞彙表對三欄：

- Definition：分母寫 plays、possessions used，還是 their own possessions。
- Formula：四個失誤條目裡只有 TO Ratio 有。
- Type：Advanced、Play Type、Four Factors。

本文的建議：分母寫法不同的兩個數字，先不要放在同一張表上比，也不要互相換算。理由只有用字不同，所以這是保守的做法，不是說它們一定不同。TOV% 和 TO Freq 雖然都寫 plays，詞彙表沒把兩者連起來（見〈TOV% 和 TO Freq〉一節），也先分開放。

下次看到失誤數字，先到 [nba.com/stats/help/glossary](https://www.nba.com/stats/help/glossary) 找出條目名，把這三欄抄下來，再決定要不要和別的數字放在一起。

## 常見問題

### TOV% 與 TO Freq 是同一個指標嗎？

詞彙表沒有寫相等，也沒有寫不同。兩個定義句都用 plays，措辭與 Type 不同，對照見上文〈TOV% 和 TO Freq〉一節。

### TO Ratio 的公式是什麼？

Formula 欄寫 `(TO * 100) / (POSS)`。四個失誤條目裡只有它有 Formula 欄；算式的 POSS 與定義句的 possessions used 怎麼看，見上文。

### possessions used 在詞彙表裡有解釋嗎？

沒有獨立條目。依本文採用的快照，它只出現在 AST Ratio 與 TO Ratio 的定義句；Poss 條目首句寫的是 possessions played。三者之間沒有一句話連起來。

### OPP TOV% 記的是球隊自己的失誤，還是對手的失誤？

定義句的主詞是對手（an opponent），記的是對手平均的失誤數，分母寫 per 100 of their own possessions。本文的讀法是：their own 指對手自己的 possessions。

## 範圍與版本

引用的條目都來自本文採用的 NBA.com 詞彙表快照；2026 年 10 月 16 日對照現行頁面，這些條目的文字與快照相同。文中說沒有 Formula 欄、沒有獨立條目、沒有說明的地方，都以這份快照為限；詞彙表是網頁，之後可能改寫，條目也沒有標示適用賽季，核對請看現行頁面。標了「本文的讀法」「本文的建議」的句子是本文的判斷，不是詞彙表的話。

## 資料來源

- Stat Glossary | Stats | NBA.com（NBA.com 統計詞彙表），本文採用的快照（2026 年 10 月 16 日對照現行頁面，引用條目的文字相同）；條目沒有標示適用賽季。條目範圍：TO Ratio、TOV%、TO Freq、OPP TOV%、Poss、TOV、Opp TOV、%TOV、AST Ratio、OffRtg、DEFRTG、NetRtg。連結：[nba.com/stats/help/glossary](https://www.nba.com/stats/help/glossary)
