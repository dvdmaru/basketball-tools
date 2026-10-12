#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch-hbl.py — HBL 高中籃球甲級聯賽 決賽名次快照。

資料源（2026-10-12 實測）：hbl.com.tw 改版後的公開 JSON（未文件化介面；無條款背書
→ fail-soft＋UA＋退避）。
  /api/public-navigation/page/76       → 聯盟／學年度／賽事／division 階層
  /api/division-matches/{divisionId}   → 賽果（總決賽 division 含準決賽／季軍戰／冠軍戰）

名次推導（不靠人工）：先按日期分「準決賽日」與「決賽日」；冠軍戰 = 兩位準決賽勝者之戰、
季軍戰 = 兩位準決賽敗者之戰 → 1-4 名全可由賽果決定。

紅線：HBL 球員為未成年學生——本管線只碰隊伍層賽果與名次，永不抓個別球員數據入站；
影音（liveUrls 為 Hami Video 獨家授權）一律不觸碰、不嵌入。

輸出：leagues/hbl-<學年度>-<台北日期>.json
  { asof_taipei_date, season_label, final,
    divisions: { boys: {label, champion, final_note, final_four:[{rank, school, note}]},
                 girls: {...} } }
"""
import datetime
import json
import pathlib
import subprocess
import sys
import time
import zoneinfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import snapshot_guard  # noqa: E402  （同目錄模組；ROOT 定義後才 import）
OUT_DIR = ROOT / "leagues"
BASE = "https://hbl.com.tw"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) basketball-tools/1.0"


def call(url: str, tries: int = 4):
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


def _hbl_league(data: dict) -> dict:
    leagues = ((data.get("site", {}).get("additional", {}) or {}).get("leagues", []) or [])
    league = next((x for x in leagues if x.get("id") == 1), None)
    if not league:
        raise RuntimeError("新版 HBL 導覽資料缺少聯盟 id=1")
    return league


def latest_season(data=None):
    """新版導覽 API 的最新學年度；尚無 division 也是合法開季前狀態。"""
    data = data if data is not None else call(f"{BASE}/api/public-navigation/page/76")
    seasons = []
    for season in _hbl_league(data).get("seasons", []):
        name = str(season.get("name", "")).replace("學年度", "")
        if name.isdigit():
            seasons.append((int(name), season))
    if not seasons:
        raise RuntimeError("新版 HBL 導覽資料沒有可辨識的學年度")
    return max(seasons, key=lambda x: x[0])


def latest_established_season(data=None):
    """最新一個已有 division 的學年度；開季前仍要沿用上一季終局資料。"""
    data = data if data is not None else call(f"{BASE}/api/public-navigation/page/76")
    seasons = []
    for season in _hbl_league(data).get("seasons", []):
        name = str(season.get("name", "")).replace("學年度", "")
        if name.isdigit() and any(event.get("divisions") for event in season.get("events", [])):
            seasons.append((int(name), season))
    if not seasons:
        raise RuntimeError("新版 HBL 導覽資料沒有已建立 division 的學年度")
    return max(seasons, key=lambda x: x[0])


def finals_stage_sns(season: dict) -> dict:
    """找男、女甲總決賽 division；新學年度尚未建立 division 時回空。"""
    out = {}
    # 114 學年度起叫「總決賽」，舊資料可能為「決賽」；較精確名稱優先。
    for wanted in ("總決賽", "決賽"):
        for event in season.get("events", []):
            event_name = event.get("name", "")
            if "甲級" not in event_name:
                continue
            key = "boys" if "男" in event_name else "girls" if "女" in event_name else None
            if not key:
                continue
            for division in event.get("divisions", []):
                if division.get("name") == wanted:
                    out.setdefault(key, division["id"])
        if out:
            break
    return out


def _score(game: dict, side: str):
    """新版 API 用 homeSquadScore，保留舊欄位以維持歷史 fixture 相容。"""
    return game.get(f"{side}SquadScore", game.get(f"{side}Score"))


def _taipei_date(value: str) -> str:
    """官網 UTC ISO 時間一律轉為台北日期。"""
    if not value:
        return ""
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        zoneinfo.ZoneInfo("Asia/Taipei")).date().isoformat()


def _squad_name(squad: dict) -> str:
    """頁面隊名優先官方 altName；空字串才回退正式名稱。"""
    return squad.get("altName") or squad.get("name") or ""


def _division_games(division_id: int) -> list:
    games = call(f"{BASE}/api/division-matches/{division_id}")
    return sorted(games, key=lambda g: g.get("matchedAt", ""))


def _stage_summary(division: dict) -> dict:
    games = _division_games(division["id"])
    dates = [_taipei_date(g.get("matchedAt", "")) for g in games]
    venues = []
    teams = set()
    for game in games:
        venue = game.get("venue") or ""
        if venue and venue not in venues:
            venues.append(venue)
        for side in ("homeSquad", "awaySquad"):
            name = _squad_name(game.get(side) or {})
            if name:
                teams.add(name)
    return {
        "name": division.get("name", ""),
        "status": division.get("status", ""),
        "games": len(games),
        "completed": sum(g.get("status") == "COMPLETED" for g in games),
        "first_date": min((d for d in dates if d), default=""),
        "last_date": max((d for d in dates if d), default=""),
        "venues": venues,
        "teams": len(teams),
    }


def stage_overview(season: dict) -> dict:
    """各官方 division 的隊伍層賽程摘要；甲級全階段、乙級僅全國決賽。"""
    targets = {
        "boys": ("甲級", "男", None, "男子甲級"),
        "girls": ("甲級", "女", None, "女子甲級"),
        "boys_b": ("乙級", "男", "全國決賽", "男子乙級"),
        "girls_b": ("乙級", "女", "全國決賽", "女子乙級"),
    }
    out = {}
    for key, (level, sex, only_name, label) in targets.items():
        divisions = []
        for event in season.get("events", []):
            name = event.get("name", "")
            if level not in name or sex not in name:
                continue
            for division in event.get("divisions", []):
                if only_name is None or division.get("name") == only_name:
                    divisions.append(_stage_summary(division))
        out[key] = {"label": label, "divisions": divisions}
    return out


def _result_games(division: dict) -> list:
    out = []
    for game in _division_games(division["id"]):
        out.append({
            "date": _taipei_date(game.get("matchedAt", "")),
            "venue": game.get("venue") or "",
            "home": _squad_name(game.get("homeSquad") or {}),
            "away": _squad_name(game.get("awaySquad") or {}),
            "home_score": _score(game, "home"),
            "away_score": _score(game, "away"),
            "round_label": game.get("roundLabel") or "",
        })
    return out


def _division_by_name(event: dict, name: str):
    return next((d for d in event.get("divisions", []) if d.get("name") == name), None)


def _names_in_division(division: dict) -> list:
    names = []
    for game in _division_games(division["id"]):
        for side in ("homeSquad", "awaySquad"):
            name = _squad_name(game.get(side) or {})
            if name and name not in names:
                names.append(name)
    return names


def stage_results(season: dict) -> dict:
    """甲級準決賽／總決賽逐場結果，以及每一前段賽事的下一階段隊伍。"""
    out = {}
    for key, sex in (("boys", "男"), ("girls", "女")):
        event = next((e for e in season.get("events", [])
                      if "甲級" in e.get("name", "") and sex in e.get("name", "")), None)
        if event is None:
            out[key] = {"semifinals": [], "finals": [], "advancers": {}}
            continue
        semi = _division_by_name(event, "準決賽")
        final = _division_by_name(event, "總決賽") or _division_by_name(event, "決賽")
        advancers = {}
        names = ["資格賽", "預賽", "複賽"]
        for i, name in enumerate(names):
            later = (_division_by_name(event, names[i + 1]) if i + 1 < len(names)
                     else semi or final)
            if later is not None:
                advancers[name] = _names_in_division(later)
        out[key] = {
            "semifinals": _result_games(semi) if semi else [],
            "finals": _result_games(final) if final else [],
            "advancers": advancers,
        }
    return out


def next_season_squads(season_name: int, season: dict, today: str) -> dict:
    """導覽最新學年度尚無 division 時，保留官方報名隊數與甲級隊名。"""
    events = call(f"{BASE}/api/season-squads/{season['id']}")
    rows = []
    for event in events:
        name = event.get("name", "")
        squads = event.get("squads", []) or []
        row = {"name": name, "squad_count": len(squads)}
        if "甲級" in name and ("男" in name or "女" in name):
            row["squads"] = [_squad_name(s) for s in squads if _squad_name(s)]
        rows.append(row)
    return {"label": f"{season_name}學年度", "events": rows, "asof": today}


def rank_division(division_id: int, label: str) -> dict:
    games = [g for g in _division_games(division_id)
             if g.get("status") == "COMPLETED" and _score(g, "home") is not None
             and _score(g, "away") is not None]
    if not games:
        raise RuntimeError(f"division {division_id}: no completed games")
    def w_l(g):
        home, away = _squad_name(g["homeSquad"]), _squad_name(g["awaySquad"])
        return (home, away) if _score(g, "home") > _score(g, "away") else (away, home)

    days = sorted({_taipei_date(g["matchedAt"]) for g in games})
    semi_games = [g for g in games if _taipei_date(g["matchedAt"]) == days[0]] if len(days) > 1 else games[:-2]
    final_day = [g for g in games if g not in semi_games]
    semi_winners = {w_l(g)[0] for g in semi_games}

    champ_game = third_game = None
    for g in final_day:
        pair = {_squad_name(g["homeSquad"]), _squad_name(g["awaySquad"])}
        if pair <= semi_winners:
            champ_game = g
        else:
            third_game = g
    if champ_game is None:  # 保底：決賽日最後一場當冠軍戰（單場決賽的舊學年也走這裡）
        champ_game = final_day[-1]
        if third_game is champ_game:
            third_game = None

    def score_note(g, prefix):
        w, l = w_l(g)
        ws, ls = max(_score(g, "home"), _score(g, "away")), min(_score(g, "home"), _score(g, "away"))
        return w, l, f"{prefix} {ws}:{ls} 勝{l}"

    champion, runner_up, final_note = score_note(champ_game, "冠軍戰")
    ranks = [{"rank": 1, "school": champion, "note": final_note.replace("冠軍戰 ", "冠軍戰 ")},
             {"rank": 2, "school": runner_up, "note": ""}]
    if third_game is not None:
        third, fourth, third_note = score_note(third_game, "季軍戰")
        ranks += [{"rank": 3, "school": third, "note": third_note},
                  {"rank": 4, "school": fourth, "note": ""}]
    return {"label": label, "champion": champion, "final_note": final_note,
            "final_four": ranks,
            "source": "整理自 hbl.com.tw 官網公開賽果（非官方文件化介面）"}


def build_history(today: str):
    """歷屆冠軍榜（官網 API 回溯至 106 學年度）→ leagues/hbl-history.json。
    一次性建檔（歷史賽果凍結，不需每日重抓）；個別學年抓不到就留空、不擋整檔。"""
    data = call(f"{BASE}/api/public-navigation/page/76")
    seasons = []
    for season in _hbl_league(data).get("seasons", []):
        name = str(season.get("name", "")).replace("學年度", "")
        if name.isdigit():
            seasons.append((int(name), season))
    seasons.sort(key=lambda x: x[0])
    rows = []
    for name, season in seasons:
        row = {"season": name, "boys_champion": None, "girls_champion": None}
        try:
            sns = finals_stage_sns(season)  # 每學年查一次，男女組共用（別在迴圈內重打 API）
            for key, field in (("boys", "boys_champion"), ("girls", "girls_champion")):
                if key in sns:
                    row[field] = rank_division(sns[key], key)["champion"]
        except Exception as e:
            print(f"  ⚠️ {name}學年度 冠軍解析失敗（跳過）：{e}", file=sys.stderr)
        rows.append(row)
        time.sleep(1)  # 官網 API 節流
    out = {"asof_taipei_date": today,
           "note": "由 hbl.com.tw 官網公開賽果推導（總決賽勝隊）；API 僅回溯至 106 學年度",
           "seasons": rows}
    path = OUT_DIR / "hbl-history.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    done = sum(1 for r in rows if r["boys_champion"])
    print(f"✅ HBL 歷屆冠軍 {done}/{len(rows)} 學年度 → {path}")


def main():
    today = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Taipei")).date().isoformat()
    if "--history" in sys.argv:
        build_history(today)
        return
    navigation = call(f"{BASE}/api/public-navigation/page/76")
    latest_name, latest = latest_season(navigation)
    season_name, season = latest_established_season(navigation)
    stage_sns = finals_stage_sns(season)
    if not stage_sns:
        raise RuntimeError(f"HBL {season_name}學年度已有 division，但找不到甲級總決賽 division")
    divisions = {}
    for key, label in (("boys", "男子甲級"), ("girls", "女子甲級")):
        if key in stage_sns:
            divisions[key] = rank_division(stage_sns[key], label)
    out = {
        "asof_taipei_date": today,
        "season_label": f"{season_name}學年度",
        "final": True,
        "divisions": divisions,
        "stages": stage_overview(season),
        "results": stage_results(season),
    }
    if not any(event.get("divisions") for event in latest.get("events", [])):
        out["next_season"] = next_season_squads(latest_name, latest, today)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"hbl-{season_name}-{today}.json"
    # 同 tw-hoops 的日期序列語意；抓到的學年度不可能一組都沒有
    if not snapshot_guard.guarded_write(
            path, out, lambda d: len((d or {}).get("divisions", {})),
            label=f"hbl-{season_name}-{today}", indent=1,
            baseline=snapshot_guard.newest(str(OUT_DIR / f"hbl-{season_name}-*.json"))):
        sys.exit(2)
    champs = "、".join(f"{d['label']} {d['champion']}" for d in divisions.values())
    print(f"✅ HBL {season_name}學年度: {champs} → {path}")
    print("📋 來源狀態｜HBL｜成功｜已寫入新版 API 的總決賽快照")


if __name__ == "__main__":
    main()
