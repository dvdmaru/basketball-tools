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


def rank_division(division_id: int, label: str) -> dict:
    games = [g for g in call(f"{BASE}/api/division-matches/{division_id}")
             if g.get("status") == "COMPLETED" and g.get("homeScore") is not None
             and g.get("awayScore") is not None]
    if not games:
        raise RuntimeError(f"division {division_id}: no completed games")
    games.sort(key=lambda g: g.get("matchedAt", ""))

    def w_l(g):
        home, away = g["homeSquad"]["name"], g["awaySquad"]["name"]
        return (home, away) if g["homeScore"] > g["awayScore"] else (away, home)

    days = sorted({g["matchedAt"][:10] for g in games})
    semi_games = [g for g in games if g["matchedAt"][:10] == days[0]] if len(days) > 1 else games[:-2]
    final_day = [g for g in games if g not in semi_games]
    semi_winners = {w_l(g)[0] for g in semi_games}

    champ_game = third_game = None
    for g in final_day:
        pair = {g["homeSquad"]["name"], g["awaySquad"]["name"]}
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
        ws, ls = max(g["homeScore"], g["awayScore"]), min(g["homeScore"], g["awayScore"])
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
    season_name, season = latest_season()
    stage_sns = finals_stage_sns(season)
    if not stage_sns:
        print(f"⏭️ HBL {season_name}學年度：尚未建立甲級總決賽 division，沿用既有終局快照")
        print("📋 來源狀態｜HBL｜成功但未更新｜新版 API 已有學年度，尚無可發布的總決賽賽果")
        return
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
