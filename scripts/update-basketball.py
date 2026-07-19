#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""update-basketball.py — basketball.twtools.cc 自動重建編排器（dashboard living-page）。

把「抓資料 → 重生頁面 →（可選）部署」串成一個指令，供 GH Actions 跑。
休賽季（2026-07 現況）：各聯盟賽季已結束，fetch 步驟為 fail-soft——抓不到就沿用
repo 內既有 leagues/*.json 快照，頁面 as-of 誠實呈現；開季後恢復每日新鮮。

跑序鐵則（sitemap 覆寫坑，沿用 baseball-tools）：
  1. 抓資料：NBA standings（ESPN）＋台灣職籃快照＋HBL 快照（各自 fail-soft）
  2. build-articles：首頁 dashboard 讀 leagues/*.json + 整個覆寫 sitemap
  3. 各 generator re-merge 自己的 sitemap path（standings / tw / hbl / data-hub）
  4.（可選）wrangler deploy

部署需非互動憑證：設環境變數 CLOUDFLARE_API_TOKEN。
未設 token 且未加 --deploy 時只重建、不部署（手動再 `npx wrangler deploy -c wrangler-basketball.jsonc`）。

用法：
  python3 scripts/update-basketball.py                 # 重建，不部署
  python3 scripts/update-basketball.py --deploy        # 重建 + wrangler deploy
  python3 scripts/update-basketball.py --skip-fetch    # 只重生頁面（用既有快照）
"""
import argparse
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable  # 子腳本一律用同一個 interpreter

FAILED = []  # 失敗步驟收集：照樣跑完全部（一步壞不全停），但結尾 exit 1 讓 CI 誠實變紅


def run(args, label, soft=False):
    """soft=True 的步驟失敗只警告不進 FAILED（fetch 類：斷源時沿用既有快照，
    頁面重生照走；build/deploy 類必須 hard）。"""
    print(f"\n▶ {label}: {' '.join(str(a) for a in args)}", flush=True)
    r = subprocess.run(args, cwd=str(ROOT))
    if r.returncode != 0:
        if soft:
            print(f"  ⚠️  {label} exit={r.returncode}（fail-soft：沿用既有快照續跑）", flush=True)
        else:
            print(f"  ⚠️  {label} exit={r.returncode}（繼續跑完其餘步驟；結尾會以非零狀態離開）", flush=True)
            FAILED.append(label)
    return r.returncode


def script(name, *extra):
    return [PY, str(ROOT / "scripts" / name), *extra]


BASE_URL = "https://basketball.twtools.cc"


def _indexnow_changed_urls():
    """本次 build 實際「新增/變動」的頁面 URL（IndexNow 協定要求只推變動，別每次全站掃）。
    偵測靠 git：public-basketball/ 產物有 commit、CI checkout 乾淨 → build 後的髒檔＝本次變動。
    回 (all_urls, new_urls)——new_urls 是 untracked 新頁，部署前 404，是「真 live」的 poll 訊號。"""
    # --untracked-files=all：預設會把未追蹤「目錄」折疊成 `?? dir/` 一行，
    # 新文章的 index.html 就不會出現、IndexNow 整批漏送（2026-07-19 外部審查實證）
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all",
                          "--", "public-basketball"],
                         cwd=str(ROOT), capture_output=True, text=True).stdout
    urls, new = set(), []
    for line in out.splitlines():
        status, path = line[:2], line[3:].strip().strip('"')
        u = None
        if path.endswith("index.html"):
            rel = path[len("public-basketball/"):-len("index.html")]
            u = f"{BASE_URL}/{rel}"
        elif path.endswith("llms.txt"):
            u = f"{BASE_URL}/llms.txt"
        if u:
            urls.add(u)
            if status == "??":
                new.append(u)
    return sorted(urls), new


def indexnow_after_deploy():
    """deploy 成功後把本次變動頁 ping 給 IndexNow（api.indexnow.org → Bing 系引擎，
    Bing 索引另餵 ChatGPT search / Copilot；Google 不吃此協定，sitemap 照舊）。
    best-effort：任何失敗只警告、不進 FAILED、不擋 pipeline。"""
    try:
        urls, new = _indexnow_changed_urls()
        if not urls:
            print("\n⏭  IndexNow：本次 build 無頁面變動，不 ping", flush=True)
            return
        if new:
            # 只有「新增頁」才是有效的 live 訊號（部署前 404 → 部署後 200）；
            # 既有頁永遠 200 不能當訊號。帶瀏覽器樣 UA：GitHub runner + python-urllib
            # 預設 UA 會被 CF 邊緣擋（baseball-tools 2026-07-02 實證）。
            probe, last = new[0], "?"
            for i in range(12):
                try:
                    req = urllib.request.Request(probe, headers={
                        "User-Agent": "Mozilla/5.0 (compatible; basketball-tools-deploy-probe/1.0)"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        last = str(r.status)
                        if r.status == 200:
                            print(f"\n🌐 IndexNow：新頁 {probe} 已 live（第 {i + 1} 次探測）", flush=True)
                            break
                except urllib.error.HTTPError as e:
                    last = str(e.code)
                except Exception as e:
                    last = type(e).__name__
                time.sleep(5)
            else:
                print(f"\n⚠️  IndexNow：新頁 {probe} 探測未見 200（最後狀態 {last}），仍續行 ping", flush=True)
        else:
            print("\n🌐 IndexNow：本次無新增頁（既有頁永遠 200 非部署訊號）；"
                  "wrangler 已回報部署成功，直接 ping", flush=True)
        r = subprocess.run(["node", str(ROOT / "scripts" / "indexnow-ping.mjs"), *urls],
                           cwd=str(ROOT))
        if r.returncode != 0:
            print("⚠️  IndexNow ping 失敗（best-effort，不擋 pipeline）", flush=True)
    except Exception as e:
        print(f"⚠️  IndexNow 步驟例外（忽略）：{e}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true", help="重建後跑 wrangler deploy")
    ap.add_argument("--skip-fetch", action="store_true", help="跳過抓資料，只用既有快照重生頁面")
    args = ap.parse_args()

    print(f"🏀 update-basketball · deploy={args.deploy} · skip_fetch={args.skip_fetch}")

    # 1. 抓資料（全部 fail-soft：斷源時沿用 repo 內既有快照；快照凍結＝頁面 as-of 誠實標示）
    if not args.skip_fetch:
        run(script("fetch-nba.py"), "fetch NBA (ESPN)", soft=True)
        run(script("fetch-tw-hoops.py"), "fetch TW hoops (TPBL/PLG)", soft=True)
        run(script("fetch-hbl.py"), "fetch HBL", soft=True)

    # 2. 首頁 dashboard + base sitemap（必須在各 generator 之前；會整個覆寫 sitemap）
    run(script("build-articles.py"), "build-articles (homepage + sitemap)")

    # 3. 各 generator re-merge 自己的 sitemap path
    run(script("gen-nba-standings.py"), "gen NBA standings page")
    run(script("gen-tw-standings.py"), "gen TW hoops page")
    run(script("gen-hbl-page.py"), "gen HBL page")
    run(script("gen-basketball-data-hub.py"), "gen data hub")

    # 4. 部署前 hard gate：建置/生成類有任何失敗 → 禁止部署，線上維持上一版。
    #    （build 步驟照樣跑完收集診斷；擋的只有「把壞產物推上線」這一步。
    #      fetch 類是 fail-soft、不進 FAILED，所以斷源不會把整站凍在這裡。）
    if FAILED:
        print(f"\n⛔ {len(FAILED)} 個建置步驟失敗（{'、'.join(FAILED)}）→ 禁止部署，線上維持上一版",
              flush=True)
        sys.exit(1)

    # 5.（可選）部署；成功後把本次變動頁 ping 給 IndexNow（Bing 系收錄）
    if args.deploy or os.environ.get("CLOUDFLARE_API_TOKEN"):
        # pin wrangler 版本：CI 每次跑此步都帶著 CLOUDFLARE_API_TOKEN，
        # 不釘版本 = 供應鏈若中毒可直接偷 token 改寫線上 Worker。
        rc = run(["npx", "wrangler@4.108.0", "deploy", "-c", "wrangler-basketball.jsonc"], "wrangler deploy")
        if rc == 0:
            indexnow_after_deploy()
    else:
        print("\n⏭  未 --deploy 且無 CLOUDFLARE_API_TOKEN → 只重建未部署。"
              "手動部署：npx wrangler deploy -c wrangler-basketball.jsonc")

    if FAILED:
        print(f"\n❌ update-basketball 完成但 {len(FAILED)} 步失敗：{'、'.join(FAILED)}", flush=True)
        sys.exit(1)
    print("\n✅ update-basketball done")


if __name__ == "__main__":
    main()
