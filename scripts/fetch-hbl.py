#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch-hbl.py — HBL 高中籃球甲級聯賽 決賽名次快照。

資料源（2026-07-19 實測）：hbl.com.tw 官網 JSON API（/rest/*，逆向自官網 bundle 的
未文件化介面；無條款背書 → fail-soft＋UA＋退避）。
  /rest/season/listorderbyseq/1        → 學年度清單（114 → sn 46）
  /rest/stage/list/1/{seasonSn}        → 階段（總決賽 M＝男甲、F＝女甲）
  /rest/game/listbystage/{stageSn}     → 賽果（總決賽 stage 含 準決賽×2＋季軍戰＋冠軍戰）

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


def latest_season():
    data = call(f"{BASE}/rest/season/listorderbyseq/1")["data"]
    seasons = [(int(s["name"]), s["seasonPk"]["sn"]) for s in data if str(s.get("name", "")).isdigit()]
    name, sn = max(seasons)
    return name, sn


def finals_stage_sns(season_sn: int) -> dict:
    stages = call(f"{BASE}/rest/stage/list/1/{season_sn}")["data"]
    out = {}
    # 114 學年度起叫「總決賽」，106-113 叫「決賽」——兩者擇一（總決賽優先）
    for wanted in ("總決賽", "決賽"):
        for s in stages:
            if s.get("name") == wanted:
                key = "boys" if s.get("gender") == "M" else "girls"
                out.setdefault(key, s["sn"])
        if out:
            break
    return out


def rank_division(stage_sn: int, label: str) -> dict:
    games = [g for g in call(f"{BASE}/rest/game/listbystage/{stage_sn}")["data"]
             if g.get("score_home") is not None and g.get("score_away") is not None]
    if not games:
        raise RuntimeError(f"stage {stage_sn}: no completed games")
    games.sort(key=lambda g: (g.get("date", ""), g.get("time", "")))

    def w_l(g):
        home, away = g["home_team_name"], g["away_team_name"]
        return (home, away) if g["score_home"] > g["score_away"] else (away, home)

    days = sorted({g["date"] for g in games})
    semi_games = [g for g in games if g["date"] == days[0]] if len(days) > 1 else games[:-2]
    final_day = [g for g in games if g not in semi_games]
    semi_winners = {w_l(g)[0] for g in semi_games}

    champ_game = third_game = None
    for g in final_day:
        pair = {g["home_team_name"], g["away_team_name"]}
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
        ws, ls = max(g["score_home"], g["score_away"]), min(g["score_home"], g["score_away"])
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
    data = call(f"{BASE}/rest/season/listorderbyseq/1")["data"]
    seasons = sorted((int(s["name"]), s["seasonPk"]["sn"]) for s in data
                     if str(s.get("name", "")).isdigit())
    rows = []
    for name, sn in seasons:
        row = {"season": name, "boys_champion": None, "girls_champion": None}
        try:
            sns = finals_stage_sns(sn)  # 每學年查一次，男女組共用（別在迴圈內重打 API）
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
    season_name, season_sn = latest_season()
    stage_sns = finals_stage_sns(season_sn)
    if not stage_sns:
        raise RuntimeError(f"season {season_name}: 總決賽 stage not found（賽季未到決賽）")
    divisions = {}
    for key, label in (("boys", "男子甲級"), ("girls", "女子甲級")):
        if key in stage_sns:
            divisions[key] = rank_division(stage_sns[key], label)
    out = {
        "asof_taipei_date": today,
        "season_label": f"{season_name}學年度",
        "final": True,
        "divisions": divisions,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"hbl-{season_name}-{today}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    champs = "、".join(f"{d['label']} {d['champion']}" for d in divisions.values())
    print(f"✅ HBL {season_name}學年度: {champs} → {path}")


if __name__ == "__main__":
    main()
