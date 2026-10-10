#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen-basketball-cover.py — 籃球數據誌 特刊封面生成器（basketball.twtools.cc）
HTML template → Chrome headless → 2400×1260 PNG（純文字、IP 安全：無 logo/球員照/隊徽/聯盟標誌）。
品牌：炭黑 #14100e + 暖白 #f3ece4 + 籃球橘 #ef7d3a + 木地板金 #d9a04c（裝飾條/dot）。
與 baseball（navy/金）、foootball（森林綠）區隔。封面寫進 articles/<slug>/cover.png。

用法：python3 gen-basketball-cover.py            # 生成 COVERS 內全部
      python3 gen-basketball-cover.py <slug>...  # 只生成指定 slug（避免重生成全部造成無關 diff）
"""
import os, subprocess, sys, tempfile

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    raise SystemExit("Chrome not found")


# (article_slug, kicker, title_html, subtitle) — 新文章加封面：在這裡加一列再跑本腳本
COVERS = [
    ("clippers-kawhi-leonard-circumvention-penalties", "NBA · 規避薪資上限",
     "6 天內<br>3 封介紹信",
     "每一封都寫著是對方先開口　·　球隊罰款 3,000 萬美元"),
    ("stephen-curry-over-38-rule-extension", "NBA · 38 歲條款",
     "38 歲條款<br>不是禁令",
     "柯瑞 2024 年只延長 1 年　·　條文寫的是把錢往前攤"),
    ("nba-league-guide", "NBA · 完全指南",
     "美國職籃<br>完全指南",
     "30 隊 · 東西區　·　附加賽到總冠軍賽一次看懂"),
    ("taiwan-hoops-two-leagues", "台灣職籃 · 並立格局",
     "為什麼有<br>兩個聯盟",
     "TPBL 7 隊 × PLG 4 隊　·　合併破局始末"),
    ("hbl-league-guide", "HBL · 完全指南",
     "高中籃球<br>完全指南",
     "男子組 37 隊 · 女子組 16 隊　·　小巨蛋的 3 月"),
    ("nba-2025-26-season-review", "2025-26 · 賽季回顧",
     "尼克<br>53 年再奪冠",
     "總冠軍賽 4:1 勝馬刺　·　東西區終局全紀錄"),
    ("nba-2026-offseason-moves", "2026 · 休賽季異動",
     "字母哥<br>轉戰熱火",
     "頭條交易 4 筆 · 待確認 1 筆　·　休賽季異動總表"),
    ("lebron-james-76ers-24th-season", "2026 · 生涯數據總表",
     "詹姆斯<br>加盟 76 人",
     "第 24 個賽季 · 第 4 支球隊　·　23 季官方數據拆解"),
    ("taiwan-asian-games-2026-basketball", "名古屋亞運 · 台灣男籃",
     "比開幕式<br>早 9 天開打",
     "B 組對約旦 · 伊朗 · 卡達　·　12 人名單 · 連兩屆第 4"),
    ("tpbl-plg-rules-compared", "台灣職籃 · 規則逐條對照",
     "身分分 2 種<br>還是 4 種",
     "TPBL 對 PLG　·　註冊 · 上場 · 薪資 · 選秀 · 交易"),
    ("nba-2026-draft-results", "2026 · 選秀完整名單",
     "60 個順位<br>27 個換了隊",
     "兩輪逐一列出　·　上台選人的隊 · 選後去向"),
    ("taiwan-hoops-2026-offseason-moves", "台灣職籃 · 2026 休賽季",
     "衛冕軍首輪籤<br>選到了空氣",
     "跨聯盟轉隊 · 林庭謙返台　·　選秀 · 洋將 · 退役"),
    # ⚠️ 封面是最會被單獨看到的載體（og:image），而標題塞不下一串限定詞。
    # 這篇的硬規則是「每一句 125 億都要看得出估值口徑＋報導層」，所以主標把「報導寫的是」
    # 四個字留著——那是限定詞不是贅字，⛔ 不要為了版面好看拿掉。
    # KG 21 號：儀式在未來（美國時間 2027-02-28），副標一律未來式；
    # 「唯一」有四個限定，封面放不下就不放，只寫「第二件」這個已證的事實。
    ("russell-westbrook-retirement-career-stats", "NBA · 生涯數據總表",
     "衛斯布魯克退休<br>大三元史上第一",
     "209 次大三元　·　18 季　·　1,301 場　·　27,176 分"),
    ("kevin-garnett-wolves-21-jersey-retirement", "NBA · 灰狼退休球衣",
     "灰狼第二件退休球衣<br>賈奈特 21 號",
     "2027-02-28 對塞爾提克賽後　·　5 號已掛在波士頓"),
    ("wolves-lynx-sale-stad", "NBA／WNBA · 灰狼與山貓",
     "買家原本<br>就是自家股東",
     "45 億美元估值 · 灰狼＋山貓合併　·　待 NBA 董事會核准"),
    ("lakers-sale-iger-kushner", "NBA · 湖人易主案",
     "報導寫的是估值<br>不是成交價",
     "125 億美元 · 條款未公開　·　待 NBA 董事會批准"),
    ("don-nelson-nellie-ball", "NBA · Nellie Ball",
     "名人堂說創新者<br>他說只是權宜",
     "例行賽 1,335 勝 · 史上第 2　·　小球 · point forward"),
    ("nba-2026-27-opening-night-christmas-schedule", "NBA · 開幕週與聖誕大戰",
     "詹姆斯開幕戰<br>作客尼克",
     "台北 10/21 早上 7 點　·　聖誕大戰 12/26 星期六"),
    ("violation-vs-foul", "NBA · 違例與犯規",
     "防守三秒<br>罰技術犯規",
     "違例章的規定 · 技術犯規的罰則　·　用三個問題判哨聲"),
    ("read-box-score", "NBA · 技術統計表",
     "12 投 2 中<br>卻得 6 分",
     "L. Dort 這一行　·　把 PTS 拆回 FGM · 3PM · FTM"),
    ("true-shooting-basics", "NBA · 命中率",
     "命中率 40%<br>效率差很多",
     "FG% · eFG% · TS%　·　假設球員，自己算一次"),
    ("salary-cap-basics", "NBA · 薪資帽",
     "薪資帽<br>不是上限",
     "帽線 · 稅線 · apron 三條線　·　2026-27 官方數字"),
    ("draft-lottery-basics", "NBA · 選秀樂透",
     "最差三隊<br>各 14%",
     "2019–2026 舊制　·　2027 年起改 3-2-1"),
    ("positions-basics", "NBA · 五個位置",
     "規則書沒有<br>五個位置",
     "球員頁只標 G · F · C　·　規則書只寫每隊五人"),
    ("coachs-challenge-basics", "NBA · 教練挑戰",
     "挑戰之前<br>先叫一次暫停",
     "只能挑三種判決　·　挑錯，暫停就沒了"),
    ("zone-vs-man-defense", "NBA · 區域聯防",
     "規則書沒有<br>區域聯防這個詞",
     "任何人可防任何人　·　管的是禁區裡的三秒"),
    ("two-way-contract-basics", "NBA · 雙向合約",
     "每隊 3 人<br>每季 50 場",
     "季後賽不能出賽　·　2023 CBA 條文"),
    ("restricted-free-agency-basics", "NBA · 限制性自由球員",
     "沒發資格報價<br>就是無限制自由球員",
     "配對權買的是優先購買權　·　不是留人的保證"),
    ("offensive-rating-pace-basics", "NBA · 進攻效率與節奏",
     "同樣 115 分<br>回合數不同",
     "每 100 回合得分　·　每 48 分鐘回合數"),
    ("read-standings-basics", "NBA · 戰績表",
     "兩隊先比對戰<br>三隊先比冠軍",
     "同勝率才進比序　·　GB 不在清單裡"),
    ("hbl-format-basics", "HBL · 甲級賽制",
     "前 8 名<br>免打資格賽",
     "男生組多一關準決賽　·　女生組複賽後直接進總決賽"),
    ("hbl-rules-vs-fiba", "HBL · 規則體系比較",
     "乙級打<br>8 分鐘制",
     "FIBA 10 分鐘、NBA 12 分鐘　·　依 ISF 規則調整"),
    ("hbl-player-eligibility-basics", "HBL · 球員資格規則",
     "兩個「1 年」<br>不是同一件事",
     "1 年學籍門檻，不是禁賽　·　7 條路讓門檻失效"),
    ("hbl-to-college-pathway", "HBL · 升學與選秀資格",
     "保送<br>不是一個詞",
     "甄審門檻天差地遠　·　選秀看的是參賽經驗"),
    ("hbl-awards-basics", "HBL · 個人獎項",
     "得分王<br>不在裡面",
     "官方獎項只有六項　·　105 學年度曾經有例外"),
    ("hbl-tier-a-vs-b", "HBL · 甲乙級賽制",
     "資格賽輸了<br>乙級也回不去",
     "報名時的二選一　·　不是打輸退一級"),
    ("tpbl-plg-stats-glossary-basics", "台灣職籃 · 進階數據",
     "有欄位名<br>沒公式",
     "PLG 22 欄沒有 EFF　·　STATZONE 公開頁 Definition 空白"),
    ("waiver-buyout-basics", "NBA · 棄約與買斷",
     "CBA 全文<br>查不到 buyout",
     "認領順序看戰績墊底　·　不是先搶先贏"),
    ("technical-flagrant-fouls-basics", "NBA · 技術犯規與惡意犯規",
     "技術犯規看行為<br>惡意犯規看接觸",
     "一級二級差在「過度」兩字　·　二級直接驅逐"),
    ("trade-rules-basics", "NBA · 交易規則",
     "選秀權<br>不算薪資",
     "上限是送出薪資 100%+25 萬美元　·　選秀權沒有薪資"),
    ("fast-break-basics", "NBA · 快攻戰術",
     "快攻的關鍵<br>不是跑得快",
     "優勢來自速度或站位　·　不只算人頭"),
    ("goaltending-basket-interference-basics", "NBA · 妨礙中籃與干擾球",
     "九款清單<br>沒有分開定義",
     "防守違規判得分　·　進攻違規判取消"),
    ("shot-clock-reset-basics", "NBA · 進攻時間重設",
     "重設 24 秒<br>還是 14 秒",
     "先判斷是哪一類事件　·　三張清單各自列出事件"),
    ("charge-vs-block-basics", "NBA · 阻擋犯規與帶球撞人",
     "防守者先站定<br>責任在進攻者",
     "4 呎半圓要三個條件同時成立　·　FIBA 半圓是另一套"),
    ("away-from-the-play-foul-basics", "NBA · 離球犯規",
     "離球犯規<br>有兩個入口",
     "最後兩分鐘的刻意接觸　·　發球出手前的防守非法接觸"),
    ("max-contract-designated-veteran-basics", "NBA · 頂薪與指定老將",
     "頂薪沒有<br>固定數字",
     "年資分三級　·　每一級都有第二條路"),
    ("nba-draft-eligibility-basics", "NBA · 選秀資格",
     "先過基本門檻<br>再選一款路徑",
     "19 歲加畢業後一個賽季　·　早期報名是第 (G) 款"),
    ("usage-rate-pie-basics", "NBA · 使用率與 PIE",
     "先看公式<br>再說數字",
     "USG% 是百分比　·　公式沒放的項目不能直接回答"),
    ("hbl-standings-tiebreak-basics", "HBL · 循環賽名次",
     "同分先看<br>對戰勝負",
     "敗一場也拿 1 分　·　互有勝負才比得失分差"),
    ("hbl-roster-size-basics", "HBL · 報名人數與名單",
     "報名人數<br>不等於每場名單",
     "甲級 15 人、乙級 18 人　·　第 12 條二寫 12 人名單"),
    ("hbl-tier-b-road-to-finals-basics", "HBL · 乙級晉級路線",
     "縣市預賽晉級後<br>還有兩關",
     "分區複賽先循環後淘汰　·　排名賽怎麼打規程沒寫"),
    ("hbl-staff-qualification-basics", "HBL · 隊職員資格",
     "四種職務<br>四種資格判準",
     "領隊看身分、教練看證照　·　兼任限制寫同一級別兩校"),
    ("hbl-eligibility-check-basics", "HBL · 資格查驗時點",
     "第一場審查<br>其餘場次備查",
     "各階段第一場交大會審查　·　其餘場次仍要攜帶文件"),
    ("traveling-gather-steps-basics", "NBA · 走步與 gather",
     "走步先看<br>什麼情境",
     "原地接球看樞軸　·　行進中與運球中從 gather 起算"),
    ("eight-second-backcourt-basics", "NBA · 八秒限時",
     "8 秒被中斷<br>兩邊寫法不同",
     "NBA 列出新的 8 秒　·　FIBA 列出剩餘時間延續"),
    ("timeouts-basics", "NBA · 暫停配額",
     "還剩幾個暫停<br>算的是不同的帳",
     "NBA 例行賽 7 次　·　FIBA 上半場 2 次、下半場 3 次"),
    ("assist-metrics-basics", "NBA · 助攻進階指標",
     "名稱都帶助攻<br>分母各不相同",
     "AST% 分母 TmFGM - FGM　·　Assist Ratio 分母 POSS"),
    ("minimum-team-salary-basics", "NBA · 球隊薪資下限",
     "球隊薪資<br>有下限",
     "一般球隊是 Salary Cap 的 90%　·　§2(c)(2) 寫了兩件事"),
    ("ten-day-contract-basics", "NBA · 10 天約",
     "10 天約<br>不是固定十天",
     "§9(a) 取十天與三場比賽的較長者　·　自 1 月 5 日起"),
    ("jump-ball-vs-alternating-possession-basics", "NBA · 跳球與交替擁有",
     "哪些情形會跳球<br>球權怎麼決定",
     "NBA 十款中圈跳球　·　FIBA 兩隊輪流取得球權"),
    ("five-second-rules-basics", "NBA · 5 秒",
     "5 秒的時限<br>出現在不同情形",
     "NBA 發球與背對籃框運球　·　FIBA 含 closely guarded"),
    ("ball-returned-to-backcourt-basics", "NBA · 回場違例",
     "回場違例<br>己方不得第一個觸球",
     "NBA Rule 10 §IX　·　FIBA Article 30 另寫兩種先觸球的條件"),
    ("offensive-three-seconds-basics", "NBA · 進攻三秒",
     "進攻三秒<br>什麼時候開始算",
     "球在前場處於控制中才起算　·　FIBA 連續超過 3 秒"),
    ("turnover-rate-metrics-basics", "NBA · 失誤指標",
     "四個失誤指標<br>三種分母字樣",
     "只有 TO Ratio 附 Formula 欄　·　TOV% 沒有 Formula 欄"),
    ("disabled-player-exception-basics", "NBA · 傷病球員例外",
     "傷病球員例外<br>簽約額度取較小者",
     "傷者薪水的 50%　·　申請被拒後要滿 90 天"),
    ("tpbl-2026-27-schedule-guide", "台灣職籃 · 2026-27 賽程",
     "夢想家<br>連續 7 場客場",
     "例行賽 126 場　·　10 月 17 日開幕"),
    ("easl-2026-27-guide", "台灣職籃 · EASL 2026-27",
     "台灣三隊互不交手<br>卻同在 7 隊池爭 1 席",
     "小組賽 36 場　·　BCL Asia 第三席"),
    ("free-throw-violations-basics", "NBA · 罰球違例",
     "罰球時對手違例<br>罰法看款次",
     "d 款沒進時補一罰　·　g、h 款記 1 分"),
    ("substitution-rules-basics", "NBA · 換人",
     "可換人的期間<br>FIBA 定了起訖",
     "NBA 按情境分款寫　·　Rule 3 §V"),
    ("three-point-line-basics", "NBA · 三分線",
     "三分線上的區域<br>算幾分？",
     "NBA 寫兩分　·　FIBA 寫線不屬於三分區"),
    ("rookie-scale-contract-basics", "NBA · 新秀合約",
     "80% 與 120%<br>量的項目不同",
     "兩季加兩個 Option　·　Section 1(c)(i)"),
    ("rebound-percentage-metrics-basics", "NBA · 籃板指標",
     "籃板百分比三層<br>一層找不到分母",
     "REB% 沒有 Formula 欄　·　Chance% 分母是 Chances"),
    ("too-many-players-basics", "NBA · 場上人數不對",
     "場上人數不對<br>六人以上可作廢重來",
     "Rule 12A §III(a)　·　四人以下只判技術犯規"),
    ("captain-role-basics", "NBA · 隊長",
     "隊長何時能問裁判<br>暫停期間或球死時",
     "NBA 暫停期間　·　FIBA 球死且比賽時鐘停止"),
    ("point-three-seconds-rule-basics", "NBA · 0.3 秒規則",
     "剩 0.2 秒還能得分嗎<br>兩邊列的動作不同",
     "NBA tip-in、high lob　·　FIBA tapping、directly dunking"),
    ("game-protest-basics", "NBA · 賽後抗議",
     "賽後抗議<br>$25,000 與 15 分鐘",
     "NBA 隨書面附 $25,000　·　FIBA 隊長 15 分鐘內告知"),
    ("moratorium-period-basics", "NBA · Moratorium Period",
     "期間內仍列了<br>九款可做的事",
     "東部時間 7 月 1 日到 7 月 6 日中午　·　(a) 四款、(b) 五款"),
    ("likely-unlikely-bonus-basics", "NBA · Likely／Unlikely Bonus",
     "假設表現相同<br>獎金會賺到嗎",
     "緊接前一個 Salary Cap Year　·　Section 3(d)(1)"),
    ("contract-option-clauses-basics", "NBA · 合約選擇權",
     "球隊與球員選擇權<br>前四款條件逐字相同",
     "Article XII　·　Any Option 於 June 29 的 5:00 p.m. 前行使"),
    ("dribble-ends-double-dribble-basics", "NBA · 運球與二次運球",
     "禁止第二次運球<br>自願結束或已經結束",
     "NBA voluntarily ended　·　FIBA first dribble has ended"),
    ("act-of-shooting-basics", "NBA · 投籃動作",
     "投籃動作從哪算起<br>兩份規則書歸組不同",
     "NBA 2025-26 Rule 4 §XI　·　FIBA 2026 版 15.1.2 與 15.1.3"),
    ("end-of-period-ball-in-flight-basics", "NBA · 時間到時的球",
     "時間到時球在飛行中<br>之後被碰到寫法不同",
     "NBA 分防守方與進攻方　·　FIBA 寫任一隊球員"),
    ("ball-out-of-bounds-last-touch-basics", "NBA · 球出界",
     "球出界算誰的<br>首句看最後碰球的人",
     "句尾 NBA 接 provided　·　FIBA 接 even if"),
    ("award-eligibility-65-games-basics", "NBA · 五項榮譽",
     "五項榮譽的出賽條件<br>65 場與 20 分鐘",
     "2023 CBA Art. XXIX §6(a)　·　打了至少 20 分鐘的一場即視為出賽"),
    ("physical-exam-contract-validity-basics", "NBA · 體檢與合約",
     "球隊判定體檢通過<br>是合約有效的前提",
     "2023 CBA Art. II §13(h)　·　載有 Exhibit 6 的體檢約定"),
]

HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1200px;height:630px;overflow:hidden}}
body{{
  font-family:"PingFang TC","Heiti TC","Noto Sans CJK TC",sans-serif;
  background:
    radial-gradient(1100px 720px at 80% -12%, rgba(239,125,58,.20), transparent 60%),
    linear-gradient(135deg,#241d19 0%,#14100e 52%,#0a0807 100%);
  color:#f3ece4;position:relative;
}}
.frame{{position:absolute;inset:28px;border:1.5px solid rgba(239,125,58,.40);border-radius:10px}}
.seam{{position:absolute;width:1500px;height:1500px;border:3px solid rgba(239,125,58,.18);
  border-radius:50%;right:-820px;top:-340px}}
.seam2{{position:absolute;width:1500px;height:1500px;border:3px solid rgba(239,125,58,.10);
  border-radius:50%;right:-760px;top:-280px}}
.pad{{position:absolute;inset:0;padding:74px 78px 128px;display:flex;flex-direction:column;height:100%}}
.top{{display:flex;align-items:center;gap:18px}}
.mark{{font-family:"Arial Black","PingFang TC",sans-serif;font-weight:900;letter-spacing:1px;
  font-size:30px;color:#ef7d3a}}
.dot{{width:7px;height:7px;border-radius:50%;background:#d9a04c;opacity:.9}}
.mk-tag{{font-size:18px;color:rgba(243,236,228,.62);letter-spacing:2px;font-weight:600}}
.kicker{{margin-top:auto;display:inline-block;align-self:flex-start;
  background:rgba(239,125,58,.16);border:1px solid rgba(239,125,58,.52);
  color:#ef7d3a;font-size:24px;font-weight:700;letter-spacing:3px;
  padding:9px 22px;border-radius:999px}}
h1{{font-size:104px;line-height:1.08;font-weight:900;margin:26px 0 0;
  letter-spacing:1px;color:#fff;text-shadow:0 2px 30px rgba(0,0,0,.40)}}
.bar{{width:96px;height:5px;background:linear-gradient(90deg,#ef7d3a,#d9a04c);
  border-radius:4px;margin:30px 0 22px}}
.sub{{font-size:32px;font-weight:600;color:rgba(243,236,228,.84);letter-spacing:1px}}
.foot{{position:absolute;left:78px;bottom:60px;font-size:21px;letter-spacing:2px;
  color:rgba(239,125,58,.74);font-weight:600}}
</style></head><body>
<div class="seam"></div><div class="seam2"></div>
<div class="frame"></div>
<div class="pad">
  <div class="top"><span class="mark">@BASKETBALL</span><span class="dot"></span>
    <span class="mk-tag">{mktag}</span></div>
  <div class="kicker">{kicker}</div>
  <h1>{title}</h1>
  <div class="bar"></div>
  <div class="sub">{sub}</div>
</div>
<div class="foot">basketball.twtools.cc</div>
</body></html>"""


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    league_tag = {"nba": "NBA", "tpbl": "TPBL", "plg": "PLG", "hbl": "HBL",
                  "taiwan": "台灣籃球", "easl": "EASL"}
    only = set(sys.argv[1:])
    unknown = only - {slug for slug, *_ in COVERS}
    if unknown:
        raise SystemExit(f"未知 slug（不在 COVERS 內）：{', '.join(sorted(unknown))}")
    for slug, kicker, title, sub in COVERS:
        if only and slug not in only:
            continue
        lg = slug.split("-", 1)[0]
        mktag = f"{league_tag.get(lg, 'NBA')} 特刊 · 數據深度"
        html = HTML.format(kicker=kicker, title=title, sub=sub, mktag=mktag)
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html); tmp = f.name
        art_dir = os.path.join(root, "articles", slug)
        os.makedirs(art_dir, exist_ok=True)
        out = os.path.join(art_dir, "cover.png")
        subprocess.run(
            [chrome(), "--headless", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=2", "--window-size=1200,630",
             "--default-background-color=00000000",
             f"--screenshot={out}", f"file://{tmp}"],
            check=True, capture_output=True)
        os.unlink(tmp)
        print(f"✓ {out}")


if __name__ == "__main__":
    main()
