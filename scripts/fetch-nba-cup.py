#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch-nba-cup.py — NBA Cup（季中錦標賽）小組賽戰績快照。

資料：ESPN scoreboard 的每一場 Cup 小組賽都帶 notes「NBA Cup - Group Play」，但**不帶組別**；
分組是 editorial fact，住在 config/nba-cup-<year>.json（附 NBA 官方公告來源）。
ESPN 的日期區間查詢對未來日期回空，**月查詢加 limit** 才拿得到整月（2026-10-26 實測：
`dates=202611&limit=400` 回 215 場、其中 50 場 Cup；`202610` 回 10 場 Cup，合計 60 場）。

排序口徑（config 的 tiebreak 由官方規則轉錄）：勝場 → 同分時對戰成績（只在恰兩隊同分時算）→
淨勝分（進延長賽的場次記 0）→ 總得分（不含延長賽）。第 4、5 層（上季戰績、抽籤）本站不算，
仍並列時 `tie_note` 寫明「待官方」。外卡＝各區小組第二名中依同口徑（不含對戰）最佳者。
⚠️ 這些都是**本站自算**，淘汰賽對戰與種子以 NBA 官方公告為準，頁面要標。

輸出：leagues/nba-cup-<season>.json
  { season, label, asof_taipei_date, source, config_sources, group_play, knockout,
    groups: [{conference, name, tie_note,
              standings: [{abbr, name_zh, wins, losses, played, diff, points}],
              games: [{date, time, home_abbr, home_zh, away_abbr, away_zh, home_score, away_score, status, ot}]}],
    wildcards: {Eastern: {abbr, name_zh}|null, Western: ...},
    unassigned: [<ESPN 標 Cup 但兩隊不同組的場次 shortName>] }
"""
import datetime
import importlib.util
import json
import pathlib
import sys
import zoneinfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import snapshot_guard  # noqa: E402
OUT_DIR = ROOT / "leagues"
TPE = zoneinfo.ZoneInfo("Asia/Taipei")


def _nba_module():
    spec = importlib.util.spec_from_file_location("fetch_nba_for_cup", ROOT / "scripts" / "fetch-nba.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


nba = _nba_module()
call = nba.call


def load_config(season_end_year: int) -> dict:
    p = ROOT / "config" / f"nba-cup-{season_end_year - 1}.json"
    if not p.exists():
        raise RuntimeError(f"沒有 {p.name}：本季 NBA Cup 分組尚未登記（editorial fact，附官方來源後再建）")
    return json.loads(p.read_text(encoding="utf-8"))


def months_between(start: str, end: str) -> list:
    s, e = datetime.date.fromisoformat(start), datetime.date.fromisoformat(end)
    out, cur = [], s.replace(day=1)
    while cur <= e:
        out.append(cur.strftime("%Y%m"))
        cur = (cur.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return out


ET = zoneinfo.ZoneInfo("America/New_York")


def is_cup(event: dict, cfg: dict = None) -> bool:
    """小組賽＝notes 標「NBA Cup - Group Play」且美東日期落在 config 的小組賽窗內（淘汰賽 notes 也含 NBA Cup，不收）。"""
    comp = event["competitions"][0]
    if not any("Group Play" in (n.get("headline") or "") and "NBA Cup" in (n.get("headline") or "")
               for n in comp.get("notes", []) or []):
        return False
    if cfg:
        try:
            et_date = datetime.datetime.fromisoformat(event["date"].replace("Z", "+00:00")).astimezone(ET).date().isoformat()
        except (KeyError, ValueError):
            return False
        gp = cfg.get("group_play", {})
        if not (gp.get("start", "") <= et_date <= gp.get("end", "9999")):
            return False
    return True


def _status(comp: dict) -> str:
    stype = comp.get("status", {}).get("type", {}) or {}
    name = str(stype.get("name") or "").upper()
    if stype.get("completed"):
        return "FINAL"
    if "POSTPONED" in name:
        return "POSTPONED"
    if "CANCEL" in name:
        return "CANCELLED"
    if stype.get("state") == "in":
        return "LIVE"
    return "SCHEDULED"


def fetch_cup_events(cfg: dict) -> list:
    events = {}
    for ym in months_between(cfg["group_play"]["start"], cfg["group_play"]["end"]):
        data = call("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
                    f"?dates={ym}&limit=400")
        for ev in data.get("events", []) or []:
            if is_cup(ev, cfg):
                events[ev.get("id") or ev.get("date")] = ev
    return list(events.values())


def _regulation_points(competitor: dict, periods: int):
    """前四節得分總和；沒有 linescores 時回 None。"""
    ls = competitor.get("linescores") or []
    if len(ls) < 4:
        return None
    try:
        return int(round(sum(float(x.get("value") or 0) for x in ls[:4])))
    except (TypeError, ValueError):
        return None


def game_row(event: dict, zh: dict) -> dict:
    comp = event["competitions"][0]
    status = comp.get("status", {}) or {}
    stype = status.get("type", {}) or {}
    done = bool(stype.get("completed"))
    periods = int(status.get("period") or 0)
    home = next((t for t in comp.get("competitors", []) if t.get("homeAway") == "home"), {})
    away = next((t for t in comp.get("competitors", []) if t.get("homeAway") == "away"), {})
    when = datetime.datetime.fromisoformat(event["date"].replace("Z", "+00:00")).astimezone(TPE)

    def side(t):
        team = t.get("team", {}) or {}
        name = team.get("displayName", "")
        score = t.get("score")
        try:
            score = int(score) if done and score not in (None, "") else None
        except (TypeError, ValueError):
            score = None
        return team.get("abbreviation", ""), zh.get(name, name), score, _regulation_points(t, periods) if done else None

    ha, hz, hs, hr = side(home)
    aa, az, as_, ar = side(away)
    return {"date": when.date().isoformat(), "time": when.strftime("%H:%M"),
            "home_abbr": ha, "home_zh": hz, "away_abbr": aa, "away_zh": az,
            "home_score": hs, "away_score": as_,
            "status": _status(comp),
            "ot": done and periods > 4,
            "_home_reg": hr, "_away_reg": ar, "_short": event.get("shortName", "")}


def build_groups(cfg: dict, games: list, zh_by_abbr: dict) -> tuple:
    """回 (groups, unassigned)。standings 依 config tiebreak 前三層自算。"""
    team_group = {}
    for g in cfg["groups"]:
        for abbr in g["teams"]:
            team_group[abbr] = g["name"]
    unassigned = []
    by_group = {g["name"]: [] for g in cfg["groups"]}
    for row in games:
        gh, ga = team_group.get(row["home_abbr"]), team_group.get(row["away_abbr"])
        if gh is None or ga is None or gh != ga:
            unassigned.append(row["_short"] or f'{row["away_abbr"]}@{row["home_abbr"]}')
            continue
        by_group[gh].append(row)

    groups = []
    for g in cfg["groups"]:
        rec = {abbr: {"abbr": abbr, "name_zh": zh_by_abbr.get(abbr, abbr), "wins": 0, "losses": 0,
                      "played": 0, "diff": 0, "points": 0} for abbr in g["teams"]}
        h2h = {abbr: {} for abbr in g["teams"]}  # h2h[a][b] = a 對 b 的勝場
        notes = []
        for row in by_group[g["name"]]:
            if row["status"] != "FINAL" or row["home_score"] is None or row["away_score"] is None:
                continue
            h, a = row["home_abbr"], row["away_abbr"]
            hs, as_ = row["home_score"], row["away_score"]
            winner, loser = (h, a) if hs > as_ else (a, h)
            rec[winner]["wins"] += 1
            rec[loser]["losses"] += 1
            rec[h]["played"] += 1
            rec[a]["played"] += 1
            h2h[winner][loser] = h2h[winner].get(loser, 0) + 1
            # 淨勝分／總得分只算正規時間；進延長賽的場次淨勝分記 0、得分只算前四節
            if row["ot"]:
                if row["_home_reg"] is None or row["_away_reg"] is None:
                    # 沒有分節資料就算不出前四節得分：不灌含延長賽的總分進第 3 層，標註待官方
                    notes.append(f'{row["date"]} {row["_short"] or (a + "@" + h)} 進延長賽但缺分節資料，總得分未計入')
                else:
                    rec[h]["points"] += row["_home_reg"]
                    rec[a]["points"] += row["_away_reg"]
            else:
                rec[h]["diff"] += hs - as_
                rec[a]["diff"] += as_ - hs
                rec[h]["points"] += hs
                rec[a]["points"] += as_

        rows = list(rec.values())
        # 小組賽進行中各隊出賽數不同：先比勝率（0 場記 0），再淨勝分、總得分（官方表同樣以 W-L 勝率排）
        pct = lambda r: (r["wins"] / r["played"]) if r["played"] else 0.0  # noqa: E731
        rows.sort(key=lambda r: (-pct(r), -r["wins"], -r["diff"], -r["points"], r["abbr"]))
        # 第 1 層：恰兩隊「同勝率且同出賽數」時看對戰成績（三隊以上的對戰成績要看互戰總和，口徑未驗，不自算）
        tie_note = ""
        i = 0
        while i < len(rows):
            j = i
            while (j + 1 < len(rows) and pct(rows[j + 1]) == pct(rows[i])
                   and rows[j + 1]["played"] == rows[i]["played"]):
                j += 1
            if j == i + 1 and rows[i]["played"]:
                a, b = rows[i]["abbr"], rows[i + 1]["abbr"]
                if h2h[b].get(a, 0) > h2h[a].get(b, 0):
                    rows[i], rows[i + 1] = rows[i + 1], rows[i]
            elif j > i + 1 and rows[i]["played"]:
                tie_note = "有三隊以上同勝率：本站只依淨勝分、總得分排列，對戰成績與後續層級以官方名次為準。"
            i = j + 1
        if notes:
            tie_note = (tie_note + " " if tie_note else "") + "；".join(notes) + "。"
        games_out = [{k: v for k, v in r.items() if not k.startswith("_")}
                     for r in sorted(by_group[g["name"]], key=lambda r: (r["date"], r["time"]))]
        groups.append({"conference": g["conference"], "name": g["name"], "tie_note": tie_note,
                       "standings": rows, "games": games_out})
    return groups, unassigned


def wildcards(groups: list) -> dict:
    out = {}
    for conf in ("Eastern", "Western"):
        seconds = [g["standings"][1] for g in groups if g["conference"] == conf and len(g["standings"]) > 1]
        seconds = [s for s in seconds if s["played"]]
        if not seconds:
            out[conf] = None
            continue
        best = sorted(seconds, key=lambda r: (-(r["wins"] / r["played"]), -r["wins"], -r["diff"], -r["points"], r["abbr"]))[0]
        out[conf] = {"abbr": best["abbr"], "name_zh": best["name_zh"]}
    return out


def main():
    today = datetime.datetime.now(TPE).date()
    season_end = nba.default_season()
    cfg = load_config(season_end)
    zh = nba.load_zh()
    events = fetch_cup_events(cfg)
    games = [game_row(ev, zh) for ev in events]
    zh_by_abbr = {}
    for row in games:
        zh_by_abbr[row["home_abbr"]] = row["home_zh"]
        zh_by_abbr[row["away_abbr"]] = row["away_zh"]
    groups, unassigned = build_groups(cfg, games, zh_by_abbr)
    out = {
        "season": cfg["season"], "label": cfg["label"],
        "asof_taipei_date": today.isoformat(),
        "source": "整理自 ESPN 公開資料（site.api.espn.com scoreboard，notes 標 NBA Cup）；分組依 NBA 官方公告（config/nba-cup）",
        "config_sources": cfg.get("sources", []),
        "group_play": cfg["group_play"], "knockout": cfg.get("knockout", {}),
        "tiebreak": cfg.get("tiebreak", []),
        "groups": groups, "wildcards": wildcards(groups), "unassigned": unassigned,
    }
    if unassigned:
        print(f"  ⚠️ {len(unassigned)} 場 ESPN 標 Cup 但兩隊不在同一組（分組設定或 ESPN 標記有誤）：{unassigned}",
              file=sys.stderr)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"nba-cup-{cfg['season']}.json"
    total = sum(len(g["games"]) for g in groups)
    done = sum(1 for g in groups for r in g["games"] if r["status"] == "FINAL")
    # 六組、每組五隊是賽制常數；缺組＝設定或上游異常 → 拒寫
    if not snapshot_guard.guarded_write(path, out, lambda d: len((d or {}).get("groups", [])),
                                        label=f"nba-cup-{cfg['season']}", indent=1, min_count=6):
        sys.exit(2)
    print(f"✅ {cfg['label']}：小組賽 {total} 場（已完成 {done}）→ {path}")
    print("📋 來源狀態｜NBA Cup（ESPN）｜成功｜已寫入小組賽戰績快照")


if __name__ == "__main__":
    main()
