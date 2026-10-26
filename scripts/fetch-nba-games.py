#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch-nba-games.py — NBA 近三日賽程與賽果（台北時間；主源 ESPN scoreboard）。

為什麼：站的定位是「看門道不是即時比分」，但開季後最多人搜的是「今天／明天誰打誰、昨天比分」
（GSC 2026-10 查詢）。本快照每天由 CI 重抓一次，頁面標資料截至時刻，不做即時更新。

ESPN `scoreboard?dates=YYYYMMDD` 以美東日期分日；台北「今天早上」的比賽是美東「昨天晚上」。
所以抓美東 D-2、D-1、D 三天，再把每場的 UTC 開賽時間換成台北日期／時間，分到台北的
昨天／今天／明天三桶。

輸出：leagues/nba-games-<台北日期>.json
  { asof_taipei_date, asof_taipei_time, season, source,
    days: [ {date, games: [{date, time, home_abbr, home_zh, away_abbr, away_zh,
                             home_score, away_score, status, venue, cup}]} ] }
  status：SCHEDULED／LIVE／FINAL；比分只在 FINAL（或 LIVE 有分）時給，未開打為 null。
  cup：ESPN notes 含「NBA Cup」＝季中錦標賽小組賽（分組戰績另見 fetch-nba-cup.py）。
  ⚠️ 休兵日某桶可能是空陣列——那是合法狀態，本檔不用筆數守門（見 snapshot_guard 檔頭）。
"""
import datetime
import importlib.util
import json
import pathlib
import sys
import zoneinfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
OUT_DIR = ROOT / "leagues"
TPE = zoneinfo.ZoneInfo("Asia/Taipei")
ET = zoneinfo.ZoneInfo("America/New_York")


def _nba_module():
    spec = importlib.util.spec_from_file_location("fetch_nba_for_games", ROOT / "scripts" / "fetch-nba.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


nba = _nba_module()
call = nba.call


def taipei_dt(iso_utc: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(TPE)


def game_row(event: dict, zh: dict) -> dict:
    comp = event["competitions"][0]
    status = comp.get("status", {}).get("type", {}) or {}
    state = status.get("state", "")
    if status.get("completed"):
        st = "FINAL"
    elif state == "in":
        st = "LIVE"
    else:
        st = "SCHEDULED"
    home = away = {}
    for t in comp.get("competitors", []):
        if t.get("homeAway") == "home":
            home = t
        elif t.get("homeAway") == "away":
            away = t

    def side(t):
        team = t.get("team", {}) or {}
        name = team.get("displayName", "")
        score = t.get("score")
        try:
            score = int(score) if score not in (None, "") and st != "SCHEDULED" else None
        except (TypeError, ValueError):
            score = None
        return team.get("abbreviation", ""), zh.get(name, name), score

    ha, hz, hs = side(home)
    aa, az, as_ = side(away)
    when = taipei_dt(event["date"])
    notes = " ".join((n.get("headline") or "") for n in comp.get("notes", []) or [])
    return {
        "date": when.date().isoformat(),
        "time": when.strftime("%H:%M"),
        "home_abbr": ha, "home_zh": hz,
        "away_abbr": aa, "away_zh": az,
        "home_score": hs, "away_score": as_,
        "status": st,
        "venue": ((comp.get("venue") or {}).get("fullName") or ""),
        "cup": "NBA Cup" in notes,
    }


def fetch_days(today_tpe: datetime.date, zh: dict) -> list:
    """回傳台北 [昨天, 今天, 明天] 三桶；每桶依開賽時間排序。"""
    wanted = [today_tpe + datetime.timedelta(days=d) for d in (-1, 0, 1)]
    et_days = [today_tpe + datetime.timedelta(days=d) for d in (-2, -1, 0)]
    rows = {}
    for d in et_days:
        data = call("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
                    f"?dates={d.strftime('%Y%m%d')}")
        for ev in data.get("events", []) or []:
            try:
                row = game_row(ev, zh)
            except (KeyError, IndexError, ValueError):
                continue
            rows[ev.get("id") or (row["date"], row["time"], row["home_abbr"])] = row
    out = []
    for d in wanted:
        games = sorted((r for r in rows.values() if r["date"] == d.isoformat()),
                       key=lambda r: (r["time"], r["home_abbr"]))
        out.append({"date": d.isoformat(), "games": games})
    return out


def main():
    now = datetime.datetime.now(TPE)
    today = now.date()
    zh = nba.load_zh()
    season = nba.season_label(nba.default_season())
    days = fetch_days(today, zh)
    out = {
        "asof_taipei_date": today.isoformat(),
        "asof_taipei_time": now.strftime("%H:%M"),
        "season": season,
        "source": "整理自 ESPN 公開資料（site.api.espn.com scoreboard）；台北時間",
        "days": days,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"nba-games-{today.isoformat()}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(d["games"]) for d in days)
    print(f"✅ NBA 近三日賽程：{n} 場（{days[0]['date']}～{days[-1]['date']}，台北）→ {path}")
    print("📋 來源狀態｜NBA 賽程（ESPN）｜成功｜已寫入近三日賽程快照")


if __name__ == "__main__":
    main()
