#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch-tw-hoops.py — 台灣職籃（TPBL＋PLG）戰績快照。

資料源（2026-07-19 實測）：
  - TPBL：官網未文件化 JSON API（api.tpbl.basketball，逆向自官網前端；無條款背書 →
    fail-soft＋UA＋退避）。/api/seasons → /api/seasons/{id}/games。
    例行賽 = 場次最多的 division；總冠軍賽 = 最晚日期且非例行賽、恰兩隊的 division
    （冠軍由賽果自算；無法明確識別 finals 時不判冠軍）。
  - PLG：官網 https://pleagueofficial.com/standings 為 server-rendered HTML → 直接
    parse 第一張戰績表。總冠軍賽頁為 JS 動態渲染 → 冠軍走 config/season-facts.json
    （editorial fact，附來源、人工 cross-check）。

輸出：leagues/tw-hoops-<台北日期>.json
  { asof_taipei_date, season, final,
    leagues: { tpbl: {name_zh, champion_zh, finals_note, standings:[...],
                      recent_results:[...], upcoming:[...]},
               plg:  {...} } }
standings row keys 對齊 build-articles._dash_simple_standings：
  {rank, team_name, win, lose, pct, games_behind}
  ⭐ 例行賽開打後，standings 列＝例行賽「排定場次」的全部隊伍（未打者 0-0），不是只有打過球的隊
  （2026-10-26：開季 10 天只有 5 隊有紀錄＋PLG 空表，合計 5 列對上季 11 列跌破 50% 被守門拒寫）。
recent_results／upcoming（僅 tpbl；隊伍層）每一列：
  {date, time, home, away, home_score, away_score, venue, status}
carried_from（可有）：同季某源回空表時沿用前一份該聯盟資料，記那份的台北日期。
"""
import datetime
import json
import pathlib
import re
import subprocess
import sys
import time
import zoneinfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import snapshot_guard  # noqa: E402  （同目錄模組；ROOT 定義後才 import）
OUT_DIR = ROOT / "leagues"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) basketball-tools/1.0"

# PLG 官網戰績表用簡稱；對齊官方全名（洋基工程為 2025-08 新軍，官方即以「洋基工程」列名，保留原樣）
PLG_FULL = {"領航猿": "桃園璞園領航猿", "勇士": "臺北富邦勇士", "獵鷹": "台鋼獵鷹"}


def curl(url: str, tries: int = 4) -> str:
    delay = 4
    for i in range(tries):
        r = subprocess.run(["curl", "-sS", "--max-time", "25", "-H", f"User-Agent: {UA}", url],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
        if i < tries - 1:
            print(f"  retry {i + 1}/{tries - 1} in {delay}s: {url}", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise RuntimeError(f"fetch failed: {url}")


def _pct(w: int, l: int) -> str:
    return f"{w / (w + l):.3f}" if (w + l) else "0.000"


def _standings_rows(rec: dict) -> list:
    """rec: team -> [wins, losses] → 排名列（勝率為主、勝場次之；出賽數不齊的
    賽季進行中兩者會分家。同勝率的正式 tie-break 各聯盟未公開文件化，
    頁面以快照標示為準。GB 對龍頭算。"""
    rows = sorted(rec.items(),
                  key=lambda kv: (-(kv[1][0] / max(kv[1][0] + kv[1][1], 1)),
                                  -kv[1][0], kv[1][1]))
    lw, ll = rows[0][1]
    out = []
    for i, (team, (w, l)) in enumerate(rows):
        gb = ((lw - w) + (l - ll)) / 2
        out.append({"rank": i + 1, "team_name": team, "win": w, "lose": l,
                    "pct": _pct(w, l),
                    "games_behind": "—" if gb <= 0 else f"{gb:.1f}".rstrip("0").rstrip(".")})
    return out


def _tpbl_finals(by_div: dict, reg_div) -> tuple:
    """由 division 分組賽果判定總冠軍 → (champion, finals_note)。
    總冠軍賽 = 最晚開打日的 division，且必須「不是例行賽 division＋恰好兩隊＋
    ≤7 場」才視為有效系列賽——開季初只有例行賽一個 division 時，最晚日期會指回
    例行賽本身，任何隊累積 4 勝就會被誤判成總冠軍（2026-07-19 外部審查 P0）。
    無法明確識別 finals、或系列賽未達 4 勝時，一律回 (None, "")，不推測。"""
    finals_div = max(by_div, key=lambda d: max(g["game_date"] for g in by_div[d]))
    finals_games = by_div[finals_div]
    finals_teams = {g[side]["name"] for g in finals_games for side in ("home_team", "away_team")}
    if not (finals_div != reg_div and len(finals_teams) == 2 and len(finals_games) <= 7):
        return None, ""
    fw = {}
    for g in finals_games:
        h, a = g["home_team"], g["away_team"]
        winner = h["name"] if h["won_score"] > a["won_score"] else a["name"]
        fw[winner] = fw.get(winner, 0) + 1
    champ = max(fw, key=fw.get)
    if fw[champ] < 4:
        return None, ""
    loser = next((t for t in fw if t != champ), "")
    return champ, f"總冠軍賽 {fw[champ]}:{fw.get(loser, 0)} 勝{loser}"


def fetch_tpbl(today=None):
    seasons = json.loads(curl("https://api.tpbl.basketball/api/seasons"))
    season = sorted(seasons, key=lambda s: s.get("started_at", ""))[-1]
    name = season.get("name", "")  # e.g. "2025-2026 賽季"
    m = re.search(r"(\d{4})-(\d{4})", name)
    season_label = f"{m.group(1)}-{m.group(2)[2:]}" if m else name
    games = json.loads(curl(f"https://api.tpbl.basketball/api/seasons/{season['id']}/games"))
    done = [g for g in games if g.get("status") == "COMPLETED"
            and g.get("home_team", {}).get("won_score") is not None]

    # 新賽季已建立、但尚無完成賽事是合法狀態；不能因 max(empty) 讓 PLG 也跟著失敗。
    if not done:
        return season_label, {
            "name_zh": "TPBL 台灣職業籃球大聯盟",
            "champion_zh": None,
            "finals_note": "",
            "regular_season_games": 0,
            "standings": [],
            "source": "整理自 TPBL 官網公開資料（api.tpbl.basketball，非官方文件化介面）",
        }, False

    # 例行賽 = 「排定場次」最多的 division（2025-26 = division 9、126 場、7 隊 × 36）。
    # ⚠️ 要用全部排定場次判，不能用已完成場次：開季前熱身／盃賽 division（2026-27 開季前
    # 有一個 7 場的 division 在 10/9–10/11 先打完）會是唯一有完賽的 division，用「已完成最多」
    # 會把它當例行賽貼上線。
    sched_by_div = {}
    for g in games:
        sched_by_div.setdefault(g["division_id"], []).append(g)
    reg_div = max(sched_by_div, key=lambda d: len(sched_by_div[d]))
    by_div = {}
    for g in done:
        by_div.setdefault(g["division_id"], []).append(g)
    if reg_div not in by_div:
        return season_label, {
            "name_zh": "TPBL 台灣職業籃球大聯盟",
            "champion_zh": None,
            "finals_note": "",
            "regular_season_games": 0,
            "standings": [],
            "source": "整理自 TPBL 官網公開資料（api.tpbl.basketball，非官方文件化介面）；例行賽尚無已完成賽事",
        }, False
    # 先用例行賽「排定場次」的隊伍集合鋪 0-0 列，再疊已完成賽果：開季第一天就是全聯盟的表，
    # 不會只列「打過球的隊」。2026-10-26 實況：開季 10 天只有 4 場完賽、5 隊有紀錄，
    # 加上 PLG 回 0 列，合計 5 列對上季終局 11 列跌破 50%，守門天天拒寫，頁面停在上季。
    rec = {}
    for g in sched_by_div[reg_div]:
        for side in ("home_team", "away_team"):
            name = (g.get(side) or {}).get("name")  # 對手未定的排定場次沒有隊伍，跳過
            if name:
                rec.setdefault(name, [0, 0])
    for g in by_div[reg_div]:
        h, a = g["home_team"], g["away_team"]
        hs, as_ = h["won_score"], a["won_score"]  # won_score = 該隊得分
        rec.setdefault(h["name"], [0, 0])
        rec.setdefault(a["name"], [0, 0])
        if hs > as_:
            rec[h["name"]][0] += 1
            rec[a["name"]][1] += 1
        elif as_ > hs:
            rec[a["name"]][0] += 1
            rec[h["name"]][1] += 1

    champ, finals_note = _tpbl_finals(by_div, reg_div)
    season_over = season.get("status") == "COMPLETED" or bool(champ)
    games_out = _tpbl_games(sched_by_div[reg_div], today)
    return season_label, {
        "name_zh": "TPBL 台灣職業籃球大聯盟",
        "champion_zh": champ,
        "finals_note": finals_note,
        "regular_season_games": len(by_div[reg_div]),
        "standings": _standings_rows(rec),
        "recent_results": games_out["recent_results"],
        "upcoming": games_out["upcoming"],
        "source": "整理自 TPBL 官網公開資料（api.tpbl.basketball，非官方文件化介面）",
    }, season_over


def _tpbl_game_row(g: dict) -> dict:
    """單場賽事的隊伍層摘要（例行賽；只到隊名、比分、場館，不含球員）。"""
    h, a = g.get("home_team", {}), g.get("away_team", {})
    venue = g.get("venue")
    venue_name = venue.get("name", "") if isinstance(venue, dict) else (venue or "")
    done = g.get("status") == "COMPLETED" and h.get("won_score") is not None
    return {"date": str(g.get("game_date", ""))[:10],
            "time": str(g.get("game_time") or "")[:5],
            "home": h.get("name", ""), "away": a.get("name", ""),
            "home_score": h.get("won_score") if done else None,
            "away_score": a.get("won_score") if done else None,
            "venue": venue_name or "",
            "status": "COMPLETED" if done else "SCHEDULED"}


def _tpbl_games(reg_games: list, today, days: int = 7, cap: int = 10) -> dict:
    """例行賽近期賽果（含今天往前 days 天）與近期賽程（今天起 days 天）。
    today 為台北日期；None 時兩個清單皆空（純函式測試用）。
    ⚠️ 已過日期但 API 仍標未完成的場次（2026-10-24 兩場實測延遲）不列入兩邊——
    不能把沒有比分的舊場次當「即將開打」，也不能替它猜結果。"""
    if today is None:
        return {"recent_results": [], "upcoming": []}
    if isinstance(today, str):
        today = datetime.date.fromisoformat(today)
    # game_date 為純台北日期字串（2026-10-26 實抓："2026-10-17"），不是 UTC ISO，可直接字串比大小。
    lo, hi = today - datetime.timedelta(days=days), today + datetime.timedelta(days=days)
    rows = [_tpbl_game_row(g) for g in reg_games]
    recent = sorted((r for r in rows if r["status"] == "COMPLETED"
                     and lo.isoformat() <= r["date"] <= today.isoformat()),
                    key=lambda r: (r["date"], r["time"]), reverse=True)[:cap]
    upcoming = sorted((r for r in rows if r["status"] != "COMPLETED"
                       and today.isoformat() <= r["date"] <= hi.isoformat()),
                      key=lambda r: (r["date"], r["time"]))[:cap]
    return {"recent_results": recent, "upcoming": upcoming}


def _carry_over(league: dict, prior: dict, previous: dict, season_label: str, key: str) -> dict:
    """同一賽季內某源回空表（官網改版、被擋、暫時下線）時沿用前一份該聯盟資料，
    而不是讓整份快照被驟減守門拒寫、連另一個健康的聯盟也一起停更。
    跨季（前一份是上季終局）不沿用——新賽季開季前空表是合法狀態。"""
    if league is None or league.get("standings"):
        return league
    if not prior or not prior.get("standings") or previous.get("final"):
        return league
    if previous.get("season") != season_label:
        return league
    carried = dict(prior)
    # 連續多天沿用時，標的是「資料真正來自哪一天」，不是前一份快照的日期——否則越沿用越舊、
    # 標示卻越新，等於把 staleness 藏起來。
    carried["carried_from"] = prior.get("carried_from") or previous.get("asof_taipei_date", "")
    # 近期賽果／賽程是依「當天」切窗的，沿用舊資料會把已過期的場次當成即將開打，一律不帶。
    carried.pop("recent_results", None)
    carried.pop("upcoming", None)
    print(f"  ⚠️  {key.upper()} 本次未取得本季戰績（{league.get('source', '')}）→ "
          f"沿用 {carried['carried_from']} 快照的該聯盟資料", file=sys.stderr)
    return carried


def _guard_season_facts(facts: dict, season_label: str) -> dict:
    """editorial fact（PLG 冠軍等）只在賽季相符時套用——否則新賽季戰績會繼續
    掛上季冠軍（2026-07-19 外部審查 P1）。不符時回空 dict＋stderr 警告。"""
    if facts and facts.get("season") != season_label:
        print(f"  ⚠️  season-facts.json plg.season={facts.get('season')!r} ≠ 目前賽季 "
              f"{season_label!r}，冠軍資料不套用（待人工核驗後更新）", file=sys.stderr)
        return {}
    return facts


def fetch_plg(season_label: str):
    # `/standings` 會停在上一季；指定賽季才能避免把歷史表貼成新賽季戰績。
    html = curl(f"https://pleagueofficial.com/standings/{season_label}")
    # 第一張表：排行/球隊/GP/W/L/PCT/勝差/…（server-rendered）
    rows_raw = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    rec_rows = []
    for tr in rows_raw:
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        # 資料列長相：['1','領航猿','24','21','3','88%','0',...]
        if (len(cells) >= 5 and cells[0].isdigit() and cells[2].isdigit()
                and cells[3].isdigit() and cells[4].isdigit()):
            rec_rows.append(cells)
    if len(rec_rows) == 0:
        # PLG 尚未刊出本季戰績表是開季前的合法狀態；與 TPBL 獨立。
        return {
            "name_zh": "P. LEAGUE+",
            "champion_zh": None,
            "finals_note": "",
            "standings": [],
            "source": "整理自 P. LEAGUE+ 官網戰績頁；目前尚未刊出本季戰績",
        }
    if not (3 <= len(rec_rows) <= 8):
        raise RuntimeError(f"PLG standings parse got {len(rec_rows)} rows — page changed?")
    rec = {}
    for c in rec_rows:
        team = PLG_FULL.get(c[1], c[1])
        rec[team] = [int(c[3]), int(c[4])]
    if all(w == 0 and l == 0 for w, l in rec.values()):
        return {
            "name_zh": "P. LEAGUE+",
            "champion_zh": None,
            "finals_note": "",
            "standings": [],
            "source": "整理自 P. LEAGUE+ 官網戰績頁；本季尚無已完成賽事",
        }
    facts_p = ROOT / "config" / "season-facts.json"
    facts = (json.loads(facts_p.read_text(encoding="utf-8")) if facts_p.exists() else {}).get("plg", {})
    facts = _guard_season_facts(facts, season_label)
    return {
        "name_zh": "P. LEAGUE+",
        "champion_zh": facts.get("champion_zh"),
        "finals_note": facts.get("finals_note", ""),
        "standings": _standings_rows(rec),
        "source": "整理自 P. LEAGUE+ 官網戰績頁；總冠軍出處見 config/season-facts.json",
    }


def main():
    today = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Taipei")).date().isoformat()
    errors = []
    try:
        season_label, tpbl, season_over = fetch_tpbl(today)
    except Exception as e:
        errors.append(f"TPBL：{e}")
        season_label, tpbl, season_over = "", None, False
    try:
        # TPBL 不可用時仍嘗試 PLG；PLG 的冠軍 facts 會因未知賽季而安全停用。
        plg = fetch_plg(season_label)
    except Exception as e:
        errors.append(f"PLG：{e}")
        plg = None
    if not season_label:
        latest = snapshot_guard.newest(str(OUT_DIR / "tw-hoops-*.json"))
        if latest:
            prior = json.loads(latest.read_text(encoding="utf-8"))
            season_label = prior.get("season", "")
        else:
            season_label = "未知賽季"
    # 各源失敗時保留上一份該聯盟資料；成功的另一源仍可更新。
    # ⚠️ 只在「同一賽季、且前一份不是終局」才沿用——否則新賽季第一次抓、某源失敗時，
    # 上季終局的戰績與冠軍會原封不動掛進新賽季快照（2026-10-26 審視時發現的既有缺口）。
    latest = snapshot_guard.newest(str(OUT_DIR / "tw-hoops-*.json"))
    previous = json.loads(latest.read_text(encoding="utf-8")) if latest else {}
    prior_leagues = previous.get("leagues", {})
    same_season = previous.get("season") == season_label and not previous.get("final")
    if tpbl is None and plg is None and not same_season:
        raise RuntimeError("TPBL／PLG 皆抓取失敗，且沒有同季快照可沿用：" + "；".join(errors))
    names = {"tpbl": "TPBL 台灣職業籃球大聯盟", "plg": "P. LEAGUE+"}
    leagues = {"tpbl": tpbl, "plg": plg}
    for key, league in leagues.items():
        if league is not None:
            continue
        # 失敗的源先化成「本季空表」的 stub，再與「回空表」走同一條 _carry_over 路徑——
        # 兩種情況都要有 carried_from 揭露，不能只有回空表那條有標。
        err = next((e.split("：", 1)[1] for e in errors if e.startswith(key.upper())), "")
        leagues[key] = {"name_zh": names[key], "champion_zh": None, "finals_note": "",
                        "standings": [], "source": f"本次抓取失敗（{err}），本季尚無可發布戰績"}
    # 同季某源回空表或失敗 → 沿用前一份該聯盟資料（見 _carry_over）；源成功時 carried_from 不會出現。
    tpbl = _carry_over(leagues["tpbl"], prior_leagues.get("tpbl"), previous, season_label, "tpbl")
    plg = _carry_over(leagues["plg"], prior_leagues.get("plg"), previous, season_label, "plg")
    out = {
        "asof_taipei_date": today,
        "season": season_label,
        "final": season_over,
        "leagues": {"tpbl": tpbl, "plg": plg},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"tw-hoops-{today}.json"
    # 日期序列快照：新檔沒有前一份可比 → baseline 指向目前生效那份（生成端取 sorted()[-1]），
    # 否則寫進一份空的就會因檔名排序在後而 shadow 掉昨天的好資料。
    # 雙方都「例行賽尚未開打」＝開季前的合法狀態：不寫新快照（空表會被 snapshot_guard 的
    # 驟減規則拒絕，且上季終局表比空表更有資訊），頁面沿用上季終局快照，與 NBA 的處理一致。
    if not tpbl["standings"] and not plg["standings"]:
        print(f"⏭️ TW hoops {season_label}：TPBL／PLG 例行賽尚未開打，沿用上季終局快照")
        for name, league in (("TPBL", tpbl), ("PLG", plg)):
            print(f"📋 來源狀態｜{name}｜成功但未更新｜{league.get('source', '')}")
        for error in errors:
            print(f"📋 來源狀態｜{error.split('：', 1)[0]}｜失敗｜{error.split('：', 1)[1]}")
        return
    if not snapshot_guard.guarded_write(
            path, out,
            lambda d: sum(len(lg.get("standings", []))
                          for lg in (d or {}).get("leagues", {}).values()),
            label=f"tw-hoops-{today}", indent=1,
            baseline=snapshot_guard.newest(str(OUT_DIR / "tw-hoops-*.json"))):
        sys.exit(2)
    print(f"✅ TW hoops {season_label}: TPBL {len(tpbl['standings'])} 隊"
          f"（冠軍 {tpbl.get('champion_zh')}）+ PLG {len(plg['standings'])} 隊"
          f"（冠軍 {plg.get('champion_zh')}）→ {path}")
    for name, league in (("TPBL", tpbl), ("PLG", plg)):
        result = "成功（尚未開打）" if not league.get("standings") else "成功"
        print(f"📋 來源狀態｜{name}｜{result}｜{league.get('source', '')}")
    for error in errors:
        print(f"📋 來源狀態｜{error.split('：', 1)[0]}｜失敗但已保留另一源／舊快照｜{error.split('：', 1)[1]}")


if __name__ == "__main__":
    main()
