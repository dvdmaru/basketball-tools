#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch-tw-hoops.py — 台灣職籃（TPBL＋PLG）戰績快照。

資料源（2026-07-19 實測）：
  - TPBL：官網未文件化 JSON API（api.tpbl.basketball，逆向自官網前端；無條款背書 →
    fail-soft＋UA＋退避）。/api/seasons → /api/seasons/{id}/games。
    例行賽 = 場次最多的 division；總冠軍賽 = 最晚日期的 division（冠軍由賽果自算）。
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
    """rec: team -> [wins, losses] → 排名列（勝率排序，GB 對龍頭算）。"""
    rows = sorted(rec.items(), key=lambda kv: (-kv[1][0], kv[1][1]))
    lw, ll = rows[0][1]
    out = []
    for i, (team, (w, l)) in enumerate(rows):
        gb = ((lw - w) + (l - ll)) / 2
        out.append({"rank": i + 1, "team_name": team, "win": w, "lose": l,
                    "pct": _pct(w, l),
                    "games_behind": "—" if gb <= 0 else f"{gb:.1f}".rstrip("0").rstrip(".")})
    return out


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

    # 總冠軍賽 = 最晚開打日的 division；冠軍 = 該系列勝場多者
    finals_div = max(by_div, key=lambda d: max(g["game_date"] for g in by_div[d]))
    fw = {}
    for g in by_div[finals_div]:
        h, a = g["home_team"], g["away_team"]
        winner = h["name"] if h["won_score"] > a["won_score"] else a["name"]
        fw[winner] = fw.get(winner, 0) + 1
    champ = max(fw, key=fw.get) if fw else None
    loser = next((t for t in fw if t != champ), "")
    finals_note = (f"總冠軍賽 {fw[champ]}:{fw.get(loser, 0)} 勝{loser}" if champ else "")

    season_over = season.get("status") == "COMPLETED" or bool(champ and fw[champ] >= 4)
    return season_label, {
        "name_zh": "TPBL 台灣職業籃球大聯盟",
        "champion_zh": champ if (champ and fw[champ] >= 4) else None,
        "finals_note": finals_note if (champ and fw[champ] >= 4) else "",
        "regular_season_games": len(by_div[reg_div]),
        "standings": _standings_rows(rec),
        "source": "整理自 TPBL 官網公開資料（api.tpbl.basketball，非官方文件化介面）",
    }, season_over


def fetch_plg():
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
    plg = fetch_plg()
    out = {
        "asof_taipei_date": today,
        "season": season_label,
        "final": season_over,
        "leagues": {"tpbl": tpbl, "plg": plg},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"tw-hoops-{today}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ TW hoops {season_label}: TPBL {len(tpbl['standings'])} 隊"
          f"（冠軍 {tpbl['champion_zh']}）+ PLG {len(plg['standings'])} 隊"
          f"（冠軍 {plg['champion_zh']}）→ {path}")


if __name__ == "__main__":
    main()
