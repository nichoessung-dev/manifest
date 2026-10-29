// v9 tools, round 2 (29 Oct 2026): the shipping calculator (with the old weight estimator's item list as "Add My Items"),
// the size estimator and the parcel tracker, rebuilt on the shared tool kit (tk-* classes in ds.css, spec:
// r2/TOOLS_SPEC.md). pages.js merges TOOLS9 into TOOLS (hub, sitemap) and hands these three slugs to toolPage9().
// Everything runs in the browser: no network calls, no keys. Inline scripts are ES5, escape everything they print and
// keep every localStorage access in try/catch so the pages work without storage.
import { SITE, esc, crumbs, page, TOOL_LINKS, ICONS, ic, icTile, howItWorks } from "./site.js";

// JSON for an inline <script>: "<" is escaped so no value can close the script tag.
const js = v => JSON.stringify(v).replace(/</g, "\\u003c");

// ------------------------------------------------------------------ icons
// The one icon set lives in site.js (ICONS, ic()). P_ keeps the short names this file used, as ICONS names; svg(name, cls)
// returns the whole <svg>. The garment icons are the homepage category geometry.
const svg = (name, cls = "") => ic(name, cls);
const P_ = { qc: "camera", link: "link", box: "box", ruler: "ruler", pin: "pin", check: "check", copy: "copy", alert: "alert", x: "x", plus: "plus",
  minus: "minus", ext: "ext", paste: "paste", tee: "tee", hoodie: "hoodie", jacket: "jacket", pants: "pants", shoe: "shoe" };
export const TOOL_ICON_PATHS = { "qc-checker": ICONS.camera, "link-converter": ICONS.link, "shipping-calculator": ICONS.box, "size-estimator": ICONS.ruler, "parcel-tracker": ICONS.pin };
const TOOL_ICON_NAME = { "qc-checker": P_.qc, "link-converter": P_.link, "shipping-calculator": P_.box, "size-estimator": P_.ruler, "parcel-tracker": P_.pin };
export const toolIcon = slug => svg(TOOL_ICON_NAME[slug] || P_.box);
// One line per tool (the homepage v9_tool_*_d strings), for the hub and the related-tools cards.
export const TOOL_SHORT = { "qc-checker": "See real buyer photos of any listing.", "link-converter": "Turn any seller link into agent buy links.",
  "shipping-calculator": "Ballpark your parcel cost by weight and country.", "size-estimator": "Find your size from height, weight and fit.",
  "parcel-tracker": "Spot the carrier and track your parcel." };

// ------------------------------------------------------------------ data
// Typical shipped weight per item type in grams, light packaging included. These are the weight estimator's numbers
// (pages.js TYPE_WEIGHT uses the same ones for the product facts).
export const ITEM_WEIGHTS = [["T-shirt", 250], ["Shirt / polo", 330], ["Shorts", 350], ["Hoodie / sweater", 700], ["Pants / jeans", 600],
  ["Light jacket", 700], ["Puffer / heavy jacket", 1100], ["Sneakers (no box)", 900], ["Sneakers (with box)", 1300], ["Bag", 550],
  ["Cap / beanie", 220], ["Belt / small accessory", 200]];
// The garment icon on each item chip, same order as ITEM_WEIGHTS.
const ITEM_ICONS = ["tee", "tee", "shorts", "hoodie", "pants", "jacket", "jacket", "shoe", "box", "bag", "cap", "watch"];
// URL keys for ITEM_WEIGHTS, same order (?items=hoodie:2,sneakers-box:1).
const ITEM_KEYS = ["tshirt", "shirt", "shorts", "hoodie", "pants", "light-jacket", "puffer", "sneakers", "sneakers-box", "bag", "cap", "accessory"];
// Shipping ballpark per region: [line, base USD, USD per kg]. Unchanged from the live calculator.
const ZONES = { "United States": "na", "Canada": "na", "United Kingdom": "eu", "Germany": "eu", "France": "eu", "Netherlands": "eu", "Italy": "eu",
  "Spain": "eu", "Poland": "eu", "Ireland": "eu", "Norway": "nordic", "Sweden": "nordic", "Denmark": "nordic", "Finland": "nordic", "Rest of Europe": "eu",
  "Australia": "oce", "New Zealand": "oce", "Rest of world": "row" };
const RATES = { nordic: [["Economy", 5, 7], ["Registered / special line", 7, 10], ["Express (DHL/EMS)", 9, 15]], eu: [["Economy", 5, 6.5], ["Registered / special line", 7, 9.5], ["Express (DHL/EMS)", 8, 14]],
  na: [["Economy", 6, 8], ["Registered / special line", 8, 11], ["Express (DHL/EMS)", 9, 16]], oce: [["Economy", 6, 9], ["Registered / special line", 8, 12], ["Express (DHL/EMS)", 10, 17]],
  row: [["Economy", 6, 9], ["Registered / special line", 8, 12], ["Express (DHL/EMS)", 10, 18]] };
// Destination groups for the <select>, every ZONES key exactly once.
const DEST_GROUPS = [["North America", ["United States", "Canada"]], ["Europe", ["United Kingdom", "Germany", "France", "Netherlands", "Italy", "Spain", "Poland", "Ireland", "Rest of Europe"]],
  ["Nordics", ["Norway", "Sweden", "Denmark", "Finland"]], ["Oceania", ["Australia", "New Zealand"]], ["Other", ["Rest of world"]]];
// Browser language region (or language) to destination, used once when nothing is stored. No network call.
const LANG_DEST = { US: "United States", CA: "Canada", GB: "United Kingdom", UK: "United Kingdom", DE: "Germany", AT: "Rest of Europe", CH: "Rest of Europe", FR: "France", BE: "Rest of Europe",
  NL: "Netherlands", IT: "Italy", ES: "Spain", PT: "Rest of Europe", PL: "Poland", IE: "Ireland", NO: "Norway", SE: "Sweden", DK: "Denmark", FI: "Finland", AU: "Australia", NZ: "New Zealand",
  nb: "Norway", nn: "Norway", no: "Norway", sv: "Sweden", da: "Denmark", fi: "Finland", de: "Germany", nl: "Netherlands", pl: "Poland", it: "Italy", es: "Spain", fr: "France" };

// Pure shipping maths, shared by the page script and the unit tests: [[line, low USD, high USD], ...] for a weight in kg.
export function shipQuote(zone, kg) {
  return (RATES[zone] || RATES.row).map(l => [l[0], Math.round(l[1] + l[2] * kg * 0.85), Math.round(l[1] + l[2] * kg * 1.2)]);
}
export const SHIP_ZONES = ZONES;

// Size maths (same as the live estimator). Returns {x: EU/US index, a: Asian label index, top: true when past the chart}.
const SIZE_L = ["XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL"], SIZE_EU = [44, 46, 48, 50, 52, 54, 56, 58], SIZE_WA = [28, 30, 32, 34, 36, 38, 40, 42];
const GADJ = { tops: 0, hoodies: 0.25, jackets: 0.5, pants: 0 };
// Common men's / unisex sneaker chart: [foot length cm, US men, EU]
const SHOES = [[24, 6, 38.5], [24.5, 6.5, 39], [25, 7, 40], [25.5, 7.5, 40.5], [26, 8, 41], [26.5, 8.5, 42], [27, 9, 42.5], [27.5, 9.5, 43], [28, 10, 44],
  [28.5, 10.5, 44.5], [29, 11, 45], [29.5, 11.5, 45.5], [30, 12, 46], [30.5, 12.5, 47], [31, 13, 47.5]];
const SIZE_FN = `function sizeFor(g,h,w,fit){var s=(w-50)/10+Math.max(-0.75,Math.min(0.75,(h-175)/40))+fit+(G[g]||0),x=Math.max(0,Math.min(7,Math.floor(s)));return{x:x,a:Math.min(7,x+1),top:x>=7};}
function shoeFor(f){if(f<SH[0][0]-0.25)return{r:SH[0],top:false,low:true};for(var i=0;i<SH.length;i++)if(SH[i][0]>=f-0.05)return{r:SH[i],top:false};return{r:SH[SH.length-1],top:true};}`;
// Chart parser and comparison (seller's chart mode), also unit-tested.
const CHART_FN = String.raw`function parseChart(t){var rows=[];String(t||"").split(/\r?\n/).forEach(function(line){var m=line.trim().match(/^([A-Za-z0-9.]{1,8})[\s:,;|]+(\d+(?:\.\d+|,\d(?!\d))?)(?:[\s,;|]+(\d+(?:\.\d+|,\d(?!\d))?))?/);if(m)rows.push([m[1],parseFloat(m[2].replace(",",".")),m[3]?parseFloat(m[3].replace(",",".")):null]);});return rows.slice(0,12);}
function closest(yc,yl,rows){var best=null,res=[];rows.forEach(function(r){var c=r[1],l=r[2];if(!isFinite(c)||c===null||!isFinite(yc))return;var dc=c-yc,dl=(l!==null&&isFinite(l)&&isFinite(yl))?l-yl:null,sc=Math.abs(dc)+(dl===null?0:Math.abs(dl)*0.5),o={n:String(r[0]||"").trim()||"?",dc:dc,dl:dl,sc:sc};res.push(o);if(!best||sc<best.sc)best=o;});return{best:best,res:res};}`;

// Carrier detection for the parcel tracker. Checked top to bottom on the number in upper case without spaces or dashes;
// the first match wins, so the specific formats come before the all-digit ones. `url` is the carrier's own tracking page
// ("{n}" is replaced by the number); null means we only offer the universal tracker. All-digit formats are shared by
// several carriers, so those are shown as "likely". `fmt` and `ex` feed the "Supported Carriers" list on the page
// (format illustrations only, never links).
export const CARRIERS = [
  { id: "ups", name: "UPS", re: /^1Z[0-9A-Z]{16}$/, url: "https://www.ups.com/track?tracknum={n}", fmt: "1Z + 16 letters or digits", ex: "1Z999AA10123456784" },
  { id: "yun", name: "YunExpress", re: /^YT\d{16}$/, url: "https://www.yuntrack.com/parcelTracking?id={n}", fmt: "YT + 16 digits", ex: "YT2412345678901234" },
  { id: "cainiao", name: "Cainiao", re: /^LP\d{14}$/, url: "https://global.cainiao.com/newDetail.htm?mailNoList={n}", fmt: "LP + 14 digits", ex: "LP00512345678901" },
  { id: "4px", name: "4PX", re: /^4PX\d{10,16}CN$/, url: "https://track.4px.com/#/result/0/{n}", fmt: "4PX + 10 to 16 digits + CN", ex: "4PX3000123456789CN" },
  { id: "sf", name: "SF Express", re: /^SF\d{12,13}$/, url: null, fmt: "SF + 12 or 13 digits", ex: "SF1234567890123" },
  { id: "evri", name: "Evri", re: /^H[0-9A-Z]{15}$/, url: "https://www.evri.com/track/parcel/{n}/details", fmt: "H + 15 letters or digits", ex: "H00A0A0012345678" },
  { id: "dhl", name: "DHL", re: /^(?:JJD\d{10,20}|JVGL\d{10,20})$/, url: "https://www.dhl.com/global-en/home/tracking/tracking-express.html?submit=1&tracking-id={n}", fmt: "JJD or JVGL + 10 to 20 digits", ex: "JVGL0123456789012345" },
  { id: "usps420", name: "USPS", re: /^420\d{5}(?:\d{4})?9[1-5]\d{18,20}$/, url: "https://tools.usps.com/go/TrackConfirmAction?tLabels={n}", fmt: "420 + ZIP + a 91 to 95 number", ex: "420902109400111202555842332669" },
  { id: "postnl", name: "PostNL", re: /^3S[A-Z]{4}\d{6,9}$/, url: "https://jouw.postnl.nl/track-and-trace/{n}", fmt: "3S + 4 letters + 6 to 9 digits", ex: "3SABCD1234567" },
  { id: "dhlec", name: "DHL", re: /^00340434\d{12}$/, url: "https://www.dhl.com/global-en/home/tracking/tracking-express.html?submit=1&tracking-id={n}", fmt: "00340434 + 12 digits (DHL eCommerce)", ex: "00340434123456789012" },
  // UPU S10 international post format (EMS, ePacket, registered mail): 2 letters + 9 digits + country code. Handled by POSTS.
  { id: "s10", name: "Post", re: /^[A-Z]{2}\d{9}[A-Z]{2}$/, url: null, fmt: "2 letters + 9 digits + country code (China Post, EMS, Royal Mail, PostNord and other posts)", ex: "LX123456789CN" },
  // Cainiao numbers that start with CN (after s10, so CN123456789CN stays a China Post parcel).
  { id: "cainiao2", name: "Cainiao", re: /^CN[A-Z]{0,4}\d{9,16}[A-Z]{0,2}$/, url: "https://global.cainiao.com/newDetail.htm?mailNoList={n}", fmt: "CN + letters and 9 to 16 digits", ex: "CNGBR0012345678" },
  { id: "usps", name: "USPS", re: /^9[1-5]\d{18,20}$/, url: "https://tools.usps.com/go/TrackConfirmAction?tLabels={n}", fmt: "20 to 22 digits starting 91 to 95", ex: "9400111202555842332669" },
  { id: "dpd", name: "DPD", re: /^\d{14}$/, url: "https://tracking.dpd.de/status/en_US/parcel/{n}", likely: 1, fmt: "14 digits (shared format)", ex: "01234567890123" },
  { id: "fedex", name: "FedEx", re: /^(?:\d{12}|\d{15})$/, url: "https://www.fedex.com/fedextrack/?trknbr={n}", likely: 1, fmt: "12 or 15 digits (shared format)", ex: "123456789012" },
  { id: "gls", name: "GLS", re: /^\d{11}$/, url: "https://gls-group.com/EU/en/parcel-tracking?match={n}", likely: 1, fmt: "11 digits (shared format)", ex: "12345678901" },
  { id: "dhlx", name: "DHL Express", re: /^\d{10}$/, url: "https://www.dhl.com/global-en/home/tracking/tracking-express.html?submit=1&tracking-id={n}", likely: 1, fmt: "10 digits (shared format)", ex: "1234567890" },
];
// S10 numbers end in the country of the post that issued them. [name, tracking page or null].
const POSTS = {
  CN: ["China Post", null], GB: ["Royal Mail", "https://www.royalmail.com/track-your-item#/tracking-results/{n}"],
  US: ["USPS", "https://tools.usps.com/go/TrackConfirmAction?tLabels={n}"], NL: ["PostNL", "https://jouw.postnl.nl/track-and-trace/{n}"],
  SE: ["PostNord Sweden", "https://www.postnord.se/en/our-tools/track-and-trace?shipmentId={n}"], DK: ["PostNord Denmark", null],
  NO: ["Posten Norge", "https://sporing.posten.no/sporing/{n}"], FI: ["Posti", null], DE: ["Deutsche Post", "https://www.dhl.de/en/privatkunden/pakete-empfangen/verfolgen.html?piececode={n}"],
  FR: ["La Poste", "https://www.laposte.fr/outils/suivre-vos-envois?code={n}"], CA: ["Canada Post", null], AU: ["Australia Post", "https://auspost.com.au/mypost/track/#/details/{n}"],
  HK: ["Hongkong Post", null], SG: ["Singapore Post", null],
};
const TRACK_FN = String.raw`function norm(s){return String(s||"").toUpperCase().replace(/[\s-]/g,"");}
function detect(n){for(var i=0;i<C.length;i++){if(new RegExp(C[i][2]).test(n)){var c={id:C[i][0],name:C[i][1],url:C[i][3],likely:C[i][4],note:""};
if(c.id==="s10"){var cc=n.slice(-2),p=P[cc];c.name=p?p[0]:"Postal service ("+cc+")";c.url=p?p[1]:null;if(cc==="CN"){c.name=n[0]==="E"?"EMS (China Post)":"China Post";c.note="Once it lands, your local post usually tracks the same number too.";}}return c;}}return null;}
function split(t){var out=[];String(t||"").split(/[\n,;]+/).forEach(function(chunk){var j=norm(chunk);if(!j)return;if(detect(j)||chunk.trim().indexOf(" ")<0){out.push(j);return;}chunk.trim().split(/\s+/).forEach(function(x){x=norm(x);if(x)out.push(x);});});
return out.filter(function(n,i){return /^(?=[A-Z]*\d)[A-Z0-9]{8,40}$/.test(n)&&out.indexOf(n)===i;}).slice(0,20);}`;

// Placeholder fill without String.replace's $ patterns (regex sources contain $).
// An icon for a JS string literal in an inline script: \x22 is a double quote in either quote style.
const qsvg = (p, cls = "") => svg(p, cls).replace(/"/g, "\\x22");
const fill = (str, map) => Object.keys(map).reduce((a, k) => a.split(k).join(map[k]), str);

// ------------------------------------------------------------------ shared kit JS (inlined once per tool page)
// K.esc, K.$, K.say (polite live region), K.copy(text, button, message) with a fallback for browsers without the
// Clipboard API, K.deb, K.qs.get / K.qs.put (replaceState, debounced), K.store (localStorage in try/catch),
// K.seg(el, onChange) (roving radiogroup: arrows, Home, End), K.paste(button, input), K.ago(ms), K.cbtn(text, label, msg).
const COPY_ICONS = svg(P_.copy, "i-cp") + svg(P_.check, "i-ok");
const KIT_RAW = String.raw`var K=(function(){var d=document;
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c];});}
function $(i){return d.getElementById(i);}
var live=null;function say(t){if(!live){live=d.createElement("div");live.className="vh";live.setAttribute("aria-live","polite");d.body.appendChild(live);}live.textContent="";setTimeout(function(){live.textContent=t;},50);}
var MAC=/Mac|iPhone|iPad/.test(navigator.platform||"");
function flash(b,t){if(!b)return;var l=b.querySelector(".tk-cl");if(!l)return;if(b._t0==null)b._t0=l.textContent;l.textContent=t;b.classList.add("ok");clearTimeout(b._tt);b._tt=setTimeout(function(){l.textContent=b._t0;b.classList.remove("ok");},1500);}
function copy(text,b,msg){function ok(){flash(b,"Copied");say(msg||"Copied");}
function fb(){var ta=d.createElement("textarea"),r=false;ta.value=text;ta.setAttribute("readonly","");ta.style.cssText="position:fixed;top:0;left:0;opacity:0;font-size:16px";d.body.appendChild(ta);ta.select();try{r=d.execCommand("copy");}catch(e){}d.body.removeChild(ta);if(r){ok();return;}
var p=b&&b.parentNode,x=p&&p.querySelector(".tk-copyfb");if(p&&!x){x=d.createElement("input");x.className="tk-in tk-copyfb";x.readOnly=true;x.setAttribute("aria-label","Text to copy");p.appendChild(x);}
if(x){x.value=text;x.focus();x.select();}var k=MAC?"Cmd+C":"Ctrl+C";if(b){var l=b.querySelector(".tk-cl");if(l){if(b._t0==null)b._t0=l.textContent;l.textContent="Press "+k;}}say("Press "+k+" to copy");}
var fin=false,once=function(f){return function(){if(fin)return;fin=true;f();};};
try{if(navigator.clipboard&&navigator.clipboard.writeText&&window.isSecureContext){navigator.clipboard.writeText(text).then(once(ok),once(fb));setTimeout(once(fb),800);return;}}catch(e){}fb();}
function deb(f,ms){var t;return function(){var a=arguments;clearTimeout(t);t=setTimeout(function(){f.apply(null,a);},ms);};}
var qs={get:function(k){try{return new URLSearchParams(location.search).get(k);}catch(e){return null;}},
put:deb(function(o){try{var u=new URLSearchParams();for(var k in o)if(o[k]!=null&&o[k]!=="")u.set(k,o[k]);var s=u.toString().replace(/%2C/g,",").replace(/%3A/g,":");history.replaceState(history.state,"",location.pathname+(s?"?"+s:"")+location.hash);}catch(e){}},300)};
var store={get:function(k,def){try{var v=localStorage.getItem(k);return v==null?def:JSON.parse(v);}catch(e){return def;}},set:function(k,v){try{localStorage.setItem(k,JSON.stringify(v));}catch(e){}},del:function(k){try{localStorage.removeItem(k);}catch(e){}}};
function seg(el,cb){var bs=[].slice.call(el.querySelectorAll('[role="radio"]'));
function pick(b,fire,focus){bs.forEach(function(x){var on=x===b;x.setAttribute("aria-checked",on?"true":"false");x.tabIndex=on?0:-1;});if(focus)b.focus();if(fire&&cb)cb(b.getAttribute("data-v"));}
bs.forEach(function(b,i){b.addEventListener("click",function(){if(b.getAttribute("aria-checked")!=="true")pick(b,true);});b.addEventListener("keydown",function(e){var j=-1,k=e.key;
if(k==="ArrowRight"||k==="ArrowDown")j=(i+1)%bs.length;else if(k==="ArrowLeft"||k==="ArrowUp")j=(i-1+bs.length)%bs.length;else if(k==="Home")j=0;else if(k==="End")j=bs.length-1;if(j>=0){e.preventDefault();pick(bs[j],true,true);}});});
return{set:function(v){for(var i=0;i<bs.length;i++)if(bs[i].getAttribute("data-v")===String(v)){pick(bs[i],false);return true;}return false;},
get:function(){for(var i=0;i<bs.length;i++)if(bs[i].getAttribute("aria-checked")==="true")return bs[i].getAttribute("data-v");return null;}};}
function paste(b,inp){if(!b)return;if(!(navigator.clipboard&&navigator.clipboard.readText)){b.hidden=true;return;}
b.addEventListener("click",function(){navigator.clipboard.readText().then(function(t){t=String(t||"").trim();if(!t)return;inp.value=t;inp.dispatchEvent(new Event("input",{bubbles:true}));inp.dispatchEvent(new Event("tk-paste"));inp.focus();},function(){inp.focus();say("Press "+(MAC?"Cmd+V":"Ctrl+V")+" to paste");});});}
function ago(t){var s=Math.max(0,(Date.now()-t)/1000);if(s<60)return"Just now";if(s<3600)return Math.floor(s/60)+" min ago";if(s<86400)return Math.floor(s/3600)+" h ago";var n=Math.floor(s/86400);return n===1?"Yesterday":n+" days ago";}
function cbtn(text,label,msg,cls){return'<button type="button" class="btn sm tk-copy'+(cls?" "+cls:"")+'" data-copy="'+esc(text)+'"'+(msg?' data-msg="'+esc(msg)+'"':"")+'>'+ICP+'<span class="tk-cl">'+esc(label||"Copy")+"</span></button>";}
var ICP=__COPY_ICONS__;
d.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-copy],[data-share]");if(!b)return;
if(b.hasAttribute("data-share"))copy(location.href,b,"Link copied");else copy(b.getAttribute("data-copy"),b,b.getAttribute("data-msg")||"Copied");});
return{esc:esc,$:$,say:say,copy:copy,deb:deb,qs:qs,store:store,seg:seg,paste:paste,ago:ago,cbtn:cbtn,MAC:MAC};})();`;
export const KIT_JS = fill(KIT_RAW, { __COPY_ICONS__: js(COPY_ICONS) });

// Server-side snippets that mirror the kit JS.
const copyBtn = (label, attrs, cls = "") => `<button type="button" class="btn sm tk-copy${cls ? " " + cls : ""}" ${attrs}>${COPY_ICONS}<span class="tk-cl">${esc(label)}</span></button>`;
const segHtml = (id, label, opts, on, cls = "tk-seg") => `<div class="${cls}" role="radiogroup" ${label.startsWith("#") ? `aria-labelledby="${label.slice(1)}"` : `aria-label="${esc(label)}"`} id="${id}">` +
  opts.map(([v, t, icn]) => `<button type="button" role="radio" data-v="${esc(v)}" aria-checked="${v === on}" tabindex="${v === on ? 0 : -1}">${icn ? svg(icn) : ""}<span>${esc(t)}</span></button>`).join("") + `</div>`;
const unitIn = (id, unit, attrs) => `<div class="tk-unitwrap"><input class="tk-in" id="${id}" ${attrs}><span class="tk-unit" data-u="${id}">${esc(unit)}</span></div>`;

// ------------------------------------------------------------------ copy and meta
export const TOOLS9 = {
  "shipping-calculator": { name: "Shipping Calculator", h1: "Know Your Shipping Cost Before You Pay",
    title: "Rep Shipping Calculator: Estimate Parcel Weight and Shipping Cost · Puro Classico",
    desc: "Add your items or type a weight and get a ballpark shipping cost from China for economy, registered and express lines. Free, no sign-up.",
    lead: "Pick your country, add the items in your haul (or type a weight) and see a ballpark cost for the common line types.",
    about: "<p>Item weights are typical shipped weights with light packaging. Your agent weighs the real parcel, and shoe boxes and puffers take extra space, which can raise the <a href=\"/guides/shipping-lines\">volumetric weight</a>. Prices are estimates only: the real price depends on the agent, line, box size and current promotions, so always check your agent's own estimator before paying.</p>",
    faq: [["How much does shipping reps cost?", "It depends on your country, the shipping line and the parcel weight. Add your items or type a weight above for a ballpark on economy, registered and express lines, then check the exact price in your agent's estimator."],
      ["How heavy is a hoodie or a pair of sneakers when shipped?", "As a rough guide a hoodie ships at about 700 g and sneakers at about 900 g without the box or 1.3 kg with it. Your agent weighs the real parcel before you pay for shipping."],
      ["How do I make shipping cheaper?", "Remove shoe boxes you don't need, combine items into one parcel and compare two or three lines for your country in your agent's estimator."]] },
  "size-estimator": { name: "Size Estimator", h1: "Know Your Size Before You Order",
    title: "Rep Size Estimator: Asian Size to EU/US From Height and Weight · Puro Classico",
    desc: "Turn your height, weight and fit preference into a recommended Asian size and the EU/US equivalent for tops, hoodies, jackets, pants and sneakers. Or compare your own garment with the seller's chart.",
    lead: "Enter your height, weight and the fit you like. Get the size label to look for on Weidian and Taobao charts, with the EU/US equivalent.",
    about: "<p>Many Weidian and Taobao sellers use Asian sizing, which tends to run about one size smaller than EU/US, so the estimate shows both. It is a starting point from body size, not a promise: cuts differ between sellers and models. The most reliable check is the second mode, where you compare a garment you own with the seller's chart in centimetres. More in our <a href=\"/guides/sizing\">rep sizing guide</a>.</p>",
    faq: [["Do reps run small?", "Often, because many sellers use Asian sizing that runs about one size smaller than EU/US. That is why the estimator shows the Asian label next to the EU/US size."],
      ["How accurate is the size estimator?", "It gives a starting point from height, weight and fit. Brands and sellers cut differently, so compare a garment you own with the seller's chart in centimetres before you order."],
      ["How do I pick a rep sneaker size?", "Measure your foot length in centimetres, use the size the estimator gives and check whether that model runs large or small at retail. If you are between two sizes, the half size up is usually the safer pick."]] },
  "parcel-tracker": { name: "Parcel Tracker", h1: "Track Your Haul From China To Your Door",
    title: "Rep Parcel Tracker: Track Your Agent Parcel From China · Puro Classico",
    desc: "Paste the tracking number your agent gives you. We spot the carrier (YunExpress, Cainiao, 4PX, EMS, PostNL, DHL, UPS and more) and open the right tracking page in one tap.",
    lead: "Paste one or more tracking numbers. We detect the carrier and open its tracking page or a universal tracker in one tap.",
    about: "<p>Detection runs in your browser from the number's format, nothing is sent to us. Recent numbers are kept on this device only so you can check them again later. Some all-digit numbers fit more than one carrier, so those are marked as likely, and the universal tracker works for all of them. New to shipping? Read <a href=\"/guides/shipping-lines\">shipping lines explained</a> and <a href=\"/how-to-order\">how to order</a>.</p>",
    faq: [["Where do I find my tracking number?", "Your agent shows it on the parcel page once the parcel has shipped from their warehouse. Copy it from there and paste it here."],
      ["Why does my tracking show no updates yet?", "Tracking often starts only after the carrier scans the parcel, which can take a few days after your agent ships it. Check again later or open the universal tracker."],
      ["Is my tracking number saved?", "Only in your own browser, so you can see your recent numbers again on this device. You can clear them at any time. Nothing is sent to Puro Classico."]] },
};
// Hub and sitemap order (the shipping calculator replaces the weight estimator).
export const TOOL_SLUGS = ["qc-checker", "link-converter", "shipping-calculator", "size-estimator", "parcel-tracker"];

// ------------------------------------------------------------------ shipping calculator
const SHIP_JS = fill(String.raw`(function(){var W=__W__,KEYS=__KEYS__,Z=__Z__,RT=__RT__,LD=__LD__,LI=['__LI1__','__LI2__','__LI3__'];
var $=K.$,esc=K.esc,co=$("co"),kg=$("kg"),out=$("out"),hl=$("hl"),sb=$("sb"),cnt={},unit="kg",mode="items",LB=2.20462,vis=true,res=null,ready=false,sayD=K.deb(K.say,700);
var wm=K.seg($("wm"),function(v){mode=v;show();if(v==="type")setTimeout(function(){kg.focus();},0);run();});
var ut=K.seg($("ut"),function(v){var k=typed();unit=v;if(k>0)kg.value=fmtIn(k);K.store.set("pc.ship.unit",v);paint();run();});
function fmtIn(k){var v=unit==="lb"?k*LB:k;return String(Math.round(v*100)/100);}
function typed(){var v=parseFloat(String(kg.value).replace(",","."));if(!(v>0))return 0;return unit==="lb"?v/LB:v;}
function itemsG(){var g=0,n=0;for(var i in cnt){g+=cnt[i]*W[i][1];n+=cnt[i];}return{g:g,n:n};}
function wfmt(k){return unit==="lb"?(k*LB).toFixed(2)+" lb":k.toFixed(2)+" kg";}
function gfmt(g){return unit==="lb"?"~"+(g/1000*LB).toFixed(2)+" lb":"~"+g+" g";}
function show(){$("pt").hidden=mode!=="type";$("pi").hidden=mode!=="items";}
function paint(){[].forEach.call(document.querySelectorAll('[data-u="kg"]'),function(s){s.textContent=unit;});kg.setAttribute("aria-label","Parcel weight in "+unit);
var it=itemsG(),ids=Object.keys(cnt).sort(function(a,b){return a-b;});
$("hh").hidden=!ids.length;$("he").hidden=!!ids.length;$("ht").textContent=it.n?it.n+" item"+(it.n>1?"s":"")+" · "+wfmt(it.g/1000):"";
hl.innerHTML=ids.map(function(i){var w=W[i],c=cnt[i];return '<li><div class="tk-haul-n"><span>'+esc(w[0])+"</span><small>"+esc(gfmt(w[1]))+" each</small></div>"+
'<div class="tk-step"><button type="button" data-d="-1" data-i="'+i+'" aria-label="Fewer '+esc(w[0])+'">__MINUS__</button><output aria-label="'+esc(w[0])+'">'+c+'</output><button type="button" data-d="1" data-i="'+i+'" aria-label="More '+esc(w[0])+'"'+(c>=99?" disabled":"")+">__PLUS__</button></div></li>";}).join("");
[].forEach.call(document.querySelectorAll("[data-add]"),function(b){var c=cnt[b.getAttribute("data-add")]||0,n=b.querySelector(".tk-n");if(n)n.textContent=c?"×"+c:"";b.classList.toggle("on",c>0);});}
function add(i,dlt){i=+i;var c=Math.max(0,Math.min(99,(cnt[i]||0)+dlt));if(c)cnt[i]=c;else delete cnt[i];paint();run();}
function money(v){return"$"+v.toLocaleString("en-US");}
function run(){var k,it=itemsG(),sub="",to=co.value;
if(mode==="type"){k=typed();sub=k>0?"Typed weight":"";}else{k=it.g/1000;sub=it.n?it.n+" item"+(it.n>1?"s":""):"";}
save();res=null;
if(!(k>0)){out.setAttribute("data-state","empty");out.innerHTML='<div class="tk-empty">__BOX__<p>'+(mode==="type"?"Type a weight to see prices.":"Add an item or type a weight to see prices.")+'</p><div class="tk-chips"><span>Try:</span><button type="button" class="tk-chip" data-add="3">+ Hoodie</button><button type="button" class="tk-chip" data-add="8">+ Sneakers (with box)</button></div></div>';bar();return;}
if(k>30){out.setAttribute("data-state","error");out.innerHTML='<div class="tk-alert" role="alert">__ALERT__<div><b>Too Heavy For One Parcel</b><p>That is over 30 kg. Split it into several parcels or ask your agent for a freight quote.</p></div></div>';bar();return;}
var L=RT[Z[to]].map(function(l){return[l[0],Math.round(l[1]+l[2]*k*0.85),Math.round(l[1]+l[2]*k*1.2)];}),lo=Infinity,hi=0,best=0;
L.forEach(function(l,i){if(l[1]<lo){lo=l[1];best=i;}if(l[2]>hi)hi=l[2];});
var rng=function(l){return"~"+(l[1]===l[2]?money(l[1]):money(l[1])+" to "+money(l[2]));};
res={k:k,lo:lo};if(ready)sayD(wfmt(k)+", from ~"+money(lo));
var txt="Shipping estimate to "+to+", "+wfmt(k)+(unit==="lb"?" ("+k.toFixed(2)+" kg)":"")+(sub&&mode==="items"?", "+sub:"")+":\n"+L.map(function(l){return l[0]+": "+rng(l);}).join("\n")+"\nBallpark only. Check your agent's estimator for the real price.";
out.setAttribute("data-state","success");
out.innerHTML='<div class="tk-res"><p class="tk-res-k">Estimated weight</p><p class="tk-big">'+esc(wfmt(k))+'</p><p class="tk-res-sub">'+esc((unit==="lb"?k.toFixed(2)+" kg · ":"")+(sub?sub+" to ":"To ")+to)+"</p>"+
'<div class="tk-lines">'+L.map(function(l,i){return '<div class="tk-opt"><div class="tk-opt-main"><span>'+(LI[i]||"")+esc(l[0])+"</span>"+(i===best?'<span class="tk-badge">Lowest Price</span>':"")+'<span class="tk-bar" aria-hidden="true"><i style="width:'+Math.max(6,Math.round(l[2]/hi*100))+'%"></i></span></div><span class="tk-opt-v">'+esc(rng(l))+"</span></div>";}).join("")+"</div>"+
'<div class="tk-actions">'+K.cbtn(txt,"Copy Estimate","Estimate copied")+'<button type="button" class="btn sm" data-share>__LINK__<span class="tk-cl">Share</span></button></div>'+
'<p class="tk-foot">Ballpark only. Check your agent\'s estimator for the real price.</p>'+
'<details class="tk-more"><summary>How We Estimate</summary><p>Each line is a base fee plus a price per kg for your region, shown as a range from about 15% under to 20% over that figure. Bulky boxes can be charged by <a href="/guides/shipping-lines">volumetric weight</a> instead of real weight.</p></details></div>';
bar();}
function bar(){if(!sb)return;var on=!!res&&!vis;sb.classList.toggle("on",on);sb.hidden=!on;if(res)$("sbt").textContent=wfmt(res.k)+" · from ~"+money(res.lo);}
function itemsQ(){return Object.keys(cnt).sort(function(a,b){return a-b;}).map(function(i){return KEYS[i]+":"+cnt[i];}).join(",");}
function save(){var o={to:co.value};if(mode==="type"){var k=typed();if(k>0)o.kg=String(Math.round(k*1000)/1000);else o.m="type";}else{var q=itemsQ();if(q)o.items=q;}if(unit==="lb")o.unit="lb";K.qs.put(o);
K.store.set("pc.ship.last",{m:mode,kg:mode==="type"?typed():0,items:itemsQ()});}
function loadItems(s){cnt={};String(s||"").split(",").forEach(function(p){var a=p.split(":"),i=KEYS.indexOf(a[0]),c=parseInt(a[1],10);if(i>=0&&c>0)cnt[i]=Math.min(99,c);});}
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-add],[data-d]");if(!b)return;
if(b.hasAttribute("data-add")){if(mode!=="items"){mode="items";wm.set("items");show();}add(b.getAttribute("data-add"),1);K.say("Added "+W[+b.getAttribute("data-add")][0]);return;}
var i=b.getAttribute("data-i"),d=+b.getAttribute("data-d");add(i,d);if(!cnt[i]){var c=document.querySelector('#pi [data-add="'+i+'"]');if(c)c.focus();K.say("Removed "+W[+i][0]);}else{var nb=hl.querySelector('[data-i="'+i+'"][data-d="'+d+'"]');if(nb&&!nb.disabled)nb.focus();}});
$("hc").addEventListener("click",function(){cnt={};paint();run();K.say("Haul cleared");var c=document.querySelector("#pi [data-add]");if(c)c.focus();});
kg.addEventListener("input",run);co.addEventListener("change",function(){K.store.set("pc.ship.to",co.value);run();});
if(sb){sb.addEventListener("click",function(){out.scrollIntoView({block:"start",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"});});
if("IntersectionObserver"in window)new IntersectionObserver(function(es){vis=es[0].isIntersecting;bar();},{rootMargin:"0px 0px -40px 0px"}).observe(out);}
// initial state: URL, then this device's last state, then the browser language for the destination
var q={to:K.qs.get("to"),kg:K.qs.get("kg"),items:K.qs.get("items"),unit:K.qs.get("unit"),m:K.qs.get("m")},any=q.to||q.kg||q.items||q.m,last=any?null:K.store.get("pc.ship.last",null);
unit=(q.unit||K.store.get("pc.ship.unit","kg"))==="lb"?"lb":"kg";ut.set(unit);
var to=q.to&&Z.hasOwnProperty(q.to)?q.to:K.store.get("pc.ship.to","");if(!Z.hasOwnProperty(to)){to="";try{var lg=String(navigator.language||""),pr=lg.split("-");to=LD[(pr[1]||"").toUpperCase()]||LD[pr[0].toLowerCase()]||"";}catch(e){}}
if(to&&Z.hasOwnProperty(to))co.value=to;
var qk=parseFloat(q.kg);if(qk>0&&isFinite(qk)){mode="type";kg.value=fmtIn(qk);}
else if(q.items){loadItems(q.items);mode="items";}
else if(q.m==="type")mode="type";
else if(last&&typeof last==="object"){if(last.m==="type"&&last.kg>0){mode="type";kg.value=fmtIn(+last.kg);}else if(last.items)loadItems(last.items);}
wm.set(mode);show();paint();run();ready=true;})();`, { __W__: js(ITEM_WEIGHTS), __KEYS__: js(ITEM_KEYS), __Z__: js(ZONES), __RT__: js(RATES), __LD__: js(LANG_DEST), __MINUS__: qsvg(P_.minus), __PLUS__: qsvg(P_.plus), __BOX__: qsvg(P_.box), __ALERT__: qsvg(P_.alert), __LINK__: qsvg(P_.link), __LI1__: qsvg("truck", "sm"), __LI2__: qsvg("shield", "sm"), __LI3__: qsvg("zap", "sm") });

function shipUI() {
  const opts = DEST_GROUPS.map(([g, l]) => `<optgroup label="${esc(g)}">${l.map(c => `<option>${esc(c)}</option>`).join("")}</optgroup>`).join("");
  const chips = ITEM_WEIGHTS.map(([n], i) => `<button type="button" class="tk-chip" data-add="${i}" aria-label="Add ${esc(n)}">${svg(P_.plus)}${svg(ITEM_ICONS[i], "sm")}<span>${esc(n)}</span><span class="tk-n"></span></button>`).join("");
  return `<section class="tk-card tk-ship" aria-label="Shipping calculator"><div class="tk-ship-in">
<div class="tk-field"><label class="tk-label" for="co">Ship to</label><select class="tk-in" id="co" autocomplete="country-name">${opts}</select></div>
<div class="tk-field"><div class="tk-label"><span id="wml">Weight</span>${segHtml("ut", "Weight unit", [["kg", "kg"], ["lb", "lb"]], "kg", "tk-toggle")}</div>
${segHtml("wm", "#wml", [["items", "Add My Items"], ["type", "Type It"]], "items")}</div>
<div class="tk-field" id="pt" hidden><label class="tk-label" for="kg">Parcel weight</label>${unitIn("kg", "kg", 'type="number" inputmode="decimal" min="0" step="0.1" placeholder="2.5" autocomplete="off"')}</div>
<div class="tk-field" id="pi"><span class="tk-label">Tap to add<span class="tk-hint">Typical shipped weights</span></span><div class="tk-chips tk-add">${chips}</div>
<div class="tk-haul"><div class="tk-haul-h" id="hh" hidden><b>Your haul</b><span id="ht"></span><button type="button" class="btn ghost sm" id="hc">Clear Haul</button></div><p class="tk-haul-e" id="he">Your haul is empty. Tap an item above to add it.</p><ul id="hl"></ul></div></div>
</div><div class="tk-out tk-ship-out" id="out" data-state="empty"></div></section>
<button type="button" class="tk-sumbar" id="sb" hidden><span id="sbt"></span><span class="tk-sumbar-go">See prices</span></button>
<script>${KIT_JS}
${SHIP_JS}</script>`;
}

// ------------------------------------------------------------------ size estimator
const SIZE_JS = fill(String.raw`(function(){var L=__L__,EU=__EU__,WA=__WA__,SH=__SH__,G=__G__,CAT=__CAT__;
__SIZEFN__
__CHARTFN__
var $=K.$,esc=K.esc,o=$("out"),co=$("cout"),FN={"-0.5":"fitted cut","0":"regular fit","0.5":"relaxed fit","1":"oversized fit"},GN={tops:"Tops",hoodies:"Hoodies",jackets:"Jackets",pants:"Pants",shoes:"Sneakers"};
var st={m:"body",g:"tops",u:"m",fit:"0"},said="",ready=false,sayD=K.deb(function(m){if(m!==said){said=m;K.say(m);}},700);
var md=K.seg($("md"),function(v){st.m=v;pane();upd();if(v==="chart")cmp();});
var ga=K.seg($("ga"),function(v){st.g=v;pane();run();});
var fi=K.seg($("fi"),function(v){st.fit=v;run();});
var un1=K.seg($("un"),function(v){units(v);}),un2=K.seg($("un2"),function(v){units(v);});
function num(i){var v=parseFloat(String($(i).value).replace(",","."));return isFinite(v)?v:NaN;}
function r1(v){return Math.round(v*10)/10;}
function setv(i,v){$(i).value=isFinite(v)?String(v):"";}
function units(v){if(v===st.u)return;var imp=v==="i";
// convert what is typed so nothing is lost when switching
if(imp){var h=num("hc");if(h>0){var ti=h/2.54,f=Math.floor(ti/12),n=Math.round(ti-f*12);if(n===12){f++;n=0;}setv("hf",f);setv("hn",n);}var w=num("wg");if(w>0)setv("wg",Math.round(w/0.4536));var fl=num("fl");if(fl>0)setv("fl",r1(fl/2.54));}
else{var hf=num("hf");if(hf>0)setv("hc",Math.round((hf*12+(num("hn")||0))*2.54));var wl=num("wg");if(wl>0)setv("wg",Math.round(wl*0.4536));var fi2=num("fl");if(fi2>0)setv("fl",r1(fi2*2.54));}
["yc","yl"].forEach(function(i){var x=num(i);if(x>0)setv(i,r1(imp?x/2.54:x*2.54));});
[].forEach.call($("ct").querySelectorAll("input[data-n]"),function(x){var y=parseFloat(x.value);if(y>0)x.value=String(r1(imp?y/2.54:y*2.54));});
st.u=v;un1.set(v);un2.set(v);K.store.set("pc.size.unit",v);pane();run();cmp();}
function pane(){var imp=st.u==="i",shoe=st.g==="shoes";$("pb").hidden=st.m!=="body";$("pc").hidden=st.m!=="chart";
$("hm").hidden=imp;$("hi").hidden=!imp;$("body").hidden=shoe;$("foot").hidden=!shoe;$("fitf").hidden=shoe;
[].forEach.call(document.querySelectorAll("[data-u]"),function(s){var k=s.getAttribute("data-u");s.textContent=k==="hf"?"ft":k==="hn"?"in":k==="wg"?(imp?"lb":"kg"):(imp?"in":"cm");});
$("fl").placeholder=imp?"10.6":"27";$("wg").placeholder=imp?"165":"75";["yc","yl"].forEach(function(i){$(i).placeholder=imp?(i==="yc"?"22":"27.5"):(i==="yc"?"56":"70");});}
function scale(x,a){return'<ol class="tk-scale" aria-label="Size scale">'+L.map(function(s,i){var c=i===a?"is-a":i===x?"is-x":"";return"<li"+(c?' class="'+c+'"':"")+(i===a?' aria-label="'+s+', label to look for"':i===x?' aria-label="'+s+', your EU/US size"':"")+">"+s+"</li>";}).join("")+'</ol><p class="tk-scale-k"><span class="is-a"></span>Label to look for<span class="is-x"></span>Your EU/US size</p>';}
function acts(txt){var c=CAT[st.g];return'<div class="tk-actions">'+(c?'<a class="btn primary" href="'+esc(c[0])+'">'+esc(c[1])+"</a>":"")+K.cbtn(txt,"Copy Result","Result copied")+'<button type="button" class="btn sm" data-share>__LINK__<span class="tk-cl">Share</span></button></div>';}
function remember(o2){K.store.set("pc.size.last",o2);$("clr").hidden=false;}
function upd(){var p={g:st.g,fit:st.fit==="0"?"":st.fit,u:st.u==="i"?"i":""};if(st.m==="chart"){p.m="chart";var yc=num("yc"),yl=num("yl");if(yc>0)p.yc=r1(yc);if(yl>0)p.yl=r1(yl);var cr=[].map.call($("ct").querySelectorAll(".tk-chart-r"),function(r){var q=r.querySelectorAll("input"),n=String(q[0].value).replace(/[^A-Za-z0-9.]/g,"").slice(0,8),c=parseFloat(q[1].value),l=parseFloat(q[2].value);return n&&isFinite(c)?n+":"+r1(c)+(isFinite(l)?":"+r1(l):""):"";}).filter(Boolean);if(cr.length)p.c=cr.join(",");}var x=metric();if(st.g==="shoes"){if(x.f>0)p.f=r1(x.f);}else{if(x.h>0)p.h=Math.round(x.h);if(x.w>0)p.w=Math.round(x.w);}K.qs.put(p);}
function metric(){var imp=st.u==="i",h=imp?(num("hf")*12+(num("hn")||0))*2.54:num("hc"),w=imp?num("wg")*0.4536:num("wg"),f=imp?num("fl")*2.54:num("fl");return{h:h,w:w,f:f};}
function empty(t){said="";o.setAttribute("data-state","empty");o.innerHTML='<div class="tk-empty">__RULER__<p>'+esc(t)+"</p></div>";}
function alertBox(t,b){if(ready)sayD(t);o.setAttribute("data-state","error");o.innerHTML='<div class="tk-alert">__ALERT__<div><b>'+esc(t)+"</b><p>"+esc(b)+"</p></div></div>";}
function run(){upd();var x=metric(),imp=st.u==="i";
if(st.g==="shoes"){if(!(x.f>0)){empty("Enter your foot length to see your sneaker size.");return;}
if(x.f<20||x.f>33){alertBox("Check Your Numbers",imp?"Foot length 7.9 to 13 in, heel to longest toe.":"Foot length 20 to 33 cm, heel to longest toe.");return;}
remember({g:st.g,f:x.f,u:st.u});var s=shoeFor(x.f),r=s.r,big=s.low?"EU "+r[2]+" or smaller":s.top?"EU "+r[2]+" or bigger":"EU "+r[2];if(ready)sayD("Your sneaker size: "+big);
o.setAttribute("data-state","success");
o.innerHTML='<div class="tk-res"><p class="tk-res-k">Your sneaker size</p><p class="tk-big">'+esc(big)+'</p><p class="tk-res-sub">'+(s.low?"You are below our chart. Check the seller's chart in cm.":s.top?"You are at the top of our chart. Check the seller's chart in cm.":esc("US men "+r[1]+" · Chinese label "+r[0]*10+" mm"))+"</p>"+
acts("Sneakers: "+big+" (US men "+r[1]+", "+r[0]*10+" mm) for a "+r1(x.f)+" cm foot")+
'<details class="tk-more"><summary>How We Work This Out</summary><p>A '+esc(r1(x.f).toFixed(1))+" cm foot fits the "+esc(r[0])+" cm row of a common men's sneaker chart (we round up to the next half size). Check whether the model runs large or small at retail, and compare with the seller's chart.</p></details></div>";return;}
var hasH=x.h>0,hasW=x.w>0;if(!hasH||!hasW){empty("Enter your height and weight to see your size.");return;}
if(!(x.h>=120&&x.h<=230)||!(x.w>=35&&x.w<=250)){alertBox("Check Your Numbers",imp?"Height 3 ft 11 to 7 ft 6, weight 78 to 551 lb.":"Height 120 to 230 cm, weight 35 to 250 kg.");return;}
remember({g:st.g,h:x.h,w:x.w,fit:st.fit,u:st.u});
var z=sizeFor(st.g,x.h,x.w,parseFloat(st.fit)),west=st.g==="pants"?"US waist "+WA[z.x]+" · EU "+(WA[z.x]+16)+" · "+L[z.x]:"EU/US "+L[z.x]+" · EU "+EU[z.x];
var big=z.top?"4XL or bigger":L[z.a],sub=z.top?"You are at the top of our chart. Check the seller's chart in cm.":west;
var who=imp?esc($("hf").value||0)+"'"+esc($("hn").value||0)+'" and '+esc(Math.round(num("wg")))+" lb":esc(Math.round(x.h))+" cm and "+esc(Math.round(x.w))+" kg";
if(ready)sayD("Look for "+big);var txt=GN[st.g]+", "+FN[st.fit]+": look for "+(z.top?"4XL or bigger":L[z.a])+" ("+west+")";
o.setAttribute("data-state","success");
o.innerHTML='<div class="tk-res"><p class="tk-res-k">Look for this size on the seller\'s chart</p><p class="tk-big">'+esc(big)+'</p><p class="tk-res-sub">'+esc(sub)+"</p>"+scale(z.x,z.a)+acts(txt)+
'<p class="tk-next"><button type="button" class="tk-link" id="tochart">Compare with the seller\'s chart</button></p>'+
'<details class="tk-more"><summary>How We Work This Out</summary><p>At '+who+" a "+esc(FN[st.fit])+(st.g==="jackets"?" with room for layers":"")+" is usually "+esc(L[z.x])+" in EU/US sizing. Many Weidian and Taobao sellers use Asian sizing that runs about one size small, so the label to look for is "+esc(z.top?"4XL or bigger":L[z.a])+". A rough starting point: confirm it with the seller's chart in cm.</p></details></div>";}
o.addEventListener("click",function(e){if(e.target.closest&&e.target.closest("#tochart")){md.set("chart");st.m="chart";pane();upd();cmp();$("md").querySelector('[data-v="chart"]').focus();}});
["hc","hf","hn","wg","fl"].forEach(function(i){$(i).addEventListener("input",run);});
$("clr").addEventListener("click",function(){["hc","hf","hn","wg","fl"].forEach(function(i){$(i).value="";});K.store.del("pc.size.last");$("clr").hidden=true;run();$(st.g==="shoes"?"fl":st.u==="i"?"hf":"hc").focus();});
// seller's chart
var tb=$("ct");
function addRow(sz,c,l){var r=document.createElement("div");r.className="tk-chart-r";var n=tb.children.length+1;
r.innerHTML='<input class="tk-in" aria-label="Size, row '+n+'" maxlength="8" autocapitalize="characters"><input class="tk-in" data-n="1" type="number" inputmode="decimal" step="0.1" aria-label="Chest, row '+n+'"><input class="tk-in" data-n="2" type="number" inputmode="decimal" step="0.1" aria-label="Length, row '+n+'"><button type="button" class="tk-x" aria-label="Remove row '+n+'">__X__</button>';
var p=r.querySelectorAll("input");p[0].value=sz||"";p[1].value=c==null?"":c;p[2].value=l==null?"":l;tb.appendChild(r);return r;}
function rows(){var imp=st.u==="i",f=imp?2.54:1;return[].map.call(tb.querySelectorAll(".tk-chart-r"),function(r){var p=r.querySelectorAll("input"),c=parseFloat(p[1].value),l=parseFloat(p[2].value);return[p[0].value,isFinite(c)?c*f:null,isFinite(l)?l*f:null];});}
function cmp(){var imp=st.u==="i",f=imp?2.54:1,yc=num("yc")*f,yl=num("yl")*f,r=closest(yc,yl,rows().filter(function(x){return x[1]!==null;}));
if(st.m==="chart")upd();
if(!(yc>0)){co.setAttribute("data-state","empty");co.innerHTML='<div class="tk-empty">__RULER__<p>Measure your garment, then add the seller\'s sizes to find the closest one.</p></div>';return;}
if(!r.best){co.setAttribute("data-state","empty");co.innerHTML='<div class="tk-empty">__RULER__<p>Add at least one size from the seller\'s chart.</p></div>';return;}
var d=function(v){var x=r1(v/f);return(x>0?"+":"")+x+(imp?" in":" cm");},b=r.best;
var line=function(x){return"Chest "+d(x.dc)+(x.dl===null?"":", length "+d(x.dl));};
co.setAttribute("data-state","success");if(ready)sayD(b.n+" is closest");
co.innerHTML='<div class="tk-res tk-chart-res"><p class="tk-res-k">Closest to your garment</p><p class="tk-big">'+esc(b.n)+'</p><p class="tk-res-sub">'+esc(line(b))+' vs your garment</p><ul class="tk-rows">'+
r.res.map(function(x){return'<li><span class="k">'+esc(x.n)+(x===b?' <span class="tk-badge">Closest</span>':"")+'</span><span class="v">'+esc(line(x))+"</span></li>";}).join("")+"</ul>"+
'<p class="tk-foot">Plus means the seller\'s size is bigger than your garment. Within about '+(imp?"1 in":"2 cm")+" is usually close enough. For a relaxed fit pick the size just above.</p>"+
'<div class="tk-actions">'+K.cbtn("Seller's chart: "+b.n+" is closest ("+line(b)+")","Copy Result","Result copied")+'<button type="button" class="btn sm" data-share>__LINK__<span class="tk-cl">Share</span></button></div></div>';}
for(var k=0;k<3;k++)addRow();
$("ar").addEventListener("click",function(){var r=addRow();r.querySelector("input").focus();});
tb.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest(".tk-x");if(!b)return;var r=b.parentNode;var nx=r.nextElementSibling||r.previousElementSibling;r.parentNode.removeChild(r);if(!tb.children.length)addRow();(nx||tb.firstChild).querySelector("input").focus();cmp();});
$("pt").addEventListener("input",function(){var p=parseChart(this.value);if(p.length){tb.innerHTML="";p.forEach(function(r){addRow(r[0],r[1],r[2]);});$("pth").textContent=p.length+" size"+(p.length>1?"s":"")+" found";}else $("pth").textContent="";cmp();});
$("pc").addEventListener("input",function(e){if(e.target.id!=="pt")cmp();});
$("pt").addEventListener("paste",function(){setTimeout(function(){if(parseChart($("pt").value).length){$("pt").hidden=true;$("pa").hidden=false;$("pag").focus();}},0);});
$("pag").addEventListener("click",function(){$("pa").hidden=true;$("pt").hidden=false;$("pt").focus();$("pt").select();});
// initial state: URL (legacy ?h&w from the homepage teaser too), then this device's last numbers
var Q=function(k){return K.qs.get(k);},any=Q("h")||Q("w")||Q("g")||Q("f")||Q("m"),last=any?null:K.store.get("pc.size.last",null);
var u0=Q("u")==="i"||Q("u")==="m"?Q("u"):(K.store.get("pc.size.unit","m")==="i"?"i":"m");
var g0=Q("g")||(last&&last.g)||"tops";if(!GN.hasOwnProperty(g0))g0="tops";st.g=g0;ga.set(g0);
var f0=Q("fit")||(last&&last.fit)||"0";if(!FN.hasOwnProperty(f0))f0="0";st.fit=f0;fi.set(f0);
var h0=parseFloat(Q("h")||(last&&last.h)),w0=parseFloat(Q("w")||(last&&last.w)),ft0=parseFloat(Q("f")||(last&&last.f));
if(h0>=120&&h0<=230)setv("hc",Math.round(h0));if(w0>=35&&w0<=250)setv("wg",Math.round(w0));if(ft0>=20&&ft0<=33)setv("fl",r1(ft0));
$("clr").hidden=!last;
st.u="m";if(u0==="i"){units("i");}else{un1.set("m");un2.set("m");}
if(Q("m")==="chart"){st.m="chart";md.set("chart");}
var c0=Q("c");if(c0){var rr=String(c0).slice(0,400).split(",").map(function(x){var a=x.split(":");return[String(a[0]||"").replace(/[^A-Za-z0-9.]/g,"").slice(0,8),parseFloat(a[1]),parseFloat(a[2])];}).filter(function(x){return x[0]&&x[1]>0&&x[1]<500;}).slice(0,12);if(rr.length){tb.innerHTML="";rr.forEach(function(x){addRow(x[0],x[1],x[2]>0&&x[2]<500?x[2]:null);});}}
var yc0=parseFloat(Q("yc")),yl0=parseFloat(Q("yl"));if(yc0>0&&yc0<500)setv("yc",r1(yc0));if(yl0>0&&yl0<500)setv("yl",r1(yl0));
pane();run();cmp();ready=true;})();`, { __L__: js(SIZE_L), __EU__: js(SIZE_EU), __WA__: js(SIZE_WA), __SH__: js(SHOES), __G__: js(GADJ), __CAT__: js({ tops: ["/category/tops", "Shop Tops"], hoodies: ["/category/tops", "Shop Hoodies"], jackets: ["/category/jackets", "Shop Jackets"], pants: ["/category/pants", "Shop Pants"], shoes: ["/category/sneakers", "Shop Sneakers"] }), __SIZEFN__: SIZE_FN, __CHARTFN__: CHART_FN, __RULER__: qsvg(P_.ruler), __ALERT__: qsvg(P_.alert), __LINK__: qsvg(P_.link), __X__: qsvg(P_.x) });

const MEASURE_SVG = `<svg class="tk-measure-svg" viewBox="0 0 120 80" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
<path d="M44 6 30 12 14 26l8 12 10-6v42h56V32l10 6 8-12-16-14-14-6a16 16 0 0 1-32 0Z" opacity=".5"/>
<path d="M33 34h54" stroke-dasharray="3 3"/><path d="M33 31v6M87 31v6"/><path d="M96 9v65" stroke-dasharray="3 3"/><path d="M93 9h6M93 74h6"/></svg>`;

function sizeUI() {
  const unitSeg = (id, o = [["m", "cm, kg"], ["i", "ft, lb"]]) => segHtml(id, "Units", o, "m", "tk-toggle");
  return `${segHtml("md", "Mode", [["body", "From My Body"], ["chart", "Seller's Chart"]], "body", "tk-seg tk-mode")}
<section class="tk-card" id="pb" aria-label="Size from your body">
<div class="tk-field"><span class="tk-label" id="gal">What are you buying?</span>${segHtml("ga", "#gal", [["tops", "Tops", P_.tee], ["hoodies", "Hoodies", P_.hoodie], ["jackets", "Jackets", P_.jacket], ["pants", "Pants", P_.pants], ["shoes", "Sneakers", P_.shoe]], "tops", "tk-seg wrap")}</div>
<div class="tk-field"><div class="tk-label"><span>Your measurements</span>${unitSeg("un")}</div>
<div class="tk-grid2" id="body"><div class="tk-field" id="hm"><label class="tk-label" for="hc">Height</label>${unitIn("hc", "cm", 'type="number" inputmode="numeric" min="120" max="230" placeholder="180" autocomplete="off"')}</div>
<div class="tk-field" id="hi" hidden><label class="tk-label" for="hf">Height</label><div class="tk-pair">${unitIn("hf", "ft", 'type="number" inputmode="numeric" min="3" max="7" placeholder="5" aria-label="Height, feet" autocomplete="off"')}${unitIn("hn", "in", 'type="number" inputmode="numeric" min="0" max="11" placeholder="11" aria-label="Height, inches" autocomplete="off"')}</div></div>
<div class="tk-field"><label class="tk-label" for="wg">Weight</label><div class="tk-unitwrap"><input class="tk-in" id="wg" type="number" inputmode="decimal" min="35" max="551" placeholder="75" autocomplete="off"><span class="tk-unit" data-u="wg">kg</span></div></div></div>
<div class="tk-field" id="foot" hidden><label class="tk-label" for="fl">Foot length<span class="tk-hint">Heel to longest toe, standing</span></label><div class="tk-unitwrap"><input class="tk-in" id="fl" type="number" inputmode="decimal" step="0.1" placeholder="27" autocomplete="off"><span class="tk-unit" data-u="fl">cm</span></div></div></div>
<div class="tk-field" id="fitf"><span class="tk-label" id="fil">Fit you like</span>${segHtml("fi", "#fil", [["-0.5", "Fitted"], ["0", "Regular"], ["0.5", "Relaxed"], ["1", "Oversized"]], "0")}</div>
<div class="tk-out" id="out" data-state="empty"></div>
<p class="tk-clear"><button type="button" class="tk-link" id="clr" hidden>Clear my numbers</button></p>
</section>
<section class="tk-card" id="pc" hidden aria-label="Compare with the seller's chart">
<div class="tk-field"><div class="tk-label"><span>1. Measure a garment that fits you</span>${unitSeg("un2", [["m", "cm"], ["i", "in"]])}</div>
<div class="tk-measure">${MEASURE_SVG}<p>Lay it flat. Chest is pit to pit, length is from the top of the shoulder to the hem. Measure it the way the seller's chart does.</p></div>
<div class="tk-grid2"><div class="tk-field"><label class="tk-label" for="yc">Chest</label><div class="tk-unitwrap"><input class="tk-in" id="yc" type="number" inputmode="decimal" step="0.1" placeholder="56" autocomplete="off"><span class="tk-unit" data-u="yc">cm</span></div></div>
<div class="tk-field"><label class="tk-label" for="yl">Length</label><div class="tk-unitwrap"><input class="tk-in" id="yl" type="number" inputmode="decimal" step="0.1" placeholder="70" autocomplete="off"><span class="tk-unit" data-u="yl">cm</span></div></div></div></div>
<div class="tk-field"><div class="tk-label"><label for="pt">2. Add the seller's sizes</label><span class="tk-hint" id="pth" aria-live="polite"></span></div>
<textarea class="tk-in tk-paste" id="pt" rows="3" aria-describedby="pth" placeholder="Paste the size chart, one size per line:&#10;M 54 70&#10;L 56 72" spellcheck="false"></textarea>
<div class="tk-pasted" id="pa" hidden><button type="button" class="btn sm secondary" id="pag">Paste Again</button><span>Edit the sizes below or paste a new chart.</span></div>
<div class="tk-chart"><div class="tk-chart-h" aria-hidden="true"><span>Size</span><span>Chest</span><span>Length</span><span></span></div><div id="ct"></div></div>
<div><button type="button" class="btn sm secondary" id="ar">${svg(P_.plus)}Add Row</button></div></div>
<div class="tk-out" id="cout" data-state="empty"></div>
</section>
<script>${KIT_JS}
${SIZE_JS}</script>`;
}

// ------------------------------------------------------------------ parcel tracker
const TRACK_EX = [["YunExpress", "YT2412345678901234"], ["China Post", "LX123456789CN"], ["UPS", "1Z999AA10123456784"]];
const TRACK_EMPTY = `<div class="tk-empty">${svg(P_.pin)}<p>Paste a tracking number to see the carrier.</p><div class="tk-chips"><span>Try:</span>${TRACK_EX.map(([n, v]) => `<button type="button" class="tk-chip" data-ex="${esc(v)}">${esc(n)}</button>`).join("")}</div></div>`;
const TRACK_JS = fill(String.raw`(function(){var C=__C__,P=__P__,KEY="pc.track",U="https://t.17track.net/en#nums=";
__TRACKFN__
var $=K.$,esc=K.esc,tn=$("tn"),dt=$("dt"),out=$("out"),go=$("go"),rc=$("rc"),rl=$("rl"),cur=[],CP=false,lastRun=null,EMPTY=__EMPTY__;
function load(){var v=K.store.get(KEY,[]);return Array.isArray(v)?v.filter(function(x){return x&&/^(?=[A-Z]*\d)[A-Z0-9]{8,40}$/.test(x.n);}):[];}
function save(a){K.store.set(KEY,a.slice(0,10));}
function off(c,n){return c&&c.url?c.url.replace("{n}",encodeURIComponent(n)):"";}
function multi(){return /\n/.test(tn.value);}
function grow(){tn.style.height="auto";tn.style.height=Math.min(Math.max(tn.scrollHeight,56),240)+"px";}
function kbd(){$("kb").innerHTML=multi()?"<kbd>"+(K.MAC?"Cmd":"Ctrl")+"</kbd><kbd>Enter</kbd> to track":"<kbd>Enter</kbd> to track";}
function detectChip(){var v=tn.value.trim(),ns=split(v);$("tx").hidden=!v;$("tp").hidden=!CP||!!v;tn.classList.toggle("has-v",!!v);go.classList.toggle("primary",v!==lastRun);kbd();
if(!v){dt.innerHTML="";$("th").textContent="";return;}
$("th").textContent=ns.length>1?ns.length+" numbers":"";
if(ns.length>1){var k=ns.filter(function(n){return detect(n);}).length;dt.innerHTML='<span class="tk-dt-s">'+(k===ns.length?"All "+k+" recognised":k+" of "+ns.length+" recognised")+"</span>";return;}
if(!ns.length){dt.innerHTML='<span class="tk-dt-s">'+(norm(v).length<8?"Keep typing":"Not recognised yet")+"</span>";return;}
var c=detect(ns[0]);dt.innerHTML=c?'<span class="tk-dt-s">Detected</span><span class="tk-badge">'+esc(c.name)+"</span>"+(c.likely?'<span class="tk-badge tk-soft">Likely</span>':""):'<span class="tk-dt-s">Not recognised yet. The universal tracker usually finds it.</span>';}
function block(n){var c=detect(n),o=off(c,n),uni=U+encodeURIComponent(n),h,body="",act;
if(c){h=esc(c.name)+(c.likely?' <span class="tk-badge">Likely</span>':"");body=c.note?'<p class="tk-trk-note">'+esc(c.note)+"</p>":"";
act=o?'<a class="btn primary" href="'+esc(o)+'" target="_blank" rel="noopener">Open '+esc(c.name)+' Tracking __EXT__</a><a class="btn" href="'+esc(uni)+'" target="_blank" rel="noopener">Universal Tracker</a>'
:'<a class="btn primary" href="'+esc(uni)+'" target="_blank" rel="noopener">Open Universal Tracker __EXT__</a>';}
else{h="Carrier Not Recognised";body='<p class="tk-trk-note">Your agent\'s parcel page names the carrier. The universal tracker usually finds it anyway.</p>';act='<a class="btn primary" href="'+esc(uni)+'" target="_blank" rel="noopener">Open Universal Tracker __EXT__</a>';}
return'<article class="tk-res tk-trk"><div class="tk-trk-h"><h3>'+h+'</h3></div><div class="tk-trk-n"><span class="tk-num">'+esc(n)+"</span>"+K.cbtn(n,"Copy","Tracking number copied")+"</div>"+body+'<div class="tk-actions">'+act+"</div></article>";}
function recent(){var a=load().filter(function(x){return cur.indexOf(x.n)<0;});rc.hidden=!a.length;
rl.innerHTML=a.map(function(x){var c=detect(x.n),o=off(c,x.n)||U+encodeURIComponent(x.n);
return'<li><button type="button" data-run="'+esc(x.n)+'" aria-label="Track '+esc(x.n)+' again"><span><span class="t tk-num">'+esc(x.n)+'</span><span class="s">'+esc((c?c.name:"Carrier not recognised")+" · "+K.ago(x.t))+'</span></span></button><a class="btn sm" href="'+esc(o)+'" target="_blank" rel="noopener" aria-label="Open tracking for '+esc(x.n)+'">Open</a><button type="button" class="tk-x" data-rm="'+esc(x.n)+'" aria-label="Remove '+esc(x.n)+'">__X__</button></li>';}).join("");}
function run(){var v=tn.value.trim(),ns=split(v);
if(!v){cur=[];lastRun=null;go.classList.add("primary");out.setAttribute("data-state","empty");out.innerHTML=EMPTY;K.qs.put({});recent();return;}
if(!ns.length){cur=[];lastRun=null;go.classList.add("primary");out.setAttribute("data-state","error");out.innerHTML='<div class="tk-alert" role="alert">__ALERT__<div><b>That Does Not Look Like A Tracking Number</b><p>Copy it from your agent\'s parcel page once the parcel has shipped.</p></div></div>';recent();return;}
cur=ns;lastRun=v;go.classList.remove("primary");out.setAttribute("data-state","success");
out.innerHTML=(ns.length>1?'<p class="tk-res-k tk-trk-count">'+ns.length+" parcels</p>":"")+ns.map(block).join("")+(ns.length>1?'<div class="tk-actions"><a class="btn" href="'+esc(U+ns.map(encodeURIComponent).join(","))+'" target="_blank" rel="noopener">Track All '+ns.length+" On The Universal Tracker __EXT__</a></div>":"");
var a=load().filter(function(x){return ns.indexOf(x.n)<0;});save(ns.map(function(n){return{n:n,t:Date.now()};}).concat(a));K.qs.put({n:ns.join(",")});recent();K.say(ns.length>1?ns.length+" parcels ready to track":"Carrier "+(detect(ns[0])?detect(ns[0]).name:"not recognised"));}
var dchip=K.deb(detectChip,150);
tn.addEventListener("input",function(){grow();dchip();});
tn.addEventListener("paste",function(){setTimeout(function(){grow();detectChip();if(split(tn.value).length)run();},0);});
tn.addEventListener("tk-paste",function(){grow();detectChip();if(split(tn.value).length)run();});
tn.addEventListener("keydown",function(e){if(e.key!=="Enter"||e.shiftKey)return;if(multi()&&!(e.metaKey||e.ctrlKey))return;e.preventDefault();run();});
$("tf").addEventListener("submit",function(e){e.preventDefault();run();});
$("tx").addEventListener("click",function(){tn.value="";grow();detectChip();run();tn.focus();});
K.paste($("tp"),tn);CP=!$("tp").hidden;
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-run],[data-rm],[data-ex]");if(!b)return;
if(b.hasAttribute("data-ex")){tn.value=b.getAttribute("data-ex");grow();detectChip();run();tn.focus();return;}
if(b.hasAttribute("data-run")){tn.value=b.getAttribute("data-run");grow();detectChip();run();tn.focus();return;}
var n=b.getAttribute("data-rm"),li=b.closest("li"),nx=li&&(li.nextElementSibling||li.previousElementSibling);save(load().filter(function(x){return x.n!==n;}));recent();K.say("Removed "+n);
var f=nx&&rl.querySelector('[data-rm="'+nx.querySelector("[data-rm]").getAttribute("data-rm")+'"]');(f||tn).focus();});
$("clr").addEventListener("click",function(){K.store.del(KEY);recent();K.say("Recent numbers cleared");tn.focus();});
var q=K.qs.get("n");if(q){tn.value=String(q).slice(0,400).split(",").join("\n");grow();detectChip();run();}else{detectChip();recent();}})();`, { __C__: js(CARRIERS.map(c => [c.id, c.name, c.re.source, c.url, c.likely ? 1 : 0])), __P__: js(POSTS), __TRACKFN__: TRACK_FN, __EMPTY__: js(TRACK_EMPTY), __EXT__: qsvg(P_.ext), __X__: qsvg(P_.x), __ALERT__: qsvg(P_.alert) });

function trackUI() {
  const fmts = CARRIERS.filter(c => c.id !== "s10").map(c => `<li><b>${esc(c.name)}</b><span>${esc(c.fmt)}, like <code>${esc(c.ex)}</code></span></li>`).join("") +
    `<li><b>${esc(Object.values(POSTS).map(p => p[0]).filter((v, i, a) => a.indexOf(v) === i).join(", "))}, EMS</b><span>${esc(CARRIERS.find(c => c.id === "s10").fmt.replace(/ \(.*\)$/, ""))}, like <code>LX123456789CN</code> or <code>EA123456789CN</code></span></li>`;
  return `<section class="tk-card" aria-label="Parcel tracker"><form id="tf" class="tk-field" novalidate action="/tools/parcel-tracker" method="get">
<div class="tk-label"><label for="tn">Tracking number</label><span class="tk-hint" id="th"></span></div>
<div class="tk-inwrap"><span class="tk-in-ic">${svg(P_.box)}</span><textarea class="tk-in tk-in-lg tk-grow" id="tn" name="n" rows="1" placeholder="Paste tracking number" aria-describedby="th" autocomplete="off" autocapitalize="characters" autocorrect="off" spellcheck="false" enterkeyhint="go"></textarea>
<span class="tk-in-act"><button type="button" class="btn sm secondary" id="tp">Paste</button><button type="button" class="tk-x" id="tx" hidden aria-label="Clear">${svg(P_.x)}</button></span></div>
<div class="tk-detect" id="dt" aria-live="polite"></div>
<div class="tk-row tk-go"><button class="btn primary" id="go" type="submit">Track Parcel</button><span class="tk-kbd" id="kb" aria-hidden="true"><kbd>Enter</kbd> to track</span></div>
</form><div class="tk-out" id="out" data-state="empty">${TRACK_EMPTY}</div></section>
<section class="tk-recent" id="rc" hidden aria-labelledby="rch"><div class="tk-recent-h"><h2 id="rch">Recent</h2><button type="button" class="btn ghost sm" id="clr">Clear</button></div><ul id="rl"></ul></section>
<details class="tk-more tk-fmts"><summary>${svg("truck", "sm")}Supported Carriers</summary><p>We spot these from the number's format. Examples show the format only.</p><ul class="tk-fmt">${fmts}</ul></details>
<script>${KIT_JS}
${TRACK_JS}</script>`;
}

export const TOOL_UI9 = { "shipping-calculator": shipUI, "size-estimator": sizeUI, "parcel-tracker": trackUI };

// ------------------------------------------------------------------ page shell (spec 1.2 and 1.6)
const TRUST = { "shipping-calculator": ["Free", "No sign-up", "Runs in your browser"], "size-estimator": ["Free", "No sign-up", "Runs in your browser"],
  "parcel-tracker": ["Free", "No sign-up", "Runs in your browser"], "qc-checker": ["Free", "No sign-up"], "link-converter": ["Free", "No sign-up", "Nothing is stored"] };
export const tkHero = (slug, name, h1, lead, trust = TRUST[slug] || ["Free", "No sign-up"]) =>
  `<header class="tk-hero"><span class="tk-hero-ic">${toolIcon(slug)}</span><p class="tk-name">${esc(name)}</p><h1>${esc(h1)}</h1><p class="lead">${esc(lead)}</p>` +
  `<ul class="tk-trust">${trust.map(t => `<li>${svg(P_.check)}${esc(t)}</li>`).join("")}</ul></header>`;
export const tkRelated = path => `<h2 class="h-ic">${icTile("grid")}More Free Tools</h2><div class="tk-related">${TOOL_LINKS.filter(([, u]) => u !== path).map(([n, u]) => {
  const k = u.replace(/^\/tools\//, ""); return `<a href="${u}"><span class="tk-ic">${toolIcon(k)}</span><span><b>${esc(n)}</b><span>${esc(TOOL_SHORT[k] || "")}</span></span></a>`; }).join("")}</div>
<p><a href="/how-to-order">${svg("play", "sm")}How to order</a></p>`;

const faqLd = faq => ({ "@context": "https://schema.org", "@type": "FAQPage",
  mainEntity: faq.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) });

// Same shape as pages.js renderTool(): a page() Response, or null for an unknown slug. baseCss is pages.js TOOL_CSS.
export function toolPage9(s, baseCss = "") {
  const t = Object.prototype.hasOwnProperty.call(TOOLS9, s) ? TOOLS9[s] : null; if (!t) return null;
  const path = "/tools/" + s; const bc = crumbs([["Home", "/"], ["Tools", "/tools"], [t.name, path]]);
  const app = { "@context": "https://schema.org", "@type": "WebApplication", name: t.name + ": Puro Classico", url: SITE + path, applicationCategory: "UtilitiesApplication", operatingSystem: "Any", offers: { "@type": "Offer", price: "0", priceCurrency: "USD" }, description: t.desc };
  const faq = `<h2 class="h-ic">${icTile("help")}FAQ</h2><div class="faq">${t.faq.map(([q, a]) => `<details><summary>${esc(q)}</summary><p>${esc(a)}</p></details>`).join("")}</div>`;
  const body = `${baseCss}<div class="tk-page${s === "shipping-calculator" ? " wide" : ""}" data-tool="${s}">${bc.html}${tkHero(s, t.name, t.h1 || t.name, t.lead)}
${TOOL_UI9[s]()}
<div class="tk-below">${howItWorks(s, t.about)}${faq}
${tkRelated(path)}</div></div>`;
  return page({ title: t.title, desc: t.desc, path, body, jsonld: [bc.data, app, faqLd(t.faq)] });
}
