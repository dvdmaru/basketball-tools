"""站群自有版位（2026-11-07，Charlie 裁定；規格 CoWork/Charlie/2026-11-07/site-ad-slots/site-ad-slots-spec.md）。

三種版位，只放首頁、文章列表（/articles/）、文章頁；數據頁（/standings/、/tw/、/hbl/、
/nba-cup/、/data/）一律不放、不載版位程式：
  home_hero    首頁主推位（hero 區〔H1＋狀態列〕正下方、戰績儀表板之前；卡片本身不放 H1）
  native_list  列表原生（首頁「最新文章」格的第 3 張；/articles/ 第一個主題區的第 3 張）
  native_end   文末原生（文章頁「延伸閱讀」之後、上下篇導覽之前）

⚠️ 本站站規原本是「100% 靜態、server-rendered、零 client fetch」。Charlie 11/7 裁定「版位例外」：
   內容仍零 client fetch；只有版位會在瀏覽器端讀 twtools.cc/ad-slots.json。
   數據頁的版位禁令由 tests/test_ad_slots.py 釘住。

⚠️ 本站有 CSP（public-basketball/_headers）：connect-src／img-src 已加 https://twtools.cc，
   版位程式才讀得到設定檔。檔期圖片只接受 IMG_HOSTS 裡的主機（跟 CSP img-src 對齊），
   其他主機的圖會被 CSP 擋成破圖，所以程式直接改用文字底圖。要放別家主機的圖，
   _headers 的 img-src 與 IMG_HOSTS 要一起改。

為什麼 HTML 只放預設卡、廣告本身在瀏覽器端換上：
  - 換檔要準時，不能等每日重建；
  - 廣告文字不進 AI 讀到的 HTML，AI 不會把廣告當成本站內容引用。

平常的樣子（Charlie 11/7「版位留在那邊，回到網站正常的樣子，等真的有活動的時候再放內容」）：
  - 沒有當期檔期、或讀不到設定檔 → 版位整個隱藏（HTML 帶 hidden），網站跟沒有版位時一樣；
    首頁「最新文章」照樣 5 篇（第 5 篇帶 data-ad-yield，列表原生真的出現時才讓位）。
  - 有當期檔期 → 顯示。
  - 網址加 ?ad-preview=1 → 預覽：不看檔期時間，設定檔裡的卡片與預設卡全部顯示，且不送 GA。

瀏覽器端邏輯（_JS）站別無關，照 racing 的版本寫；插槽位置、CSS（本站 ember token）、
build 整合與測試依本站地形各自寫（姊妹站禁自動同步）。
"""
import hashlib
import html as html_lib
import pathlib

SITE_KEY = "basketball"                   # ad-slots.json 的 sites 欄位用這個值
CONFIG_URL = "https://twtools.cc/ad-slots.json"
IMG_HOSTS = ["twtools.cc"]                # 與 _headers 的 CSP img-src 對齊

# 預設卡：讀不到設定檔時（只在預覽時）顯示。文字直接取 build-articles.py 的 SISTER_SITES（不另外編文案）。
FALLBACK = {
    "home_hero": ("@baseball — 中職 CPBL＋MLB 深度戰報", "https://baseball.twtools.cc/"),
    "native_list": ("賽車數據誌 — F1 積分榜・台北時間賽曆・各站賽果", "https://racing.twtools.cc/"),
    "native_end": ("賽車數據誌 — F1 積分榜・台北時間賽曆・各站賽果", "https://racing.twtools.cc/"),
}

# 只用本站 v2 token（--surface／--line／--accent／--fg-*／--r-*／--f-*，見 build-articles.py 的
# _BB_TOKEN_BLOCKS 與 alias 區塊），五個主題（含淺色 apricot／maple）自動跟著換色。
AD_CSS = """
.ad-slot{position:relative;display:block;text-decoration:none;color:var(--fg);border:1px solid var(--line);
  border-radius:var(--r-lg);background:var(--surface);overflow:hidden;transition:border-color .18s}
.ad-slot[hidden],[data-ad-yield][hidden]{display:none!important}
.ad-slot:hover,.ad-slot:focus-visible{border-color:var(--accent-line);color:var(--fg)}
.ad-label{position:absolute;top:8px;right:8px;z-index:1;font-family:var(--f-ui);font-size:11px;line-height:1;
  padding:4px 7px;border-radius:4px;background:rgba(0,0,0,.62);color:#fff;letter-spacing:1px}
.ad-media{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;
  background:linear-gradient(135deg,var(--accent-weak),var(--surface-2))}
.ad-media-fb{display:flex;align-items:center;justify-content:center;padding:12px;text-align:center;
  font-family:var(--f-text);font-weight:800;font-size:15px;line-height:1.4;color:var(--fg-soft)}
.ad-t{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
  font-family:var(--f-text);font-size:16px;line-height:1.4;font-weight:700;color:var(--fg);margin:0}
.ad-d{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
  color:var(--fg-mute);font-size:13px;line-height:1.6;margin:4px 0 0}
.ad-cta{color:var(--accent);font-family:var(--f-ui);font-size:13px;font-weight:700;margin-top:6px;display:block}
.ad-body{display:block}
/* 橫式（主推位、文末）：固定高度，換卡不跳版；標籤壓在左側圖上，不擋文字 */
.ad-row{display:flex}
.ad-row .ad-label{left:8px;right:auto}
.ad-row .ad-media{flex:0 0 auto;aspect-ratio:auto;height:100%}
.ad-row .ad-body{min-width:0;flex:1;display:flex;flex-direction:column;justify-content:center}
.ad-hero{height:132px;margin:0 0 4px}
.ad-hero .ad-media{width:251px}
.ad-hero .ad-body{padding:14px 18px}
.ad-end{height:112px;max-width:560px;margin:40px 0 0}
.ad-end .ad-media{width:213px}
.ad-end .ad-body{padding:12px 16px}
@media (max-width:640px){
  .ad-hero{height:120px}
  .ad-hero .ad-media,.ad-end .ad-media{width:120px}
  .ad-row .ad-body{padding:10px 12px}
  .ad-hero .ad-t{font-size:15px}
  .ad-row .ad-d{-webkit-line-clamp:1}
}
/* 列表原生：外觀跟所在清單的文章卡一樣（首頁 .art 16:9；/articles/ .idx-card 圖高 170px） */
.ad-native{display:flex;flex-direction:column}
.ad-native .ad-body{padding:16px 18px 18px;flex:1}
.idx-grid .ad-native .ad-media{aspect-ratio:auto;height:170px}
"""

_JS = r"""(function(){
"use strict";
var CONFIG_URL=%(url)s, SITE=%(site)s, IMG_HOSTS=%(img_hosts)s, RANK={paid:0,house:1,affiliate:2};
var slots=[].slice.call(document.querySelectorAll('.ad-slot[data-ad-slot]'));
if(!slots.length)return;
var PREVIEW=/[?&]ad-preview=1(&|$)/.test(location.search);
function ga(name,s){
  if(PREVIEW||typeof window.gtag!=='function')return;   // 預覽不送 GA，免得灌髒曝光數字
  var p={promotion_id:s.dataset.adId,promotion_name:s.dataset.adName,
         creative_name:s.dataset.adCreative,creative_slot:s.dataset.adSlot};
  p.items=[{item_id:p.promotion_id,item_name:p.promotion_name,promotion_id:p.promotion_id,
            promotion_name:p.promotion_name,creative_name:p.creative_name,creative_slot:p.creative_slot}];
  window.gtag('event',name,p);
}
// 曝光：一半以上進畫面、停留滿 1 秒才算；同一次瀏覽每個版位只算一次。分頁在背景不計時。
function watch(s){
  if(s._adWatched)return; s._adWatched=true;
  s.addEventListener('click',function(){ga('select_promotion',s);});
  if(!('IntersectionObserver' in window))return;
  var t=null, done=false;
  var io=new IntersectionObserver(function(es){
    es.forEach(function(e){
      if(done)return;
      if(e.isIntersecting&&e.intersectionRatio>=0.5&&!document.hidden){
        if(!t)t=setTimeout(function(){done=true;io.disconnect();ga('view_promotion',s);},1000);
      }else if(t){clearTimeout(t);t=null;}
    });
  },{threshold:[0,0.5,1]});
  io.observe(s);
  document.addEventListener('visibilitychange',function(){if(document.hidden&&t){clearTimeout(t);t=null;}});
}
function okUrl(u){try{var x=new URL(u);return x.protocol==='https:'?x:null;}catch(e){return null;}}
// 圖片主機要在 CSP img-src 裡（見 _headers），否則會被擋成破圖 → 改用文字底圖
function okImg(u){var x=okUrl(u);return x&&IMG_HOSTS.indexOf(x.hostname)>=0?x:null;}
function withUtm(x,slot,id){
  if(!x.searchParams.has('utm_source')){
    x.searchParams.set('utm_source',SITE);x.searchParams.set('utm_medium',slot);x.searchParams.set('utm_campaign',id);
  }
  return x.toString();
}
function apply(s,c){
  var x=okUrl(c.url); if(!x)return false;
  var img=c.image?okImg(c.image):null;
  var label=c.tier==='paid'?'贊助':'推廣';
  s.querySelector('.ad-label').textContent=label;
  s.querySelector('.ad-t').textContent=c.title;
  s.querySelector('.ad-d').textContent=c.desc||'';
  var cta=s.querySelector('.ad-cta'); if(cta)cta.textContent=(c.cta||'去看看')+' →';
  var m=s.querySelector('.ad-media');
  if(img){
    var im=document.createElement('img');
    im.className='ad-media';im.alt='';im.loading='lazy';im.src=img.toString();
    m.parentNode.replaceChild(im,m);
  }else{
    m.className='ad-media ad-media-fb';m.textContent=c.media_text||c.title;
  }
  s.href=withUtm(x,s.dataset.adSlot,c.id);
  var ext=x.host!==location.host;
  s.target=ext?'_blank':''; if(!ext)s.removeAttribute('target');
  s.rel=c.tier==='paid'?'sponsored noopener':'noopener';
  s.dataset.adId=c.id;s.dataset.adName=c.title;s.dataset.adCreative=c.creative||c.id;
  return true;
}
function valid(c,now){
  if(!c||typeof c.id!=='string'||typeof c.title!=='string'||!c.title||typeof c.url!=='string')return false;
  if(!(c.tier in RANK))return false;
  if(!Array.isArray(c.sites)||c.sites.indexOf(SITE)<0)return false;
  if(!Array.isArray(c.slots))return false;
  var a=Date.parse(c.start), b=Date.parse(c.end);
  if(isNaN(a)||isNaN(b))return false;
  return PREVIEW||(a<=now&&now<b);                      // 預覽不看檔期時間
}
// 顯示一個版位；列表原生出現時，讓同一格清單的讓位卡隱藏（首頁「最新文章」維持 5 格）
function show(s){
  s.hidden=false;
  var y=document.querySelector('[data-ad-yield="'+s.dataset.adSlot+'"]');
  if(y)y.hidden=true;
  watch(s);
}
function run(cfg){
  var now=Date.now(), used={};
  var list=(cfg&&Array.isArray(cfg.campaigns)?cfg.campaigns:[]).filter(function(c){return valid(c,now);});
  list.sort(function(p,q){return (RANK[p.tier]-RANK[q.tier])||(Date.parse(q.start)-Date.parse(p.start));});
  slots.forEach(function(s){
    var slot=s.dataset.adSlot, shown=false;
    for(var i=0;i<list.length;i++){
      var c=list[i];
      if(c.slots.indexOf(slot)<0||used[c.id])continue;   // 同一則不在同一頁出現兩次
      if(apply(s,c)){used[c.id]=true;shown=true;break;}
    }
    if(shown||PREVIEW)show(s);                         // 沒有檔期就維持隱藏（預覽時顯示預設卡）
  });
}
var done=false;
function fallback(){if(done)return;done=true;if(PREVIEW)slots.forEach(show);}
try{
  var ctl=('AbortController' in window)?new AbortController():null;
  var to=setTimeout(function(){if(ctl)ctl.abort();fallback();},4000);
  fetch(CONFIG_URL,{credentials:'omit',signal:ctl?ctl.signal:undefined})
    .then(function(r){if(!r.ok)throw new Error('http '+r.status);return r.json();})
    .then(function(cfg){clearTimeout(to);if(done)return;done=true;run(cfg);})
    .catch(function(){clearTimeout(to);fallback();});
}catch(e){fallback();}
})();
"""

JS_TEXT = _JS % {"url": '"' + CONFIG_URL + '"', "site": '"' + SITE_KEY + '"',
                 "img_hosts": "[" + ",".join('"' + h + '"' for h in IMG_HOSTS) + "]"}
_JS_BYTES = JS_TEXT.encode("utf-8")
SCRIPT_NAME = f"ad-{hashlib.sha256(_JS_BYTES).hexdigest()[:10]}.js"
SCRIPT_HREF = f"/assets/{SCRIPT_NAME}"


def write_script(pub: pathlib.Path) -> pathlib.Path:
    """把版位程式寫到 <pub>/assets/ad-<hash>.js（內容 hash 當檔名）。只留新版＋前一版兩份，
    防部署切版時舊頁引用 404。

    ⚠️ 只在真正建站時呼叫（build-articles.py 的 _build_sport_site）；頁面 render 函式只拿
    SCRIPT_HREF 組 script 標籤、不寫檔——測試直接呼叫 render 函式時才不會寫進版控目錄。"""
    assets_dir = pathlib.Path(pub) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    fpath = assets_dir / SCRIPT_NAME
    if not fpath.exists() or fpath.read_bytes() != _JS_BYTES:
        fpath.write_bytes(_JS_BYTES)
        others = sorted((p for p in assets_dir.glob("ad-*.js") if p.name != SCRIPT_NAME),
                        key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in others[1:]:
            stale.unlink()
    return fpath


def script_tag() -> str:
    return f'<script src="{SCRIPT_HREF}" defer></script>'


def slot_html(slot: str) -> str:
    """版位外殼＋預設卡，預設隱藏。有當期檔期時由 ad-*.js 換上內容並顯示；預覽模式顯示預設卡。"""
    if slot not in FALLBACK:
        raise ValueError(f"unknown ad slot: {slot}")
    title, url = FALLBACK[slot]
    t = html_lib.escape(title)
    short = html_lib.escape(title.split(" — ")[0])
    fid = f"fallback-{SITE_KEY}-{slot}"
    kind = {"home_hero": "ad-row ad-hero", "native_list": "ad-native", "native_end": "ad-row ad-end"}[slot]
    cta = '<span class="ad-cta">去看看 →</span>' if slot == "home_hero" else ''
    return (f'<a class="ad-slot {kind}" data-ad-slot="{slot}" data-ad-id="{fid}" '
            f'data-ad-name="{t}" data-ad-creative="{fid}" href="{url}" rel="noopener" hidden>'
            f'<span class="ad-label">推廣</span>'
            f'<span class="ad-media ad-media-fb">{short}</span>'
            f'<span class="ad-body"><span class="ad-t">{t}</span>'
            f'<span class="ad-d">姊妹站</span>{cta}</span></a>')


def with_native(cards: list, yield_last: bool = False) -> str:
    """文章卡清單的第 3 格插入列表原生版位；不足 2 張就不放（版位不該比內容多）。
    yield_last=True：最後一張卡帶 data-ad-yield，原生真的出現時讓位，清單總格數不變。
    cards 是已 render 好的卡片 HTML，第一個 `<a class="` 是卡片本身的開頭標籤。"""
    if len(cards) < 2:
        return "".join(cards)
    cards = list(cards)
    if yield_last and len(cards) >= 3:
        cards[-1] = cards[-1].replace('<a class="', '<a data-ad-yield="native_list" class="', 1)
    return "".join(cards[:2]) + slot_html("native_list") + "".join(cards[2:])
