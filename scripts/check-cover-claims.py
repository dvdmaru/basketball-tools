#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check-cover-claims.py — 封面文案主張錨定 gate（basketball.twtools.cc）

## 它防的是什麼

2026-08-11 實際事故：查核桌把「名人堂稱**首創**」判為過度主張（名人堂原文是
innovator 不是 inventor），標題／H1／導言／FAQ 全改成「創新者」，機械掃描器全綠、
合併、部署——**封面 PNG 還寫著「名人堂說首創」**，被否決的主張掛在 og:image 上，
社群分享卡顯示的就是它，傳播範圍比正文更廣。

成因是**載體盲區**：既有檢查全部讀 `index.md`，封面文案的來源是
`gen-basketball-cover.py` 的 `COVERS` 字串、產物是 PNG，兩者都不在任何 gate 射程內。

## 它怎麼驗

**守原始碼不解析 PNG。** 讀 `COVERS` 的主標＋副標，對照該篇 `index.md` 做
**最長匹配錨定**：封面上每一段中文，都必須能在文章裡找到長度 ≥2 的對應片段。
找不到的（＝文章從沒這樣說過）就是漂移嫌疑。

修辭走**登記制不是 default-deny**：封面本來就會用文章沒有的短促說法（「選到了空氣」），
這種要在 `RHETORIC` 明文登記＋寫理由。**沒登記的未錨定片段一律紅燈。**
（default-deny 用在例外清單是對的，用在辨識上只會讓真訊號淹在假陽性裡。）

承重數字另走**原子比對**（整串必須出現，不交給分詞）——千分位逗號會讓
「1,335」被拆成子字串，分詞版會放過「1,353」這種漂移。

## ⚠️ 宣稱邊界（它**不**驗什麼）

- **不驗語意，只驗字面錨定。** 文章寫「早 9 天」、封面寫「晚 9 天」，只要「9 天」
  在文章出現過就會過關。方向、正負、主客易位一律抓不到。
- **不驗封面說的是不是真的**，只驗「文章有沒有這樣說過」。文章本身錯了，封面照抄也全綠。
- **不驗 PNG。** 只要 `COVERS` 字串對，就算 `cover.png` 是舊的、根本沒重生成，本檢查照樣綠。
  產物是否同步請看 build 流程與 git diff，不要以為這支跑過圖就查過了。
- **不驗 kicker（分類標籤）**，那是欄目名不是主張。

用法：python3 scripts/check-cover-claims.py          # 全部
      python3 scripts/check-cover-claims.py --self-test   # 陽性＋陰性自我測試
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# gen-basketball-cover.py 檔名有連字號不能 import，用 exec 取 COVERS。
# 用 __name__ 假名避免觸發它的 main()（它有 __main__ guard，這是雙保險）。
def load_covers(path=None):
    path = path or os.path.join(ROOT, "scripts", "gen-basketball-cover.py")
    ns = {"__name__": "__notmain__"}
    with open(path, encoding="utf-8") as f:
        src = f.read()
    exec(compile(src, path, "exec"), ns)
    return ns["COVERS"]


# ── 修辭登記簿 ───────────────────────────────────────────────────────────
# 封面刻意使用、文章不會逐字出現的說法。每條都要寫理由；空 dict 代表該篇零修辭。
# ⚠️ 加一條就是放寬一次 gate——只登記「修辭」，不要拿它來塞沒查證的主張。
RHETORIC = {
    "nba-league-guide": {
        "次看懂": "欄目導引語（「一次看懂」），不是主張。",
    },
    "taiwan-hoops-two-leagues": {
        "始末": "摘要名詞。文章講的是同一件事（「破局」出現 9 次、「合併破局」4 次），封面用總括說法。",
    },
    "hbl-league-guide": {
        "男甲": "通行簡稱＝男子甲級組。⚠️文章一貫用「男子組」＋「甲級」，從未出現「男甲」；"
                "數字 37 隊有錨到文章，屬用語不一致非事實問題，是否統一由 Charlie 裁。",
        "女甲": "同上，＝女子甲級組；文章用「女子組」。",
    },
    "nba-2026-draft-results": {
        "換了隊": "口語化改寫。文章用「交易」（70 次）與「易主」（5 次）講同一件事，"
                  "承重數字「27 個」已錨到文章。",
    },
}

# ── 字元分類 ─────────────────────────────────────────────────────────────
# SKIP：標點／分隔／拉丁字母。不計分、不報。
SKIP = set(" 　·・.,，、。：:；;！!？?—－-–—「」『』（）()【】[]/|×~〜"
           "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")

# STOP：中文虛詞（結構助詞／代詞／連接詞／介詞／述說動詞）。不計分、不報，
# **而且不能單獨撐起一個錨點**——這是 2026-08-11 自測抓到的關鍵缺陷：
# 原版允許任意 ≥2 字子字串當錨點，結果「小巨蛋的三月」的「的三」在文章裡剛好
# 出現過（跨詞邊界的無意義片段），就把「三月」的漂移整個掩蓋掉。
# 錨點必須含 ≥2 個實詞字，虛詞只能搭便車。
STOP = set("的了是在和與也就都他她它我你這那之其而於及但個一到把被讓使或且則"
           "又再才只已會後前上下中內外時年說有從對向跟等麼呢吧嗎過來去做為以")

MIN_CONTENT = 2      # 未錨定區含幾個「實詞字」才報
MIN_ANCHOR_CONTENT = 2   # 一個合法錨點至少要含幾個實詞字
MAX_PROBE = 12       # 匹配片段的長度上限


def is_content(ch: str) -> bool:
    """實詞字＝不是標點也不是虛詞。數字算實詞（承重數字要被驗）。"""
    return ch not in SKIP and ch not in STOP


def content_count(s: str) -> int:
    return sum(1 for ch in s if is_content(ch))


def normalize(s: str) -> str:
    """去掉 <br>、markdown 語法雜訊與所有空白，讓『1,335 勝』對得上『1,335勝』。"""
    s = re.sub(r"<br\s*/?>", "", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[\s　]+", "", s)
    return s


def article_text(slug: str) -> str:
    p = os.path.join(ROOT, "articles", slug, "index.md")
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8") as f:
        return normalize(f.read())


def unanchored_runs(cover: str, article: str):
    """回傳封面文案中錨不到文章的片段。

    ⚠️ 用 DP 求「未錨定字數最小」的切法，**不可用貪婪最長匹配**。
    貪婪會製造假陽性：實測「衛冕軍首輪籤選到了空氣」在 i=3 貪走「首輪籤選」
    （文章確實有這 4 字），把「選」從「選到」拆走，於是「到了」被誤報成未錨定——
    但「首輪籤」＋「選到」＋「空氣」其實全部錨得到。
    局部最長 ≠ 整體最佳；gate 自己的判定先錯了，就會拿假陽性去指控別人。
    """
    n = len(cover)
    INF = float("inf")
    # cost[i] = 覆蓋 cover[i:] 所需的最小「未錨定實詞字數」
    cost = [INF] * (n + 1)
    choice = [None] * (n + 1)
    cost[n] = 0
    for i in range(n - 1, -1, -1):
        # 標點與虛詞：不計分，但也不能靠自己錨定
        if not is_content(cover[i]):
            cost[i], choice[i] = cost[i + 1], ("free", 1)
            continue
        best, bc = cost[i + 1] + 1, ("miss", 1)
        for L in range(2, min(MAX_PROBE, n - i) + 1):
            frag = cover[i:i + L]
            if content_count(frag) < MIN_ANCHOR_CONTENT:
                continue          # 虛詞撐起來的片段不算錨點
            if frag in article and cost[i + L] < best:
                best, bc = cost[i + L], ("hit", L)
        cost[i], choice[i] = best, bc

    runs, cur, i = [], "", 0
    while i < n:
        kind, L = choice[i]
        if kind == "miss":
            cur += cover[i]
        elif kind == "free":
            if cover[i] in SKIP:  # 標點／分隔符：切斷片段，不當膠水
                if content_count(cur) >= MIN_CONTENT:
                    runs.append(cur.strip("".join(STOP)))
                cur = ""
            elif cur:             # 虛詞夾在未錨定區中間時保留，方便閱讀
                cur += cover[i]
        else:
            if content_count(cur) >= MIN_CONTENT:
                runs.append(cur.strip("".join(STOP)))
            cur = ""
        i += L
    if content_count(cur) >= MIN_CONTENT:
        runs.append(cur.strip("".join(STOP)))
    return runs


NUM = re.compile(r"\d[\d,]*")


def unanchored_numbers(cover: str, article: str):
    """承重數字必須整串出現在文章裡。

    ⚠️ 不能交給分詞 DP 處理：千分位逗號是分隔符，「1,335」被拆開後
    「1,3」剛好是文章裡的子字串，於是「1,353」這種漂移會靜靜過關（自測抓到）。
    數字是最承重的內容，要當**原子**整串比對。
    """
    return [t for t in NUM.findall(cover) if t not in article]


def check(covers, verbose=True):
    """回傳 (violations, audit)。violations = 未登記的未錨定片段。"""
    violations, audit = [], []
    for slug, _kicker, title, sub in covers:
        art = article_text(slug)
        if not art:
            violations.append((slug, "—", "找不到 articles/%s/index.md" % slug))
            continue
        allowed = RHETORIC.get(slug, {})
        for label, raw in (("主標", title), ("副標", sub)):
            text = normalize(raw)
            for num in unanchored_numbers(text, art):
                if num in allowed:
                    audit.append((slug, label, num, allowed[num]))
                else:
                    violations.append((slug, label, num))
            for run in unanchored_runs(text, art):
                if run in allowed:
                    audit.append((slug, label, run, allowed[run]))
                else:
                    violations.append((slug, label, run))
    if verbose:
        for slug, label, run, why in audit:
            print(f"  ℹ️  {slug} {label}「{run}」＝已登記修辭：{why}")
        for v in violations:
            slug, label, run = v[0], v[1], v[2]
            print(f"  ❌ {slug} {label}「{run}」——文章從沒這樣說過")
    return violations, audit


# ── 自我測試：陽性（真違規要紅）＋陰性（合法內容不能紅）─────────────────
def self_test():
    covers = load_covers()
    ok = True

    print("【基線】現行 COVERS 在健康狀態下的命中數")
    v, a = check(covers)
    print(f"  → 違規 {len(v)}、已登記修辭 {len(a)}")
    if v:
        print("  ✗ 基線不為 0，判定條件需先修（新 gate 不該一出生就亮紅）")
        ok = False
    else:
        print("  ✓ 基線 0 命中")

    print("\n【陽性 1】重現 2026-08-11 事故：把封面改回「名人堂說首創」")
    probe = [(s, k, "名人堂說首創<br>他說只是權宜" if s == "don-nelson-nellie-ball" else t, sub)
             for s, k, t, sub in covers]
    v1, _ = check(probe, verbose=False)
    hit = any(x[0] == "don-nelson-nellie-ball" and "首創" in x[2] for x in v1)
    print(f"  {'✓ 抓到' if hit else '✗ 沒抓到'}（命中 {len(v1)} 項）")
    ok &= hit

    print("\n【陽性 2】數字漂移：把「1,335 勝」改成「1,353 勝」")
    probe = [(s, k, t, sub.replace("1,335", "1,353") if s == "don-nelson-nellie-ball" else sub)
             for s, k, t, sub in covers]
    v2, _ = check(probe, verbose=False)
    hit = any(x[0] == "don-nelson-nellie-ball" for x in v2)
    print(f"  {'✓ 抓到' if hit else '✗ 沒抓到'}（命中 {len(v2)} 項）")
    ok &= hit

    print("\n【陽性 3】登記制不是萬用赦免：已登記「男甲」的那篇改寫別的未錨定主張")
    probe = [(s, k, t, "男甲 37 隊 · 女甲 16 隊　·　史上最爛賽制" if s == "hbl-league-guide" else sub)
             for s, k, t, sub in covers]
    v3, a3 = check(probe, verbose=False)
    hit = any(x[0] == "hbl-league-guide" for x in v3)
    still_reg = any(x[2] == "男甲" for x in a3)
    print(f"  {'✓ 抓到新主張' if hit else '✗ 沒抓到'}；"
          f"{'同篇既有登記仍生效' if still_reg else '⚠️ 登記被連坐失效'}（命中 {len(v3)} 項）")
    ok &= hit and still_reg

    print("\n【陽性 4】程度副詞不在虛詞表：「最強」這種誇大詞必須被檢查")
    probe = [(s, k, "尼克<br>史上最強王朝" if s == "nba-2025-26-season-review" else t, sub)
             for s, k, t, sub in covers]
    v4a, _ = check(probe, verbose=False)
    hit = any(x[0] == "nba-2025-26-season-review" for x in v4a)
    print(f"  {'✓ 抓到' if hit else '✗ 沒抓到（程度副詞被誤列為虛詞？）'}（命中 {len(v4a)} 項）")
    ok &= hit

    print("\n【陰性 1】現行修正後的封面（含全形空白／盤古之白差異）不可亮紅")
    v4, _ = check(covers, verbose=False)
    nelson = [x for x in v4 if x[0] == "don-nelson-nellie-ball"]
    print(f"  {'✓ 未亮紅' if not nelson else '✗ 假陽性 ' + str(nelson)}")
    ok &= not nelson

    print("\n【陰性 2】已登記修辭（男甲／始末等）走登記路徑、不算違規")
    v5, a5 = check(covers, verbose=False)
    reg = {x[2] for x in a5}
    print(f"  {'✓ 登記生效：' + '、'.join(sorted(reg)) if reg and not v5 else '✗ ' + str(v5 or '登記未生效')}")
    ok &= (not v5 and bool(reg))

    print("\n【陰性 3】虛詞不得單獨撐起錨點（「的三」不可掩蓋「三月」漂移）")
    art = article_text("hbl-league-guide")
    r = unanchored_runs(normalize("小巨蛋的三月"), art)
    print(f"  {'✓ 仍抓到 ' + str(r) if r else '✗ 被「的三」掩蓋（貪婪／無虛詞版的舊 bug 回歸）'}")
    ok &= bool(r)

    print("\n【陰性 4】DP 必須求整體最佳，不可貪婪（「首輪籤選」不得孤立「到了」）")
    art2 = article_text("taiwan-hoops-2026-offseason-moves")
    r2 = unanchored_runs(normalize("衛冕軍首輪籤<br>選到了空氣"), art2)
    print(f"  {'✓ 無假陽性' if not r2 else '✗ 貪婪 bug 回歸：' + str(r2)}")
    ok &= not r2

    print("\n" + ("✅ 自我測試全過" if ok else "❌ 自我測試失敗"))
    return 0 if ok else 1


def main():
    if "--self-test" in sys.argv:
        return self_test()
    print("封面主張錨定檢查（守 COVERS 原始碼，不解析 PNG）")
    violations, audit = check(load_covers())
    print(f"\n違規 {len(violations)}、已登記修辭 {len(audit)}")
    if violations:
        print("\n未錨定＝封面說了文章沒說過的話。兩條路：")
        print("  1. 封面主張漂移 → 改 gen-basketball-cover.py 的 COVERS 並重生 cover.png")
        print("  2. 刻意的修辭 → 在 check-cover-claims.py 的 RHETORIC 登記並寫理由")
        return 1
    print("✅ 全部封面文案都在文章裡有依據")
    return 0


if __name__ == "__main__":
    sys.exit(main())
