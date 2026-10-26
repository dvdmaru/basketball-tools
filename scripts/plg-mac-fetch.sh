#!/bin/bash
# plg-mac-fetch.sh — 在 Charlie 的 Mac 上抓 PLG 官網戰績，寫進 GitHub Actions 變數給每日工作流用。
#
# 為什麼：pleagueofficial.com 前面是 Cloudflare，GitHub runner（資料中心 IP）拿到的是錯誤頁；
# 住宅 IP 抓得到。不闖 anti-bot、不提交資料檔、不推 main——只把「同一支抓取器在 Mac 上的結果」
# 放進 repo 的 Actions 變數 PLG_STANDINGS_OVERRIDE（repo settings → variables，48KB 上限，實際約 1KB）。
# CI 端（fetch-tw-hoops.py）只在自己抓 PLG 失敗、且變數內容是同賽季兩天內時才採用。
#
# 排程：launchd 每天 11:30（台北），早於 CI 12:00 cron；plist 見 ops/launchd/。
# 手動跑：bash scripts/plg-mac-fetch.sh
# 需要：gh 已登入（gh auth status）、Framework Python 3.13（或任一能跑 fetch-tw-hoops.py 的 python3）。
set -u
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PLG_PY:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3}"
GH="${PLG_GH:-/opt/homebrew/bin/gh}"
GH_REPO="dvdmaru/basketball-tools"
VAR_NAME="PLG_STANDINGS_OVERRIDE"
LOG="${HOME}/Library/Logs/basketball-plg-fetch.log"
TMP="$(mktemp -t plg-override)"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG" >&2; }

[ -x "$PY" ] || PY="$(command -v python3)"
if [ ! -x "$GH" ]; then GH="$(command -v gh || true)"; fi
if [ -z "$GH" ] || [ ! -x "$GH" ]; then log "FAIL gh 不在（launchd 環境沒有 PATH，請設 PLG_GH）"; exit 2; fi

if ! "$PY" "$REPO_DIR/scripts/fetch-tw-hoops.py" --plg-only > "$TMP" 2>>"$LOG"; then
  log "FAIL fetch-tw-hoops.py --plg-only 失敗（見上方 stderr）；變數維持上次值"
  rm -f "$TMP"; exit 1
fi
ROWS="$("$PY" -c 'import json,sys;d=json.load(open(sys.argv[1]));print(len(d["league"]["standings"]))' "$TMP" 2>/dev/null || echo 0)"
if [ "$ROWS" -lt 3 ]; then
  log "FAIL PLG 只解析到 ${ROWS} 列（<3）→ 不覆寫變數（可能是官網改版或本機也被擋）"
  rm -f "$TMP"; exit 1
fi
if "$GH" variable set "$VAR_NAME" --repo "$GH_REPO" --body-file "$TMP" >>"$LOG" 2>&1; then
  log "OK ${VAR_NAME} 已更新：${ROWS} 列（$("$PY" -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["season"],d["asof_taipei_date"])' "$TMP")）"
  rm -f "$TMP"; exit 0
fi
log "FAIL gh variable set 失敗（gh auth status？）"
rm -f "$TMP"; exit 1
