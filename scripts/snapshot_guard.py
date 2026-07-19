#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""snapshot_guard.py — 快照寫入前的健康檢查（last-known-good 保護）。

問題：抓取腳本拿到上游回應就直接覆寫快照檔。上游維護中／改版／被擋而回空陣列時，
「空」會被當成正常結果寫進去，蓋掉原本健康的資料，下一步就生出空白頁面上線——
而且好資料當場被覆蓋，要救得翻 git history。

策略：新資料明顯異常（空、或相對既有快照驟減）就拒寫、保留 last-known-good，
呼叫端以非零狀態離開。編排器把 fetch 類步驟設為 fail-soft，於是頁面沿用舊快照重生，
而頁面本來就會渲染快照自帶的日期 → 讀者看到的是誠實的舊日期，不是空白或假新鮮。

⚠️ 只擋「不可能合法為空」的資料。像 MLB 單日賽程表這種**真的可能是休賽日**的，
不要用筆數守門，否則休兵日會被誤判成故障。
"""
import glob
import json
import pathlib


def _load(path):
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def check(new_obj, old_obj, counter, *, min_count=1, max_drop=0.5):
    """回 (ok, reason)。old_obj 為 None（首次抓取）時只驗 min_count。"""
    new_n = counter(new_obj) if new_obj is not None else 0
    old_n = counter(old_obj) if old_obj is not None else 0
    if new_n < min_count:
        if old_n >= min_count:
            return False, f"新資料僅 {new_n} 筆（既有快照 {old_n} 筆）——上游疑似異常"
        return False, f"新資料僅 {new_n} 筆，且無既有快照可沿用"
    if old_n and new_n < old_n * (1 - max_drop):
        return False, f"筆數驟減 {old_n} → {new_n}（跌破 {int(max_drop * 100)}%）"
    return True, ""


def newest(pattern: str):
    """日期序列快照的「目前生效那份」——生成端一律 sorted(glob(...))[-1]，這裡對齊同一語意。"""
    hits = sorted(pathlib.Path(p) for p in glob.glob(pattern))
    return hits[-1] if hits else None


def guarded_write(path: pathlib.Path, data, counter, *, label="snapshot", baseline=None,
                  min_count=1, max_drop=0.5, indent=2) -> bool:
    """驗過才寫。回 True=已寫入；False=拒寫並保留既有快照（呼叫端應以非零狀態離開）。

    baseline＝拿來比對的「目前生效快照」，預設是 path 自己（覆寫同一檔的情況）。
    日期序列快照（tw-hoops-<date>.json 這種每天開新檔）必須傳 newest(pattern)：
    新檔本身永遠不存在、沒有前一份可比，若不指定 baseline，寫進一份空的就會因為
    檔名排序在後而 shadow 掉昨天的好資料——空值洗掉好資料的另一種長相。
    """
    ok, reason = check(data, _load(baseline if baseline is not None else path),
                       counter, min_count=min_count, max_drop=max_drop)
    if not ok:
        print(f"   🛑 {label}：{reason} → 拒絕覆寫，保留既有快照", flush=True)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    return True
