#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch-nba.py — NBA 戰績快照（主源：ESPN 公開 JSON API）。

為什麼是 ESPN 而不是 NBA 官方源（2026-07-19 實測結論）：
  - stats.nba.com / cdn.nba.com 自 2026-05 起套「瀏覽器 TLS 指紋 + Referer」雙重判定，
    純 curl/requests 403 或 hang；GitHub Actions（Azure IP）另吃 datacenter 封鎖。
  - ESPN site.api.espn.com 是實測唯一「datacenter IP + 零特殊 headers」直通的源。
  - basketball-reference 條款明文禁爬（Sports-Reference data_use），永不使用。
ESPN 同樣是未文件化的私有 API，可能無預警改版 → 本腳本 fail-soft：任何失敗 exit 1，
編排器沿用 repo 內既有快照（頁面 as-of 誠實標示）。

輸出：leagues/nba-standings-<season_label>.json
  { season, asof, final, champion_zh/champion_en/finals_note(奪冠年才有),
    source, standings: [{conference, rank, name, name_zh, abbr, wins, losses, pct, games_back}] }

用法：python3 scripts/fetch-nba.py [--season 2026]   # 2026 = 2025-26 賽季（ESPN 以結束年計）
"""
import argparse
import datetime
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "leagues"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) basketball-tools/1.0"


def call(url: str, tries: int = 4):
    """curl 後端（本機 Framework Python 缺 CA cert；同 baseball-tools 慣例）＋指數退避。"""
    delay = 4
    for i in range(tries):
        r = subprocess.run(["curl", "-sS", "--max-time", "25", "-H", f"User-Agent: {UA}", url],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                pass
        if i < tries - 1:
            print(f"  retry {i + 1}/{tries - 1} in {delay}s: {url}", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise RuntimeError(f"fetch failed: {url}")


def load_zh() -> dict:
    p = ROOT / "scripts" / "team-zh.json"
    raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def season_label(season_end_year: int) -> str:
    return f"{season_end_year - 1}-{str(season_end_year)[2:]}"


def fetch_standings(season: int, zh: dict) -> list:
    data = call(f"https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
                f"?season={season}&level=2")
    rows = []
    for conf in data.get("children", []):
        cname = "Eastern" if "East" in conf.get("name", "") else "Western"
        for e in conf.get("standings", {}).get("entries", []):
            team = e.get("team", {})
            stats = {s.get("name"): s for s in e.get("stats", [])}

            def sval(key, default=""):
                return stats.get(key, {}).get("displayValue", default)

            name = team.get("displayName", "")
            rows.append({
                "conference": cname,
                "seed": int(sval("playoffSeed", "0") or 0),
                "name": name,
                "name_zh": zh.get(name, name),
                "abbr": team.get("abbreviation", ""),
                "wins": int(sval("wins", "0") or 0),
                "losses": int(sval("losses", "0") or 0),
                "pct": sval("winPercent", ""),
                "games_back": ("—" if sval("gamesBehind", "-") in ("-", "0", "")
                               else sval("gamesBehind")),
            })
    if len(rows) != 30:
        raise RuntimeError(f"expected 30 teams, got {len(rows)} — ESPN shape changed?")
    # ⚠️ ESPN 的 playoffSeed 是「附加賽後的季後賽種子」不是例行賽名次（2026 實例：太陽
    # 例行賽第 7 但附加賽輸給拓荒者 → seed 8）。頁面/文章要的是例行賽終局排名 →
    # 依勝率重排；同勝率之先後以 seed 為次鍵（經 2026 對照附加賽對位「7th vs 8th
    # Place」標籤，可重現官方名次）。seed 欄保留供對照。
    for conf in ("Eastern", "Western"):
        grp = [r for r in rows if r["conference"] == conf]
        grp.sort(key=lambda r: (-(r["wins"] / max(r["wins"] + r["losses"], 1)), r["seed"]))
        for i, r in enumerate(grp):
            r["rank"] = i + 1
    return rows


def fetch_finals(season: int, zh: dict):
    """總冠軍賽結果（賽季結束後才有）。掃 5/20–7/1 的 scoreboard，鎖 notes 標
    'NBA Finals' 的已完賽場次，4 勝隊＝冠軍。找不到（賽季未打完）回 None。"""
    y = season
    try:
        data = call(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
                    f"?dates={y}0520-{y}0701&limit=100")
    except RuntimeError:
        return None
    wins, last_date = {}, ""
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        note = ((comp.get("notes") or [{}])[0].get("headline") or "")
        if "NBA Finals" not in note:
            continue
        if (ev.get("status", {}).get("type", {}) or {}).get("completed") is False:
            continue
        comps = comp.get("competitors", [])
        if len(comps) != 2 or any(c.get("score") in (None, "") for c in comps):
            continue
        winner = max(comps, key=lambda c: int(c["score"]))
        wname = winner.get("team", {}).get("displayName", "")
        wins[wname] = wins.get(wname, 0) + 1
        last_date = max(last_date, ev.get("date", "")[:10])
    champ = next((t for t, w in wins.items() if w >= 4), None)
    if not champ:
        return None
    loser_wins = sum(w for t, w in wins.items() if t != champ)
    loser = next((t for t in wins if t != champ), "")
    return {
        "champion_en": champ,
        "champion_zh": zh.get(champ, champ),
        "finals_note": f"總冠軍賽 4:{loser_wins} 勝{zh.get(loser, loser)}",
        "final_game_date": last_date,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026, help="賽季結束年（2026 = 2025-26）")
    args = ap.parse_args()
    zh = load_zh()
    label = season_label(args.season)

    standings = fetch_standings(args.season, zh)
    finals = fetch_finals(args.season, zh)

    out = {
        "season": label,
        "asof": (finals or {}).get("final_game_date") or datetime.date.today().isoformat(),
        "final": bool(finals),
        "source": "整理自 ESPN 公開資料（site.api.espn.com）",
        "standings": standings,
    }
    if finals:
        out.update({k: finals[k] for k in ("champion_en", "champion_zh", "finals_note")})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"nba-standings-{label}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ch = out.get("champion_zh", "（賽季進行中）")
    print(f"✅ NBA {label}: 30 隊 standings + 冠軍 {ch} → {path}")


if __name__ == "__main__":
    main()
