---
slug: usage-rate-pie-basics
competition: nba
topic: nba-stats
type: "feature"
date: "2026-09-29"
title: "使用率很高，就代表投得好嗎？"
subtitle: "USG% 公式放了出手與失誤，卻沒有直接放命中數。PIE 納入更多統計，同一個 FGA 在兩條公式裡，正負號還不一樣。"
lede: "USG% 公式沒有直接列命中數，單看使用率，還原不出球員投得準不準。PIE 則把得分、命中、籃板等加項與出手、犯規、失誤等減項合在一起；兩個數字不能互相代替。"
topic_ref: "manual"
---

# 使用率很高，就代表投得好嗎？

**新手村｜數據入門・使用率 USG% 與 PIE**

同樣出手 18 次，投進幾球會不會改變 USG%？先把 NBA 詞彙表的公式寫出來：

```
USG% = (FGA + Possession Ending FTA + TO) / POSS
```

式子裡有出手數 FGA，卻沒有命中數 FGM。

## 18 次出手，進幾球沒有直接放進 USG% 公式

NBA 詞彙表把 USG% 稱為 Usage Percentage。定義是球員在場時，使用了球隊 team plays 的多少比例。原文的 team plays 保留英文，不能直接當成 Possessions（回合）的同義詞。

假設某球員 FGA 是 18、Possession Ending FTA 是 4、TO 是 3，在場的 POSS 是 80。這四個值都直接給定，不是真實比賽數據。

代入是（18＋4＋3）÷80＝0.3125，換成百分比就是 31.25%。

這次計算沒有問他 18 投幾中。固定這四個給定值，改填命中數也沒有地方放；只拿到 31.25%，還原不出他的命中率。助攻、抄截與阻攻，也沒有直接列在這條公式裡。

公式裡的 TO，本文對照詞彙表的失誤欄 TOV；POSS 對照 Possessions 的回合數。這是依名稱與脈絡做的編輯對照，不是 USG% 條目逐字宣告的對應關係。

## 總罰球出手數，不能直接補進這條式子

公式寫的不是一般 FTA，而是 Possession Ending FTA。引用的詞彙表條目沒有說明哪些罰球算進這個項目，也沒有給罰球係數。因此上面的 4 是假設給定值，不能拿一張表的 FTA 直接代替。

所以算式能代入，不等於一般技術統計表已經提供重算所需的所有資料。基本欄位可以看[技術統計表入門](/articles/read-box-score/)；回合數與每 48 分鐘節奏的關係，見[進攻效率值與節奏入門](/articles/offensive-rating-pace-basics/)。

## PIE 有加也有減，得分只是其中一項

PIE 的全名是 Player Impact Estimate。NBA 詞彙表說，它衡量球員的整體統計貢獻，相對於他所參賽比賽的總統計。

分子是：

```
PTS + FGM + FTM - FGA - FTA + DREB + 0.5 × OREB
+ AST + STL + 0.5 × BLK - PF - TO
```

分母把上述每一項都加上 Gm 前綴，保留相同的正負號與 0.5 係數。詞彙表沒有單獨定義 Gm；本文依定義句的「比賽總統計」，把它讀成該場所有球員各項數字的合計，這是編輯推論。

再用一組假設數字：PTS 20、FGM 8、FTM 4、FGA 16、FTA 5、DREB 5、OREB 2、AST 4、STL 1、BLK 1、PF 3、TO 2。

照公式加減，分子是 17.5。分母直接假設為 200，17.5 ÷ 200＝0.0875，換成百分比是 8.75%。這裡沒有用完整比賽數據算出 200，也沒有拿 8.75% 判斷表現好壞。

同一個 FGA，在 USG% 分子裡是加項，在 PIE 分子裡卻是減項。但不能因此說真實比賽多出手一次，PIE 就一定下降；出手也可能連動命中、得分與分母，不能只動一項就替整場下結論。

USG% 不能代替命中率，PIE 也不是把得分重新命名。兩條公式放進去的項目與分母不同，回答的問題就不同。台灣職籃數據頁另有[統計詞彙入門](/articles/tpbl-plg-stats-glossary-basics/)，不能直接套用這兩條 NBA 公式。

## 常見問題

### USG% 在 NBA 官方詞彙表是次數還是百分比？

是百分比，定義包含「球員在場時」與使用球隊 team plays 的比例；不是次數，也不能把 team plays 直接等同回合。第一節的 0.3125 寫成 31.25%，是百分比換算。

### USG% 公式裡有沒有命中數或助攻？

沒有直接列出。公式是（FGA＋Possession Ending FTA＋TO）÷POSS；TO 與 TOV、POSS 與 Possessions 的對照是本文讀法。沒有列出某項，不代表兩種統計在真實比賽裡完全無關。

### PIE 只是把得分加總嗎？

不是。分子還有命中、籃板、助攻等加項，以及 FGA、FTA、PF、TO 減項，OREB 與 BLK 各乘 0.5。分母各項加 Gm 前綴；把 Gm 讀成全場球員合計是本文推論，完整結構見「PIE 有加也有減」一節。

### USG% 或 PIE 數字高，代表球員很重要或表現好嗎？

不能只憑這兩個數字下結論。引用保存版的 USG% 與 PIE 條目沒有列高低門檻或聯盟平均；USG% 也不能還原命中率，PIE 的統計貢獻不等於已分離出個人造成的贏球貢獻。

## 資料來源

- [NBA Stats Glossary](https://www.nba.com/stats/help/glossary)：USG%、PIE、FGA、TOV、Possessions，2026 年 9 月 29 日保存頁，未標版本或賽季；2026 年 10 月 19 日重核 USG% 與 PIE 核心定義、公式相符，不代表全頁或完整演算法相同。
- 31.25% 與 8.75% 都是給定假設值後自算，非球員實測數據。TO／TOV、POSS／Possessions 是編輯對照，Gm 的解讀是編輯推論。
