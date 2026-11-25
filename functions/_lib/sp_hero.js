// /spreadsheet hero (owner, 25 Nov 2026: "for /spreadsheet i think that this + this will be a much better design"): the
// search-first hero of lab concept A on top of the app's own "All Finds" section. functions/_middleware.js puts it in place
// of the homepage hero's content (server-rendered, so it shows before any script and moves nothing), adds SP_CSS after
// <title> and SP_JS after the search script.
// The form keeps the homepage hero's ids (#v9-hero-search, #v9-q), so the app's own search drives it: the suggestion panel
// (pcs.js), Enter or the arrow putting the query into the All Finds search and scrolling there (PCS.commit), a brand or
// category from the panel applying that filter and a find opening in the app's product view.

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fold = s => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/['’`]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
// plain words people search, shown as a plural label (the search itself keeps what they typed)
const NOUN = { watch: "Watches", jacket: "Jackets", hoodie: "Hoodies", sneaker: "Sneakers", shoe: "Shoes", belt: "Belts", bag: "Bags",
  cap: "Caps", wallet: "Wallets", shirt: "Shirts", tee: "Tees", jean: "Jeans", chain: "Chains", ring: "Rings", sunglass: "Sunglasses" };
const FALLBACK = ["Supreme", "Moncler", "Ralph Lauren", "Burberry", "Arc'teryx", "Dior", "Jeans", "Nike"];

// The week's top searches (data/dashboard.json search.top, the same list the search panel's Popular chips use) as chips:
// a query that is a brand, or starts one ("arc"), shows and searches the brand's name; a plain word gets a plural label.
export function trendItems(queries, brands) {
  const out = [], seen = new Set();
  const list = (queries && queries.length >= 4 ? queries : FALLBACK);
  for (const raw of list) {
    const q = String(raw || "").trim(), f = fold(q);
    if (!f || seen.has(f)) continue;
    let label = brands.find(b => fold(b) === f) || "";
    if (!label && f.length >= 3 && !f.includes(" ")) label = brands.find(b => fold(b).startsWith(f)) || "";
    const term = label || q;
    if (!label) label = NOUN[f] || q.charAt(0).toUpperCase() + q.slice(1);
    const k = fold(term); if (seen.has(k)) continue;
    seen.add(f); seen.add(k);
    out.push({ q: term, label });
    if (out.length >= 10) break;
  }
  return out;
}

const AGENT_STACK = [["mycnbox", "MyCNBox"], ["kakobuy", "KakoBuy", "?v=2"], ["oopbuy", "Oopbuy"], ["litbuy", "Litbuy"], ["joyagoo", "Joyagoo"]];
const TREND_SVG = '<svg class="spx-ti" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M3 17l6-6 4 4 8-8"/><path d="M14.5 7H21v6.5"/></svg>';
const PLAY_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M7 4.8v14.4L19 12z"/></svg>';
const ic = (id, cls) => `<svg class="ic ${cls}" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><use href="#${id}"/></svg>`;

// On phones a tap on the field opens the app's search sheet, which closes with history.back(); the browser then puts the page
// back where the sheet opened, which can cancel the scroll to All Finds that the search started (seen on the homepage too).
// A search made in the sheet (the app's query or filters changed) ends at All Finds. Registered here, before the search
// script, because that script stops the sheet's own popstate from reaching listeners added after it.
const SHEET_FIX = `<script>(function(){try{var w=window,d=document,sig=null,at=0;
function cur(){try{return[state.q||"",JSON.stringify(state.brand),JSON.stringify(state.cats)].join("|");}catch(e){return null;}}
d.addEventListener("click",function(e){var t=e.target;if(t&&t.id==="v9-q"&&(w.innerWidth<768||(w.matchMedia&&matchMedia("(pointer: coarse)").matches&&w.innerWidth<1024))){sig=cur();at=Date.now();}},true);
w.addEventListener("popstate",function(){var s=sig;sig=null;if(s===null||Date.now()-at>6e5)return;var n=cur();if(n===null||n===s)return;
setTimeout(function(){var el=d.getElementById("v9-all");if(el)try{el.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});}catch(x){}},0);},true);
}catch(e){}})();</script>`;

export function spHero({ finds, qc, agents, built, trend }) {
  const chips = trend.map(t => `<a class="spx-chip" href="/spreadsheet?q=${encodeURIComponent(t.q)}" data-q="${esc(t.q)}">${esc(t.label)}</a>`).join("");
  const stack = AGENT_STACK.map(a => `<img src="/img/agents/${a[0]}.webp${a[2] || ""}" alt="" width="24" height="24" decoding="async">`).join("");
  return `<div class="spx">
<h1 class="spx-h1" id="v9-hero-title">Search ${esc(finds)} finds</h1>
<form class="spx-form" id="v9-hero-search" action="/spreadsheet" method="get" role="search">
${ic("i-search", "spx-sic")}
<input id="v9-q" name="q" type="search" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" enterkeyhint="search" placeholder="Try Moncler or Jordan 4" aria-label="Search ${esc(finds)} finds">
<kbd class="spx-kbd" aria-hidden="true">/</kbd>
<button type="submit" class="spx-go" aria-label="Search">${ic("i-arrow-right", "")}</button>
</form>
${SHEET_FIX}
<div class="spx-trend" id="spx-trend" role="group" aria-label="Trending searches"><span class="spx-tl">${TREND_SVG}Trending</span>${chips}</div>
<div class="spx-proof">
<p class="spx-trust"><span class="spx-ta"><span class="spx-stack" aria-hidden="true">${stack}</span><span>Buy in <b>${agents}</b> agents</span></span><span class="spx-sep spx-s1" aria-hidden="true">·</span><span><b>${esc(qc)}</b> with <span class="spx-dk">buyer </span>QC photos</span><span class="spx-sep" aria-hidden="true">·</span><span>Links checked weekly</span></p>
<a class="spx-video" id="spx-video" href="/how-to-order"><span class="spx-play" aria-hidden="true">${PLAY_SVG}</span><span class="spx-vt"><span>New to buying from China?</span> <b>Watch the 56s video</b></span></a>
</div>
</div>`;
}

// Styles: the app's own tokens (Inter, --ground, --surface, --ink ...), so light, dark and "system" follow the app.
// The blue dot, focus halo and soft glow are lab concept A's (the owner's screenshot).
export const SP_CSS = `<style id="pc-sp-css">
html[data-sp]{--spx-dot:#0066CC;--spx-halo:rgba(0,102,204,.16);--spx-glow:rgba(0,102,204,.055);--spx-fsh:0 1px 2px rgba(0,0,0,.04),0 12px 32px -16px rgba(0,0,0,.2);--spx-sep:#B4B4B4;--spx-pop:0 30px 70px -26px rgba(0,0,0,.3),0 2px 8px rgba(0,0,0,.05)}
@media (prefers-color-scheme:dark){html[data-sp]:not([data-theme="light"]){--spx-dot:#8EA6DC;--spx-halo:rgba(142,166,220,.22);--spx-glow:rgba(142,166,220,.08);--spx-fsh:0 12px 32px -18px rgba(0,0,0,.7);--spx-sep:#4D4D4D;--spx-pop:0 30px 80px -24px rgba(0,0,0,.85)}}
html[data-sp][data-theme="dark"]{--spx-dot:#8EA6DC;--spx-halo:rgba(142,166,220,.22);--spx-glow:rgba(142,166,220,.08);--spx-fsh:0 12px 32px -18px rgba(0,0,0,.7);--spx-sep:#4D4D4D;--spx-pop:0 30px 80px -24px rgba(0,0,0,.85)}
html[data-sp] .hero::before{content:"";position:absolute;left:0;right:0;top:-150px;height:560px;background:radial-gradient(min(600px,75vw) 270px at 50% 50%,var(--spx-glow),transparent);pointer-events:none}
.spx{position:relative;box-sizing:border-box;max-width:var(--_maxw,1280px);margin:0 auto;padding:26px var(--_gut,24px) 6px;text-align:center;font-family:var(--f-body);color:var(--ink)}
@media (min-width:768px){.spx{padding-top:52px;padding-bottom:10px}}
.spx-sep{margin:0 .5em;color:var(--spx-sep)}
html[data-sp] .hero h1.spx-h1{margin:0 auto!important;max-width:15ch;padding-bottom:.04em;font:600 clamp(34px,2.6vw + 24px,64px)/1.05 var(--f-disp)!important;letter-spacing:-.04em!important;text-wrap:balance;color:var(--ink);background:linear-gradient(180deg,var(--ink) 40%,var(--ink-2));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
html[data-sp] .hero h1.spx-h1::selection{-webkit-text-fill-color:var(--ink)}
@media (forced-colors:active){html[data-sp] .hero h1.spx-h1{background:none;-webkit-text-fill-color:CanvasText}}
.spx-form{position:relative;display:block;width:100%;max-width:720px;margin:16px auto 0}
@media (min-width:768px){.spx-form{margin-top:26px}}
.spx-form #v9-q{box-sizing:border-box;display:block;width:100%;height:56px;margin:0;padding:0 62px 0 50px;border:1px solid var(--input-line);border-radius:999px;background:var(--surface);color:var(--ink);font:500 17px/1.2 var(--f-body);letter-spacing:-.005em;box-shadow:var(--spx-fsh);outline:none;-webkit-appearance:none;appearance:none;transition:border-color var(--dur-1,120ms) linear,box-shadow .2s ease}
@media (min-width:768px){.spx-form #v9-q{height:62px;padding:0 112px 0 56px;font-size:18px}}
.spx-form #v9-q::placeholder{color:var(--muted);opacity:1;font-weight:400}
.spx-form #v9-q::-webkit-search-cancel-button,.spx-form #v9-q::-webkit-search-decoration{-webkit-appearance:none;appearance:none}
.spx-form #v9-q:focus{border-color:var(--spx-dot);box-shadow:0 0 0 4px var(--spx-halo),var(--spx-fsh)}
.spx-sic{position:absolute;left:19px;top:50%;width:20px;height:20px;margin-top:-10px;color:var(--muted);pointer-events:none}
@media (min-width:768px){.spx-sic{left:23px}}
.spx-kbd{display:none;position:absolute;right:66px;top:50%;min-width:26px;height:26px;margin-top:-13px;padding:0 7px;box-sizing:border-box;border:1px solid var(--line-2);border-radius:7px;color:var(--muted);font:500 13px/24px var(--f-body);text-align:center;pointer-events:none}
@media (hover:hover) and (pointer:fine) and (min-width:768px){.spx-form #v9-q:placeholder-shown:not(:focus)~.spx-kbd{display:block}}
.spx-go{position:absolute;right:5px;top:50%;width:44px;height:44px;margin-top:-22px;padding:0;border:0;border-radius:50%;background:var(--fill);color:var(--fill-ink);display:grid;place-items:center;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:transform var(--dur-1,120ms) var(--ease-out,ease)}
@media (min-width:768px){.spx-go{width:50px;height:50px;margin-top:-25px;right:6px}}
.spx-go .ic{width:20px;height:20px}
.spx-go:active{transform:scale(.96)}
.spx-trend{display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:8px;max-width:900px;margin:12px auto 0}
@media (min-width:768px){.spx-trend{margin-top:16px}.spx-trend .spx-chip:nth-of-type(n+9){display:none}}
.spx-tl{display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 4px 0 2px;color:var(--muted);font:500 14px/1 var(--f-body);white-space:nowrap}
.spx-ti{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.spx-chip{position:relative;display:inline-flex;align-items:center;flex:none;height:36px;padding:0 15px;box-sizing:border-box;border:1px solid var(--line-2);border-radius:999px;background:var(--surface);color:var(--ink-2)!important;font:500 14px/1 var(--f-body);text-decoration:none!important;white-space:nowrap;-webkit-tap-highlight-color:transparent;transition:background-color var(--dur-1,120ms) linear,border-color var(--dur-1,120ms) linear,transform var(--dur-1,120ms) var(--ease-out,ease)}
.spx-chip::after{content:"";position:absolute;inset:-4px -2px}
.spx-chip:active{transform:scale(.96)}
@media (hover:hover){.spx-chip:hover{background:var(--surface-2);border-color:var(--input-line);color:var(--ink)!important}}
@media (max-width:767px){.spx-trend{flex-wrap:nowrap;justify-content:flex-start;overflow-x:auto;margin-left:calc(-1*var(--_gut,16px));margin-right:calc(-1*var(--_gut,16px));padding:4px var(--_gut,16px);scrollbar-width:none;-webkit-mask:linear-gradient(90deg,#000 calc(100% - 36px),transparent);mask:linear-gradient(90deg,#000 calc(100% - 36px),transparent)}.spx-trend::-webkit-scrollbar{display:none}}
.spx-proof{display:flex;flex-direction:column;align-items:center;gap:12px;margin-top:14px}
@media (min-width:768px){.spx-proof{margin-top:20px}}
@media (min-width:1180px){.spx-proof{flex-direction:row;justify-content:center;gap:28px}}
.spx-trust{display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:6px 9px;margin:0;color:var(--muted);font:400 13.5px/1.35 var(--f-body)}
@media (min-width:768px){.spx-trust{font-size:14px}}
.spx-trust b{font-weight:600;color:var(--ink-2)}
.spx-trust .spx-sep{margin:0}
.spx-ta{display:inline-flex;align-items:center;gap:8px}
.spx-stack{display:inline-flex}
.spx-stack img{display:block;width:24px;height:24px;border-radius:50%;background:#fff;box-shadow:0 0 0 2px var(--ground);object-fit:cover}
.spx-stack img+img{margin-left:-6px}
@media (max-width:599px){.spx-dk{display:none}.spx-ta{flex-basis:100%;justify-content:center}.spx-s1{display:none}}
.spx-video{display:inline-flex;align-items:center;gap:11px;min-height:44px;padding:5px 18px 5px 5px;box-sizing:border-box;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--ink-2)!important;font:400 14px/1.25 var(--f-body);text-align:left;text-decoration:none!important;-webkit-tap-highlight-color:transparent;transition:border-color var(--dur-1,120ms) linear,transform var(--dur-1,120ms) var(--ease-out,ease)}
@media (min-width:768px){.spx-video{font-size:14.5px}}
.spx-video b{font-weight:600;color:var(--ink)}
.spx-video:active{transform:scale(.98)}
@media (hover:hover){.spx-video:hover{border-color:var(--input-line)}}
.spx-play{flex:none;width:34px;height:34px;border-radius:50%;background:var(--fill);color:var(--fill-ink);display:grid;place-items:center}
.spx-play svg{width:13px;height:13px;margin-left:2px;fill:currentColor}
@media (max-width:599px){.spx-video{border-radius:18px;padding:6px 18px 6px 6px}.spx-vt{display:flex;flex-direction:column;gap:1px}}
html[data-sp] .v9-all-head{padding-top:26px}
@media (prefers-reduced-motion:reduce){.spx-chip,.spx-go,.spx-video{transition:none}.spx-chip:active,.spx-go:active,.spx-video:active{transform:none}}
/* the suggestion panel under this hero field: lab concept A's rounder, roomier look */
html[data-sp] .pcs-panel.pcs-float{padding:8px;border-radius:24px;box-shadow:var(--spx-pop)}
@media (min-width:768px){html[data-sp] .pcs-panel.pcs-float{max-height:max(280px,min(600px,calc(100vh - 330px)))}}
html[data-sp] .pcs-float .pcs-row,html[data-sp] .pcs-float .pcs-tile{border-radius:14px}
html[data-sp] .pcs-float .pcs-prod{min-height:68px}
html[data-sp] .pcs-float .pcs-well{width:52px;height:52px;border-radius:12px}
html[data-sp] .pcs-float .pcs-pt{font-size:15px}
html[data-sp] .pcs-float .pcs-pp{font-size:15px}
html[data-sp] .pcs-float .pcs-all{bottom:-8px;margin:8px 0 0;padding:0 18px;min-height:50px;border:0;border-radius:999px;background:var(--fill);color:var(--fill-ink)!important;justify-content:center;box-shadow:0 -14px 14px -6px var(--surface)}
html[data-sp] .pcs-float .pcs-all .ic,html[data-sp] .pcs-float .pcs-all .pcs-go{color:var(--fill-ink)}
html[data-sp] .pcs-float .pcs-all .pcs-t{flex:0 1 auto}
html[data-sp] .pcs-float .pcs-all .pcs-go{margin-left:0}
html[data-sp] .pcs-float .pcs-all.is-act{background:var(--fill-hover)}
@media (prefers-color-scheme:light){html[data-sp]:not([data-theme="dark"]) .pcs-float .pcs-well{background:var(--well)}html[data-sp]:not([data-theme="dark"]) .pcs-float .pcs-well img{padding:4px}}
html[data-sp][data-theme="light"] .pcs-float .pcs-well{background:var(--well)}
html[data-sp][data-theme="light"] .pcs-float .pcs-well img{padding:4px}
</style>`;

// Trending chips and the video pill (the search itself is the app's, through the form's ids), and "/" for this field.
export const SP_JS = `<script id="pc-sp">(function(){try{
var d=document,w=window,f=d.getElementById("v9-hero-search"),inp=d.getElementById("v9-q");if(!f||!inp)return;
function plain(e){return!(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button>0);}
/* a chip runs its search the way the arrow does: the form's submit handler hands it to the app (All Finds, then a scroll there) */
function run(q){inp.value=q;try{if(f.requestSubmit){f.requestSubmit();return;}}catch(x){}var ev;try{ev=new Event("submit",{bubbles:true,cancelable:true});}catch(x){ev=d.createEvent("Event");ev.initEvent("submit",true,true);}if(f.dispatchEvent(ev))f.submit();}
var tr=d.getElementById("spx-trend");
if(tr)tr.addEventListener("click",function(e){var a=e.target.closest?e.target.closest("a[data-q]"):null;if(!a||!plain(e))return;e.preventDefault();run(a.getAttribute("data-q"));});
/* the video pill opens the app's own tutorial player and starts the 56-second video (the tap allows sound); without the app it is a link to /how-to-order */
var v=d.getElementById("spx-video");
if(v)v.addEventListener("click",function(e){if(!plain(e)||typeof showTutorialPopup!=="function")return;e.preventDefault();try{showTutorialPopup(true);var b=d.querySelector('#tut-pop [data-act="video"]');if(b&&!b.hidden)b.click();}catch(x){location.href=v.href;}});
/* "/" goes to this field (the header's Cmd/Ctrl+K stays the app's); not while typing, a dialog is open or a find is showing */
w.addEventListener("keydown",function(e){
if(e.key!=="/"||e.metaKey||e.ctrlKey||e.altKey)return;
var a=d.activeElement,t=a&&a.tagName;if(t==="INPUT"||t==="TEXTAREA"||t==="SELECT"||(a&&a.isContentEditable))return;
if(inp.offsetParent===null||inp.closest("[inert]")||d.querySelector("#tut-pop,#drawer.open,.pcs-ov:not([hidden])"))return;
e.preventDefault();e.stopImmediatePropagation();try{inp.focus();}catch(x){}
},true);
}catch(e){}})();</script>`;
