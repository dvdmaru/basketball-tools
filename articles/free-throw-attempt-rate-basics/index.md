---
slug: free-throw-attempt-rate-basics
competition: nba
topic: nba-stats
type: "feature"
date: "2026-10-13"
title: "罰球出手率一樣，罰球就一樣準嗎？"
subtitle: "兩支假設球隊的罰球出手率都是 0.25，罰球命中率卻差 15 個百分點。FTA RATE 用出手數相除，沒有放進罰進的球數。"
lede: "球隊的罰球出手率是 FTA 除以同隊 FGA，罰球命中率則是 FTM 除以 FTA。出手率相同，罰球未必一樣準；比值較高，也可能是投籃出手較少，不能只憑它判斷球隊多會製造犯規。"
topic_ref: "manual"
---

# 罰球出手率一樣，罰球就一樣準嗎？

**新手村｜數據入門・Free Throw Attempt Rate**

假設 A 隊罰了 20 球，C 隊罰了 25 球。兩隊都罰進 15 球，誰比較準？A 隊是 75%，C 隊是 60%。

但把 NBA.com 的罰球出手率（Free Throw Attempt Rate，FTA RATE）打開，兩隊卻可以都是 0.25。這一欄的分母，根本不是罰球出手數。

## 同樣 0.25，一隊投籃少，一隊罰球多

FTA RATE 的公式是 **FTA ÷ FGA**：球隊的罰球出手數，除以同一隊的投籃出手數。FGA 包括兩分球與三分球出手。

把三支假設球隊放在一起：

| 假設球隊 | 罰球出手 FTA | 投籃出手 FGA | 罰進 FTM | FTA RATE |
|---|---|---|---|---|
| A 隊 | 20 | 80 | 15 | 0.25 |
| B 隊 | 20 | 100 | 15 | 0.20 |
| C 隊 | 25 | 100 | 15 | 0.25 |

拿 B 隊當參照，就看得出 A 隊和 C 隊的不同。

A、B 都罰 20 球，A 的投籃出手少了 20 次，分母較小，比值就較高。B、C 都投 100 次，C 多罰了 5 球，分子較大，比值也較高。

A 和 C 都是 0.25，卻走了兩條不同的路。只抄最後那個數字，就看不出是罰球較多，還是投籃較少。

0.25 換成百分比是 25%，但不能讀成「所有出手有 25% 是罰球」。公式的分母只有 FGA，沒有把 FTA 加進去。

## FTA RATE 不看罰進幾球，FT% 才看

罰球命中率（Free Throw Percentage，FT%）的公式是 **FTM ÷ FTA**，也就是罰進球數除以罰球出手數。

同一個 FTA，在出手率裡當分子，在命中率裡當分母：

| 指標 | 算什麼 | A 隊 | C 隊 |
|---|---|---|---|
| FTA RATE | 罰球出手 ÷ 投籃出手 | 20 ÷ 80 = 0.25 | 25 ÷ 100 = 0.25 |
| FT% | 罰進 ÷ 罰球出手 | 15 ÷ 20 = 75% | 15 ÷ 25 = 60% |

兩隊的出手率相同，準度卻差 15 個百分點。FTA RATE 的公式裡沒有 FTM，無論罰進幾球，都不會直接改變這個比值。

要從技術統計表找到這些原始欄位，可以接著讀[技術統計表入門](/articles/read-box-score/)。

## FT Freq 連分母都換了

名字相近的 Free Throw Frequency（FT Freq），算的是球員或球隊因犯規而罰球的 plays，占全部 plays 的百分比。

它的分母是 plays，FTA RATE 的分母則是同隊的 FGA。兩個分母不同，不能把兩個數字當成同一欄。詞彙表這個 FT Freq 條目沒有解釋 plays 如何切分，也不能直接把它換成自己想像的球權次數。

至於場上哪些接觸會被吹犯規，是另一個問題，可看[違例與犯規有什麼不同](/articles/violation-vs-foul/)。FTA RATE 本身只拿兩種出手數相除，不能單靠它還原吹判或犯規的形成過程。

## 比值較高，還不足以替球風下結論

看到較高的比值，常會想接著說「比較有侵略性」「更會製造犯規」。但 A 隊已經提供反例：它和 B 隊罰球出手一樣多，只因投籃出手少了，比值就較高。

先把 FTA、FGA 拆開，才知道比值的差別出在哪裡。至於哪隊比較準，得另外拿出 FTM；一個 0.25，答不了這三個問題。

## 常見問題

### NBA.com 的 Free Throw Attempt Rate 怎麼算？

NBA 詞彙表這個條目以球隊為主詞，公式是 FTA ÷ FGA，即球隊的罰球出手數除以同隊的投籃出手數。20 除以 80 是 0.25；換成百分比為 25%。

### 這個比值高，代表罰進得多嗎？

不能這樣判斷。FTA RATE 不用罰進數 FTM，只用 FTA 和 FGA。要知道罰進幾球，看 FTM；要知道罰進的比例，看 FT% = FTM ÷ FTA。

### Free Throw Frequency 和 Free Throw Attempt Rate 是同一欄嗎？

不是。FT Freq 看球員或球隊因犯規而罰球的 plays 百分比；FTA RATE 則是球隊的 FTA ÷ FGA。分母不同，不能混讀。

### 詞彙表裡有球員版的 Free Throw Attempt Rate 嗎？

本文採用的 2026 年 9 月 25 日詞彙表快照，這個條目寫的是球隊，情境欄只列 Four Factors，沒有另給球員版公式。這個結論只限該條目，不能據此說 NBA.com 所有資料頁都沒有球員版。

## 資料來源

- [NBA Stats Glossary](https://www.nba.com/stats/help/glossary)：Free Throw Attempt Rate、Free Throws Attempted、Field Goals Attempted、Free Throws Made、Free Throw Percentage、Free Throw Frequency，採 2026 年 9 月 25 日保存的無版次頁面。
- A、B、C 隊與全部數字都是說明用的假設。百分比由公式換算，所有除法均以分母大於 0 為前提；罰球出手率、罰球頻率為本文使用的中文譯法。
