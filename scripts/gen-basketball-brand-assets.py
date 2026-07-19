#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen-basketball-brand-assets.py — 籃球數據誌 站台品牌資產（basketball.twtools.cc 根目錄）

產出（皆寫進 public-basketball/）：
  - og-home.png        2400×1260  首頁/文章列表頁 og:image（補 Meta 標籤分數）
  - apple-touch-icon.png  180×180  iOS 加入主畫面
  - icon-192.png / icon-512.png    PWA manifest 圖示
  - favicon.png        32×32       瀏覽器分頁圖示
  - site.webmanifest               PWA manifest（theme/icons）

全部純文字／幾何，IP 安全（無 logo/球員照/隊徽/聯盟標誌）。
品牌：炭黑 #14100e + 暖白 #f3ece4 + 籃球橘 #ef7d3a（與 baseball navy/金、foootball 森林綠區隔）。
icon 在 512 一次 render，PIL 高品質縮到 192/180/32（保持邊緣銳利）。

用法：python3 scripts/gen-basketball-brand-assets.py
"""
import os
import subprocess
import tempfile

from PIL import Image

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    raise SystemExit("Chrome not found")


def shot(html: str, out: str, w: int, h: int, scale: int = 2):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        tmp = f.name
    subprocess.run(
        [chrome(), "--headless", "--disable-gpu", "--hide-scrollbars",
         f"--force-device-scale-factor={scale}", f"--window-size={w},{h}",
         "--default-background-color=00000000",
         f"--screenshot={out}", f"file://{tmp}"],
        check=True, capture_output=True)
    os.unlink(tmp)
    print(f"✓ {out}")


# ---------- og-home.png (2400×1260, render 1200×630 @2x) ----------
OG_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1200px;height:630px;overflow:hidden}
body{font-family:"PingFang TC","Heiti TC","Noto Sans CJK TC",sans-serif;
  background:radial-gradient(1100px 720px at 80% -12%, rgba(239,125,58,.20), transparent 60%),
    linear-gradient(135deg,#241d19 0%,#14100e 52%,#0a0807 100%);
  color:#f3ece4;position:relative}
.frame{position:absolute;inset:28px;border:1.5px solid rgba(239,125,58,.40);border-radius:10px}
.seam{position:absolute;width:1500px;height:1500px;border:3px solid rgba(239,125,58,.22);
  border-radius:50%;right:-820px;top:-340px}
.seam2{position:absolute;width:1500px;height:1500px;border:3px solid rgba(239,125,58,.14);
  border-radius:50%;right:-760px;top:-280px}
.pad{position:absolute;inset:0;padding:78px 82px 132px;display:flex;flex-direction:column;height:100%}
.top{display:flex;align-items:center;gap:18px}
.mark{font-family:"Arial Black","PingFang TC",sans-serif;font-weight:900;letter-spacing:1px;
  font-size:32px;color:#ef7d3a}
.dot{width:7px;height:7px;border-radius:50%;background:#d9a04c;opacity:.9}
.mk-tag{font-size:18px;color:rgba(243,236,228,.62);letter-spacing:2px;font-weight:600}
h1{font-size:96px;line-height:1.1;font-weight:900;margin:auto 0 0;letter-spacing:1px;
  color:#fff;text-shadow:0 2px 30px rgba(0,0,0,.40)}
.bar{width:96px;height:5px;background:linear-gradient(90deg,#ef7d3a,#d9a04c);
  border-radius:4px;margin:28px 0 22px}
.sub{font-size:30px;font-weight:600;color:rgba(243,236,228,.84);letter-spacing:1px}
.foot{position:absolute;left:82px;bottom:62px;font-size:21px;letter-spacing:2px;
  color:rgba(239,125,58,.74);font-weight:600}
</style></head><body>
<div class="seam"></div><div class="seam2"></div><div class="frame"></div>
<div class="pad">
  <div class="top"><span class="mark">@BASKETBALL</span><span class="dot"></span>
    <span class="mk-tag">NBA + 台灣職籃 + HBL · 數據深度</span></div>
  <h1>NBA × 台灣籃球，<br>用數據看門道。</h1>
  <div class="bar"></div>
  <div class="sub">東西區排名 · TPBL／PLG 戰績 · HBL 四強　|　繁體中文 · 台北時間</div>
</div>
<div class="foot">basketball.twtools.cc</div>
</body></html>"""


# ---------- icon (render 512×512 @1x, PIL downscale) ----------
ICON_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:512px;height:512px;overflow:hidden}
body{font-family:"Arial Black","PingFang TC",sans-serif;
  background:radial-gradient(360px 360px at 70% 18%, rgba(239,125,58,.28), transparent 62%),
    linear-gradient(135deg,#241d19 0%,#14100e 55%,#0a0807 100%);
  position:relative;display:flex;align-items:center;justify-content:center}
.ring{position:absolute;inset:44px;border:6px solid rgba(239,125,58,.55);border-radius:50%}
.seam-v{position:absolute;left:50%;top:44px;bottom:44px;width:0;
  border-left:5px solid rgba(217,160,76,.5);transform:translateX(-50%)}
.seam-h{position:absolute;top:50%;left:44px;right:44px;height:0;
  border-top:5px solid rgba(217,160,76,.5);transform:translateY(-50%)}
.b{font-size:300px;font-weight:900;color:#ef7d3a;line-height:1;
  text-shadow:0 6px 30px rgba(0,0,0,.45);position:relative;margin-top:-8px}
</style></head><body>
<div class="ring"></div><div class="seam-v"></div><div class="seam-h"></div>
<div class="b">B</div>
</body></html>"""

MANIFEST = """{
  "name": "籃球數據誌 — NBA + 台灣職籃 + HBL 數據深度",
  "short_name": "籃球數據誌",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#14100e",
  "theme_color": "#14100e",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }
  ]
}
"""


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    pub = os.path.join(root, "public-basketball")
    os.makedirs(pub, exist_ok=True)

    # og-home: 1200×630 @2x = 2400×1260
    shot(OG_HTML, os.path.join(pub, "og-home.png"), 1200, 630, scale=2)

    # icon master at 512, then PIL downscale (high quality)
    master = os.path.join(pub, "icon-512.png")
    shot(ICON_HTML, master, 512, 512, scale=1)
    img = Image.open(master).convert("RGBA")
    if img.size != (512, 512):
        img = img.resize((512, 512), Image.LANCZOS)
        img.save(master)
    for size, name in [(192, "icon-192.png"), (180, "apple-touch-icon.png"), (32, "favicon.png")]:
        img.resize((size, size), Image.LANCZOS).save(os.path.join(pub, name))
        print(f"✓ {os.path.join(pub, name)}")

    with open(os.path.join(pub, "site.webmanifest"), "w", encoding="utf-8") as f:
        f.write(MANIFEST)
    print(f"✓ {os.path.join(pub, 'site.webmanifest')}")


if __name__ == "__main__":
    main()
