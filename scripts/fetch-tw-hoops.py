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
    leagues: { tpbl: {name_zh, champion_zh, finals_note, standings:[...]},
               plg:  {...} } }
standings row keys 對齊 build-articles._dash_simple_standings：
  {rank, team_name, win, lose, pct, games_behind}
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


def fetch_tpbl():
    seasons = json.loads(curl("https://api.tpbl.basketball/api/seasons"))
    season = sorted(seasons, key=lambda s: s.get("started_at", ""))[-1]
    name = season.get("name", "")  # e.g. "2025-2026 賽季"
    m = re.search(r"(\d{4})-(\d{4})", name)
    season_label = f"{m.group(1)}-{m.group(2)[2:]}" if m else name
    games = json.loads(curl(f"https://api.tpbl.basketball/api/seasons/{season['id']}/games"))
    done = [g for g in games if g.get("status") == "COMPLETED"
            and g.get("home_team", {}).get("won_score") is not None]

    # 例行賽 = 場次最多的 division（2025-26 = division 9、126 場、7 隊 × 36）
    by_div = {}
    for g in done:
        by_div.setdefault(g["division_id"], []).append(g)
    reg_div = max(by_div, key=lambda d: len(by_div[d]))
    rec = {}
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
    return season_label, {
        "name_zh": "TPBL 台灣職業籃球大聯盟",
        "champion_zh": champ,
        "finals_note": finals_note,
        "regular_season_games": len(by_div[reg_div]),
        "standings": _standings_rows(rec),
        "source": "整理自 TPBL 官網公開資料（api.tpbl.basketball，非官方文件化介面）",
    }, season_over


def _guard_season_facts(facts: dict, season_label: str) -> dict:
    """editorial fact（PLG 冠軍等）只在賽季相符時套用——否則新賽季戰績會繼續
    掛上季冠軍（2026-07-19 外部審查 P1）。不符時回空 dict＋stderr 警告。"""
    if facts and facts.get("season") != season_label:
        print(f"  ⚠️  season-facts.json plg.season={facts.get('season')!r} ≠ 目前賽季 "
              f"{season_label!r}，冠軍資料不套用（待人工核驗後更新）", file=sys.stderr)
        return {}
    return facts


def fetch_plg(season_label: str):
    html = curl("https://pleagueofficial.com/standings")
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
    if not (3 <= len(rec_rows) <= 8):
        raise RuntimeError(f"PLG standings parse got {len(rec_rows)} rows — page changed?")
    rec = {}
    for c in rec_rows:
        team = PLG_FULL.get(c[1], c[1])
        rec[team] = [int(c[3]), int(c[4])]
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
    season_label, tpbl, season_over = fetch_tpbl()
    plg = fetch_plg(season_label)
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
    if not snapshot_guard.guarded_write(
            path, out,
            lambda d: sum(len(lg.get("standings", []))
                          for lg in (d or {}).get("leagues", {}).values()),
            label=f"tw-hoops-{today}", indent=1,
            baseline=snapshot_guard.newest(str(OUT_DIR / "tw-hoops-*.json"))):
        sys.exit(2)
    print(f"✅ TW hoops {season_label}: TPBL {len(tpbl['standings'])} 隊"
          f"（冠軍 {tpbl['champion_zh']}）+ PLG {len(plg['standings'])} 隊"
          f"（冠軍 {plg['champion_zh']}）→ {path}")


if __name__ == "__main__":
    main()
