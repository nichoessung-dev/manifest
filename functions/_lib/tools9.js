// v9 tools (29 Oct 2026): the shipping calculator (now with the old weight estimator's item list as an "add items" step),
// the size estimator and the parcel tracker. Installed as functions/_lib/tools9.js by tools_patch.py; pages.js merges
// TOOLS9 into TOOLS (hub, sitemap) and hands these three slugs to toolPage9(). Everything runs in the browser: no
// network calls, no keys. Inline scripts are small vanilla JS and escape everything they print.
import { SITE, esc, crumbs, page, TOOL_LINKS } from "./site.js";

// JSON for an inline <script>: "<" is escaped so no value can close the script tag.
const js = v => JSON.stringify(v).replace(/</g, "\\u003c");
const ESC = String.raw`function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c];});}`;

// Typical shipped weight per item type in grams, light packaging included. These are the weight estimator's numbers
// (pages.js TYPE_WEIGHT uses the same ones for the product facts).
export const ITEM_WEIGHTS = [["T-shirt", 250], ["Shirt / polo", 330], ["Shorts", 350], ["Hoodie / sweater", 700], ["Pants / jeans", 600],
  ["Light jacket", 700], ["Puffer / heavy jacket", 1100], ["Sneakers (no box)", 900], ["Sneakers (with box)", 1300], ["Bag", 550],
  ["Cap / beanie", 220], ["Belt / small accessory", 200]];
// Shipping ballpark per region: [line, base USD, USD per kg]. Unchanged from the live calculator.
const ZONES = { "United States": "na", "Canada": "na", "United Kingdom": "eu", "Germany": "eu", "France": "eu", "Netherlands": "eu", "Italy": "eu",
  "Spain": "eu", "Poland": "eu", "Ireland": "eu", "Norway": "nordic", "Sweden": "nordic", "Denmark": "nordic", "Finland": "nordic", "Rest of Europe": "eu",
  "Australia": "oce", "New Zealand": "oce", "Rest of world": "row" };
const RATES = { nordic: [["Economy", 5, 7], ["Registered / special line", 7, 10], ["Express (DHL/EMS)", 9, 15]], eu: [["Economy", 5, 6.5], ["Registered / special line", 7, 9.5], ["Express (DHL/EMS)", 8, 14]],
  na: [["Economy", 6, 8], ["Registered / special line", 8, 11], ["Express (DHL/EMS)", 9, 16]], oce: [["Economy", 6, 9], ["Registered / special line", 8, 12], ["Express (DHL/EMS)", 10, 17]],
  row: [["Economy", 6, 9], ["Registered / special line", 8, 12], ["Express (DHL/EMS)", 10, 18]] };

// Carrier detection for the parcel tracker. Checked top to bottom on the number in upper case without spaces or dashes;
// the first match wins, so the specific formats come before the all-digit ones. `url` is the carrier's own tracking page
// ("{n}" is replaced by the number); null means we only offer the universal tracker. All-digit formats are shared by
// several carriers, so those are shown as "likely".
export const CARRIERS = [
  // UPS: "1Z" + 16 letters/digits. Example: 1Z999AA10123456784
  { id: "ups", name: "UPS", re: /^1Z[0-9A-Z]{16}$/, url: "https://www.ups.com/track?tracknum={n}" },
  // YunExpress (China to Europe/US line): "YT" + 16 digits. Example: YT2412345678901234
  { id: "yun", name: "YunExpress", re: /^YT\d{16}$/, url: "https://www.yuntrack.com/parcelTracking?id={n}" },
  // Cainiao (AliExpress / Cainiao lines): "LP" + 14 digits. Example: LP00512345678901
  { id: "cainiao", name: "Cainiao", re: /^LP\d{14}$/, url: "https://global.cainiao.com/newDetail.htm?mailNoList={n}" },
  // 4PX: "4PX" + 10 to 16 digits + "CN". Example: 4PX3000123456789CN
  { id: "4px", name: "4PX", re: /^4PX\d{10,16}CN$/, url: "https://track.4px.com/#/result/0/{n}" },
  // SF Express: "SF" + 12 or 13 digits. Example: SF1234567890123
  { id: "sf", name: "SF Express", re: /^SF\d{12,13}$/, url: null },
  // Evri (UK last mile, formerly Hermes): "H" + 15 letters/digits. Example: H00A0A0012345678
  { id: "evri", name: "Evri", re: /^H[0-9A-Z]{15}$/, url: "https://www.evri.com/track/parcel/{n}/details" },
  // DHL piece and parcel IDs: "JJD" + digits (DHL Express piece) or "JVGL" + digits (DHL Parcel). Example: JVGL0123456789012345
  { id: "dhl", name: "DHL", re: /^(?:JJD\d{10,20}|JVGL\d{10,20})$/, url: "https://www.dhl.com/global-en/home/tracking/tracking-express.html?submit=1&tracking-id={n}" },
  // USPS with the 420 + ZIP routing prefix: "420" + 5 or 9 digit ZIP + the 91-95 number. Example: 420902109400111202555842332669
  { id: "usps420", name: "USPS", re: /^420\d{5}(?:\d{4})?9[1-5]\d{18,20}$/, url: "https://tools.usps.com/go/TrackConfirmAction?tLabels={n}" },
  // PostNL domestic and parcel codes: "3S" + 4 letters + digits. Example: 3SABCD1234567
  { id: "postnl", name: "PostNL", re: /^3S[A-Z]{4}\d{6,9}$/, url: "https://jouw.postnl.nl/track-and-trace/{n}" },
  // DHL eCommerce: "00340434" + 12 digits. Example: 00340434123456789012
  { id: "dhlec", name: "DHL", re: /^00340434\d{12}$/, url: "https://www.dhl.com/global-en/home/tracking/tracking-express.html?submit=1&tracking-id={n}" },
  // UPU S10 international post format (EMS, ePacket, registered mail): 2 letters + 9 digits + country code.
  // Example: LX123456789CN (China Post ePacket), EA123456789CN (EMS), RR123456789NL (PostNL). Handled by POSTS below.
  { id: "s10", name: "Post", re: /^[A-Z]{2}\d{9}[A-Z]{2}$/, url: null },
  // Cainiao numbers that start with CN (after s10, so CN123456789CN stays a China Post parcel). Example: CNGBR0012345678
  { id: "cainiao2", name: "Cainiao", re: /^CN[A-Z]{0,4}\d{9,16}[A-Z]{0,2}$/, url: "https://global.cainiao.com/newDetail.htm?mailNoList={n}" },
  // USPS: 20 to 22 digits starting 91 to 95. Example: 9400111202555842332669
  { id: "usps", name: "USPS", re: /^9[1-5]\d{18,20}$/, url: "https://tools.usps.com/go/TrackConfirmAction?tLabels={n}" },
  // DPD: 14 digits. Example: 01234567890123 (shared format, shown as likely)
  { id: "dpd", name: "DPD", re: /^\d{14}$/, url: "https://tracking.dpd.de/status/en_US/parcel/{n}", likely: 1 },
  // FedEx: 12 or 15 digits. Example: 123456789012 (shared format, shown as likely)
  { id: "fedex", name: "FedEx", re: /^(?:\d{12}|\d{15})$/, url: "https://www.fedex.com/fedextrack/?trknbr={n}", likely: 1 },
  // GLS: 11 digits. Example: 12345678901 (shared format, shown as likely)
  { id: "gls", name: "GLS", re: /^\d{11}$/, url: "https://gls-group.com/EU/en/parcel-tracking?match={n}", likely: 1 },
  // DHL Express waybill: 10 digits. Example: 1234567890 (shared format, shown as likely)
  { id: "dhlx", name: "DHL Express", re: /^\d{10}$/, url: "https://www.dhl.com/global-en/home/tracking/tracking-express.html?submit=1&tracking-id={n}", likely: 1 },
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

const CSS9 = `<style>.tool .seg{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px}.tool .seg button{min-height:44px;padding:0 16px;border-radius:999px;border:1px solid var(--line);background:transparent;color:var(--ink);font:inherit;font-size:14px;font-weight:600;cursor:pointer}.tool .seg button[aria-pressed="true"]{background:var(--fill);color:var(--fill-ink);border-color:var(--fill)}
.tool .grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.tool .grid2>div{min-width:0}.tool .pair{display:flex;gap:8px}.tool .pair input{min-width:0}.tool .lbl{margin-top:12px}
.tool input,.tool select,.tool textarea{font-size:16px}.tool textarea{width:100%;min-height:96px;background:var(--bg);color:var(--ink);border:1px solid var(--input-line,var(--line));border-radius:12px;padding:12px 14px;font:inherit;font-size:16px;resize:vertical}
.tool details.items{margin-top:14px;border:1px solid var(--line);border-radius:12px;padding:0 14px}.tool details.items summary{min-height:48px;display:flex;align-items:center;cursor:pointer;font-weight:600;color:var(--ink)}.tool details.items[open]{padding-bottom:12px}
.tool .qty{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:6px 0;border-top:1px solid var(--line)}.tool .qty span small{color:var(--muted)}.tool .qty input{width:84px;text-align:center}
.tool .card9{border:1px solid var(--line);border-radius:12px;padding:14px;margin-top:12px;background:var(--bg)}.tool .card9 h2{margin:0 0 4px;font-size:16px;line-height:1.35;letter-spacing:-.01em}.tool .card9 .num{font-variant-numeric:tabular-nums;word-break:break-all;color:var(--muted);font-size:14px}.tool .card9 .row{margin-top:10px}.tool .card9 button.btn{background:transparent;color:var(--ink);border:1px solid var(--line)}
.tool .big{font-size:28px;font-weight:700;letter-spacing:-.02em;color:var(--ink)}.tool .muted{color:var(--muted)}.tool .best{outline:2px solid var(--fill);outline-offset:-2px}
.tool table.chart input{padding:10px}.tool table.chart th{text-align:left;font-size:13px;color:var(--muted);font-weight:500;padding:4px}.tool .btn{min-height:44px}.tool .linkbtn{background:none;border:0;color:var(--muted);font:inherit;font-size:14px;text-decoration:underline;cursor:pointer;padding:8px 0;min-height:44px}
.tool [hidden]{display:none!important}</style>`;

export const TOOLS9 = {
  "shipping-calculator": { name: "Shipping Calculator", h1: "Shipping Calculator: Weight And Cost In One Place",
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

export const TOOL_UI9 = {
  "shipping-calculator": () => `<div class="tool"><div class="grid2"><div><label for="co">Destination</label><select id="co"></select></div><div><label for="kg">Parcel weight (kg)</label><input id="kg" type="number" inputmode="decimal" min="0" step="0.1" placeholder="e.g. 2.5"></div></div>
<details class="items" id="it"><summary>Don't know the weight? Add your items</summary><div id="wt"></div><button type="button" class="linkbtn" id="rs">Reset items</button></details>
<div class="out" id="out" role="status" aria-live="polite">Pick a destination and weight.</div></div>
<script>${String.raw`(function(){var W=${js(ITEM_WEIGHTS)},Z=${js(ZONES)},RT=${js(RATES)};
${ESC}
var co=document.getElementById("co"),kg=document.getElementById("kg"),wt=document.getElementById("wt"),out=document.getElementById("out"),fromItems=false;
co.innerHTML=Object.keys(Z).map(function(k){return "<option>"+esc(k)+"</option>";}).join("");
wt.innerHTML=W.map(function(w,i){return '<div class="qty"><label for="q'+i+'" style="margin:0">'+esc(w[0])+' <small class="muted">~'+w[1]+' g</small></label><input id="q'+i+'" type="number" inputmode="numeric" min="0" value="0" data-i="'+i+'"></div>';}).join("");
var q=new URLSearchParams(location.search).get("kg");if(q&&isFinite(+q)&&+q>0)kg.value=String(+q);
function items(){var g=0,n=0;wt.querySelectorAll("input").forEach(function(x){var c=Math.max(0,Math.min(99,parseInt(x.value,10)||0));g+=c*W[+x.dataset.i][1];n+=c;});return{g:g,n:n};}
function money(v){return v.toLocaleString("en-US");}
function run(){var k=parseFloat(kg.value),it=items(),pre="";if(fromItems&&it.n)pre="Estimated shipped weight: <b>~"+(it.g/1000).toFixed(2)+" kg</b> for "+it.n+" item"+(it.n>1?"s":"")+".\n\n";
if(!k||k<=0){out.textContent="Pick a destination and weight, or add your items.";return;}
if(k>30){out.textContent="Too heavy for a parcel estimate (over 30 kg). Split it into several parcels or ask your agent for a freight quote.";return;}
out.innerHTML=pre+RT[Z[co.value]].map(function(l){var lo=Math.round(l[1]+l[2]*k*0.85),hi=Math.round(l[1]+l[2]*k*1.2);return esc(l[0])+": <b>~$"+(lo===hi?money(lo):money(lo)+"-"+money(hi))+"</b>";}).join("\n")+'\n\n<span class="muted">Ballpark only. Check your agent\'s estimator for the real price.</span>';}
wt.addEventListener("input",function(){var it=items();fromItems=true;kg.value=it.n?(it.g/1000).toFixed(2):"";run();});
kg.addEventListener("input",function(){fromItems=false;run();});co.onchange=run;
document.getElementById("rs").onclick=function(){wt.querySelectorAll("input").forEach(function(x){x.value=0;});fromItems=false;kg.value="";run();};
run();})();`}</script>`,

  "size-estimator": () => `<div class="tool"><div class="seg" role="group" aria-label="Mode"><button type="button" id="mb" aria-pressed="true">From my body</button><button type="button" id="mc" aria-pressed="false">Compare with the seller chart</button></div>
<div id="pb"><div class="grid2"><div><label for="ga">Garment</label><select id="ga"><option value="tops">T-shirts and tops</option><option value="hoodies">Hoodies and sweaters</option><option value="jackets">Jackets and coats</option><option value="pants">Pants and jeans</option><option value="shoes">Sneakers and shoes</option></select></div>
<div><label for="un">Units</label><select id="un"><option value="m">cm and kg</option><option value="i">ft/in and lb</option></select></div></div>
<div id="body" class="grid2 lbl"><div id="hm"><label for="hc">Height (cm)</label><input id="hc" type="number" inputmode="numeric" min="120" max="230" placeholder="180"></div>
<div id="hi" hidden><label for="hf">Height (ft and in)</label><div class="pair"><input id="hf" type="number" inputmode="numeric" min="4" max="7" placeholder="5" aria-label="Feet"><input id="hn" type="number" inputmode="numeric" min="0" max="11" placeholder="11" aria-label="Inches"></div></div>
<div><label for="wg" id="wl">Weight (kg)</label><input id="wg" type="number" inputmode="decimal" min="35" max="250" placeholder="75"></div>
<div><label for="fi">Fit you like</label><select id="fi"><option value="-0.5">Fitted</option><option value="0" selected>Regular</option><option value="0.5">Relaxed</option><option value="1">Oversized</option></select></div></div>
<div id="foot" class="grid2 lbl" hidden><div><label for="fl" id="fll">Foot length (cm)</label><input id="fl" type="number" inputmode="decimal" step="0.1" placeholder="27"></div></div>
<div class="out" id="out" role="status" aria-live="polite">Enter your height and weight.</div></div>
<div id="pc" hidden><p class="muted" style="margin:0 0 10px">Lay a garment you own that fits well flat and measure it the same way the seller's chart does (pit to pit or full chest), in cm.</p>
<div class="grid2"><div><label for="yc">Your chest (cm)</label><input id="yc" type="number" inputmode="decimal" placeholder="56"></div><div><label for="yl">Your length (cm)</label><input id="yl" type="number" inputmode="decimal" placeholder="70"></div></div>
<label for="pt" class="lbl">Paste the seller chart (optional): one size per line, like "L 56 72"</label><textarea id="pt" placeholder="M 54 70&#10;L 56 72&#10;XL 58 74"></textarea>
<table class="chart lbl" id="ct"><thead><tr><th>Size</th><th>Chest (cm)</th><th>Length (cm)</th></tr></thead><tbody></tbody></table><button type="button" class="linkbtn" id="ar">Add a row</button>
<div class="out" id="cout" role="status" aria-live="polite">Fill in your measurements and at least one chart row.</div></div></div>
<script>${String.raw`(function(){${ESC}
var $=function(i){return document.getElementById(i);};
var L=["XS","S","M","L","XL","XXL","3XL","4XL"],EU=[44,46,48,50,52,54,56,58],WA=[28,30,32,34,36,38,40,42];
// Common men's / unisex sneaker chart: [foot length cm, US men, EU]
var SH=[[24,6,38.5],[24.5,6.5,39],[25,7,40],[25.5,7.5,40.5],[26,8,41],[26.5,8.5,42],[27,9,42.5],[27.5,9.5,43],[28,10,44],[28.5,10.5,44.5],[29,11,45],[29.5,11.5,45.5],[30,12,46],[30.5,12.5,47],[31,13,47.5]];
var GADJ={tops:0,hoodies:0.25,jackets:0.5,pants:0},FN={"-0.5":"fitted","0":"regular","0.5":"relaxed","1":"oversized"};
function mode(c){$("mb").setAttribute("aria-pressed",c?"false":"true");$("mc").setAttribute("aria-pressed",c?"true":"false");$("pb").hidden=!!c;$("pc").hidden=!c;}
$("mb").onclick=function(){mode(0);};$("mc").onclick=function(){mode(1);};
function num(i){var v=parseFloat($(i).value);return isFinite(v)?v:NaN;}
function run(){var g=$("ga").value,imp=$("un").value==="i",o=$("out"),shoe=g==="shoes";
$("hm").hidden=imp;$("hi").hidden=!imp;$("wl").textContent=imp?"Weight (lb)":"Weight (kg)";$("fll").textContent=imp?"Foot length (in)":"Foot length (cm)";$("body").hidden=shoe;$("foot").hidden=!shoe;
if(shoe){var f=num("fl");if(imp)f*=2.54;if(!(f>=20&&f<=33)){o.textContent="Enter your foot length, heel to longest toe, standing.";return;}
var r=SH[SH.length-1],i;for(i=0;i<SH.length;i++)if(SH[i][0]>=f-0.05){r=SH[i];break;}
o.innerHTML='<span class="big">EU '+esc(r[2])+"</span>\nUS men "+esc(r[1])+" · Chinese label "+esc(r[0]*10)+" mm\n\n"+'<span class="muted">Why: a '+esc(f.toFixed(1))+" cm foot fits the "+esc(r[0])+" cm row of a common men's sneaker chart (we round up to the next half size). Check whether the model runs large or small at retail, and compare with the seller's chart.</span>";return;}
var h=imp?(num("hf")*12+(num("hn")||0))*2.54:num("hc"),w=imp?num("wg")*0.4536:num("wg"),fit=$("fi").value;
if(!(h>=120&&h<=230)||!(w>=35&&w<=250)){o.textContent="Enter your height and weight.";return;}
var s=(w-50)/10+Math.max(-0.75,Math.min(0.75,(h-175)/40))+parseFloat(fit)+GADJ[g],x=Math.max(0,Math.min(7,Math.floor(s))),a=Math.min(7,x+1);
var west=g==="pants"?"US waist "+WA[x]+" · EU "+(WA[x]+16)+" · "+L[x]:L[x]+" · EU "+EU[x];
o.innerHTML='Look for <span class="big">'+esc(L[a])+"</span> on the seller's chart\nEU/US equivalent: "+esc(west)+"\n\n"+'<span class="muted">Why: at '+(imp?esc($("hf").value||0)+"'"+esc($("hn").value||0)+'" and '+esc(Math.round(num("wg")))+" lb":esc(Math.round(h))+" cm and "+esc(Math.round(w))+" kg")+" a "+esc(FN[fit])+" fit"+(g==="jackets"?" with room for layers":"")+" is usually "+esc(L[x])+" in EU/US sizing. Many Weidian and Taobao sellers use Asian sizing that runs about one size small, so the label to look for is "+esc(L[a])+". A rough starting point: confirm it with the seller's chart in cm.</span>";}
try{var u=new URLSearchParams(location.search),qh=parseFloat(u.get("h")),qw=parseFloat(u.get("w"));if(qh>=120&&qh<=230)$("hc").value=String(Math.round(qh));if(qw>=35&&qw<=250)$("wg").value=String(Math.round(qw));}catch(e){}
["ga","un","hc","hf","hn","wg","fi","fl"].forEach(function(i){$(i).addEventListener("input",run);$(i).addEventListener("change",run);});run();
var tb=$("ct").querySelector("tbody");
function addRow(sz,c,l){var tr=document.createElement("tr");tr.innerHTML='<td><input aria-label="Size" maxlength="8"></td><td><input type="number" inputmode="decimal" aria-label="Chest (cm)"></td><td><input type="number" inputmode="decimal" aria-label="Length (cm)"></td>';var p=tr.querySelectorAll("input");p[0].value=sz||"";p[1].value=c==null?"":c;p[2].value=l==null?"":l;tb.appendChild(tr);}
for(var k=0;k<4;k++)addRow();
$("ar").onclick=function(){addRow();};
$("pt").addEventListener("input",function(){var rows=[];this.value.split(/\n/).forEach(function(line){var m=line.trim().match(/^([A-Za-z0-9.]{1,8})[\s:,;|]+(\d+(?:[.,]\d+)?)(?:[\s,;|]+(\d+(?:[.,]\d+)?))?/);if(m)rows.push([m[1],parseFloat(m[2].replace(",",".")),m[3]?parseFloat(m[3].replace(",",".")):null]);});
if(rows.length){tb.innerHTML="";rows.slice(0,12).forEach(function(r){addRow(r[0],r[1],r[2]);});}cmp();});
function cmp(){var yc=num("yc"),yl=num("yl"),o=$("cout"),best=null,res=[];
tb.querySelectorAll("tr").forEach(function(tr){tr.classList.remove("best");var p=tr.querySelectorAll("input"),c=parseFloat(p[1].value),l=parseFloat(p[2].value);if(!isFinite(c)||!isFinite(yc))return;
var dc=c-yc,dl=isFinite(l)&&isFinite(yl)?l-yl:null,sc=Math.abs(dc)+(dl==null?0:Math.abs(dl)*0.5),r={tr:tr,n:p[0].value.trim()||"?",dc:dc,dl:dl,sc:sc};res.push(r);if(!best||sc<best.sc)best=r;});
if(!best){o.textContent="Fill in your measurements and at least one chart row.";return;}
best.tr.classList.add("best");var d=function(v){return(v>0?"+":"")+(Math.round(v*10)/10)+" cm";};
o.innerHTML='Closest to your garment: <span class="big">'+esc(best.n)+"</span>\n"+res.map(function(r){return esc(r.n)+": chest "+esc(d(r.dc))+(r.dl==null?"":", length "+esc(d(r.dl)));}).join("\n")+'\n\n<span class="muted">Plus means the seller\'s size is bigger than your garment. Within about 2 cm is usually close enough. For a relaxed fit pick the size just above.</span>';}
$("pc").addEventListener("input",function(e){if(e.target.id!=="pt")cmp();});})();`}</script>`,

  "parcel-tracker": () => `<div class="tool"><label for="tn">Tracking number(s)</label><textarea id="tn" placeholder="YT2412345678901234&#10;LX123456789CN" autocomplete="off" autocapitalize="characters" spellcheck="false"></textarea>
<div class="row"><button class="btn primary" id="go" type="button">Track</button></div><div id="out" role="status" aria-live="polite"></div>
<div id="rc" hidden><h2 style="margin:22px 0 4px;font-size:16px">Recent on this device</h2><div id="rl"></div><button type="button" class="linkbtn" id="clr">Clear recent numbers</button></div></div>
<script>${String.raw`(function(){${ESC}
var C=${js(CARRIERS.map(c => [c.id, c.name, c.re.source, c.url, c.likely ? 1 : 0]))},P=${js(POSTS)},K="pc.track",U="https://t.17track.net/en#nums=";
var $=function(i){return document.getElementById(i);};
function norm(s){return String(s||"").toUpperCase().replace(/[\s-]/g,"");}
function detect(n){for(var i=0;i<C.length;i++){if(new RegExp(C[i][2]).test(n)){var c={id:C[i][0],name:C[i][1],url:C[i][3],likely:C[i][4]};
if(c.id==="s10"){var cc=n.slice(-2),p=P[cc];c.name=p?p[0]:"Postal service ("+cc+")";c.url=p?p[1]:null;if(cc==="CN"){c.name=n[0]==="E"?"EMS (China Post)":"China Post";c.note="Once it lands, your local post usually tracks the same number too.";}}return c;}}return null;}
function split(t){var out=[];String(t||"").split(/[\n,;]+/).forEach(function(chunk){var j=norm(chunk);if(!j)return;if(detect(j)||chunk.trim().indexOf(" ")<0){out.push(j);return;}chunk.trim().split(/\s+/).forEach(function(x){x=norm(x);if(x)out.push(x);});});
return out.filter(function(n,i){return /^[A-Z0-9]{8,40}$/.test(n)&&out.indexOf(n)===i;}).slice(0,20);}
function load(){try{var v=JSON.parse(localStorage.getItem(K)||"[]");return Array.isArray(v)?v.filter(function(x){return x&&/^[A-Z0-9]{8,40}$/.test(x.n);}):[];}catch(e){return [];}}
function save(a){try{localStorage.setItem(K,JSON.stringify(a.slice(0,10)));}catch(e){}}
function card(n){var c=detect(n),off=c&&c.url?c.url.replace("{n}",encodeURIComponent(n)):"";
return '<div class="card9"><h2>'+esc(c?c.name+(c.likely?" (likely)":""):"Carrier not recognised")+'</h2><div class="num">'+esc(n)+"</div>"+(c&&c.note?'<p class="muted" style="margin:6px 0 0;font-size:14px">'+esc(c.note)+"</p>":"")+
'<div class="row">'+(off?'<a class="btn primary" href="'+esc(off)+'" target="_blank" rel="noopener">Open '+esc(c.name)+"</a>":"")+'<a class="btn" href="'+esc(U+encodeURIComponent(n))+'" target="_blank" rel="noopener">Universal tracker</a><button type="button" class="btn" data-copy="'+esc(n)+'">Copy</button></div></div>';}
function recent(){var a=load();$("rc").hidden=!a.length;$("rl").innerHTML=a.map(function(x){return card(x.n);}).join("");}
function run(){var ns=split($("tn").value),o=$("out");if(!ns.length){o.innerHTML='<p class="muted">Paste a tracking number from your agent\'s parcel page.</p>';return;}
o.innerHTML=ns.map(card).join("")+(ns.length>1?'<div class="row"><a class="btn" href="'+esc(U+ns.map(encodeURIComponent).join(","))+'" target="_blank" rel="noopener">Track all '+ns.length+" on the universal tracker</a></div>":"");
var a=load().filter(function(x){return ns.indexOf(x.n)<0;});save(ns.map(function(n){return{n:n,t:Date.now()};}).concat(a));recent();}
$("go").onclick=run;$("tn").addEventListener("keydown",function(e){if(e.key==="Enter"&&(e.metaKey||e.ctrlKey)){e.preventDefault();run();}});
$("clr").onclick=function(){try{localStorage.removeItem(K);}catch(e){}recent();};
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-copy]");if(!b)return;var t=b.getAttribute("data-copy");
var done=function(){b.textContent="Copied";setTimeout(function(){b.textContent="Copy";},1500);};if(navigator.clipboard)navigator.clipboard.writeText(t).then(done,function(){});});
var q=new URLSearchParams(location.search).get("n");if(q){$("tn").value=q.slice(0,400);run();}else recent();})();`}</script>`,
};

const faqLd = faq => ({ "@context": "https://schema.org", "@type": "FAQPage",
  mainEntity: faq.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) });

// Same shape as pages.js renderTool(): a page() Response, or null for an unknown slug. baseCss is pages.js TOOL_CSS.
export function toolPage9(s, baseCss = "") {
  const t = Object.prototype.hasOwnProperty.call(TOOLS9, s) ? TOOLS9[s] : null; if (!t) return null;
  const path = "/tools/" + s; const bc = crumbs([["Home", "/"], ["Tools", "/tools"], [t.name, path]]);
  const app = { "@context": "https://schema.org", "@type": "WebApplication", name: t.name + ": Puro Classico", url: SITE + path, applicationCategory: "UtilitiesApplication", operatingSystem: "Any", offers: { "@type": "Offer", price: "0", priceCurrency: "USD" }, description: t.desc };
  const faq = `<h2>FAQ</h2><div class="faq">${t.faq.map(([q, a]) => `<details><summary>${esc(q)}</summary><p>${esc(a)}</p></details>`).join("")}</div>`;
  const body = `${bc.html}${baseCss}${CSS9}<h1>${esc(t.h1 || t.name)}</h1><p class="lead">${esc(t.lead)}</p>${TOOL_UI9[s]()}<div class="prose">${t.about}</div>${faq}
<h2>More tools</h2><div class="chips">${TOOL_LINKS.filter(([, u]) => u !== path).map(([n, u]) => `<a href="${u}">${esc(n)}</a>`).join("")}<a href="/how-to-order">How to order</a></div>`;
  return page({ title: t.title, desc: t.desc, path, body, jsonld: [bc.data, app, faqLd(t.faq)] });
}
