// Server-rendered SEO pages. Each renderer returns a Response (or null when the route doesn't exist -> 404).
import { SITE, MYCNBOX_INVITE, BUILT, P, P_ALL, SWAP_HIDE, recBadge, idx, indexable, gone, LINKS_CHECKED, GONE_COUNTS, views, score, CATS, CAT_BY_SLUG, AGENTS, esc, slug, money, isPH, imgSrc, thumbSrc, IMG_FALLBACK, productUrl, brandUrl, catUrl, cutCls,
  grid, crumbs, pager, page, card, colourBadge, GUIDE_LINKS, FOOTER_GUIDES, TOOL_LINKS, QC_ICON, origUrl,
  TK_ICONS, TK_I, TOOL_ONE, TK_TRUST, TK_JS, tkHero, tkCopyBtn, toolShell, ic, icTile, icSteps, more , QC_BANKED, newest, rowDays, AGENT_N, FINDS_PLUS, QC_PLUS, gone as goneOf, shown as findShown, hiddenVer} from "./site.js";
import { CAT_INTRO, AGENT_INTRO, agentBrandCopy, OLD_MONEY, BRAND_INTRO as BRAND_INTRO1, GUIDES as GUIDES1 } from "./content.js";
import { BRAND_INTRO2, MODELS as MODELS2, GUIDES2, TOOLS as TOOLS0 } from "./content2.js";
import { TOOLS9, TOOL_UI9, toolPage9 } from "./tools9.js";
import { itemTypeOf, typeGrams, boxedGrams, fmtGrams } from "./weights.js";
// v9 tools: the weight estimator merged into the shipping calculator (/tools/weight-estimator 301s there), plus the size
// estimator and parcel tracker. TOOLS drives the tools hub descriptions and the sitemap.
const TOOLS = Object.fromEntries(Object.entries(Object.assign({}, TOOLS0, TOOLS9)).filter(([k]) => k !== "weight-estimator"));
import { MODELS3, GUIDES3, MODEL_TERM as MODEL_TERM3 } from "./content3.js";
import { MODELS4, MODEL_TERM4 } from "./content4.js";
import { MODELS5, MODEL_TERM5 } from "./content5.js";
import { SHIP_READ, SHIP_TO, SHIP_LINES, MYCNBOX_SHIP } from "./shipping_lines.js";
import { ensureAlso, alsoOf } from "./also.js";
import { SG } from "./store_gallery.js";
import { AGENT_BRAND_CANON } from "./seo_canon.js";
// The day each shown price was confirmed on the live Weidian listing (scripts/prices.py, the Prices workflow, owner
// 23 Nov 2026: "a lot of the prices is not accurate"). Read through the namespace so an older file still loads.
import * as PCK from "./price_checks.js";
const MODELS = MODELS2.concat(MODELS3, MODELS4, MODELS5);
const MODEL_TERM = Object.assign({}, MODEL_TERM3, MODEL_TERM4, MODEL_TERM5);
// Model pages of the 23 Nov 2026 batch (content5.js) count and list only the finds a visitor can see (shown() in site.js, findShown here);
// the earlier pages keep their lists as they were.
const VIS_ONLY = new Set(MODELS5.map(m => m.slug));
export const modelList = m => { if (!VIS_ONLY.has(m.slug)) return m.list; const l = m.list.filter(findShown); return l.length ? l : m.list; };
const BRAND_INTRO = Object.assign({}, BRAND_INTRO2, BRAND_INTRO1);
const GUIDES = Object.assign({}, GUIDES1, GUIDES2, GUIDES3);
const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);   // a slug from the URL must be the object's own key: "constructor" is a key of every plain object, and not a guide
// "Best X" pages merged into a brand hub: an entry "model-slug": "Brand" stops the model page being rendered, listed and
// put in the sitemap, and functions/_middleware.js answers its address (and /2, /3 ...) with one 301 to the hub. A merge
// only applies while the brand has a hub. Delete the entry to bring the /best page back.
// Empty on purpose. Three model pages list every find of one brand in the same order as that brand's hub (counted
// 10 Oct 2026): "goyard-wallet-bag": "Goyard" (73 of 73), "canada-goose-parka": "Canada Goose" (39 of 39) and
// "rolex-watches": "Rolex" (65 of 66). Before adding one of them here, look the URL up in Search Console (Performance >
// Pages): if it gets clicks or impressions for a "best ..." search, leave it alone, because the hub's title has no "Best"
// in it. When adding "rolex-watches", also point the Rolex link in index.html ("Best reps by model") at /brand/rolex.
export const BEST_MERGED = {};
export const mergedBest = s => (own(BEST_MERGED, s) ? brandUrl(BEST_MERGED[s]) : null);
// model pages: which catalogue items belong to each model (by brand + title)
let _models = null, _modelsIdx = null;
export function models() {
  const ix = idx();
  if (_models && _modelsIdx === ix) return _models;
  _modelsIdx = ix;
  const { all } = ix;
  _models = MODELS.filter(m => !mergedBest(m.slug))
                  .map(m => { const re = new RegExp(m.rx, "i"); return Object.assign({}, m, { list: all.filter(p => re.test((p.brand || "") + " " + p.title)) }); })
                  .filter(m => m.list.length >= 5);
  return _models;
}
export function modelFor(p) { return models().find(m => m.list.some(x => x.id === p.id)) || null; }
// The model pages most like this one (23 Nov 2026): the ones that share its main category or one of its three biggest
// brands, biggest first, then the rest in their usual order. Before, every model page linked the same first 14 models.
export function relatedModels(m, k) {
  const top = l => { const c = new Map(); for (const p of l) c.set(p, (c.get(p) || 0) + 1); return [...c].sort((a, b) => b[1] - a[1]).map(x => x[0]); };
  const mine = modelList(m), cat = top(mine.map(p => p.cat))[0], brands = new Set(top(mine.map(p => p.brand).filter(Boolean)).slice(0, 3));
  const rest = models().filter(x => x.slug !== m.slug);
  const near = rest.filter(x => { const l = modelList(x); return top(l.map(p => p.cat))[0] === cat || l.slice(0, 40).some(p => brands.has(p.brand)); })
    .sort((a, b) => modelList(b).length - modelList(a).length);
  return near.concat(rest.filter(x => !near.includes(x))).slice(0, k);
}
// The model pages of one category, biggest first: the ones whose finds are mostly (60%+) in it.
export function modelsInCat(c, k = 12) {
  return models().map(x => [x, modelList(x)]).filter(([, l]) => l.filter(p => p.cat === c).length >= 0.6 * l.length)
    .sort((a, b) => b[1].length - a[1].length).slice(0, k).map(([x]) => x);
}
// A brand page links a model page when the brand has a find on it; a cross-brand page (brandMin in content5.js) only when
// the brand has that many of its finds there and is one of the three brands with the most of them.
const modelOnBrand = (m, b) => {
  if (!m.brandMin) return m.list.some(p => p.brand === b);
  const c = new Map(); for (const p of modelList(m)) if (p.brand) c.set(p.brand, (c.get(p.brand) || 0) + 1);
  const k = c.get(b) || 0, ahead = [...c.values()].filter(n => n > k).length;
  return k >= m.brandMin && ahead < 3;
};

const PER_PAGE = 60;
// The catalogue date as people write it ("8 Oct 2026"), the format the guides and the hub FAQs already use.
const BUILT_DAY = (d => isNaN(d) ? BUILT : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }))(new Date(BUILT + "T00:00:00Z"));
// Titles (9 Nov 2026): Google shows about 60 characters, and 49 server-rendered titles were longer. A longer title loses, in
// this order, the site name (Google prints it above every result anyway), "Compared", then the year, so the main keyword
// stays first. page() (site.js) and hubApp (functions/_middleware.js) get titles that already fit.
export function fitTitle(t, max = 60) {
  for (const cut of [s => s.replace(/ [·|] Puro Classico$/, ""), s => s.replace(/ Compared\b/, ""), s => s.replace(/ \(2026\)| 2026\b/, "")]) { if (t.length <= max) break; t = cut(t); }
  return t;
}
// "8 Nov 2026" from "2026-11-08"; the latest of several YYYY-MM-DD dates (sitemaps, page copy).
const dayOf = d => new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
const latestDay = (...d) => d.filter(x => typeof x === "string" && ISO_DAY.test(x)).sort().pop() || null;
const andList = a => a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1];
const faqLd = faq => ({ "@context": "https://schema.org", "@type": "FAQPage",
  mainEntity: faq.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) });
// ------------------------------------------------------------------ icon pass (29 Oct 2026, icons/SPEC.md)
// Icons sit next to the text they belong to; no text is removed. Long prose that moves out of view goes into a
// <details class="more"> (still in the HTML Google indexes). Maps from labels and URLs to ICONS names (site.js):
const CAT_IC = { Tops: "tee", Outerwear: "jacket", Shoes: "shoe", Pants: "pants", Shorts: "shorts", Bags: "bag", Accessories: "watch", Headwear: "cap", Toys: "grid" };
const CAT_SLUG_IC = Object.fromEntries(Object.entries(CATS).map(([k, v]) => [v.slug, CAT_IC[k] || "grid"]));
const AGENT_URL = /^\/(mycnbox|kakobuy|oopbuy|lovegobuy|sugargoo|hipobuy)-spreadsheet(\/|$)/;
// The icon a chip link gets from its URL: best-model pages, categories and agent spreadsheets (brand chips get none).
const chipIcon = u => /^\/best\//.test(u) ? ic("award", "sm") : /^\/category\//.test(u) ? ic(CAT_SLUG_IC[u.split("/")[2]] || "grid", "sm") : AGENT_URL.test(u) ? ic("users", "sm") : "";
// A heading with a leading icon tile: <h2 class="h-ic">
const hIc = (tag, name, html, attrs = "") => `<${tag}${attrs} class="h-ic">${icTile(name)}${html}</${tag}>`;
const firstIcon = (map, text, dflt) => { for (const [re, n] of map) if (re.test(text)) return n; return dflt; };
const faqHtml = faq => `${hIc("h2", "help", "FAQ")}<div class="faq">${faq.map(([q, a]) => `<details><summary>${esc(q)}</summary><p>${esc(a)}</p></details>`).join("")}</div>`;
const listLd = (name, url, items, count = items.length) => ({ "@context": "https://schema.org", "@type": "CollectionPage", name, url: SITE + url,
  mainEntity: { "@type": "ItemList", numberOfItems: count,
    itemListElement: items.slice(0, 30).map((p, i) => ({ "@type": "ListItem", position: i + 1, url: SITE + productUrl(p), name: p.title })) } });
const priceRange = l => { const u = l.map(p => p.cny).filter(x => !isPH(x)).sort((a, b) => a - b); return u.length ? `${money(u[0])} to ${money(u[u.length - 1])}` : ""; };
// The prices for a meta description. A listed price under a third of the list's half-way price is mostly a deposit or a
// placeholder (the same test as priceDoubt in brandFacts), so the snippet leaves it out and then says "most" (always
// true: everything from the half-way price up is kept). The page body keeps the full priceRange.
const fromPrice = l => { const u = l.map(p => p.cny).filter(x => !isPH(x)).sort((a, b) => a - b); return u.length ? ` From ${money(u[0])}` : ""; };
const typicalPrices = l => { const u = l.map(p => p.cny).filter(x => !isPH(x)).sort((a, b) => a - b); if (!u.length) return "";
  const med = u[Math.floor((u.length - 1) / 2)], v = u.filter(x => x * 3 >= med), lo = money(v[0]), hi = money(v[v.length - 1]);
  return `, ${v.length < u.length ? "most " : ""}listed at ${lo === hi ? lo : `${lo} to ${hi}`}`; };

// ------------------------------------------------------------------ product
// Part of the edge-cache key in functions/product/[id].js, next to BUILT. BUILT only moves when the catalogue data
// changes, so without this a change to the product page's HTML could stay hidden behind cached copies for up to a day.
// Give it a new value (w1 -> w2 ...) in the same deploy as any change to the product page that must show at once.
export const PRODUCT_TPL = "w138";   // w138: Boonbuy joins the agents (26 Nov 2026); w137: QC photos with our QR badge (?b=2) (26 Nov 2026); w136: size.js v9, no chart: usual size or one up (26 Nov 2026); w135: no homepage flash on refresh of a /#p/<id> link (26 Nov 2026); w134: no MyCNBox sign-up line under the buy button (26 Nov 2026); w133: chat desktop only, chat.js v8 (26 Nov 2026); w132: track.js v6 visit timing (26 Nov 2026); w131: tour v2, size.js v8 (26 Nov 2026); w130: hub related links fold into a toggle (26 Nov 2026); w129: style and size steps in the welcome tour, shoe size advice (26 Nov 2026); w128: Hipobuy spreadsheet in the footer and the agent tables (26 Nov 2026); w127: /spreadsheet hero glow fades out with no edge (26 Nov 2026); w126: 172 more cut-outs on the dark grey tile (26 Nov 2026); w125: category counts are visible finds only (26 Nov 2026); w124: speed and SEO sweep (early hints, /spreadsheet LCP, sitemap, pagers, srcset) (26 Nov 2026); w123: dark-mode grey photo tiles for cut-outs (26 Nov 2026); w122: design sweep fixes (26 Nov 2026); w121: slim footer with "All pages" and a compact guides list (26 Nov 2026); w120: /spreadsheet hero without the pill (25 Nov 2026); w119: /spreadsheet gets lab concept A's search-first hero (25 Nov 2026); w118: 78 finds back in the QC bank, their photos in the page (25 Nov 2026); w117: brand counts are visible finds only (25 Nov 2026); w116: MyCNBox review dated, MyCNBox description (25 Nov 2026); w115: guides show finds of their own kind (25 Nov 2026); w114: agent spreadsheets: updated day, side by side with MyCNBox (25 Nov 2026); w113: /spreadsheet structured data and sitemap entry (25 Nov 2026); w112: guide layout v12, agent FAQs, hub #seo block out (25 Nov 2026, SEO pass); w111: the new 56-second tutorial video (25 Nov 2026); w110: the header wordmark is a small static /img/wordmark.webp, preloaded (it was a slow on-the-fly resize, the logo came in late on phones), ds.css v38; w109: calm loading 2 (scroll chunks without the entrance, toolbar skeleton pills, the size line keeps its height, ds.css v37); w108: calm loading, the partner swaps preloaded at low priority; w107: calm loading (skeleton tiles, server cards with the app's srcset, sub-pre on category hubs); w106: size.js v6 (the fit picker slides); w105: /spreadsheet hiding style after <title> (no <head> tag in index.html); w104: SEO pass (24 Nov 2026): QC Photo Checker with product search, MyCNBox guide links and "Open the spreadsheet" on agent pages, 7 more agent x brand brands (product pages link them); w103: /spreadsheet hides sections by html[data-sp]; w102: no favourite count, no "Best batch" (owner, 24 Nov 2026)
// earlier versions: w101: every visible Weidian find checked against its live listing (23 Nov 2026); w100: size.js v5, the size is saved on the member's account too (23 Nov 2026); w99: the size card became a subtle "We recommend size L" note under the price on clothes, with the size step at sign-up (size.js v4, 23 Nov 2026); w98: the agent shipping tables say what each estimator was given (KakoBuy: no goods type), 23 Nov 2026; w97: SEO pass (23 Nov 2026): 34 more /best model pages (content5.js) linked from product, brand and category pages, visible-only counts on the marketplace, QC and agent spreadsheets, agent shipping lines, new finds this week, QC spreadsheet and QC finder sections, CNFans status; w96: the 3,000 most viewed finds checked against their live Weidian listings (23 Nov 2026); w95: prices from the live Weidian listings, the cheapest real variant, and the day each price was checked (Price check row, 23 Nov 2026); w94: the size card is always open with the recommended size and the seller's chart as a table (size.js v3, 23 Nov 2026); w93: the dark mode photo tiles are light grey #DEDEDE (owner pick, ds.css v33) and the MyCNBox button says "Up to $500 coupons" instead of "Most popular" (23 Nov 2026); w92: dark mode puts product photos on white tiles (ds.css v32, 23 Nov 2026); w91: white cut-outs for the store photos the polish step skipped (23 Nov 2026); w90: 10 more mains from passing angles after the re-rating (22 Nov 2026); w89: angles the re-rating failed dropped, 8 wrong pass-2 mains back to their earlier photo (22 Nov 2026); w88: the new pass-2 store photos polished too (22 Nov 2026); w87: new store photo sets for weak and wrong-item finds (pass 2, 22 Nov 2026); w86: SEO pass (22 Nov 2026): what to check in QC for each find, its marketplace spreadsheet linked, photo alt text; w85: SEO pass (22 Nov 2026): 86 agent x brand pages canonical to their brand page, so the edge copies are rebuilt; w84: polished store photos (pure white 1600 px cut-outs, products/store2/, 22 Nov 2026); w83: photo fixes from the AI ratings (wrong / hanger / duplicate angles dropped, better mains, 22 Nov 2026); w82: store angles preloaded as 1000 px copies (21 Nov 2026); w81: store photo angles under the main photo (store_gallery.js, 21 Nov 2026); w79: "Find my size" helper (size.js, 19 Nov 2026); w78: feedback pop-up for the most active visitors (feedback.js, 19 Nov 2026); w77: the removed notice only for member-reported finds, not photo-cleanup or owner hides (19 Nov 2026); w76: no Recommended badge on cards, 'Best batch' on the product page (18 Nov 2026); w75: brand hubs counted on all finds (15 Nov 2026); w74: in-text agent spreadsheet links (15 Nov 2026); w73: product shadow, no Swipe nav, baked finds count (15 Nov 2026); w72: cleaner tools block on the homepage (15 Nov 2026); w71: img/rl thumbs get ?c=1 (stale white resize cache, 15 Nov 2026); w70: pcs.js multilingual search words (15 Nov 2026); w69: subtle icon-only Recommended dot on cards (15 Nov 2026); w68: nicer Recommended tag, no photo blend in dark mode (ds.css v26); w67: partner swaps (12 Nov 2026): the partner item's price, swapped finds first, look-alike pages point to the swapped find; w65: hub layout v10 (compact head, one related-links row, agent logo row, About section under the grid; HX_CSS); w64: 16 agents in the buy menu, first 5 + "See more agents" (11 Nov 2026); w63: distinct agent page copy (AGENT_INTRO about/desc/faq, agentBrandCopy); w62: footer links to the Weidian, Taobao and 1688 spreadsheets, price ranges written "¥x to ¥y", titles fitted to 60 characters (fitTitle); w61: "Ask AI about this item" row, chat.js?v=7 (saved chats note), sharper agent logos; w60: no colour-count badge on cards (owner); w59: chat.js?v=6 (scrollable card row); w58: chat.js?v=5 (better answers); w57: no yen price next to the main price (owner); w56: product page like the app view (muted brand, Details folded, QC button only with stored photos); w55: chat.js?v=4 (pcChatAsk hook for the beta Ask box); w54: size answer beside the form on wide screens; w53: size estimator counts height for length, scrolls to the result; w52: pcs.js 5f23e99c (search: zero-result queries from the log, Nordic words, typo pass under 3 finds); w51: QC badge only for finds with stored QC photos (QC_BANKED); w50: chat.js?v=3 (messenger look; finds open in the app view);   // w49: "People also liked" row (data/also.json, functions/_lib/also.js);   // w48: track.js?v=4 (one taste log for the feed and For you: hovers, finds scrolled past, unsaves);   // w47: chat.js?v=2 (smoother assistant: cards while it writes, Stop, Try again);   // w46: instant search menu on focus (pcs.js dd943831, pcs.css 0cc49aee);   // w45: the header is the app's (Swipe, MyCNBox pill, Sign in, globe; hover is text only; ds.css v23);   // w44: track.js?v=2 (taste log for the Swipe feed);   // w43: 44 more /best model pages (content4.js), product pages link to them;   // w42: card QC link is a camera badge on the photo, Buy fills the row;   // w41: compact tool sections on phones (ds.css v22);   // w40: light is the default theme;   // w39: affiliate label under the buy button removed;   // w38: ship gate (tool name inside the tool h1, ds.css v21); w37: round 8 (estimated-weight + QC stat chips under the title, colour-count badge on cards); w36: round 6 (affiliate label under the buy button, disclosures, no photo wells); w35: round 5 (web app manifest + apple-touch-icon)
// QC photos on the server-rendered page come only from /api/qc's edge cache (cached=1), never from a new qualit.ly
// lookup (21 Oct 2026): the plan allows 1,000 lookups a month, and crawlers rendering ~2,500 product pages used them up
// by mid-month, leaving none for people. A page without cached photos gets a "Show QC photos" button that looks them
// up for the visitor who asks (QC_LOAD_JS). failed = the cache read itself went wrong, so the page is kept only briefly.
async function qcThumbs(origin, p) {
  if (p.qc < 1) return { list: [], failed: false };
  try {
    const r = await Promise.race([
      fetch(`${origin}/api/qc?storefront=${p.platform}&id=${encodeURIComponent(p.itemId || p.id)}&cached=1`),
      new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), 1500)),
    ]);
    if (r.status === 404) return { list: [], failed: false };          // nobody has looked this find up lately
    if (!r.ok) return { list: [], failed: true };
    const d = await r.json();
    return { list: (Array.isArray(d.thumbnails) ? d.thumbnails : []).filter(u => /^https:\/\//.test(u)).slice(0, 8), failed: false };
  } catch (e) { return { list: [], failed: true }; }
}
const QC_LOAD_JS = '(function(){var w=document.currentScript.previousElementSibling,b=w.querySelector("button");' +
  'function e(s){return String(s).replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;")}' +
  'function t(s){s=String(s);var o=location.origin;return s.indexOf(o+"/api/img?")===0?o+"/cdn-cgi/image/width=400,quality=75,format=auto"+s.slice(o.length):s}' +
  'b.addEventListener("click",function(){b.disabled=true;b.textContent="Loading QC photos…";' +
  'fetch("/api/qc?storefront="+encodeURIComponent(b.getAttribute("data-sf"))+"&id="+encodeURIComponent(b.getAttribute("data-id")))' +
  '.then(function(r){return r.ok?r.json():null}).then(function(d){' +
  'var u=((d&&d.thumbnails)||[]).filter(function(x){return String(x).indexOf("https://")===0}).slice(0,8);' +
  'if(!u.length){w.innerHTML="<p class=\\"qc-none\\">QC photos can’t be loaded right now. Your agent photographs your exact item at the warehouse before it ships.</p>";return}' +
  'w.innerHTML="<h2 class=\\"qc-h\\">Real QC photos</h2><div class=\\"qcs\\">"+u.map(function(x,i){return "<a href=\\""+e(x)+"\\" target=\\"_blank\\" rel=\\"noopener\\"><img src=\\""+e(t(x))+"\\""+(t(x)!==x?" data-o=\\""+e(x)+"\\"":"")+" alt=\\"QC photo "+(i+1)+"\\" width=\\"96\\" height=\\"96\\" decoding=\\"async\\" onerror=\\"if(this.dataset.o){this.src=this.dataset.o;delete this.dataset.o}else this.parentNode.remove()\\"></a>"}).join("")+"</div>"})' +
  '.catch(function(){b.disabled=false;b.textContent="Try again"})})})();';

// Store photos (21 Nov 2026, owner): more angles of the find from real shops (scripts/apply_store_photos.py ->
// store_gallery.js). A row of thumbnails under the main photo; a tap shows the angle in the main square on every screen.
const SG_PUB = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/store/";
// "s2/<name>": the polished copy (scripts/store_photos_polish.py, pure white 1600 px) in products/store2/
const sgUrl = k => k.startsWith("s2/") ? SG_PUB.replace("/store/", "/store2/") + k.slice(3) : SG_PUB + k;
// "w/<name>": the white cut-out (scripts/photo_white.py, pure white 1600 px) in the site's own files, img/white/store/
const sgSrc = k => k.startsWith("w/") ? SITE + "/img/white/store/" + k.slice(2) : SITE + "/api/img?u=" + encodeURIComponent(sgUrl(k));
// Each thumbnail carries its photo's dark mode tile (pc-cut, photo_tiles.js); GALLERY_JS hands it to the main square.
function storeThumbs(p, src, list) {
  const title = p.title, cls = (u, i) => { const c = ((i ? "" : "on") + cutCls(p, u)).trim(); return c ? ` class="${c}"` : ""; };
  const b = (u, i, own) => `<button type="button"${cls(u, i)}${own ? "" : ` data-u="${esc(thumbSrc(u).replace("width=400,quality=75", "width=1000,quality=80"))}"`} aria-label="${esc(title)} photo ${i + 1}"><img src="${esc(thumbSrc(u))}" data-o="${esc(u)}" alt="${esc(title)} photo ${i + 1}" width="72" height="72" loading="lazy" decoding="async" ${IMG_FALLBACK}></button>`;
  // data-u: a 1000 px copy from Cloudflare (about 35 KB instead of the 1200 px original), fetched in the background once the
  // page has loaded so a tap swaps at once
  return `<div class="thumbs">${b(src, 0, true)}${list.map((k, i) => b(sgSrc(k), i + 1)).join("")}</div>` +
    '<script>addEventListener("load",function(){setTimeout(function(){[].forEach.call(document.querySelectorAll(".thumbs button[data-u]"),function(b){var i=new Image();i.decoding="async";i.src=b.getAttribute("data-u")})},300)})</script>';
}

// The product photo (25 Nov 2026, speed check): it is the page's largest paint and came as the stored original, 1600 px
// and about 80 KB of WebP for a 358 px box on a phone. It now offers the two copies the app already makes with Cloudflare
// (cdnOf and bigOf in index.html: 720 px for the cards on retina screens, 1400 px for the product view), so no new resizes
// are made and a visitor coming from the app may have them cached: for /product/7775316835, 18 KB (720 px) or 59 KB
// (1400 px) of AVIF instead of 80 KB. src stays the original (og:image, the image sitemap and the structured data name it);
// GALLERY_JS drops the srcset while it shows another photo.
const mainSet = s => {
  const a = thumbSrc(s); if (a === s) return "";
  const w = (n, q) => a.replace("/cdn-cgi/image/width=400,quality=75,", `/cdn-cgi/image/width=${n},quality=${q},`);
  return ` srcset="${esc(w(720, 80))} 720w, ${esc(w(1400, 85) + (/\/api\/img\?/.test(a) ? "&hd=2" : ""))} 1400w" sizes="(max-width:900px) calc(100vw - 32px), 600px"`;
};
// Product photo gallery (v9): on screens wider than a phone a QC thumbnail shows its photo in the main square instead of
// opening a new tab, and a "Product photo" thumbnail (added on the first swap) brings the listing photo back. Phones keep
// the large swipeable row, where a tap opens the full photo. Works for photos QC_LOAD_JS adds later too (delegated).
// The main square takes the dark mode tile of the photo it shows (pc-cut from the thumbnail; QC photos have none).
const GALLERY_JS = '<script>(function(){try{var w=document.currentScript.parentNode,m=document.getElementById("pmain");if(!m)return;var o=m.getAttribute("src"),os=m.getAttribute("srcset"),oa=m.alt,bx=m.parentNode,oc=bx.classList.contains("pc-cut");' +
  'w.addEventListener("click",function(e){var a=e.target.closest(".qcs a,.thumbs button");if(!a)return;var on=a.tagName==="BUTTON";if(!on&&!matchMedia("(min-width: 641px)").matches)return;e.preventDefault();' +
  'var t=w.querySelector(".thumbs");if(!t&&o){t=document.createElement("div");t.className="thumbs";t.innerHTML=\'<button type="button"\'+(oc?\' class="pc-cut"\':"")+\' aria-label="Product photo"><img alt="" src="\'+o.replace(/"/g,"&quot;")+\'"></button>\';var h=w.querySelector(".qc-h");if(h)h.parentNode.insertBefore(t,h)}' +
  'var u=on?(a.getAttribute("data-u")||o):a.href;if(u===o&&os)m.setAttribute("srcset",os);else m.removeAttribute("srcset");m.src=u;m.alt=on?oa:(a.querySelector("img")||{}).alt||oa;bx.classList.toggle("pc-cut",on&&a.classList.contains("pc-cut"));' +
  '[].forEach.call(w.querySelectorAll(".qcs a,.thumbs button"),function(x){x.classList.toggle("on",x===a)})})}catch(e){}})();</script>';

// Rings of indexable finds for the related blocks on product pages (28 Oct 2026). "More <brand> finds" and "Similar
// <category>" showed the 8 most viewed finds of the brand or category: the same 8 on every page, so 2,405 of the 2,923
// indexable product pages had no link from any other product page. A ring holds the indexable finds of one brand or one
// category, sorted by item type and then catalogue position (fixed for a deploy, unlike the view order). A page shows the
// 4 most viewed plus the next 4 finds after its own place in the ring, so every indexable find is linked from the pages
// of the finds just before it, mostly of the same item type.
let _pos = null;
const _rings = new Map();
function ringAfter(key, list, p, k, skip = [], ok = () => true) {
  if (!_pos) _pos = new Map(P.map((x, i) => [x, i]));
  let r = _rings.get(key);
  if (!r) {
    r = list.filter(indexable).map(x => [itemType(x), _pos.get(x), x]).sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] - b[1]));
    _rings.set(key, r);
  }
  const t = itemType(p), at = _pos.get(p), out = [];
  let s = r.findIndex(e => e[0] > t || (e[0] === t && e[1] > at)); if (s < 0) s = 0;
  for (let j = 0; j < r.length && out.length < k; j++) { const x = r[(s + j) % r.length][2]; if (x !== p && !skip.includes(x) && ok(x)) out.push(x); }
  return out;
}

// opt.reported: the find was removed after member reports (data/reported.json, functions/product/[id].js): the page says so
// instead of the buy box, has no buy bar and is noindex,follow. A look-alike of a partner-swapped find (SWAP_HIDE, site.js)
// is shown the same way, with a link to the swapped find instead of the report notice.
// What to check in QC (22 Nov 2026, SEO check): product pages had one general QC note for every find. Now each page lists what
// to check for that find: the model's own checklist when the find is on a best model page (MODELS: m.qc), otherwise the list
// for its category. Shown under "About this find", with a link to the full guide.
const CAT_QC = {
  Tops: ["Logo or print: size, placement and clean edges", "Stitching at the collar, cuffs and hem", "Fabric weight and colour next to retail photos", "The size tag against the seller's size chart"],
  Outerwear: ["Logo patch or badge: shape, stitching and placement", "Zips and snaps: brand marks and smooth pulls", "Fill and loft on puffers (it should look full)", "Seams, pockets and the lining"],
  Shoes: ["Shape from the side and the toe box", "Logo placement and stitching on the upper", "Sole, midsole and the size label inside", "The box and its label, if they matter to you"],
  Pants: ["Waist and length against the seller's size chart", "Stitching, rivets and buttons", "Logo tabs and patches", "Colour and wash next to retail photos"],
  Shorts: ["Waist and length against the seller's size chart", "Logo or print placement", "Stitching at the hem and pockets", "Fabric and colour"],
  Bags: ["Shape and size against the listed measurements", "Hardware: engraving, colour and finish", "Stitching, edge paint and the lining", "Logo, pattern alignment and the heat stamp"],
  Accessories: ["Engravings and logo marks", "Finish and colour of metal parts", "Stitching and edges on leather", "Size or length against the listing"],
  Headwear: ["Logo embroidery: density and placement", "Shape of the crown and the brim", "Size band or strap", "Inside tags and stitching"],
  Toys: ["Paint and print quality", "All parts in the box", "The box and its print"],
};
function qcCheck(p, model) {
  const list = model && model.qc && model.qc.length ? model.qc : CAT_QC[p.cat] || null;
  if (!list) return "";
  const what = model ? esc(model.name) : esc(((CATS[p.cat] || {}).name || p.cat || "find").toLowerCase());
  return `<h2>What to check in the QC photos</h2><p>What to look for on ${what}:</p><ul class="ic-list">${list.map(q => `<li>${ic(firstIcon(QC_ITEM_IC, q, "check-circle"), "sm")}<span>${esc(q)}</span></li>`).join("")}</ul>` +
    `<p>Step by step: <a href="/guides/how-to-qc">how to read QC photos</a>. No buyer photos yet? Paste the link into the <a href="/tools/qc-checker">QC finder</a>, or wait for your agent's photos of your own item.</p>`;
}
// About page (22 Nov 2026, SEO check): who runs the site, how finds are checked, how it is paid for and how to reach us,
// under the brand name only. AboutPage data names the Organization.
export function renderAbout() {
  const path = "/about", bc = crumbs([["Home", "/"], ["About", path]]);
  const day = d => new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  const body = `${bc.html}<article class="prose"><h1>About Puro Classico</h1>
<p class="lead">Puro Classico is a free, searchable <a href="/">rep spreadsheet</a>: ${FINDS_PLUS} finds from Weidian, Taobao and 1688, each with the seller's listed price, buyer QC photos where they exist and links that open the listing in a shopping agent. We don't sell, stock or ship anything.</p>
<h2>Where the finds come from</h2><p>Finds come from our own searches, from the community and from sellers we work with. Each one keeps the seller's listed price from the last catalogue update, so check the price in your agent before you pay. Lists by marketplace: the <a href="/weidian-spreadsheet">Weidian spreadsheet</a>, the <a href="/taobao-spreadsheet">Taobao spreadsheet</a> and the <a href="/1688-spreadsheet">1688 spreadsheet</a>.</p>
<h2>How we check them</h2><ul>${LINKS_CHECKED ? `<li>Every Weidian link is checked each week. The last check, on ${day(LINKS_CHECKED)}, found ${GONE_COUNTS.dead.toLocaleString("en-US")} listings gone, which the spreadsheet hides, and ${GONE_COUNTS.sold.toLocaleString("en-US")} sold out.</li>` : ""}<li>${QC_PLUS} finds are marked as having buyer QC photos: real warehouse photos from earlier orders. The <a href="/tools/qc-checker">QC finder</a> looks them up for any link.</li><li>Members can report a find with a dead link, wrong photos or a bad seller. Finds that several members report are taken down.</li></ul>
<p>The details: <a href="/guides/how-we-check">how we check the spreadsheet</a>.</p>
<h2>How the site is paid for</h2><p>Buy buttons are affiliate links: when you order through them, the shopping agent may pay us a commission, at no extra cost to you. That is the only way the site earns money. We are not affiliated with any brand named on the site, and brand names describe the style of a listing.</p>
<h2>Contact</h2><p>The quickest way to reach us is the <a href="/discord">Discord community</a>. To flag a problem with one find, use Report this find on its page.</p>
</article>`;
  const ld = [bc.data, { "@context": "https://schema.org", "@type": "AboutPage", name: "About Puro Classico", url: SITE + path,
    mainEntity: { "@type": "Organization", "@id": SITE + "/#org", name: "Puro Classico", url: SITE + "/", logo: SITE + "/logo-mark.png", sameAs: ["https://www.tiktok.com/@puroclassico.com", "https://discord.gg/FUUsSCGqQf"] } }];
  return page({ title: "About Puro Classico: Who We Are and How We Check Finds", desc: `Puro Classico is a free rep spreadsheet of ${FINDS_PLUS} Weidian, Taobao and 1688 finds: how finds are picked and checked, how the site is paid for, and contact.`, path, body, jsonld: ld });
}
export async function renderProduct(id, origin, opt = {}) {
  const { byId, byBrand, byCat } = idx();
  const p = byId.get(id);
  if (!p) return null;
  const [qcr] = await Promise.all([qcThumbs(origin, p), ensureAlso(origin)]), qcs = qcr.list;
  const bUrl = brandUrl(p.brand), cUrl = catUrl(p.cat), cat = CATS[p.cat] || { name: p.cat };
  const trail = [["Home", "/"]];
  if (cUrl) trail.push([cat.name, cUrl]);
  if (bUrl) trail.push([p.brand, bUrl]);
  trail.push([p.title, productUrl(p)]);
  const bc = crumbs(trail);
  const variants = p.variants ? p.variants.split("|") : [];
  const opts = variants.filter(v => v.trim() && !/^standard$/i.test(v.trim()));   // "Standard" is the importer's placeholder (9,000 of 9,202 rows), not a real option
  const src = imgSrc(p);
  // Buy box (v9, 29 Oct 2026): one black split button, the rep-find pattern. The main part is the visitor's agent from the
  // app's saved state, else MyCNBox; the arrow opens a <details> menu with the other agents. Under it the MyCNBox
  // new-user coupon line (a quiet muted row, only with MyCNBox) and the affiliate note. On phones a bar keeps the price
  // and the main button on screen while the main button is out of view (.buybar, filled in by the script).
  const ag = Object.entries(AGENTS);
  const buyLink = ([k, a], main) => `<a${main ? ' class="first"' : ""} data-agent="${k}" href="${esc(a.build(p))}" target="_blank" rel="sponsored nofollow noopener">Buy via ${a.name}${k === "mycnbox" ? "<small>Up to $500 coupons</small>" : ""}</a>`;
  const ARROW = ic("arrow-right", "sm"), CHEVRON = ic("chevron-down");
  // A listing the weekly link check found gone: say so above the buttons (a sold-out listing often comes back).
  const g = gone(p), checked = LINKS_CHECKED ? new Date(LINKS_CHECKED + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "";
  const goneNote = !g ? "" : `<p class="buy-gone">${ic("alert", "sm")}${g === "dead" ? "This listing was no longer online" : "This listing was sold out"} at our link check${checked ? ` on ${checked}` : ""}. ` +
    `${g === "dead" ? "The buttons still open it in case the seller puts it back" : "The buttons still open it, since sellers often restock"}; similar finds are below.</p>`;
  const swapOf = SWAP_HIDE[p.id] ? byId.get(SWAP_HIDE[p.id]) : null;
  const rep = !!(opt && opt.reported) || !!swapOf;
  const repNote = swapOf ? `<p class="buy-gone">${ic("alert", "sm")}This listing is no longer on the spreadsheet. The same item is listed here: ` +
    `<a href="${productUrl(swapOf)}">${esc(swapOf.title)}</a>, ${money(swapOf.cny)}.</p>` : `<p class="buy-gone">${ic("alert", "sm")}This find was removed after several members reported it (a dead link, the wrong item or a scam seller). ` +
    `Its buy links are switched off; similar finds are below.</p>`;
  const buyBox = rep ? repNote : goneNote + `<div class="buybox"><div class="buy-split"><div class="buy-main">${buyLink(ag[0], true)}</div>` +
    `<details class="buy-more"><summary aria-label="Other agents">${CHEVRON}</summary><div class="buy-menu"><p class="buy-or">Or buy via</p><div class="buy-alt">${ag.slice(1).map(x => buyLink(x, false)).join("")}<a href="#" class="buy-agx" role="button" style="display:none;color:var(--muted)">See more agents</a></div></div></details></div>` +
    // affiliate label under the buy button removed (owner, 30 Oct 2026); the disclosure stays in the footer, FAQ and /terms
    // owner, 26 Nov 2026: the "New to MyCNBox? Sign up with our link" line under the buy button is removed
    `</div>` +
    // The agent the visitor picked in the app becomes the main button (it swaps places with MyCNBox, which moves into
    // the menu); the coupon line only goes with MyCNBox. The menu closes on Escape or a click outside it.
    `<script>(function(){var x=document.currentScript.previousElementSibling;try{var a=String((JSON.parse(localStorage.getItem("manifest.state")||"{}")||{}).agent||"").replace(/[^a-z0-9]/g,""),m=x.querySelector(".buy-main a"),e=a&&x.querySelector('.buy-alt a[data-agent="'+a+'"]');if(e&&m){var n=e.nextSibling,q=e.parentNode;m.parentNode.replaceChild(e,m);q.insertBefore(m,n);e.className="first";m.className="";x.querySelector(".buy-hint").hidden=true;}}catch(_){}` +
    // "See more agents" (11 Nov 2026): the menu shows 4 agents (5 with the main button); MyCNBox moves to the top of the
    // menu when it is not the main button; the link reveals the rest in place. Without JS every agent shows.
    `try{var my=x.querySelector('.buy-alt a[data-agent="mycnbox"]');if(my)my.parentNode.insertBefore(my,my.parentNode.firstChild);var al=[].slice.call(x.querySelectorAll(".buy-alt a[data-agent]")),mb=x.querySelector(".buy-agx");if(mb&&al.length>4){al.slice(4).forEach(function(l){l.style.display="none"});mb.style.display="";mb.addEventListener("click",function(ev){ev.preventDefault();ev.stopPropagation();al.forEach(function(l){l.style.display=""});mb.remove();try{al[4].focus()}catch(_){}})}else if(mb)mb.remove()}catch(_){}` +
    `try{var d=x.querySelector(".buy-more");document.addEventListener("click",function(ev){if(d.open&&!d.contains(ev.target))d.open=false});document.addEventListener("keydown",function(ev){if(ev.key==="Escape"&&d.open){d.open=false;d.querySelector("summary").focus()}})}catch(_){}})();</script>`;
  const buyBar = rep ? "" : `<div class="buybar" aria-hidden="true"><div class="bb-price">${money(p.cny)}</div><a class="bb-buy" href="${esc(ag[0][1].build(p))}" target="_blank" rel="sponsored nofollow noopener" tabindex="-1">Buy via ${ag[0][1].name}</a></div>` +
    `<script>(function(){var b=document.querySelector(".buybar"),m=document.querySelector(".buy-main a");if(!b||!m||!window.IntersectionObserver)return;var l=b.querySelector("a");l.href=m.href;l.setAttribute("data-agent",m.getAttribute("data-agent"));l.textContent=m.firstChild.nodeValue;document.body.classList.add("has-buybar");new IntersectionObserver(function(es){var on=!es[0].isIntersecting;b.classList.toggle("on",on);b.setAttribute("aria-hidden",on?"false":"true");l.tabIndex=on?0:-1;}).observe(m);})();</script>`;
  const plat = { weidian: "Weidian", taobao: "Taobao", "1688": "1688" }[p.platform] || p.platform;
  const realSeller = p.seller && !/marketplace/i.test(p.seller) && p.seller.trim().toLowerCase() !== plat.toLowerCase() ? p.seller : "";   // "Weidian" as seller is just the platform
  const catLc = (cat.name || "").toLowerCase();
  const dup = (idx().titleCount.get(((p.brand || "") + "|" + p.title).toLowerCase()) || 1) > 1;
  const tName = dup ? `${p.title} (${plat}, ${money(p.cny)})` : p.title;
  // p.qc >= 1 is a flag from import ("QC photos exist for this listing"); the photos themselves come from a live
  // lookup that can fail. So title, description and text may say photos are on record, never that this page shows them.
  // Google cuts descriptions at ~160 characters (SEO pass, 21 Oct 2026): use the long ending only when it fits.
  const dHead = `${p.title} rep ${isPH(p.cny) ? "(ask the seller for the price)" : `for about ${money(p.cny)} (¥${p.cny})`} on ${plat}` + (dup && realSeller ? ` from seller ${realSeller}` : "");
  const desc = [dHead + (p.qc ? ", a listing with buyer QC photos on record" : "") + `. Open it on MyCNBox, KakoBuy, Oopbuy or any shopping agent.`,
                dHead + (p.qc ? ", QC photos on record" : "") + `. Buy via MyCNBox or any agent.`,
                dHead + "."].find(x => x.length <= 160) || dHead + ".";
  const topBrand = bUrl ? (byBrand.get(p.brand) || []).filter(x => x.id !== p.id).slice(0, 4) : [];
  const sameBrand = bUrl ? topBrand.concat(ringAfter("b:" + p.brand, byBrand.get(p.brand) || [], p, 4, topBrand)) : [];
  const topCat = (byCat.get(p.cat) || []).filter(x => x.id !== p.id && x.brand !== p.brand).slice(0, 4);
  const sameCat = topCat.concat(ringAfter("c:" + p.cat, byCat.get(p.cat) || [], p, 4, topCat, x => x.brand !== p.brand));
  // "People also liked" (data/also.json, scripts/bake_also.py): finds that members who saved or opened this one also
  // saved or opened (pairs held by 3+ members only), blended with the closest finds by type, brand, model, colour and price.
  // Finds already in the brand and category rows are skipped, so those rows (and the links they guarantee) stay as they
  // were. The row needs 4 finds; it says "People also liked" only when at least 3 of them come from members' co-likes.
  const shownIds = new Set([p.id, ...sameBrand.map(x => x.id), ...sameCat.map(x => x.id)]), alsoList = [];
  let alsoCo = 0;
  for (const [aid, , co] of alsoOf(p.id)) {
    const x = byId.get(aid);
    if (!x || shownIds.has(x.id) || gone(x) === "dead" || SWAP_HIDE[x.id]) continue;
    shownIds.add(x.id); alsoList.push(x); if (co) alsoCo++;
    if (alsoList.length >= 8) break;
  }
  // 23 Nov 2026 (owner: "make it match the app"): these finds sit right under the find as the app's swipeable
  // "Similar finds" row (was a grid of cards further down, after the how-to-buy steps).
  const alsoRow = alsoList.length >= 4 ? `<section class="psim"><h2>${alsoCo >= 3 ? "People also liked" : "Similar finds"}</h2><div class="psim-r">${alsoList.map(x => {
    const s = imgSrc(x);
    return `<a class="psim-t" href="${productUrl(x)}"><span class="ci${cutCls(x)}">${s ? `<img src="${esc(thumbSrc(s))}" data-o="${esc(s)}" alt="${esc(x.title)}" width="200" height="200" loading="lazy" decoding="async" ${IMG_FALLBACK}>` : ""}</span>` +
      `<span class="psim-n">${esc(x.title)}</span><span class="psim-p">${money(x.cny)}</span></a>`;
  }).join("")}</div></section>` : "";
  const about1 = `<p>The <strong>${esc(p.title)}</strong> is listed on ${plat}${realSeller ? ` by ${esc(realSeller)}` : ""}, in our ${cUrl ? `<a href="${cUrl}">${esc(cat.name)}</a>` : esc(cat.name || p.cat)} section${p.brand ? ` (${esc(p.brand)} style)` : ""}.` +
    (isPH(p.cny) ? ` The seller shows a placeholder price (¥${p.cny}), so ask them for the real price before ordering.` : ` The listed price is ¥${p.cny} (about ${money(p.cny)}) before shipping.`) +
    (opts.length ? ` Listed option${opts.length > 1 ? "s" : ""}: ${esc(opts.slice(0, 8).join(", "))}${opts.length > 8 ? "…" : ""}.` : "") + `</p>`;
  const aboutMore = (p.qc ? `<p>Our catalogue data marks this listing as having <strong>buyer QC photos</strong>: warehouse photos taken for earlier orders. When we can load them, they are shown on this page. Either way, once your own order reaches the warehouse your agent photographs your exact item, so you can check logos, stitching and colour before it ships.</p>`
          : `<p>There are no buyer QC photos for this listing yet. Once you order, your agent photographs your exact item at the warehouse before it ships, so you can still check it before paying for shipping.</p>`) +
    `<p>International shipping isn't included in the price; you pay it when you ship your parcel, and it depends on weight and your country.</p>`;
  // Icon facts above the first paragraph; they restate the paragraphs (platform, price, QC flag, shipping not included).
  const aboutFacts = `<ul class="ic-row">${[["store", plat], ["coins", isPH(p.cny) ? "Ask seller" : `${money(p.cny)} · ¥${p.cny}`], ["camera", p.qc ? "QC photos on record" : "No QC photos yet"], ["truck", "Shipping not included"]]
    .map(([n, t]) => `<li>${ic(n)}<span>${esc(t)}</span></li>`).join("")}</ul>`;
  const DT_IC = { "Marketplace": "store", "Category": "grid", "QC photos": "camera", "Item ID": "hash", "Typical weight": "scale", "Price compared": "chart", "Price check": "coins", "Same name": "layers",
    "Spreadsheets": "sheet", "Views (30 days)": "eye", "Saved by": "star", "Link check": "refresh" };
  const dtIcons = html => html.replace(/<dt>([^<]+)<\/dt>/g, (m, k) => `<dt>${ic(DT_IC[k] || "info", "sm")}${k}</dt>`);
  const sheetBrand = p.brand && agentBrands().includes(p.brand) ? idx().brandSlug.get(p.brand) : null;
  const sheets = AGENT_BRAND_AGENTS.map(k => `<a href="/${k}-spreadsheet${sheetBrand ? "/" + sheetBrand : ""}">${esc(AGENTS[k].name)}</a>`).join(" · ");
  const model = modelFor(p);
  const body = `${bc.html}
<div class="pd">
  <div class="pd-media"><div class="pimg${cutCls(p)}">${src ? `<img id="pmain" src="${esc(src)}"${mainSet(src)} alt="${esc(p.title)}" width="600" height="600" fetchpriority="high">` : ""}</div>
    ${src && SG[p.id] ? storeThumbs(p, src, SG[p.id]) : ""}
    ${qcs.length ? `<h2 class="qc-h" id="qc">Real QC photos</h2><div class="qcs">${qcs.map((u, i) => `<a href="${esc(u)}" target="_blank" rel="noopener"><img src="${esc(thumbSrc(u))}" data-o="${esc(u)}" alt="${esc(p.title)} QC photo ${i + 1}" width="96" height="96" loading="lazy" decoding="async" onerror="if(this.dataset.o){this.src=this.dataset.o;this.dataset.o=''}else this.parentNode.remove()"></a>`).join("")}</div>`
      : p.qc >= 1 && QC_BANKED[p.id] ? `<div class="qc-load" id="qc"><button class="btn sm" type="button" data-sf="${esc(p.platform)}" data-id="${esc(p.itemId || p.id)}">${ic("camera", "sm")}Show buyer QC photos</button></div><script>${QC_LOAD_JS}</script>` : ""}
    ${GALLERY_JS}
  </div>
  <div class="pd-info">
    ${bUrl ? `<a class="pd-brand" href="${bUrl}">${esc(p.brand)}</a>` : (p.brand ? `<span class="pd-brand">${esc(p.brand)}</span>` : "")}
    <h1>${esc(p.title)}</h1>${statRow(p)}
    ${swapOf ? "" : recBadge(p, false, "inline") ? `<p style="margin:10px 0 0">${recBadge(p, false, "inline").replace("margin-left:10px;", "")}</p>` : ""}
    <div class="price">${money(p.cny)}<small>${isPH(p.cny) ? "placeholder price · ask seller" : "before shipping" + (priceChecked(p) ? ` · checked ${dayShort(priceChecked(p))}` : "")}</small></div>
    ${!rep && /^(Tops|Outerwear|Pants|Shorts|Shoes)$/.test(p.cat || "") ? `<div data-pcsz-id="${esc(p.id)}" data-pcsz-cat="${esc(p.cat)}"${p.g === "w" ? ' data-pcsz-g="w"' : ""}></div><script src="/size.js?v=9" defer></script>` : ""}
    <p class="pd-bl">Buy through your agent</p>
    ${buyBox}
    ${askRow(p)}
    ${opts.length ? `<div class="opts"><span class="opts-l">${ic("tag", "sm")}Options</span><div class="chips">${opts.slice(0, 12).map(o => `<span>${esc(o)}</span>`).join("")}</div></div>` : ""}
  </div>
</div>
${alsoRow}
<h2>About this find</h2>${aboutFacts}<div class="prose">${about1}</div>${more("Read more", `<div class="prose">${aboutMore}</div>`)}
<div class="pd-more">${agentHubLine(p)}
    <details class="dcard dmore"><summary><h2 id="pd-details">Details</h2>${ic("chevron-down", "sm")}</summary>
    <dl class="kv">${dtIcons(`<dt>Marketplace</dt><dd>${plat}${PLAT_HUBS[p.platform] ? ` · <a href="/${p.platform}-spreadsheet">${PLAT_HUBS[p.platform].name} spreadsheet</a>` : ""}</dd><dt>Category</dt><dd>${cUrl ? `<a href="${cUrl}">${esc(cat.name)}</a>` : esc(p.cat)}</dd>
      <dt>QC photos</dt><dd>${qcs.length ? qcs.length + " shown" : (p.qc && QC_BANKED[p.id] ? "On record" : "None yet")}</dd><dt>Item ID</dt><dd>${esc(p.itemId || p.id)}</dd>${productFacts(p, g, checked)}<dt>Spreadsheets</dt><dd>${sheets}</dd>`)}</dl></details>
    <p class="more"><a href="/#p/${encodeURIComponent(p.id)}">${ic("grid", "sm")}Open in the catalogue${ic("arrow-right", "sm")}</a></p>
</div>
${qcCheck(p, model)}
<h2>How to buy it</h2>${icSteps([["cart", "Tap Buy"], ["ruler", "Pick size, pay"], ["camera", "Check QC, ship"]])}${more("Step by step", `<ol class="steps prose"><li>Tap <strong>Buy via MyCNBox</strong> (or your agent). The listing opens pre-filled.</li><li>Pick your size and colour, check our <a href="/guides/sizing">sizing guide</a>, and pay for the item plus delivery to the warehouse.</li><li>Check the QC photos (<a href="/guides/how-to-qc">what to look for</a>), then combine items into one parcel and ship. <a href="/how-to-order">Watch the 56-second video</a>.</li></ol>`)}
${model ? `<div class="note" style="margin-top:22px">${ic("award", "sm")}Comparing batches? See all <a href="/best/${model.slug}">${modelList(model).length} ${esc(model.name)} rep listings</a> ranked by views.</div>` : ""}
${sameBrand.length ? `<div class="sh"><h2>More ${esc(p.brand)} finds</h2><a class="vm" href="${bUrl}">All ${brandFacts(p.brand).n.toLocaleString("en-US")} ${esc(p.brand)} reps on the spreadsheet${ic("arrow-right", "sm")}</a></div>${grid(sameBrand)}` : ""}
${sameCat.length ? `<div class="sh"><h2>Similar ${esc((cat.name || p.cat).toLowerCase())}</h2>${cUrl ? `<a class="vm" href="${cUrl}">All ${esc((cat.name || p.cat).toLowerCase())}${ic("arrow-right", "sm")}</a>` : ""}</div>${grid(sameCat)}` : ""}
${buyBar}`;
  const pageLd = { "@context": "https://schema.org", "@type": "ItemPage", name: p.title, url: SITE + productUrl(p), description: desc,
    primaryImageOfPage: src ? { "@type": "ImageObject", contentUrl: src } : undefined, isPartOf: { "@type": "WebSite", name: "Puro Classico", url: SITE + "/" } };
  // Google shows ~60-65 characters of a title (SEO pass, 21 Oct 2026): drop the least useful part first.
  const tMid = p.qc ? "Price, QC & Agent Links" : "Price & Where to Buy";
  const title = [`${tName} Rep: ${tMid} | Puro Classico`, `${tName} Rep: ${tMid}`, `${tName} Rep | Puro Classico`].find(x => x.length <= 65) || `${tName} Rep`;
  // A refresh in a tab that had this find open in the app (sessionStorage "pc.appfind", set by index.html openDetail) goes back
  // to the app view before anything paints (owner, 23 Nov 2026). New tabs, shared links and Google get this page.
  const appBack = `<script>try{if(sessionStorage.getItem("pc.appfind")===${JSON.stringify(String(p.id))})location.replace("/#p/"+encodeURIComponent(${JSON.stringify(String(p.id))}))}catch(e){}</script>`;
  const res = page({ title, desc, path: productUrl(p), body, extraHead: appBack,
    jsonld: [bc.data, pageLd], image: src || undefined, robots: indexable(p) && !rep ? "index,follow,max-image-preview:large" : "noindex,follow" });
  if (qcr.failed) res.headers.set("x-qc-miss", "1");   // the QC cache read failed or timed out: product/[id].js keeps this render only briefly
  return res;
}

// "Ask AI about this item" (owner, 9 Nov 2026: live on product pages). Shown once chat.js says the assistant is ready
// (pc-chat-ready); a tap opens the chat and asks about this find. The chat reads the find id from the URL (/product/<id>).
const ASK_SPARK = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l1.8 4.6L18.5 9.4l-4.7 1.8L12 16l-1.8-4.8L5.5 9.4l4.7-1.8z"/><path d="M19 15l.8 2 .2.2 2 .8-2 .8-.2.2-.8 2-.8-2-.2-.2-2-.8 2-.8.2-.2z"/></svg>';
const ASK_CSS = "<style>.pd-ask{display:flex;align-items:center;gap:10px;width:100%;min-height:48px;margin-top:14px;padding:4px 0 0;border:0;border-top:1px solid var(--line);background:none;color:var(--ink);font:inherit;font-size:14px;font-weight:500;text-align:left;cursor:pointer;-webkit-tap-highlight-color:transparent}.pd-ask[hidden]{display:none}.pd-ask-ic{flex:none;display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--surface-2);color:var(--ink-2)}.pd-ask-t{flex:1}.pd-ask>svg:last-child{width:16px;height:16px;color:var(--muted);transition:transform .15s cubic-bezier(.22,1,.36,1)}@media (hover:hover){.pd-ask:hover>svg:last-child{transform:translateX(2px)}}</style>";
// 15 Nov 2026 (SEO, agent keywords): an in-text link from every product page to the agent spreadsheets. Links in the page
// text count for more than the footer. Three of the five agent hubs, picked by the find's id so the anchors spread evenly;
// for a big brand the link goes to that brand on the agent's sheet ("Acne Studios on the KakoBuy spreadsheet").
function agentHubLine(p) {
  const names = { mycnbox: "MyCNBox", kakobuy: "KakoBuy", oopbuy: "Oopbuy", lovegobuy: "LoveGoBuy", sugargoo: "Sugargoo" };
  const ks = AGENT_BRAND_AGENTS, h = [...String(p.id)].reduce((t, c) => (t * 31 + c.charCodeAt(0)) >>> 0, 7), pick = [0, 1, 2].map(i => ks[(h + i) % ks.length]);
  const { brandSlug } = idx(), bs = p.brand && agentBrands().includes(p.brand) ? brandSlug.get(p.brand) : "";
  const a = pick.map((k, i) => i === 0 && bs ? `<a href="/${k}-spreadsheet/${bs}">${esc(p.brand)} on the ${names[k]} spreadsheet</a>` : `<a href="/${k}-spreadsheet">${names[k]} spreadsheet</a>`);
  return `<p class="pd-hubs" style="margin:14px 0 0;font-size:13px;line-height:1.5;color:var(--muted,#888)">More finds: ${a[0]}, the ${a[1]} and the ${a[2]}.</p>`;
}
function askRow(p) {
  const q = JSON.stringify(`Tell me about the ${p.title}: is it worth it, and what should I check before I buy?`).replace(/</g, "\\u003c");
  return `${ASK_CSS}<button type="button" class="pd-ask" id="pd-ask" hidden><span class="pd-ask-ic">${ASK_SPARK}</span><span class="pd-ask-t">Ask AI about this item</span>${ic("chevron-right", "sm")}</button>` +
    `<script>(function(){var b=document.getElementById("pd-ask");if(!b)return;function on(){b.hidden=false;}if(window.pcChatReady)on();else document.addEventListener("pc-chat-ready",on);b.addEventListener("click",function(){if(window.pcChatAsk)window.pcChatAsk(${q});});})();</script>`;
}

// ------------------------------------------------------------------ hub layout v10 (12 Nov 2026)
// Owner (12 Nov 2026, /old-money): "so many ugly pages". Hubs opened on three paragraphs, a facts row and three rows of
// chips, and no find was on the first screen. Every hub now has one compact head: breadcrumbs, the h1, one short lead
// sentence and a slim facts line, then ONE row of related links (sideways scroll on phones, "More" on wide screens) and a
// "Shop this on" row of agent logos, then the finds. The long copy, the link groups and the FAQ are unchanged and still in
// the HTML, in an "About" section under the grid (hxAbout: two columns from 900px, a 68ch measure, FAQ as <details>).
// The app hubs (hubParts) use the same pieces. HX_CSS is inlined because the app hubs do not load ds.css; its colours are
// the shared tokens (the app's --ground stands in for --bg).
const HX_MORE_AT = 8;   // more related links than this: a "More" button on wide screens (phones scroll the row)
const AGENT_PATH = /^\/([a-z0-9]+)-spreadsheet(?:\/|$)/;
const agentOf = u => { const m = String(u).match(AGENT_PATH); return m && AGENTS[m[1]] ? m[1] : null; };
const hxChip = ([t, u, cls]) => `<a href="${u}"${cls ? ` class="${cls}"` : ""}>${AGENT_URL.test(u) ? "" : chipIcon(u)}${esc(t)}</a>`;
const HX_MORE_JS = "var r=this.parentNode,o=r.classList.toggle('open');this.setAttribute('aria-expanded',o);this.firstChild.textContent=o?'Less':'More'";
function hxRow(links, label = "Related pages") {
  const seen = new Set(), L = (links || []).filter(([, u]) => !seen.has(u) && seen.add(u));
  if (!L.length) return "";
  // 26 Nov 2026 (owner): the related links fold into one quiet toggle (closed), like the footer's "All pages"; every link
  // stays in the page for crawlers.
  return `<details class="hx-rel"><summary>${esc(label === "Related pages" ? "Guides and related pages" : label)}${ic("chevron-down", "sm")}</summary>` +
    `<nav class="hx-row open" aria-label="${esc(label)}"><div class="hx-chips">${L.map(hxChip).join("")}</div></nav></details>`;
}
// Agent links ([text, "/<agent>-spreadsheet..."]) as logo pills, one per agent, the first five then "+N". The link text
// is the agent's name; the full text ("Old money on KakoBuy") is the aria-label and stays as link text in the About lists.
function hxShop(links, label = "Shop this on") {
  const seen = new Set(), L = (links || []).filter(([, u]) => { const k = agentOf(u); return k && !seen.has(k) && seen.add(k); });
  if (!L.length) return "";
  const pill = ([t, u]) => { const k = agentOf(u); return `<a href="${u}" aria-label="${esc(t)}"><img src="/img/agents/${k}.webp" width="24" height="24" alt="" decoding="async">${esc(AGENTS[k].name)}</a>`; };
  const first = L.slice(0, 5), rest = L.slice(5);
  return `<div class="hx-shop"><span class="hx-shop-l">${esc(label)}</span><div class="hx-shop-r">${first.map(pill).join("")}` +
    (rest.length ? `<details class="hx-shop-x"><summary>+${rest.length}<span class="vh"> more agents</span></summary><div>${rest.map(pill).join("")}</div></details>` : "") + `</div></div>`;
}
const hxFacts = items => `<p class="hx-facts">${items.filter(Boolean).map(x => `<span>${x}</span>`).join("")}</p>`;
// The About section under the grid. main: HTML copy (left column); faq: [[q, a]] (plain text, <details>); groups:
// [[title, [[text, url]]]] as link lists (right column).
function hxAbout({ title, main = "", faq = [], groups = [], tail = "", after = "" }) {
  const side = groups.filter(g => g && g[1] && g[1].length).map(([t, links]) => `<div class="hx-group"><h3>${esc(t)}</h3><ul class="hx-links${links.length > 7 ? " two" : ""}">${links.map(([x, u]) => `<li><a href="${u}">${esc(x)}</a></li>`).join("")}</ul></div>`).join("") + tail;
  const fq = faq && faq.length ? `<h2 class="hx-h2">FAQ</h2><div class="hx-faq">${faq.map(([q, a]) => `<details><summary>${esc(q)}</summary><p>${esc(a)}</p></details>`).join("")}</div>` : "";
  if (!main && !fq && !side) return after ? `<section class="hx-about">${after}</section>` : "";
  return `<section class="hx-about" aria-labelledby="hx-about-h"><h2 id="hx-about-h" class="hx-title">${esc(title)}</h2>` +
    `<div class="hx-cols${main || fq ? "" : " solo"}">${main || fq ? `<div class="hx-main">${main}${fq}</div>` : ""}${side ? `<div class="hx-side">${side}</div>` : ""}</div>${after}</section>`;
}
// "New finds" (12 Nov 2026, SEO check): plain links to the newest finds, in the server HTML of the homepage, every brand
// hub (that brand's newest) and /new. Before this the homepage HTML linked no RepLibrary find at all, and new finds of a
// big brand sat on its last pages. Text links only (no photos), so the block costs a few KB and no image requests.
export const NEW_LINKS = 24;
export function newFindsHtml(list, title, all = "/new") {
  if (!list.length) return "";
  return `<section class="hx-new" aria-labelledby="hx-new-h"><div class="hx-new-top"><h2 id="hx-new-h" class="hx-h2">${esc(title)}</h2><a href="${all}">See all new finds${ic("arrow-right", "sm")}</a></div>` +
    `<ul class="hx-newl">${list.map(p => `<li><a href="${productUrl(p)}">${p.brand && !p.title.toLowerCase().startsWith(p.brand.toLowerCase()) ? `<span>${esc(p.brand)}</span> ` : ""}${esc(p.title)}</a></li>`).join("")}</ul></section>`;
}
export const HX_CSS = `<style id="hx-css">
details.hx-rel{margin:12px 0 0}
details.hx-rel>summary{list-style:none;display:inline-flex;align-items:center;gap:6px;min-height:36px;cursor:pointer;font-size:13.5px;font-weight:500;color:var(--muted);-webkit-tap-highlight-color:transparent}
details.hx-rel>summary::-webkit-details-marker{display:none}
details.hx-rel>summary:hover{color:var(--ink)}
details.hx-rel>summary .ic{transition:transform .2s ease}
details.hx-rel[open]>summary .ic{transform:rotate(180deg)}
details.hx-rel>summary:focus-visible{outline:2px solid var(--ink);outline-offset:3px;border-radius:6px}
details.hx-rel .hx-row{margin-top:6px}
details.hx-rel .hx-chips{flex-wrap:wrap;overflow:visible;max-height:none}
@media (pointer:coarse){details.hx-rel>summary{min-height:44px}}
@media (prefers-reduced-motion:reduce){details.hx-rel>summary .ic{transition:none}}
.hx{--hx-g:32px;--hx-bg:var(--bg,var(--ground,#fff))}
.hx-head .bc{margin:0 0 10px}
.hx-top{display:flex;align-items:center;justify-content:space-between;gap:16px}
.hx-top h1{margin:0;font-size:clamp(24px,1.2vw + 18px,34px);line-height:1.15;letter-spacing:-.025em;text-wrap:balance}
.hx-top h1 small{color:var(--muted);font-size:.5em;font-weight:500;letter-spacing:0}
.hx-lead{margin:8px 0 0;max-width:80ch;font-size:16px;line-height:1.5;color:var(--muted);text-wrap:pretty}
.hx-facts{display:flex;flex-wrap:wrap;margin:8px 0 0;overflow:hidden;font-size:13.5px;line-height:22px;color:var(--muted);font-variant-numeric:tabular-nums}
.hx-facts span{margin:0 17px 0 -17px;white-space:nowrap}
.hx-facts span::before{content:"\\00B7";display:inline-block;width:17px;text-align:center;color:var(--muted)}
.hx-facts b{color:var(--ink);font-weight:600}
.hx-row{display:flex;align-items:flex-start;gap:8px;margin:16px 0 0}
.hx-chips{flex:1;min-width:0;display:flex;flex-wrap:wrap;gap:8px;max-height:40px;overflow:hidden}
.hx-row.open .hx-chips{max-height:none}
.hx-chips a,.hx-more,.hx-shop a,.hx-shop-x summary{flex:none;display:inline-flex;align-items:center;gap:6px;height:40px;padding:0 16px;border:1px solid var(--line-2);border-radius:999px;background:var(--hx-bg);color:var(--ink);font:inherit;font-size:14px;font-weight:500;line-height:1;white-space:nowrap;text-decoration:none;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:background-color .1s linear,border-color .1s linear,transform .12s cubic-bezier(.22,1,.36,1)}
.hx-chips a .ic{width:16px;height:16px;color:var(--muted)}
.hx-chips a.hot{background:var(--fill);border-color:var(--fill);color:var(--fill-ink)}
.hx-chips a.hot .ic{color:inherit}
.hx-more .ic{width:16px;height:16px;color:var(--muted);transition:transform .2s cubic-bezier(.22,1,.36,1)}
.hx-row.open .hx-more .ic{transform:rotate(180deg)}
.hx-shop{display:flex;align-items:center;gap:12px;margin:12px 0 0}
.hx-shop-l{flex:none;font-size:13.5px;color:var(--muted)}
.hx-shop-r{display:flex;align-items:center;gap:8px;min-width:0}
.hx-shop a{gap:8px;padding:0 14px 0 7px;background:var(--surface-2,var(--hx-bg));border-color:transparent}
.hx-shop img{flex:none;width:24px;height:24px;border-radius:50%;object-fit:cover;outline:1px solid rgba(0,0,0,.08);outline-offset:-1px}
.hx-shop-x{position:relative}
.hx-shop-x summary{list-style:none;padding:0 14px;font-variant-numeric:tabular-nums}
.hx-shop-x summary::-webkit-details-marker{display:none}
.hx-shop-x[open]>div{position:absolute;z-index:20;top:46px;left:0;display:grid;gap:4px;min-width:200px;padding:6px;border:1px solid var(--line);border-radius:22px;background:var(--hx-bg);box-shadow:0 10px 30px rgba(0,0,0,.12)}
.hx-shop-x[open]>div a{justify-content:flex-start;background:transparent}
@media (hover:hover){.hx-chips a:hover,.hx-more:hover,.hx-shop-x summary:hover{background:var(--surface-2)}.hx-shop a:hover{border-color:var(--line-2)}.hx-chips a.hot:hover{background:var(--fill);opacity:.9}}
.hx-chips a:active,.hx-more:active,.hx-shop a:active{transform:scale(.97)}
.hx .vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
html.hub .v9-hero-in{align-items:flex-start;text-align:left}
.hx-hero{align-self:stretch;min-width:0}
.hx-app>.hx-about{box-sizing:border-box;max-width:1280px;margin:56px auto 0;padding:40px 24px 16px;border:0;box-shadow:inset 0 1px 0 var(--line);background-clip:content-box}
@media (min-width:1329px){.hx-app>.hx-about{box-shadow:none;border-top:1px solid var(--line);max-width:1232px;padding-inline:0}}
.hx-hero .hx-row{margin-top:6px}
.hx-about{margin:56px 0 0;padding:40px 0 16px;border-top:1px solid var(--line)}
.hx-title{margin:0 0 24px;font-size:24px;line-height:1.25;letter-spacing:-.02em;text-wrap:balance}
.hx-about table{display:block;max-width:100%;overflow-x:auto;border-collapse:collapse;margin:12px 0;font-size:14px;line-height:1.4;font-variant-numeric:tabular-nums}
.hx-about th,.hx-about td{padding:7px 14px 7px 0;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.hx-about th{font-weight:600;color:var(--ink);white-space:nowrap}
.hx-cols{display:grid;gap:40px}
@media (min-width:900px){.hx-cols{grid-template-columns:minmax(0,1fr) minmax(280px,340px);gap:72px}.hx-cols.solo{grid-template-columns:1fr}.hx-cols.solo .hx-side{grid-template-columns:repeat(auto-fill,minmax(280px,1fr));column-gap:48px}}
.hx-main{max-width:68ch;min-width:0;color:var(--ink-2);font-size:16px;line-height:1.65}
.hx-main>:first-child{margin-top:0}
.hx-main p,.hx-main ul,.hx-main ol{margin:0 0 14px}
.hx-main h3{margin:32px 0 8px;font-size:18px;line-height:1.35;letter-spacing:-.01em;font-weight:600}
.hx-main a{color:var(--ink);text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px;text-decoration-color:color-mix(in srgb,var(--ink) 30%,transparent)}
.hx-main strong{color:var(--ink);font-weight:600}
.hx-h2{margin:40px 0 4px;font-size:20px;line-height:1.3;letter-spacing:-.015em}
.hx-faq details{border-bottom:1px solid var(--line)}
.hx-faq summary{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:52px;padding:12px 0;font-size:16px;font-weight:500;line-height:1.4;color:var(--ink);cursor:pointer;list-style:none;-webkit-tap-highlight-color:transparent}
.hx-faq summary::-webkit-details-marker{display:none}
.hx-faq summary::after{content:"";flex:none;width:16px;height:16px;background:var(--muted);-webkit-mask:var(--hx-chev) center/16px no-repeat;mask:var(--hx-chev) center/16px no-repeat;transition:transform .2s cubic-bezier(.22,1,.36,1)}
.hx-faq details[open] summary::after{transform:rotate(180deg)}
.hx-faq p{margin:0 0 16px;color:var(--ink-2)}
.hx{--hx-chev:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")}
.hx-side{display:grid;gap:32px;align-content:start;min-width:0}
.hx-group h3{margin:0 0 6px;font-size:13.5px;font-weight:600;line-height:1.4;letter-spacing:0;color:var(--muted)}
.hx-links{margin:0;padding:0;list-style:none}
.hx-links.two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:20px}
.hx-links.two li{display:flex}
.hx-links.two li>a{flex:1}
.hx-links li{break-inside:avoid}
.hx-links a{display:flex;align-items:center;min-height:38px;padding:4px 0;border-bottom:1px solid var(--line);font-size:14.5px;line-height:1.3;color:var(--ink);text-decoration:none;transition:color .1s linear}
@media (hover:hover){.hx-links a:hover{color:var(--muted)}}
.hx-pages{display:flex;flex-wrap:wrap;gap:6px}
.hx-pages a{display:inline-flex;align-items:center;justify-content:center;min-width:40px;height:40px;padding:0 12px;border:1px solid var(--line-2);border-radius:999px;color:var(--ink);font-size:14px;font-weight:500;text-decoration:none;font-variant-numeric:tabular-nums}
.hx-new{margin:48px 0 0}
.hx-about .hx-new{margin-top:48px}
.hx-new-top{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin:0 0 8px}
.hx-new-top .hx-h2{margin:0}
.hx-new-top a{display:inline-flex;align-items:center;gap:4px;min-height:44px;font-size:14px;font-weight:500;color:var(--ink);text-decoration:none;white-space:nowrap}
.hx-new-top a .ic{width:16px;height:16px}
.hx-newl{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));column-gap:24px;margin:0;padding:0;list-style:none}
.hx-newl a{display:block;padding:10px 0;border-bottom:1px solid var(--line);font-size:14.5px;line-height:1.35;color:var(--ink);text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hx-newl a span{color:var(--muted)}
@media (hover:hover){.hx-newl a:hover,.hx-new-top a:hover{color:var(--muted)}}
.hx-app.hx-home{box-sizing:border-box;max-width:1280px;margin:0 auto;padding:8px 24px 32px}
@media (max-width:640px){
.hx{--hx-g:16px}
.hx-app.hx-home{padding-inline:16px}
.hx-newl a{padding:12px 0}
.hx.hx-hero{--hx-g:var(--_gut,16px)}
.hx-app>.hx-about{padding-inline:16px}
.hx-top{flex-direction:column;align-items:stretch;gap:12px}
.hx-lead{font-size:15px}
.hx-row,.hx-shop{margin-inline:calc(-1 * var(--hx-g));padding-inline:var(--hx-g)}
.hx-row{display:block;margin-top:14px;padding-inline:0}
.hx-chips{flex-wrap:nowrap;max-height:none;overflow-x:auto;padding-inline:var(--hx-g);scroll-padding-inline:var(--hx-g);scrollbar-width:none;overscroll-behavior-x:contain}
.hx-chips::-webkit-scrollbar,.hx-shop-r::-webkit-scrollbar{display:none}
.hx-chips a,.hx-shop a,.hx-shop-x summary{height:44px}
.hx-more{display:none}
.hx-shop{padding-inline:0}
.hx-shop-l{display:none}
.hx-shop-r{overflow-x:auto;padding-inline:var(--hx-g);scrollbar-width:none}
.hx-shop-x[open]>div{position:fixed;left:16px;right:16px;top:auto;bottom:16px}
.hx-about{margin-top:40px;padding-top:32px}
.hx-links a,.hx-pages a{min-height:44px}
.hx-pages a{height:44px;min-width:44px}
}
@media (prefers-reduced-motion:reduce){.hx *{transition:none!important}}
</style>`;
// ------------------------------------------------------------------ hubs
// lead: one short plain-text sentence under the h1. filters: [[text, url, class?]] for the one row of related links.
// shop: { label, links } for the agent logo row (hxShop). groups: [[title, [[text, url]]]] for the About section's link
// lists. intro and extra (HTML) and the FAQ are page 1 only, in the About section under the grid.
function hub({ path, n, list, title, desc, h1, intro = "", lead = "", trail, filters = [], shop = null, groups = [], top = "", extra = "", faq = null, total = null, ldCount = undefined, idxFirst = false, facts = [], full = "", aboutTitle = "", key = "" }) {
  const pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
  if (n < 1 || n > pages) return null;
  // idxFirst (brand and category hubs, 28 Oct 2026): page 1 is the app with the 60 most viewed. From page 2 on, the finds
  // whose own page may be indexed come before the noindex ones, each group most viewed first. In plain view order the
  // indexable finds of /category/tops ran to page 30 of 56; this way they end on page 18 and the later pages hold the rest.
  const order = idxFirst && n > 1 ? list.slice(0, PER_PAGE).concat(list.slice(PER_PAGE).filter(indexable), list.slice(PER_PAGE).filter(p => !indexable(p))) : list;
  const slice = order.slice((n - 1) * PER_PAGE, n * PER_PAGE);
  const url = n === 1 ? path : `${path}/${n}`;
  const bc = crumbs(trail.concat(n > 1 ? [[`Page ${n}`, url]] : []));
  // v10 (12 Nov 2026): every server hub has the app hub's compact head (hxRow, hxShop above) and the same card grid
  // (ds.css .hub-p2); pages 2+ of brand and category hubs keep the "Open the full ... spreadsheet" pill next to the h1.
  const p2 = idxFirst && n > 1 && full;
  const h1Html = `<h1>${esc(h1)}${n > 1 ? ` <small>page ${n}</small>` : ""}</h1>`;
  const pr = priceRange(list);
  const head = `<header class="hx-head">${bc.html}<div class="hx-top">${h1Html}${p2 ? `<a class="btn primary hub-full" href="${path}">${ic("sheet", "sm")}Open the full ${esc(full)} spreadsheet${ic("arrow-right", "sm")}</a>` : ""}</div>` +
    `${lead ? `<p class="hx-lead">${esc(lead)}</p>` : ""}${hxFacts([`<b>${nf(total || list.length)}</b> finds`, ...facts, idxFirst && n > 1 ? "QC-marked, curated and viewed finds first" : "", pr, `Catalogue updated ${BUILT_DAY}`])}</header>`;
  const about = hxAbout({ title: n === 1 ? (aboutTitle || `About ${h1}`) : "Keep browsing", main: n === 1 ? intro + extra : "", faq: n === 1 ? faq : [], groups });
  const body = `<div class="hub-p2 hx">${head}
${hxRow(filters)}${shop ? hxShop(shop.links, shop.label) : ""}
${n === 1 ? top : ""}${grid(slice, 4)}
${pager(path, n, pages)}
${about}</div>`;
  const ld = [bc.data, listLd(h1, url, slice, ldCount)]; if (n === 1 && faq && faq.length) ld.push(faqLd(faq));
  const meta = n > 1 ? pageNMeta({ key: key || h1, n, slice, from: (n - 1) * PER_PAGE + 1, N: total || list.length }) : { title: fitTitle(title), desc };
  return page({ title: meta.title, desc: meta.desc, path: url, body, jsonld: ld, image: slice[0] ? imgSrc(slice[0]) : undefined, extraHead: HX_CSS });
}
// Pages 2+ of a list (22 Nov 2026, SEO check): a title and a description of their own, made from the finds on that page.
// Before, page N had page 1's title plus ": Page N" and a near-copy of page 1's description, and Google showed some of them
// in place of page 1 (page 8 of the 1688 spreadsheet for "1688 spreadsheet", page 2 of Acne Studios for "acne studios
// reps"). The list's own words (key: "Acne Studios Reps", "Weidian Spreadsheet") stay first, so a page N that already
// ranks keeps them; what follows is what only that page has: its brands (or item types on a one-brand list), its prices
// and how many of its finds are marked with buyer QC photos. Canonicals stay on the page itself.
function pageNMeta({ key, n, slice, from, N }) {
  const top = f => { const m = new Map(); for (const p of slice) { const k = f(p); if (k) m.set(k, (m.get(k) || 0) + 1); } return [...m].sort((a, b) => b[1] - a[1]).map(x => x[0]); };
  const brands = top(p => p.brand), kinds = top(p => (CATS[p.cat] || {}).name || p.cat);
  const names = brands.length > 1 ? brands : kinds.length > 1 ? kinds : [];
  const to = from + slice.length - 1, prices = typicalPrices(slice), q = slice.filter(p => p.qc >= 1).length;
  const base = `${key}, Page ${n}`;
  let title = base, i = 0;
  if (names.length) { while (i < names.length && `${base}: ${names.slice(0, i + 1).join(", ")}`.length <= 60) i++; if (i) title = `${base}: ${names.slice(0, i).join(", ")}`; }
  else { const pr = priceRange(slice).replace(/^(\S+) to \1$/, "$1"); if (pr && `${base}: ${pr}`.length <= 60) title = `${base}: ${pr}`; }
  const span = from === to ? `${nf(from)} of ${nf(N)}` : `${nf(from)} to ${nf(to)} of ${nf(N)}`;
  const lead = /finds$/i.test(key) ? `${key} ${span}` : `${key}, ${from === to ? "find" : "finds"} ${span}`;
  const qc = q ? `, ${nf(q)} marked with buyer QC photos` : "";
  const say = (k, withQc) => `${lead}${k && names.length ? `: ${andList(names.slice(0, k))}` : ""}${prices}${withQc ? qc : ""}. Open any of them in your agent.`;
  const opts = [[4, 1], [3, 1], [2, 1], [4, 0], [3, 0], [2, 0], [0, 1], [0, 0]].map(([k, w]) => say(k, w));
  const desc = opts.find(x => x.length <= 160) || `${lead}${prices}.`;
  return { title, desc };
}

// ------------------------------------------------------------------ brand hubs: facts, top picks, related brands
// Everything a brand hub says about its finds is worked out here, from the catalogue rows and the view stats, each time
// the page renders. Rules that keep it true:
//   - p.qc === 1 is a yes/no flag ("the catalogue marks this listing as having buyer QC photos"), never a number of
//     photos. p.qc >= 2 is the photo count that was stored when the row was imported; nothing refreshes it, so it is
//     printed as "on record", not as "shown". The flag is worded "marked as having", the count "N ... on record".
//   - Views and saves are the site's own counts (data/stats.json). A pick is labelled "most viewed" only from PICK_VIEWS
//     views, "most saved" only from PICK_SAVES saves; a brand without those numbers simply has fewer picks, or no block.
//   - A superlative belongs to one find. When several finds share the top number the label says "Joint ..." and how
//     many others are level, and the card goes to a find whose own page is indexable when there is one.
//   - A listed price far below the same brand's other listings of that item type is not vouched for (priceDoubt below).
//   - The <title> and the meta description use catalogue data only, never the view stats: a failed stats read must not
//     change them. The picks block and the FAQ answer about it are the only parts that move with the stats.
//   - No retail prices, no opinions, no dates: only what a row or the stats file holds.
const PICK_VIEWS = 5, PICK_SAVES = 3, PICK_MAX = 8, PICK_BLOCK_MIN = 3;
const PRICE_TYPE_MIN = 3;   // an item type needs this many priced finds before one of its prices can be called out of line
const nf = n => n.toLocaleString("en-US");
// Item types and their typical shipped weights: functions/_lib/weights.js (one table with the shipping calculator and the app).
// Rows for a product page's facts list that only this site has (21 Oct 2026): its own view and save counts, the link
// check and a typical shipped weight. A row appears only when there is a real number behind it.
// The day the find's shown price was confirmed on its live Weidian listing (price_checks.js), while the shown price is
// still the one confirmed (a partner swap price read later may differ); null otherwise.
const PC_DAYS = PCK.PRICE_DAYS || [], PC_CHECK = PCK.PRICE_CHECK || {};
function priceChecked(p) { const c = PC_CHECK[p.id]; return Array.isArray(c) && +c[1] === +p.cny ? PC_DAYS[c[0]] || null : null; }
const dayShort = (d, year) => new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", year ? { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" } : { day: "numeric", month: "short", timeZone: "UTC" });
function productFacts(p, goneAs, checked) {
  const v = views(p), out = [];
  if (v[1] >= 5) {
    const l = p.brand ? idx().byBrand.get(p.brand) : null;
    let rank = "";
    if (l && l.length >= 10) {
      const r = 1 + l.filter(x => views(x)[1] > v[1]).length, joint = l.some(x => x !== p && views(x)[1] === v[1]);
      if (r <= 10) rank = `, ${joint ? "joint " : ""}#${r} of ${nf(l.length)} ${esc(p.brand)} finds`;
    }
    out.push(["Views (30 days)", `${nf(v[1])}${rank}`]);
  }
  if (false && v[3] >= 1) out.push(["Saved by", `${nf(v[3])} member${v[3] === 1 ? "" : "s"}`]);
  if (p.platform === "weidian" && checked && !goneAs) out.push(["Link check", `Online on ${checked}`]);
  const pc = priceChecked(p);
  if (pc) out.push(["Price check", `Cheapest option on the live Weidian listing on ${dayShort(pc, true)}`]);
  const t = itemType(p);
  const w = weightOf(p);
  if (w) out.push(["Typical weight", `About ${w.long}${w.box ? `, ${w.box.long} with the box` : ""} (<a href="/tools/shipping-calculator">shipping calculator</a>)`]);
  // Facts only this page has (28 Oct 2026), worked out from the catalogue rows. Product pages shared most of their text
  // with every other product page, and 431 indexable ones share their exact title with another find.
  //  - Price compared: where the listed price sits among the same brand's listings of the same item type. Only with 3+
  //    priced listings of that type, and never for a price we do not vouch for (under a third of the half-way price,
  //    the priceDoubt rule in brandFacts). Seller prices only: nothing here is checked against the live listing.
  //  - Same name: the other listings with this exact title (marketplace, item ID and price), linked, so each page says
  //    which one it is.
  if (p.brand && !isPH(p.cny) && !t.startsWith("other") && idx().brandSlug.has(p.brand)) {
    const f = brandFacts(p.brand), tl = ((f.types.find(x => x[0] === t) || [])[1] || []).filter(x => !isPH(x.cny));
    const med = tl.length >= PRICE_TYPE_MIN ? f.lowMedian(tl).cny : 0;
    if (med && p.cny * 3 >= med) {
      const less = tl.filter(x => x.cny < p.cny).length, others = tl.length - 1;
      const who = less === 0 ? `None of the other ${nf(others)}` : less === others ? `All ${nf(others)} other` : `${nf(less)} of the other ${nf(others)}`;
      const noun = t === "jewellery" ? "jewellery pieces" : t;   // "12 Chrome Hearts jewellery" does not read as a count
      out.push(["Price compared", `${who} ${esc(p.brand)} ${esc(noun)} on the spreadsheet ${less === 1 ? "is" : "are"} listed for less; half of all ${nf(tl.length)} are listed at ${money(med)} or less`]);
    }
  }
  const twins = ((p.brand ? idx().byBrand.get(p.brand) : idx().byCat.get(p.cat)) || []).filter(x => x !== p && x.brand === p.brand && x.title.toLowerCase() === p.title.toLowerCase()).slice(0, 6);
  if (twins.length) out.push(["Same name", `<span class="lchips">${twins.map(x => `<a href="${productUrl(x)}">${esc(PLAT[x.platform] || x.platform)} ${esc(x.itemId || x.id)}, ${money(x.cny)}</a>`).join("")}</span>`]);
  return out.map(([k, x]) => `<dt>${k}</dt><dd>${x}</dd>`).join("");
}
const _itemType = new WeakMap();   // a find's item type never changes, so it is worked out once per server instance, not after every stats refresh
export function itemType(p) {
  let t = _itemType.get(p);
  if (t === undefined) { t = itemTypeOf(p); _itemType.set(p, t); }
  return t;
}
// A find's estimated shipped weight (round 8, item 27): the typical weight of its item type, rounded the way pages show it.
// null for types without a sensible figure (toys, "other finds"). box: the weight with the shoe box, for footwear.
export function weightOf(p) {
  const t = itemType(p), w = fmtGrams(typeGrams(t));
  return w ? Object.assign(w, { box: fmtGrams(boxedGrams(t)) }) : null;
}
// The stat chips under the product title (round 8, item 27, the rep-find row): the QC photo count when one is stored,
// then the estimated weight. Short visible text, the full sentence in title / aria-label. Not in JSON-LD (an estimate).
function statRow(p) {
  const w = weightOf(p), out = [];
  if (p.qc >= 2) { const l = `${nf(p.qc)} buyer QC photos on record`; out.push(`<span class="pst" role="img" title="${l}" aria-label="${l}">${ic("camera", "sm")}${nf(p.qc)}</span>`); }
  { const fv = 0; if (fv >= 2) { const l = `Saved by ${nf(fv)} members`; out.push(`<span class="pst" role="img" title="${l}" aria-label="${l}">${ic("star", "sm")}${nf(fv)}</span>`); } }   // owner, 9 Nov 2026: favourite count public
  if (w) { const l = `Estimated weight, about ${w.long}${w.box ? ` (${w.box.long} with the box)` : ""}`; out.push(`<span class="pst" role="img" title="${l}" aria-label="${l}">${ic("bag", "sm")}${w.short}</span>`); }
  return out.length ? `<div class="pstats">${out.join("")}</div>` : "";
}
const firstMax = (arr, f) => { let best = null, bv = -Infinity; for (const p of arr) { const v = f(p); if (v > bv) { bv = v; best = p; } } return best; };   // arr is in score order, so ties go to the higher-ranked find
// Every find of arr that holds the top value of f, in arr's order; none when that value is under min.
const leaders = (arr, f, min) => { let bv = -Infinity; for (const p of arr) { const v = f(p); if (v > bv) bv = v; } return bv >= min ? arr.filter(p => f(p) === bv) : []; };
const lc1 = s => s.charAt(0).toLowerCase() + s.slice(1);
const joint = (label, n) => (n > 1 ? "Joint " + lc1(label) : label);                         // the label of a superlative that n finds share
const level = n => (n > 1 ? `, level with ${nf(n - 1)} other find${n === 2 ? "" : "s"}` : "");   // ...and the words after its number
const shown = ls => ls.find(indexable) || ls[0];                                                // which of the level finds gets the card

// The picks of one brand. `vw` gives a find's [all-time, 30-day, 7-day views, saves]; with NO_STATS only the picks that
// need no view stats come out, which is how brandFacts() knows what a hub can show whatever happens to the stats read.
const NO_STATS = () => [0, 0, 0, 0];
const VIEW_RANK = ["Most viewed", "Second most viewed", "Third most viewed"];
function brandPicks(list, types, priced, priceDoubt, lowDoubt, vw) {
  const picks = [];
  // `rank` orders the labels on the page and in the FAQ answer: the three view ranks, this week, saves, QC photos,
  // price, then the per-type ones. A card sits where its first label does, so "third" never comes before "second".
  const add = (p, rank, k, d) => { let e = picks.find(x => x.p === p); if (!e) { e = { p, why: [], rank, doubt: priceDoubt(p) }; picks.push(e); } e.why.push({ k, d, rank }); if (rank < e.rank) e.rank = rank; };
  const v30 = p => vw(p)[1], v7 = p => vw(p)[2], sv = p => vw(p)[3];
  // Most, second and third most viewed. A find's place is 1 + the number of finds with more views, so two finds on the
  // same number share a place ("Joint second most viewed") and the next one down is third, not second.
  const viewed = list.filter(p => v30(p) >= PICK_VIEWS).sort((x, y) => v30(y) - v30(x) || indexable(y) - indexable(x));   // stable: level finds stay in score order, indexable ones first
  viewed.slice(0, 3).forEach(p => { const v = v30(p), r = viewed.filter(x => v30(x) > v).length, t = viewed.filter(x => v30(x) === v).length;
    add(p, r, joint(VIEW_RANK[r], t), `${nf(v)} views in the last 30 days${level(t)}`); });
  const top30 = viewed.filter(p => v30(p) === v30(viewed[0]));
  const wk = leaders(list, v7, PICK_VIEWS);
  if (wk.length && !wk.some(p => top30.includes(p))) add(shown(wk), 3, joint("Most viewed this week", wk.length), `${nf(v7(wk[0]))} views in the last 7 days${level(wk.length)}`);
  const saved = leaders(list, sv, PICK_SAVES);
  if (saved.length) add(shown(saved), 4, joint("Most saved", saved.length), `saved ${nf(sv(saved[0]))} times${level(saved.length)}`);
  const qTops = leaders(list, p => p.qc, 2);   // a real photo count, never the flag value 1
  if (qTops.length) add(shown(qTops), 5, joint("Most QC photos on record", qTops.length), `${nf(qTops[0].qc)} buyer QC photos${level(qTops.length)}`);
  // Cheapest among the finds that carry a photo count. Named only when that price is believable (lowDoubt): if the
  // cheapest one is priced far below the rest, there is no pick, because naming the next one "lowest" would not be true.
  const counted = priced.filter(p => p.qc >= 2);
  if (counted.length >= 2 && !lowDoubt(counted[0])) { const low = counted.filter(p => p.cny === counted[0].cny);
    add(shown(low), 6, joint("Lowest price with a QC photo count", low.length), `${money(low[0].cny)}${level(low.length)}`); }
  // Then, per item type with 3+ finds: its most viewed find (busiest type first), then the one with the most QC photos
  // on record when at least two finds of that type carry a count. Types already covered by an overall leader are skipped.
  const perType = types.filter(([t, l]) => l.length >= 3 && !t.startsWith("other"));
  const topTypes = new Set(top30.map(itemType)), qTypes = new Set(qTops.map(itemType));
  perType.filter(([t]) => !topTypes.has(t)).map(([t, l]) => [t, l.length, leaders(l, v30, PICK_VIEWS)]).filter(x => x[2].length)
    .sort((x, y) => v30(y[2][0]) - v30(x[2][0]))
    .forEach(([t, n, ls]) => add(shown(ls), 7, joint(`Most viewed of the ${nf(n)} ${t}`, ls.length), `${nf(v30(ls[0]))} views in the last 30 days${level(ls.length)}`));
  perType.filter(([t, l]) => !qTypes.has(t) && l.filter(p => p.qc >= 2).length >= 2).map(([t, l]) => [t, l.length, leaders(l, p => p.qc, 2)])
    .sort((x, y) => y[2][0].qc - x[2][0].qc)
    .forEach(([t, n, ls]) => add(shown(ls), 8, joint(`Most QC photos of the ${nf(n)} ${t}`, ls.length), `${nf(ls[0].qc)} buyer QC photos on record${level(ls.length)}`));
  picks.sort((x, y) => x.rank - y.rank);   // stable, so cards of the same rank keep the order they were added in
  for (const x of picks) x.why.sort((a, c) => a.rank - c.rank);
  const out = picks.slice(0, PICK_MAX);
  return out.length >= PICK_BLOCK_MIN ? out : [];
}

let _bf = null, _bfIdx = null, _bfHv = -1;
export function brandFacts(b) {
  const ix = idx();
  if (_bfIdx !== ix || _bfHv !== hiddenVer()) { _bf = new Map(); _bfIdx = ix; _bfHv = hiddenVer(); }
  if (_bf.has(b)) return _bf.get(b);
  // 25 Nov 2026 (owner): only the finds a visitor can see (not hidden after reports or the photo check, listing not gone),
  // as the app's listing shows them. Brand titles, counts, facts, picks and pages 2+ follow it. It was every row.
  const list = (ix.byBrand.get(b) || []).filter(findShown);
  const tm = new Map();
  for (const p of list) { const t = itemType(p); if (!tm.has(t)) tm.set(t, []); tm.get(t).push(p); }
  const types = [...tm].sort((x, y) => y[1].length - x[1].length || (x[0] < y[0] ? -1 : 1));   // ties by name, so the sentence does not reorder when views change
  const lowMedian = l => { const u = l.filter(p => !isPH(p.cny)).sort((x, y) => x.cny - y.cny); return u.length ? u[Math.floor((u.length - 1) / 2)] : null; };   // at least half the priced finds of l cost this or less
  const priced = list.filter(p => !isPH(p.cny)).sort((x, y) => x.cny - y.cny);
  const plats = new Map(); for (const p of list) plats.set(p.platform, (plats.get(p.platform) || 0) + 1);
  const q1 = list.filter(p => p.qc >= 1).length, q2 = list.filter(p => p.qc >= 2).length;
  const qTop = q2 ? firstMax(list, p => p.qc) : null;
  // A price we do not vouch for: under a third of the half-way price of this brand's finds of the same item type.
  // Such listings are mostly deposits, per-part prices or placeholders (a watch at ¥50 among watches at ¥500), and they
  // attract views, so they turn up among the picks. The card then shows the price in yuan "as listed" and the FAQ
  // answer leaves it out. Placeholder prices proper (isPH) already read "Ask seller".
  const typeMed = new Map();
  for (const [t, l] of types) if (l.filter(p => !isPH(p.cny)).length >= PRICE_TYPE_MIN) typeMed.set(t, lowMedian(l).cny);
  const priceDoubt = p => !isPH(p.cny) && typeMed.has(itemType(p)) && p.cny * 3 < typeMed.get(itemType(p));
  // The "lowest price" pick is the one a wrong price would win, so it is held to more: where the item type has too
  // few priced finds to judge by, the price is compared with the half-way price of the whole brand instead.
  const brandMed = priced.length >= PRICE_TYPE_MIN ? lowMedian(list).cny : 0;
  const lowDoubt = p => priceDoubt(p) || (!typeMed.has(itemType(p)) && p.cny * 3 < brandMed);
  const f = { b, list, n: list.length, types, priced, lo: priced[0] || null, hi: priced[priced.length - 1] || null, med: lowMedian(list), lowMedian,
    plats: [...plats].sort((x, y) => y[1] - x[1]), q1, q2, qTop,
    picks: brandPicks(list, types, priced, priceDoubt, lowDoubt, views),                      // top picks: every pick carries the fact that put it there, and one find can hold several
    solid: brandPicks(list, types, priced, priceDoubt, lowDoubt, NO_STATS).length > 0 };      // true when the block is there even without view stats
  _bf.set(b, f);
  return f;
}
// "Best" goes into a hub's <title>, description, picks heading and FAQ question only for a brand people search with
// "best <brand> reps" (Search Console, 28 Sep - 6 Oct 2026: Ralph Lauren 20 impressions, Golden Goose 16, Essentials 5,
// Stussy 4) and only while the catalogue can back the word: BEST_MIN_COUNTED or more finds with a stored QC photo count,
// and a picks block that is there without any view stats (f.solid). The test uses catalogue data only, so the title
// cannot change from one request to the next. Today: Ralph Lauren 30 counted finds, six QC-count picks without stats
// (yes); Golden Goose 3, Essentials 1, Stussy 1 (no: plain title until their data grows).
// To hold "Best" back everywhere, empty the set.
const BEST_SEARCHED = new Set(["Ralph Lauren", "Golden Goose", "Essentials", "Stussy"]);
const BEST_MIN_COUNTED = 6;
export const bestHub = f => BEST_SEARCHED.has(f.b) && f.q2 >= BEST_MIN_COUNTED && f.solid;

const PLAT = { weidian: "Weidian", taobao: "Taobao", "1688": "1688" };
const AGENT_NAMES = Object.values(AGENTS).map(a => a.name);
const agentList = AGENT_NAMES.length > 6 ? AGENT_NAMES.slice(0, 5).join(", ") + " and " + (AGENT_NAMES.length - 5) + " more agents"
  : AGENT_NAMES.slice(0, -1).join(", ") + " and " + AGENT_NAMES[AGENT_NAMES.length - 1];
// The named item types of a brand: the largest ones with at least two finds; the rest are summed as "others".
function typeSplit(f, max = 6) {
  const named = f.types.filter(([t, l]) => l.length >= 2 && !t.startsWith("other")).slice(0, max);
  return { named, rest: f.n - named.reduce((s, x) => s + x[1].length, 0) };
}
// Two short paragraphs of facts, generated from the rows: how many finds, which item types, listed prices, QC on record
// and marketplaces. (The agents the buy links work with are named once per hub, in the FAQ.)
function brandFactsHtml(f) {
  const b = esc(f.b), plain = f.b.replace(/['’]/g, "");
  const { named, rest } = typeSplit(f);
  let s = `<p>The spreadsheet has ${nf(f.n)} ${b}${plain !== f.b ? ` (also written ${esc(plain)})` : ""} find${f.n === 1 ? "" : "s"}.`;
  if (named.length === 1 && !rest) s += ` All ${nf(f.n)} are ${named[0][0]}.`;
  else if (named.length) {
    const groups = named.map(([t, l]) => `${t} (${nf(l.length)})`).join(", ").replace(/, ([^,]*)$/, " and $1");
    s += rest ? ` Going by the listing titles, the largest group${named.length > 1 ? "s are" : " is"} ${groups}, plus ${nf(rest)} other${rest === 1 ? "" : "s"}.` : ` Going by the listing titles, they are ${groups}.`;
  }
  // The half-way price is taken over the finds that have a real listed price, so the sentence says so when some do not.
  const halfOf = f.priced.length < f.n ? `the ${nf(f.priced.length)} finds with a listed price` : "the finds";
  if (f.lo && f.hi && f.lo.cny !== f.hi.cny) s += ` Listed prices run from ${money(f.lo.cny)} to ${money(f.hi.cny)} before shipping, and half of ${halfOf} are listed at ${money(f.med.cny)} or less.`;
  else if (f.lo) s += ` Every ${f.priced.length < f.n ? "find with a listed price" : "find"} is listed at about ${money(f.lo.cny)} before shipping.`;
  s += "</p><p>";
  if (!f.q1) s += `Our catalogue does not mark any of these listings as having buyer QC photos yet, so the first QC photos you see will be the ones your agent takes of your own order.`;
  else {
    s += `Our catalogue marks ${f.q1 === f.n ? `all ${nf(f.n)}` : `${nf(f.q1)} of the ${nf(f.n)}`} as having buyer QC photos: warehouse photos taken for earlier orders.`;
    if (f.q2 === 1) s += ` For ${f.q1 === 1 ? "that one" : "one of them"} the catalogue also stores how many: ${nf(f.qTop.qc)} photos for the ${esc(f.qTop.title)}.`;
    else if (f.q2 > 1) s += ` For ${nf(f.q2)} of them the catalogue also stores how many, up to ${nf(f.qTop.qc)} photos for a single listing.`;
  }
  const pl = f.plats.map(([k, c]) => [PLAT[k] || k, c]);
  s += pl.length === 1 ? ` ${f.n === 1 ? "It is a" : "All are"} ${esc(pl[0][0])} listing${f.n === 1 ? "" : "s"}.` : ` The listings are on ${pl.map(([k, c]) => `${esc(k)} (${nf(c)})`).join(", ").replace(/, ([^,]*)$/, " and $1")}.`;
  return s + "</p>";
}
// The QC line of a pick card. A count is printed only when one is stored; the flag alone is "marked as having".
const qcLine = p => p.qc >= 2 ? `${nf(p.qc)} buyer QC photos on record` : p.qc === 1 ? "Marked as having buyer QC photos" : "No buyer QC photos on record yet";
const BRAND_CSS = `<style>.pk .c{box-shadow:inset 0 0 0 1px var(--line)}.pkw{display:block;font-size:12.5px;line-height:1.35;color:var(--ink-2)}.pkw b{color:var(--ink);font-weight:600}.pkq{font-size:12.5px;color:var(--muted)}.pkn{color:var(--muted);font-size:14px;max-width:780px;margin:0 0 4px}</style>`;
function pickCard({ p, why, doubt }, eager) {
  const src = imgSrc(p);
  // A price we do not vouch for (priceDoubt in brandFacts) is shown as the seller lists it, in yuan, without our dollar figure.
  const price = doubt ? `Listed at ¥${p.cny} <small>check the listing</small>` : `${money(p.cny)}`;
  return `<a class="c" href="${productUrl(p)}"><span class="ci${cutCls(p)}">${src ? `<img src="${esc(thumbSrc(src))}" data-o="${esc(src)}" alt="${esc(p.title)}" width="300" height="300"${eager ? "" : ' loading="lazy"'} decoding="async" ${IMG_FALLBACK}>` : ""}${colourBadge(p)}</span>` +
    `<span class="cb">${why.map(w => `<span class="pkw"><b>${esc(w.k)}</b> · ${esc(w.d)}</span>`).join("")}<span class="ct">${esc(p.title)}</span>` +
    `<span class="cp">${price}</span><span class="pkq">${qcLine(p)}</span></span></a>`;
}
function brandPicksHtml(f, best) {
  if (!f.picks.length) return "";
  const b = esc(f.b);
  return `<h2>${best ? `Best ${b} reps by the numbers` : `Top ${b} picks by the numbers`}</h2>
<p class="pkn">Picked by numbers only: views and saves counted on Puro Classico, and the QC photo count stored when each listing was added to our catalogue. That count is a number on record; the photos themselves appear on a find's own page when they can be loaded. Prices are the sellers' listed prices, so check the listing before you pay.${f.picks.some(x => x.doubt) ? ` A price shown in yuan "as listed" is less than a third of what this brand's other listings of the same item type usually cost; such a price is often a deposit or a placeholder, so treat it as unconfirmed.` : ""} Nothing here is an opinion or a paid placement.</p>
<div class="g pk">${f.picks.map((x, i) => pickCard(x, i < 4)).join("")}</div>
<h2>All ${nf(f.n)} ${b} finds</h2>`;
}
// What a pick is, in a sentence, for the FAQ answer: the find, its brand-wide labels with their numbers (its per-type
// labels only when it has no other), and its listed price unless we do not vouch for it (or a label already gave it).
const pickSentence = x => { const why = x.why.some(w => w.rank < 7) ? x.why.filter(w => w.rank < 7) : x.why.slice(0, 1);
  return `${x.p.title} (${why.map(w => `${lc1(w.k)}: ${w.d}`).join("; ")}` +
    (x.doubt || isPH(x.p.cny) || why.some(w => w.d.charAt(0) === "$") ? "" : `; listed at ${money(x.p.cny)}`) + ")"; };
function brandFaq(f, best) {
  const b = f.b, range = priceRange(f.list);
  const { named } = typeSplit(f, 3);
  const perType = named.map(([t, l]) => [t, l, l.filter(p => !isPH(p.cny)).length]).filter(([, l, k]) => l.length < f.n && k >= 4)
    .map(([t, l, k]) => `half of the ${nf(k)} ${t}${k < l.length ? " with a listed price" : ""} at ${money(f.lowMedian(l).cny)} or less`);
  const from = f.plats.map(([k]) => PLAT[k] || k).join(", ").replace(/, ([^,]*)$/, " and $1");
  // The agents are named here and nowhere else on the hub, which also answers "<brand> kakobuy" style searches without a page per agent and brand.
  const faq = [[`Where can I buy ${b} reps?`, `Puro Classico lists ${nf(f.n)} ${b} find${f.n === 1 ? "" : "s"} from ${from}. Each find's page has buy links for ${agentList}, so this one ${b} spreadsheet works with each of those agents. The agent buys the item for you and ships it internationally.`]];
  if (range) faq.push([`How much do ${b} reps cost?`, `The finds on this page are listed at ${range} before international shipping, which depends on weight and your country.` +
      (f.med && f.lo.cny !== f.hi.cny ? ` Half of ${f.priced.length < f.n ? `the ${nf(f.priced.length)} with a listed price` : "them"} are listed at ${money(f.med.cny)} or less.` : "") + (perType.length ? ` By item type: ${perType.join(", ")}.` : "") + ` These are the sellers' listed prices and can change.`]);
  if (f.picks.length) {
    const byViews = f.picks.some(x => x.why.some(w => /viewed|saved/i.test(w.k))), byQc = f.picks.some(x => x.why.some(w => /QC/.test(w.k)));
    const list = f.picks.slice(0, 4).map(pickSentence).join("; ");
    const basis = (byViews ? ` Views and saves are counted on this site.` : "") + (byQc ? ` QC photo numbers are the counts stored with each listing when it was added.` : "");
    faq.push(best ? [`What are the best ${b} reps?`, `Going by the numbers we have, these: ${list}.${basis} "Best" here means the most viewed and the most photographed by earlier buyers. We have not handled the items ourselves, so check the QC photos of your own order before it ships.`]
      : [byViews ? `Which ${b} reps are the most viewed?` : `Which ${b} reps have the most QC photos on record?`, `On Puro Classico: ${list}.${basis}`]);
  }
  return faq;
}
// Related hubs: brands with a similar mix of item types (cosine of the type counts) at a similar price level (median
// listed price within a factor of four); two brands that are both on the old-money list get a fixed bonus.
const OLD_MONEY_ALL = new Set(OLD_MONEY.brands.concat(OLD_MONEY.linked));   // on the old-money list, or linked from that page
const RELATED_MIN = 0.2;   // below this the item types hardly overlap, and the brand is not offered as related
let _rel = null, _relIdx = null;
export function relatedBrands(b, k = 10) {
  const ix = idx();
  if (_relIdx !== ix) {
    _relIdx = ix; _rel = new Map();
    const om = OLD_MONEY_ALL, vec = new Map();
    for (const x of ix.brandSlug.keys()) {
      const f = brandFacts(x), v = {};
      for (const [t, l] of f.types) v[t] = l.length;
      vec.set(x, { v, norm: Math.sqrt(Object.values(v).reduce((s, c) => s + c * c, 0)), med: f.med ? f.med.cny : 0, om: om.has(x), n: f.n });
    }
    for (const [x, a] of vec) {
      const sc = [];
      for (const [y, c] of vec) {
        if (y === x) continue;
        let dot = 0; for (const key in a.v) if (c.v[key]) dot += a.v[key] * c.v[key];
        const price = a.med && c.med ? 1 - Math.min(1, Math.abs(Math.log(a.med / c.med)) / Math.log(4)) : 0;
        const cos = dot / (a.norm * c.norm);
        if (cos >= RELATED_MIN) sc.push([y, cos * (0.6 + 0.4 * price) + (a.om && c.om ? 0.25 : 0), c.n]);
      }
      _rel.set(x, sc.sort((p, q) => q[1] - p[1] || q[2] - p[2] || (p[0] < q[0] ? -1 : 1)).map(s => s[0]));
    }
  }
  return (_rel.get(b) || []).slice(0, k);
}

export function renderBrand(s, n) {
  const { slugBrand, brandSlug, byBrand } = idx();
  const b = slugBrand.get(s); if (!b) return null;
  const f = brandFacts(b), list = f.list, N = nf(f.n), range = priceRange(list), rb = range ? ` (${range})` : "";
  const best = bestHub(f);
  const cats = [...new Set(list.map(p => p.cat))].filter(c => CATS[c]);
  const intro = (BRAND_INTRO[b] || "") + brandFactsHtml(f);
  const bm = models().filter(m => modelOnBrand(m, b));
  let related = relatedBrands(b), relTitle = "Related brands", relNote = `<p class="pkn">Brands on the spreadsheet with a similar mix of item types and prices.</p>`;
  if (related.length < 4) {   // nothing really similar (a watch or toy brand, say): the largest hubs, under a heading that does not claim more
    related = [...brandSlug.keys()].filter(x => x !== b).sort((x, y) => byBrand.get(y).length - byBrand.get(x).length).slice(0, 10); relTitle = "Other brands"; relNote = "";
  }
  const extra = `<h3>How to buy ${esc(b)} reps</h3><p>Open a find, tap <strong>Buy via MyCNBox</strong> (or your agent), pick your size and pay for the item plus delivery to the warehouse. Check the QC photos before shipping, see <a href="/guides/how-to-qc">how to read QC photos</a>, then combine your items into one parcel. New to this? <a href="/how-to-order">Watch the how-to-order video</a>.</p>`;
  const relLinks = related.map(x => [`${x} reps`, `/brand/${brandSlug.get(x)}`]).concat(OLD_MONEY_ALL.has(b) ? [["Old money reps", "/old-money"]] : [], [["All brands", "/brands"]]);
  const modelLinks = bm.map(m => [`Best ${MODEL_TERM[m.slug] || m.name} reps`, `/best/${m.slug}`]), catLinks = cats.length > 1 ? cats.map(c => [CATS[c].name, catUrl(c)]) : [];
  const agentLinks = agentBrands().includes(b) ? AGENT_BRAND_AGENTS.map(k => [`${b} on ${AGENTS[k].name}`, `/${k}-spreadsheet/${s}`]) : [];
  // Title and description: catalogue data only (see the rules above), so they are the same whether or not the stats were read.
  const qcBit = f.q1 ? `, ${nf(f.q1)} marked as having QC photos` : "";
  const t0 = f.types[0], share = t0 && !t0[0].startsWith("other") ? t0[1].length / f.n : 0;
  const main = share === 1 ? `, all ${t0[0]}` : share > 0.5 ? `, mostly ${t0[0]}` : "";   // only when one item type is more than half the list
  const desc = n > 1 ? `Page ${n} of the ${N} ${b} rep finds on Puro Classico${range ? `, with prices${rb}` : ""}. Open any listing on MyCNBox, KakoBuy, Oopbuy or your agent.`
    : best ? `Best ${b} reps by the numbers: ${N} finds${rb}, ${nf(f.q2)} with a stored QC photo count. Picks by views and QC photos, with MyCNBox, KakoBuy and Oopbuy links.`
    : `${N} ${b} rep find${f.n === 1 ? "" : "s"}${range ? ` with prices${rb}` : ""}${main}${qcBit}. Open any listing on MyCNBox, KakoBuy, Oopbuy or your agent.`;
  return hub({ path: "/brand/" + s, n, list, title: `${n === 1 && best ? "Best " : ""}${b} Reps Spreadsheet 2026: ${N} Finds · Puro Classico`, desc,
    h1: `${b} reps spreadsheet`, intro, trail: [["Home", "/"], ["Brands", "/brands"], [b, "/brand/" + s]],
    lead: `${N} ${b} finds from Weidian, Taobao and 1688, most viewed first.`, aboutTitle: `About ${b} reps`,
    filters: modelLinks.map(x => [...x, "hot"]).concat(catLinks, relLinks), shop: { links: agentLinks },
    groups: [["Best reps by model", modelLinks], ["Categories", catLinks], [relTitle, relLinks], [`Buy ${b} with your agent`, agentLinks]],
    top: BRAND_CSS + brandPicksHtml(f, best), extra, faq: brandFaq(f, best), ldCount: f.n, idxFirst: true, full: b, key: `${b} Reps` });
}

export function renderCategory(s, n) {
  const c = own(CAT_BY_SLUG, s) ? CAT_BY_SLUG[s] : null; if (!c) return null;
  const { byCat, byBrand, brandSlug } = idx(); const list = (byCat.get(c) || []).filter(findShown);   // visible finds only (26 Nov 2026), like brands
  const topBrands = [...new Set(list.map(p => p.brand))].filter(b => brandSlug.has(b)).slice(0, 24);   // was 18: room for the allow-listed hubs without dropping a brand that was linked before
  const meta = CATS[c], q1 = list.filter(p => p.qc >= 1).length;
  const brandLinks = topBrands.map(b => [b, `/brand/${brandSlug.get(b)}`]);
  const catLinks = Object.values(CATS).filter(x => x.slug !== s && x.slug !== "toys").map(x => [x.name, `/category/${x.slug}`]);
  // Shoes have their own page on each agent (AGENT_STYLES.shoes).
  const agentLinks = c === "Shoes" ? AGENT_BRAND_AGENTS.map(k => [`Shoes on ${AGENTS[k].name}`, `/${k}-spreadsheet/shoes`]) : [];
  return hub({ path: "/category/" + s, n, list, title: `Rep ${meta.name} Spreadsheet 2026: ${list.length.toLocaleString("en-US")} Finds · Puro Classico`,
    desc: n > 1 ? `Page ${n} of the ${list.length.toLocaleString("en-US")} ${meta.name.toLowerCase()} rep finds on Puro Classico${priceRange(list) ? `, with prices (${priceRange(list)})` : ""}. Open any listing on MyCNBox, KakoBuy, Oopbuy or your agent.`
      : `${list.length.toLocaleString("en-US")} ${meta.name.toLowerCase()} rep finds with prices and agent links${q1 ? `, ${q1.toLocaleString("en-US")} marked as having buyer QC photos` : ""}, sorted by most viewed.`,
    h1: meta.h, intro: CAT_INTRO[c] || "", trail: [["Home", "/"], [meta.name, "/category/" + s]], idxFirst: true, full: meta.name, key: `Rep ${meta.name}`,
    lead: `${nf(list.length)} ${meta.name.toLowerCase()} finds from Weidian, Taobao and 1688, most viewed first.`, aboutTitle: `About ${meta.name.toLowerCase()} reps`,
    filters: brandLinks.concat(catLinks), shop: { links: agentLinks },
    groups: [[`Top brands in ${meta.name.toLowerCase()}`, brandLinks], ["Other categories", catLinks], [`${meta.name} on your agent`, agentLinks]] });
}

// ------------------------------------------------------------------ agent spreadsheets (+ brand pages per agent)
// Brand x agent pages (/kakobuy-spreadsheet/ralph-lauren): only for the largest brand hubs and the agents people search
// together with a brand name, so every page has a real list behind it instead of thousands of near-empty variations.
// LoveGoBuy joined on 9 Nov 2026: it was the one agent hub without brand and style pages.
export const AGENT_BRAND_AGENTS = ["mycnbox", "kakobuy", "oopbuy", "lovegobuy", "sugargoo"];
export const AGENT_BRAND_MIN = 40, AGENT_BRAND_MAX = 30;
// Brands outside the 30 largest that visitors look at a lot (23 Oct 2026, data/stats.json: 200+ views in 30 days, 40+
// finds): Arc'teryx 295 views, Acne Studios 273, Rolex 246, Patagonia 215. A fixed list, so a page never comes and goes
// with the view counts. Add a name only with that kind of evidence.
// 24 Nov 2026 (Search Console, 6 months to 22 Nov 2026): agent + brand searches and clicks on brands outside the 30 largest.
// Saint Laurent, Loro Piana and Celine had agent x brand pages until they dropped out of the 30 largest, and those pages had
// Google clicks (/kakobuy-spreadsheet/saint-laurent 95 clicks at 15% CTR, /kakobuy-spreadsheet/loro-piana 48,
// /mycnbox-spreadsheet/celine 14, more on Oopbuy, Sugargoo and LoveGoBuy). UGG ("kakobuy spreadsheet ugg", 203 impressions), Golden
// Goose (KakoBuy 59, Sugargoo 29), Lululemon (KakoBuy 38) and CP Company (KakoBuy 19) are searched with an agent name.
// The agents without such searches or clicks for these brands get canonicals to the brand page (seo_canon.js).
const AGENT_BRAND_PIN = ["Arc'teryx", "Acne Studios", "Rolex", "Patagonia", "Saint Laurent", "Loro Piana", "Celine", "UGG", "Golden Goose", "Lululemon", "CP Company"];
let _agentBrands = null;
export function agentBrands() {
  if (_agentBrands) return _agentBrands;
  const { byBrand, brandSlug } = idx();
  // 15 Nov 2026: counted on every find of the brand (look-alikes hidden by partner swaps too), so a swap refresh can not
  // take an agent + brand page offline (the Arc'teryx ones went 404 that way)
  const allN = new Map(); for (const p of P_ALL) if (p.brand) allN.set(p.brand, (allN.get(p.brand) || 0) + 1);
  const n = b => Math.max(byBrand.get(b).length, allN.get(b) || 0);
  const top = [...brandSlug.keys()].filter(b => n(b) >= AGENT_BRAND_MIN)
    .sort((a, b) => n(b) - n(a)).slice(0, AGENT_BRAND_MAX);
  return (_agentBrands = top.concat(AGENT_BRAND_PIN.filter(b => !top.includes(b) && brandSlug.has(b) && n(b) >= AGENT_BRAND_MIN)));
}
const COUPON_GUIDE = { mycnbox: ["MyCNBox coupon code", "/guides/mycnbox-coupon-code"], kakobuy: ["KakoBuy coupon code", "/guides/kakobuy-coupon-code"] };
function agentHowTo(a) {
  return `<h2>How to order from the ${a.name} spreadsheet</h2>
<ol class="steps ic-steps-list">
<li>${icTile("user-plus")}<strong>Make a free ${a.name} account.</strong> Sign-up bonuses differ per agent; see <a href="${(COUPON_GUIDE[a.key] || ["", "/guides/agent-coupons"])[1]}">${esc((COUPON_GUIDE[a.key] || ["all agent sign-up bonuses"])[0])}</a>.</li>
<li>${icTile("search")}<strong>Find an item here.</strong> Search or filter the spreadsheet by brand, category, colour or price, and open the find you like.</li>
<li>${icTile("cart")}<strong>Tap "Buy via ${a.name}".</strong> The listing opens inside ${a.name}. Pick your size and colour, then pay for the item and the short delivery to the warehouse.</li>
<li>${icTile("camera")}<strong>Check your QC photos.</strong> When the item reaches the warehouse, ${a.name} photographs it. Compare logos, stitching and the size tag; read <a href="/guides/how-to-qc">how to read QC photos</a>.</li>
<li>${icTile("truck")}<strong>Ship your parcel.</strong> Combine your items, pick a shipping line and pay international shipping. <a href="/guides/shipping-lines">Shipping lines explained</a> · <a href="/tools/shipping-calculator">shipping calculator</a>.</li>
</ol>`;
}
export function renderAgent(key, n) {
  const a = AGENTS[key], meta = AGENT_INTRO[key]; if (!a || !meta) return null;
  const { all, brandSlug } = idx(); const path = `/${key}-spreadsheet`; const N = FINDS_PLUS;   // 15 Nov 2026: the visible count, same as the rest of the site
  const faq = [[`What is the ${a.name} spreadsheet?`, `A list of Weidian, Taobao and 1688 finds that open directly in ${a.name}. Puro Classico's spreadsheet has ${N} finds, each with ${a.name} buy links, prices and buyer QC photo counts where we have them.`],
               [`How do I order from the ${a.name} spreadsheet?`, `Open a find, tap Buy via ${a.name}, choose your size and pay for the item plus delivery to the warehouse. After the QC photos arrive, submit your parcel and pay international shipping.`],
               [`Is the ${a.name} spreadsheet free?`, `Yes. Browsing, searching and saving finds on Puro Classico is free. You only pay ${a.name} for the items you order and for shipping. Our links to agents are affiliate links: we may earn a commission if you order, at no extra cost to you.`],
               [`Can I use the spreadsheet with another agent?`, `Yes. The catalogue is the same for every agent: each product page has buy links for MyCNBox, KakoBuy, Oopbuy, LoveGoBuy and Sugargoo, and the link converter turns any Weidian, Taobao or 1688 link into a link for your agent.`],
               [`How often is the ${a.name} spreadsheet updated?`, `New finds are added to the catalogue regularly; the date of the last catalogue update is shown on this page (${BUILT}).`]];
  const brands = AGENT_BRAND_AGENTS.includes(key) ? agentBrands() : [];
  const brandLinks = brands.map(b => [b, `${path}/${brandSlug.get(b)}`]).concat(brands.length ? [["All brands", "/brands"]] : []);
  const otherLinks = Object.keys(AGENT_INTRO).filter(k => k !== key).map(k => [AGENT_INTRO[k].title.replace(/ 2026$/, ""), `/${k}-spreadsheet`]);
  const coupon = COUPON_GUIDE[key];
  return hub({ path, n, list: all, title: `${meta.title}: ${N} Finds · Puro Classico`,
    desc: `The ${a.name} spreadsheet: ${N} rep finds with prices, QC photo counts and direct ${a.name} links. Updated ${BUILT}.`,
    h1: meta.title, intro: `<p class="lead">${esc(meta.lede)}</p>${meta.body}${key === "mycnbox" ? `<p><a class="btn red" href="${MYCNBOX_INVITE}" target="_blank" rel="sponsored noopener">Claim your MyCNBox new-user coupons</a></p>` : ""}`,
    trail: [["Home", "/"], [meta.title, path]], faq, lead: `${N} finds, each with a one-tap ${a.name} buy button.`, aboutTitle: `How the ${a.name} spreadsheet works`,
    filters: brands.slice(0, 12).map(b => [`${b} on ${a.name}`, `${path}/${brandSlug.get(b)}`]), shop: { label: "Other agents", links: otherLinks },
    groups: [[`Popular brands on the ${a.name} spreadsheet`, brandLinks], ["Other agent spreadsheets", otherLinks.concat([["Which agent is best?", "/guides/best-shopping-agent"], [`Browse all ${N} finds`, "/"]])]],
    extra: `${agentHowTo({ ...a, key })}${coupon ? `<p>Before your first order, check the <a href="${coupon[1]}">${esc(coupon[0])}</a> guide for the current sign-up bonus.</p>` : ""}` });
}
export function renderAgentBrand(key, s, n) {
  const a = AGENTS[key], meta = AGENT_INTRO[key]; if (!a || !meta || !AGENT_BRAND_AGENTS.includes(key)) return null;
  const { slugBrand, byBrand, brandSlug } = idx(); const b = slugBrand.get(s);
  if (!b || !agentBrands().includes(b)) return null;
  const list = byBrand.get(b), N = list.length.toLocaleString("en-US"), path = `/${key}-spreadsheet/${s}`, range = priceRange(list);
  const others = AGENT_BRAND_AGENTS.filter(k => k !== key);
  const intro = `<p class="lead">${N} ${esc(b)} finds from Weidian, Taobao and 1688${range ? `, listed at ${esc(range)}` : ""}. Every find has a one-tap <strong>Buy via ${esc(a.name)}</strong> button.</p>
<p>This is the <a href="/brand/${s}">${esc(b)} reps spreadsheet</a> with ${esc(a.name)} as your agent: open a find, tap <strong>Buy via ${esc(a.name)}</strong>, pick your size and check the QC photos before you ship. The full catalogue for this agent is on the <a href="/${key}-spreadsheet">${esc(meta.title.replace(/ 2026$/, ""))}</a>.</p>`;
  const faq = [[`How do I buy ${b} reps on ${a.name}?`, `Open one of the ${N} ${b} finds below, tap Buy via ${a.name}, choose your size and pay for the item plus warehouse delivery. ${a.name} sends QC photos when it arrives; check them, then ship.`],
               [`Are these ${b} finds only for ${a.name}?`, `No. The same finds open on ${andList(others.map(k => AGENTS[k].name))}; each product page has a button for every agent.`]];
  return hub({ path, n, list, title: `${b} ${a.name} Spreadsheet 2026: ${N} Finds · Puro Classico`,
    desc: `${N} ${b} rep finds with one-tap ${a.name} buy links${range ? `, ${range}` : ""}. Prices and QC photo counts on every find.`,
    h1: `${b} on ${a.name}`, intro, trail: [["Home", "/"], [meta.title, `/${key}-spreadsheet`], [b, path]], faq,
    lead: `${N} ${b} finds, each with a one-tap ${a.name} buy button.`, aboutTitle: `How to buy ${b} on ${a.name}`,
    filters: [[`All ${b} reps`, `/brand/${s}`]].concat(agentBrands().filter(x => x !== b).slice(0, 16).map(x => [x, `/${key}-spreadsheet/${brandSlug.get(x)}`])),
    shop: { label: "Other agents", links: others.map(k => [`${b} on ${AGENTS[k].name}`, `/${k}-spreadsheet/${s}`]) },
    groups: [[`${b} on other agents`, others.map(k => [`${b} on ${AGENTS[k].name}`, `/${k}-spreadsheet/${s}`]).concat([[`All ${b} reps`, `/brand/${s}`]])],
             [`More brands on ${a.name}`, agentBrands().filter(x => x !== b).slice(0, 16).map(x => [x, `/${key}-spreadsheet/${brandSlug.get(x)}`])]],
    extra: agentHowTo({ ...a, key }), ldCount: list.length });
}

export function renderOldMoney(n) {
  const { all, brandSlug } = idx(); const set = new Set(OLD_MONEY.brands);
  const list = all.filter(p => set.has(p.brand));
  const brands = OLD_MONEY.brands.concat(OLD_MONEY.linked).filter(b => brandSlug.has(b));   // `linked` brands get a chip; their finds are not part of this page's list
  const brandLinks = brands.map(b => [b, `/brand/${brandSlug.get(b)}`]), agentLinks = AGENT_BRAND_AGENTS.map(k => [`Old money on ${AGENTS[k].name}`, `/${k}-spreadsheet/old-money`]);
  return hub({ path: "/old-money", n, list, title: `Old Money Spreadsheet 2026: ${list.length.toLocaleString("en-US")} Quiet Luxury Rep Finds | Puro Classico`,
    desc: `${list.length.toLocaleString("en-US")} old money and quiet luxury rep finds from Ralph Lauren, Loro Piana, Lacoste, Moncler, Golden Goose and more, each with MyCNBox, KakoBuy and Oopbuy links.`,
    h1: "Old money & quiet luxury reps", key: "Old Money Reps", intro: OLD_MONEY.intro, trail: [["Home", "/"], ["Old money", "/old-money"]],
    lead: "Cashmere knits, polos, loafers and clean sneakers from the quiet luxury brands, most viewed first.", aboutTitle: "About old money reps",
    filters: [["Stockholm style spreadsheet", "/stockholm-spreadsheet"], ["Grisch spreadsheet", "/grisch-spreadsheet"]].concat(brandLinks),
    shop: { links: agentLinks },
    groups: [["Old money brands", brandLinks], ["Old money styles", [["Stockholm style spreadsheet", "/stockholm-spreadsheet"], ["Grisch spreadsheet", "/grisch-spreadsheet"]]], ["Old money on your agent", agentLinks]],
    faq: [["What are old money reps?", "Replica finds in the understated 'old money' or quiet-luxury style: knitwear, polos, loafers and clean sneakers from brands like Ralph Lauren, Loro Piana and Brunello Cucinelli, without big logos."],
          ["What should I check in QC for old money pieces?", "Knit texture and ribbing, the density of small chest-logo embroidery, collar shape on polos, and leather grain and stitching on shoes and belts."]] });
}

// /new (12 Nov 2026, SEO check): the newest finds, newest first, paged like the other hubs and in the sitemap. The last
// NEW_MAX rows of the catalogue (rows are appended, so that is the order they were added); older finds are on their brand
// and category hubs. The order does not depend on the view stats, so the page is the same on every server instance.
export const NEW_MAX = 600;
export function renderNew(n) {
  const list = newest(NEW_MAX), { brandSlug } = idx();
  const bc = new Map(); for (const p of list) if (brandSlug.has(p.brand)) bc.set(p.brand, (bc.get(p.brand) || 0) + 1);
  const brandLinks = [...bc].sort((x, y) => y[1] - x[1]).slice(0, 16).map(([b]) => [b, `/brand/${brandSlug.get(b)}`]);
  const catLinks = Object.values(CATS).filter(x => x.slug !== "toys").map(x => [x.name, `/category/${x.slug}`]);
  const days = list.map(p => (rowDays(p) || {}).added).filter(Boolean).sort();
  const intro = `<p>Finds join the catalogue as we and the community find them, and new ones are added at the end of the list. This page shows the newest ${nf(list.length)} in that order, newest first${days.length ? `; the newest of them were added on ${dayOf(days[days.length - 1])}` : ""}. Older finds stay on their <a href="/brands">brand pages</a> and category pages.</p>` +
    `<p>New finds often have no buyer QC photos yet. Check the seller's photos and measurements, and the QC photos your agent takes at its warehouse before you ship: see <a href="/guides/how-to-qc">how to read QC photos</a>.</p>`;
  return hub({ path: "/new", n, list, title: `New Rep Finds 2026: The Latest ${nf(list.length)} Added | Puro Classico`,
    desc: `The ${nf(list.length)} newest finds on the Puro Classico rep spreadsheet, newest first, with prices and one-tap links for ${AGENT_N} agents.`,
    h1: "New finds", key: "New Rep Finds", lead: "The latest finds added to the spreadsheet, newest first.", intro, aboutTitle: "About new finds",
    trail: [["Home", "/"], ["New finds", "/new"]], filters: brandLinks.concat(catLinks),
    groups: [["Brands with new finds", brandLinks], ["Categories", catLinks]], facts: ["Newest first"], ldCount: list.length });
}

export function renderBrands() {
  const { byBrand, brandSlug } = idx();
  const hubs = [...brandSlug.keys()].sort((a, b) => a.localeCompare(b));
  const groups = {};
  for (const b of hubs) { const L = /[a-z]/i.test(b[0]) ? b[0].toUpperCase() : "#"; (groups[L] = groups[L] || []).push(b); }
  const bc = crumbs([["Home", "/"], ["Brands", "/brands"]]);
  const body = `${bc.html}<h1>Rep brands A to Z</h1><p class="lead">The ${hubs.length} brands with their own page on Puro Classico, with the number of finds for each.</p>
${Object.keys(groups).sort().map(L => `<h2 class="az-h">${L}</h2><div class="chips">${groups[L].map(b => `<a href="/brand/${brandSlug.get(b)}">${esc(b)} <span style="color:var(--muted)">${brandFacts(b).n}</span></a>`).join("")}</div>`).join("")}`;
  return page({ title: "Rep Brands A to Z: Every Brand on the Spreadsheet · Puro Classico", desc: `Browse ${hubs.length} brands on the Puro Classico rep spreadsheet, from Corteiz and Nike to Ralph Lauren and Moncler.`,
    path: "/brands", body, jsonld: [bc.data] });
}

// ------------------------------------------------------------------ model pages ("best X rep")
export function renderModels() {
  const bc = crumbs([["Home", "/"], ["Best reps", "/best"]]);
  const ms = models().slice().sort((a, b) => modelList(b).length - modelList(a).length);
  const body = `${bc.html}<h1>Best reps by model</h1><p class="lead">Every listing of the most popular models side by side, ranked by what buyers actually view. Compare batches, prices and QC before you order.</p>
<div class="g">${ms.map(m => { const l = modelList(m), p = l[0]; const src = imgSrc(p); return `<a class="c" href="/best/${m.slug}"><span class="ci${cutCls(p)}">${src ? `<img src="${esc(thumbSrc(src))}" data-o="${esc(src)}" alt="${esc(m.name)}" width="300" height="300" loading="lazy" decoding="async" ${IMG_FALLBACK}>` : ""}</span><span class="cb"><span class="ct">${esc(m.name)}</span><span class="cbr">${l.length} listings</span></span></a>`; }).join("")}</div>`;
  return page({ title: "Best Reps by Model (2026): Compare Batches & QC · Puro Classico", desc: "Compare every listing of the most popular rep models: Air Jordan 1, Samba, Golden Goose, Moncler, Nuptse and more, ranked by views.", path: "/best", body, jsonld: [bc.data] });
}
// The icon for one "What to check in QC" line (first match wins).
const QC_ITEM_IC = [[/toe|shape|silhouette|sole/i, "shoe"], [/logo|print|swoosh|embroider|font|tag text/i, "type"], [/stitch|seam|thread/i, "scissors"],
  [/size|label|tag/i, "ruler"], [/colou?r/i, "palette"], [/zip|hardware|buckle|metal/i, "watch"], [/leather|material|knit|fabric|texture/i, "layers"]];
export function renderModel(s, n) {
  const m = models().find(x => x.slug === s); if (!m) return null;
  const list = modelList(m);
  const pr = priceRange(list);
  // The model's short intro is the lead under the h1; the rest of the copy and the QC checklist are in the About section
  // under the grid (v10). "Ranked by views" joins the facts line next to the count and the price range.
  const intro = `<p>Below are all ${list.length} ${esc(m.name)} listings on Puro Classico, ranked by how often buyers view them. Listed prices: ${pr} before shipping.</p>` +
    `${hIc("h3", "camera", "What to check in QC")}<ul class="ic-list">${m.qc.map(q => `<li>${ic(firstIcon(QC_ITEM_IC, q, "check-circle"), "sm")}<span>${esc(q)}</span></li>`).join("")}</ul>`;
  const others = relatedModels(m, 14);
  const t = MODEL_TERM[s] || m.name;
  // Link up to the hub of each brand these listings belong to (a brand needs 3 of them, or all of them; at most 6 brands).
  const { byBrand, brandSlug } = idx();
  const bn = new Map(); for (const p of list) if (brandSlug.has(p.brand)) bn.set(p.brand, (bn.get(p.brand) || 0) + 1);
  const hubs = [...bn].filter(([, c]) => c >= Math.min(3, list.length)).sort((x, y) => y[1] - x[1]).slice(0, 6).map(x => x[0]);
  const hubLinks = hubs.map(x => [`All ${brandFacts(x).n.toLocaleString("en-US")} ${x} reps`, `/brand/${brandSlug.get(x)}`]);
  const modelLinks = others.map(x => [x.name, `/best/${x.slug}`]).concat([["All models", "/best"]]);
  const faq = [[`Where can I buy ${t} reps?`, `Puro Classico lists ${list.length} ${m.name} listings from Weidian, Taobao and 1688. Each opens directly in MyCNBox, KakoBuy, Oopbuy or another shopping agent.`],
               [`Which ${m.name} listing is best?`, `Start with the most-viewed listings at the top and compare their buyer QC photos. Check ${m.qc.join(", ")}.`]];
  return hub({ path: "/best/" + s, n, list, title: `Best ${t} Reps 2026: ${list.length} Listings${fromPrice(list)} · Puro Classico`,   // 24 Nov 2026: a starting price in the title (Search Console: 3.7 to 5% clicks on these pages)
    desc: [`${list.length} ${m.name} rep listings ranked by views${typicalPrices(list)}. Check in QC: ${m.qc[0]}, then ${m.qc[1]}.`,
      `${list.length} ${m.name} rep listings ranked by views${typicalPrices(list)}. Check in QC: ${m.qc[0]}.`,
      `${list.length} ${m.name} rep listings ranked by views${typicalPrices(list)}, with what to check in QC.`].find(x => x.length <= 160) || `${list.length} ${m.name} rep listings ranked by views${typicalPrices(list)}.`,
    h1: `Best ${t} reps`, key: `Best ${t} Reps`, intro, facts: ["Ranked by views"], trail: [["Home", "/"], ["Best reps", "/best"], [m.name, "/best/" + s]], faq,
    lead: m.intro, aboutTitle: `About ${m.name} reps`, filters: hubLinks.concat(modelLinks),
    groups: [[hubs.length === 1 ? `More ${hubs[0]}` : "Brands on this page", hubLinks], ["More models", modelLinks]] });
}

// ------------------------------------------------------------------ tools
// v9 tools kit (TOOLS_SPEC.md): QC Checker and Link Converter render here through site.js toolShell(), the other three
// in tools9.js. Styles: the "v9 tools kit" block in ds.css. Client helpers: site.js TK_JS (window.TK).
const TOOL_CSS = "";   // kept for toolPage9(s, baseCss); ds.css styles every tool
const EXTRACT = `function pcExtract(u){u=(u||"").trim();if(!u)return{};for(var k=0;k<3;k++){var d;try{d=decodeURIComponent(u);}catch(e){break;}if(d===u)break;u=d;}var pl=null,v,m,i;var st=u.match(/[?&#](?:shop_type|platform|source|channel|mall_?type)=([a-z0-9_]+)/i);if(st){v=st[1].toLowerCase();if(/^(?:wd|weidian)/.test(v))pl="weidian";else if(/^(?:1688|ali)/.test(v))pl="1688";else if(/^(?:tb|tao|tmall)/.test(v))pl="taobao";}if(!pl){m=u.match(/\\/product\\/(weidian|taobao|tmall|1688)\\//i);if(m){v=m[1].toLowerCase();pl=v==="tmall"?"taobao":v;}}if(!pl){var H=[["weidian",/(?:^|[\\/.@])(?:weidian\\.com|youshop10\\.com)/i],["taobao",/(?:^|[\\/.@])(?:taobao\\.com|tmall\\.com|tmall\\.hk|tb\\.cn)/i],["1688",/(?:^|[\\/.@])(?:1688\\.com|alibaba\\.com)/i]],b=-1;for(i=0;i<H.length;i++){m=H[i][1].exec(u);if(m&&(b<0||m.index<b)){b=m.index;pl=H[i][0];}}}if(!pl){if(/weidian/i.test(u))pl="weidian";else if(/taobao|tmall/i.test(u))pl="taobao";else if(/alibaba/i.test(u))pl="1688";}var id=null,ps=[/(?:^|[?&#\\/])item_?id=(\\d{6,})/i,/(?:^|[?&#])offer_?id=(\\d{6,})/i,/[?&#]id=(\\d{6,})/i,/\\/offer\\/(\\d{6,})/i,/\\/i(\\d{6,})\\.htm/i,/\\/product\\/(?:weidian|taobao|tmall|1688)\\/(\\d{6,})/i,/\\/item\\/(\\d{6,})/i,/\\/(\\d{9,})\\.html?\\b/i];for(i=0;i<ps.length;i++){m=u.match(ps[i]);if(m){id=m[1];break;}}if(!id&&/^\\d{6,}$/.test(u))id=u;var sh=!id&&/(?:^|[\\/.])(?:m\\.tb\\.cn|e\\.tb\\.cn|youshop10\\.com|qr\\.1688\\.com)/i.test(u);if(!id&&!sh){m=u.replace(/(?:spm|memberId|referId|affcode|invite_?code|scm|pvid|ut_sk|sku_?id)=[^&#]*/gi,"").match(/(\\d{9,})/);if(m)id=m[1];}return{platform:pl,id:id,short:sh};}` +
// r6 GROUP C (item 22): pcDetect(input, look) -> {id, platform, source: "url"|"agent"|"catalogue"|"guess", guess?, pid?, pending?}.
// Marketplace hosts, then agent parameters / path forms, then our own /product/<id> links and bare IDs through the
// catalogue (look(id) -> {p, i, pid} | null | undefined while the index loads), else a guess from the ID length.
// index.html (#lc-in / #qc-in) carries the same function (V/r6/tools/detect_test.js checks both copies are identical).
  String.raw`function pcDetect(input,look){var s=String(input==null?"":input).trim();if(!s)return{id:null,platform:null,source:null};
function gs(id){var n=String(id).length;return{id:id,platform:n>=13?"1688":n>=11?"taobao":"weidian",source:"guess",guess:true};}
function cat(id){var c=look?look(id):null;if(c===undefined)return{id:id,platform:null,source:"catalogue",pending:true};if(c)return{id:c.i||id,platform:c.p,source:"catalogue",pid:c.pid||id};return gs(id);}
var own=s.match(/^(?:https?:\/\/)?(?:[a-z0-9-]+\.)*(?:puroclassico\.com|pages\.dev)(?::\d+)?\/product\/([^\/?#\s]+)/i)||s.match(/^\/product\/([^\/?#\s]+)/);
if(own){var oid=own[1];try{oid=decodeURIComponent(oid);}catch(e){}return cat(oid);}
if(/^\d{6,}$/.test(s))return cat(s);
var r=pcExtract(s),pl=r.platform||null,id=r.id||null,m=s.match(/\/(?:agent|product|item|goods)\/(weidian|taobao|tmall|1688)\/(\d{6,})/i);
if(m){pl=m[1].toLowerCase();if(pl==="tmall")pl="taobao";if(!id)id=m[2];}
if(!pl){m=s.match(/cssbuy\.com\/item-(?:(micro)-|(1688)-)?(\d{6,})/i);if(m){pl=m[1]?"weidian":m[2]?"1688":"taobao";if(!id)id=m[3];}}
if(!pl){m=s.match(/[?&#](?:type|malltype|mall_type|shop_type|platform|source|channel)=([a-z0-9_]+)/i);if(m){var v=m[1].toLowerCase();pl=/^(?:weidian|wd|weidian_item)$/.test(v)?"weidian":/^(?:taobao|tb|tmall)$/.test(v)?"taobao":/^(?:1688|ali|al|alibaba|ali_1688)$/.test(v)?"1688":null;}}
var host=((s.match(/^(?:[a-z][a-z0-9+.-]*:\/\/)?([^\/?#\s]+)/i)||[])[1]||"").toLowerCase().replace(/^.*@/,"").replace(/:\d+$/,"");
if(/(?:^|\.)(?:koudai\.com|vdian\.com)$/.test(host))pl="weidian";
var mk=/(?:^|\.)(?:weidian\.com|koudai\.com|vdian\.com|youshop10\.com|taobao\.com|tmall\.com|tmall\.hk|tb\.cn|1688\.com|alibaba\.com)$/.test(host);
if(!id)return{id:null,platform:pl,source:pl?(mk?"url":"agent"):null,short:!!r.short};
if(pl)return{id:id,platform:pl,source:mk?"url":"agent"};
return cat(id);}` +
// PCCAT: the catalogue lookup behind pcDetect, read from /search-index.json (the header search index, item 10) on the
// first product link or bare ID; nothing is requested on page load. look(): undefined until loaded, null when unknown.
  String.raw`var PCCAT=(function(){var map=null,st=0,q=[],J=null,R=null;function flush(){var a=q;q=[];a.forEach(function(f){try{f();}catch(e){}});}
function fail(){if(map)return;st=2;flush();}
function load(cb){if(cb)q.push(cb);if(map||st===2){flush();return;}if(st)return;st=1;var to=setTimeout(fail,6000);
try{fetch("/search-index.json?v=${BUILT}").then(function(r){if(!r.ok)throw 0;return r.json();}).then(function(j){clearTimeout(to);var m={},pl=j.plat||[];(j.rows||[]).forEach(function(r){var id=String(r[0]),it=r[11]?String(r[11]):id,o={p:pl[r[4]]||"weidian",i:it,pid:id};m[id]=o;if(it!==id&&!m[it])m[it]=o;});J=j;map=m;st=3;flush();},fail);}catch(e){fail();}}
function rows(){if(R||!J)return R;var pl=J.plat||[],br=J.brands||[],pre=J.pre||[];R=(J.rows||[]).map(function(r){var id=String(r[0]),b=r[2]>=0&&br[r[2]]?String(br[r[2]][0]):"",t=String(r[1]||"");
return{pid:id,i:r[11]?String(r[11]):id,p:pl[r[4]]||"weidian",t:t,b:b,qc:+r[7]||0,u:r[9]!=null?(pre[r[8]]||"")+r[9]:"",usd:+r[6]||0,pop:+r[10]||0,s:pcNorm(b+" "+t)};});return R;}
return{look:function(id){return map?(map[id]||null):st===2?null:undefined;},load:load,failed:function(){return st===2;},rows:rows};})();
function pcNorm(v){return String(v||"").toLowerCase().replace(/['’]/g,"").replace(/[^a-z0-9]+/g," ").trim();}`;
// Agent link builders: the same formats and referral codes as before (and as site.js AGENTS / AGENT_SWAP_JS).
// A[i] = [id, name, build], in AGENT_ORDER (site.js). ag(p, id) puts the visitor's agent from the app (manifest.state.agent) first,
// then MyCNBox, then the rest in this order.
const AGENT_JS = `var R={mycnbox:"LHYDVW",kakobuy:"w5war",lovegobuy:"9WJ54Y",oopbuy:"LHQC0OS8O",sugargoo:"3751749728009774836",litbuy:"N3GYNRNL7",usfans:"VKZFJG",joyagoo:"301083138",superbuy:"Expx5X",cssbuy:"R0dfOUY5QkM1RkU=",hipobuy:"6DJ8GVKLE",boonbuy:"NA6R4R4EC",fishgoo:"3920775520241738078",hubbuy:"082A1BdE",itaobuy:"6SMA234Z",gtbuy:"KI06I91RM",bbdbuy:"uDi7jz"};
function N(p){return p==="taobao"?1:p==="1688"?0:2;}
function orig(p,id){return p==="taobao"?"https://item.taobao.com/item.htm?id="+id:p==="1688"?"https://detail.1688.com/offer/"+id+".html":"https://weidian.com/item.html?itemID="+id;}
var A=[["mycnbox","MyCNBox",function(p,id){return "https://mycnbox.com/goodsDetail?mallType="+p+"&itemId="+id+"&referId="+R.mycnbox}],["kakobuy","KakoBuy",function(p,id){return "https://www.kakobuy.com/item/details?url="+encodeURIComponent(orig(p,id))+"&affcode="+R.kakobuy}],["oopbuy","Oopbuy",function(p,id){return "https://oopbuy.com/product/"+p+"/"+id+"?inviteCode="+R.oopbuy}],["litbuy","Litbuy",function(p,id){return "https://www.litbuy.com/product/"+p+"/"+id+"?inviteCode="+R.litbuy}],["joyagoo","Joyagoo",function(p,id){return "https://joyagoo.com/product?id="+id+"&platform="+({taobao:"TAOBAO","1688":"ALI_1688"}[p]||"WEIDIAN")+"&ref="+R.joyagoo}],["sugargoo","Sugargoo",function(p,id){return "https://www.sugargoo.com/#/home/productDetail?productLink="+encodeURIComponent(orig(p,id))+"&memberId="+R.sugargoo}],["hipobuy","Hipobuy",function(p,id){return "https://hipobuy.com/product/"+p+"/"+id+"?inviteCode="+R.hipobuy}],["boonbuy","Boonbuy",function(p,id){return "https://boonbuy.com/product/"+p+"/"+id+"?inviteCode="+R.boonbuy}],["usfans","USFans",function(p,id){return "https://www.usfans.com/product/"+({taobao:2,"1688":1}[p]||3)+"/"+id+"?ref="+R.usfans}],["gtbuy","GTBuy",function(p,id){return "https://www.gtbuy.com/product/"+N(p)+"/"+id+"?inviteCode="+R.gtbuy}],["lovegobuy","LoveGoBuy",function(p,id){return "https://www.lovegobuy.com/product?platform="+p+"&id="+id+"&invite_code="+R.lovegobuy}],["superbuy","Superbuy",function(p,id){return "https://www.superbuy.com/en/page/buy?from=search-input&url="+encodeURIComponent(orig(p,id))+"&partnercode="+R.superbuy}],["itaobuy","iTaoBuy",function(p,id){return "https://www.itaobuy.com/product-detail?url="+encodeURIComponent(orig(p,id))+"&inviteCode="+R.itaobuy}],["cssbuy","CSSBuy",function(){return "https://www.cssbuy.com/register?invite="+R.cssbuy}],["fishgoo","Fishgoo",function(p,id){return "https://www.fishgoo.com/#/product?productLink="+encodeURIComponent(orig(p,id))+"&memberId="+R.fishgoo}],["hubbuy","Hubbuy",function(p,id){return "https://www.hubbuy.com/product/"+N(p)+"/"+id+"?inviteCode="+R.hubbuy}],["bbdbuy","BBDBuy",function(p,id){return "https://www.bbdbuyeu.com/goods/"+({taobao:"TAOBAO","1688":"1688"}[p]||"WEIDIAN")+"/"+id+"?inviteCode="+R.bbdbuy}]];
function myAgent(){try{return String((JSON.parse(localStorage.getItem("manifest.state")||"{}")||{}).agent||"").replace(/[^a-z0-9]/g,"");}catch(e){return "";}}
function ag(p,id){var me=myAgent(),L=A.map(function(a){return{id:a[0],name:a[1],url:a[2](p,id),mine:a[0]===me};});L.sort(function(x,y){return (y.mine-x.mine)||0;});return L;}
var PL={weidian:"Weidian",taobao:"Taobao","1688":"1688"};
function onCat(id){var k="pc.pid."+id,c=TK.sess.get(k,null);function f(ok){var b=document.getElementById("opc");if(b&&ok)b.hidden=false;}if(c!=null){f(c);return;}try{fetch("/product/"+encodeURIComponent(id),{method:"HEAD",redirect:"manual"}).then(function(r){var ok=r.status===200;TK.sess.set(k,ok);f(ok);},function(){});}catch(e){}}
function opcCheck(id,pid){var b=document.getElementById("opc");function sh(x){if(b){b.href="/product/"+encodeURIComponent(x);b.hidden=false;}}if(pid){sh(pid);return;}var c=PCCAT.look(id);if(c)sh(c.pid);else if(c===undefined||PCCAT.failed())onCat(id);}`;
// Round 10 tools pass: share links, shop links and the matching find, for both paste tools (client side of
// functions/api/link.js). shortOf(v): the share link (m.tb.cn, youshop10.com, qr.1688.com...) in a pasted text, else "".
// isShop(v): a seller's shop page rather than one item. resolveShort(u, cb): the item behind a share link, via /api/link.
// findCheck(p, id, pid): fills <div id="fnd" data-k> with our find for that listing (falls back to opcCheck offline).
const LINK_JS = String.raw`var SHORT_H=/(?:^|\.)(?:tb\.cn|youshop10\.com|koudai\.com|vdian\.com)$|^qr\.1688\.com$/;
function firstUrl(v){var m=String(v||"").match(/https?:\/\/[^\s<>"'，。、「」【】（）()]+/i);return m?m[0]:"";}
function shortOf(v){var u=firstUrl(v),h=((u.match(/^https?:\/\/([^\/?#:]+)/i)||[])[1]||"").toLowerCase();return h&&SHORT_H.test(h)&&!/[?&#](?:item_?id|id)=\d{6,}/i.test(u)?u:"";}
function isShop(v){v=String(v||"");try{v=decodeURIComponent(v);}catch(e){}if(/item_?id=|[?&#](?:id|offer_?id)=\d|\/offer\/\d|\/item\/\d|\/i\d{6,}\.htm|\/product\/|^\d+$/i.test(v))return false;
return /[?&#]user_?id=\d|^(?:https?:\/\/)?shop\d*\.(?:v\.)?weidian\.com|^(?:https?:\/\/)?(?:www\.|m\.)?weidian\.com\/?(?:[?#]|$)|^(?:https?:\/\/)?shop\d+\.(?:m\.)?(?:taobao|tmall)\.com|^(?:https?:\/\/)?[a-z0-9-]+\.(?:taobao|tmall)\.com\/?(?:[?#]|$)|\.(?:taobao|tmall)\.com\/(?:shop|search|category)|winport|shop\.1688\.com|\.1688\.com\/(?:page|shop)\//i.test(v);}
var RES={};function resolveShort(u,cb){if(Object.prototype.hasOwnProperty.call(RES,u)){cb(RES[u]);return;}var c=TK.sess.get("pc.res."+u,null);if(c&&c.id){cb(c);return;}
var done=false,to=setTimeout(function(){fin(null);},9000);function fin(d){if(done)return;done=true;clearTimeout(to);d=d&&d.id&&d.url?{platform:d.platform,id:String(d.id),url:String(d.url)}:null;if(d)TK.sess.set("pc.res."+u,d);RES[u]=d;cb(d);}
try{fetch("/api/link?u="+encodeURIComponent(u)).then(function(r){return r.ok?r.json():null;}).then(fin,function(){fin(null);});}catch(e){fin(null);}}
function findCard(f){return'<a class="tk-find" href="'+esc(f.url)+'"><img src="'+esc(f.img)+'" alt="" loading="lazy" decoding="async" onerror="this.style.visibility=\'hidden\'"><span><span class="tk-find-k">Our find</span><span class="t">'+esc(f.title)+'</span><span class="s">'+esc(f.price+(f.qc?" · "+f.qc+" QC photo"+(f.qc===1?"":"s"):"")+(f.sold?" · Sold out":""))+"</span></span></a>";}
function findCheck(p,id,pid){var k="pc.find."+p+"."+id;function slot(){var s=document.getElementById("fnd");return s&&s.getAttribute("data-k")===k?s:null;}
function put(f){var s=slot();if(!s||!f||!f.url)return;s.innerHTML=findCard(f);s.hidden=false;var b=document.getElementById("opc");if(b){b.href=f.url;b.hidden=false;}}
var c=TK.sess.get(k,null);if(c!==null){if(c)put(c);return;}
try{fetch("/api/link?p="+encodeURIComponent(p)+"&id="+encodeURIComponent(id)).then(function(r){if(!r.ok)throw 0;return r.json();}).then(function(d){var f=d&&d.find&&d.find.url?d.find:false;TK.sess.set(k,f);put(f);},function(){if(slot())opcCheck(id,pid);});}catch(e){opcCheck(id,pid);}}`;
const sameItem = "function(a,b){return a.p===b.p&&a.id===b.id;}";

// Example chips: real catalogue finds that have QC photos (most viewed first), picked at render time.
let EXAMPLES = null;
function toolExamples() {
  if (EXAMPLES) return EXAMPLES;
  const ok = P.filter(p => p.qc >= 1 && !p.itemId && /^\d{6,}$/.test(p.id)).sort((a, b) => (b.views || 0) - (a.views || 0));
  const w = ok.find(p => p.platform === "weidian"), t = ok.find(p => p.platform === "taobao");
  const id = ok.find(p => p !== w && p.platform === "weidian" && p.id.length === 10) || ok.find(p => p !== w && p !== t);
  const ag = ok.find(p => p !== t && p.platform === "taobao") || t;
  const bq = new Map(); for (const p of P) if (p.qc >= 1 && p.brand) bq.set(p.brand, (bq.get(p.brand) || 0) + 1);
  const brand = [...bq].sort((a, b) => b[1] - a[1]).map(x => x[0])[0] || "";
  EXAMPLES = { w: w && origUrl(w), t: t && origUrl(t), id: id && id.id, agent: ag && `https://oopbuy.com/product/${ag.platform}/${ag.id}`, brand };
  return EXAMPLES;
}
const chip = (label, v) => v ? `<button type="button" class="tk-chip" data-ex="${esc(v)}">${esc(label)}</button>` : "";
const pasteField = (id, label, ph, hint) => `<div class="tk-field"><label class="tk-label" for="${id}">${esc(label)}${hint}</label>` +
  `<div class="tk-inwrap"><span class="tk-in-ic">${TK_I.link}</span><input id="${id}" name="u" class="tk-in tk-in-lg" type="text" inputmode="url" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="go" maxlength="2000" placeholder="${esc(ph)}">` +
  `<span class="tk-in-act"><button type="button" class="btn sm secondary" id="${id}-paste" hidden>Paste</button><button type="button" class="tk-x" id="${id}-clr" aria-label="Clear the link" hidden>${TK_I.x}</button></span></div></div>`;
const platSeg = (id, auto) => `<div class="tk-det" id="${id}d" hidden><span class="tk-det-c">${TK_I.check}<span id="${id}dt">Detected</span></span><button type="button" class="tk-det-x" id="${id}dc" aria-controls="${id}w">Change</button></div>` +
  `<div class="tk-field" id="${id}w" hidden><span class="tk-label" id="${id}l">Marketplace</span><div class="tk-seg" role="radiogroup" aria-labelledby="${id}l" id="${id}">` +
  (auto ? `<button type="button" role="radio" aria-checked="true" data-v="">Auto</button>` : "") +
  `<button type="button" role="radio" aria-checked="${auto ? "false" : "true"}" data-v="weidian">Weidian</button><button type="button" role="radio" aria-checked="false" data-v="taobao">Taobao</button><button type="button" role="radio" aria-checked="false" data-v="1688">1688</button></div><p class="tk-det-h" id="${id}h" hidden></p></div>`;
const recentBox = title => `<section class="tk-recent" id="rc" aria-labelledby="rch" hidden><div class="tk-recent-h"><h2 id="rch">${esc(title)}</h2><button type="button" class="btn ghost sm" id="rcx">Clear</button></div><ul id="rl"></ul></section>`;
// Shared client bits for both paste tools: output states, recent list rendering.
const PASTE_JS = `var $=function(i){return document.getElementById(i);},esc=TK.esc,I=${JSON.stringify({ alert: TK_I.alert, x: TK_I.x, link: TK_I.link, image: TK_I.image })},CP=${JSON.stringify(tkCopyBtn("Copy"))};
function cpBtn(l,a){return CP.replace('<span class="l">Copy</span>','<span class="l">'+esc(l)+'</span>').replace('class="btn sm tk-copy"','class="btn sm tk-copy" '+a);}
function alertH(t,b,act,role){return '<div class="tk-alert"'+(role?' role="alert"':'')+'>'+I.alert+'<div><b>'+esc(t)+'</b><p>'+b+'</p>'+(act?'<div class="tk-actions">'+act+'</div>':'')+'</div></div>';}
function pbSync(id,v){var b=$(id);if(!b)return;var ok=false;try{ok=!!(navigator.clipboard&&navigator.clipboard.readText);}catch(e){}b.hidden=!!v||!ok;}
var said="";function sayOnce(m){if(m&&m!==said){said=m;TK.say(m);}}
function setOut(st,h){var o=$("out");o.setAttribute("data-state",st);o.innerHTML=h;}
function drawRecent(q,cur,row){var a=q.list(),rl=$("rl"),idx=[];a.forEach(function(x,i){if(!(cur&&x.p===cur.p&&x.id===cur.id))idx.push(i);});$("rc").hidden=!idx.length;rl.innerHTML=idx.map(function(i){var x=a[i];return '<li><button type="button" data-r="'+i+'">'+row(x)+'<span style="min-width:0"><span class="t">'+esc((PL[x.p]||x.p)+" · "+x.id)+'</span><span class="s">'+esc(TK.ago(x.t))+'</span></span></button><button type="button" class="tk-x" data-x="'+i+'" aria-label="Remove '+esc((PL[x.p]||x.p)+" "+x.id)+'">'+I.x+'</button></li>';}).join("");}`;

const TOOL_UI = {
  "link-converter": () => { const ex = toolExamples();
    const empty = `<div class="tk-empty">${TK_I.link}<p>Paste a link to get a buy link for every agent.</p><div class="tk-chips"><span>Try:</span>${chip("Weidian link", ex.w)}${chip("Taobao link", ex.t)}${chip("Agent link", ex.agent)}</div></div>`;
    return `<section class="tk-card" aria-label="Link Converter">${pasteField("lc", "Weidian, Taobao, 1688 or agent link", "Paste a Weidian, Taobao, 1688 or agent link", `<span class="tk-kbd" aria-hidden="true"><kbd>Enter</kbd> to convert</span>`)}${platSeg("lp", false)}
<div class="tk-out" id="out" data-state="empty">${empty}</div></section>${recentBox("Recent")}
<script>(function(){${EXTRACT}${TK_JS}${AGENT_JS}${LINK_JS}${PASTE_JS}
var EMPTY=${JSON.stringify(empty)},inp=$("lc"),clr=$("lc-clr"),pw=$("lpw"),pick=null,chg=null,cur=null,L=[],rq=TK.recent("pc.link.recent",6),same=${sameItem};
function nodet(){pw.hidden=true;$("lpd").hidden=true;$("lph").hidden=true;}
function det(r,p,ov,v){var known=!!r.platform&&r.source!=="guess",sw=!known||chg===v,gh=!known&&!ov;pw.hidden=!sw;if(sw)seg.set(p);$("lpd").hidden=!known||sw;if(known)$("lpdt").textContent="Detected: "+PL[r.platform];$("lph").hidden=!gh;if(gh)$("lph").textContent="We guessed "+PL[r.platform]+" from the ID length. Pick the right marketplace if it is wrong.";}
var seg=TK.seg($("lp"),function(v){if(cur){pick={id:cur.id,p:v,v:inp.value.trim()};run(true);}});
var keep=TK.debounce(function(d){if(cur&&cur.id===d.id){rq.add({p:d.p,id:d.id,t:Date.now()},same);}},1200);
function recent(){drawRecent(rq,cur,function(){return '<span class="tk-ic">'+I.link+'</span>';});}
function run(now){var v=inp.value.trim();clr.hidden=!v;pbSync("lc-paste",v);if(!v){nodet();cur=null;said="";setOut("empty",EMPTY);TK.qs.set({u:null});recent();return;}
var r=pcDetect(v,PCCAT.look);
if(isShop(v)){nodet();cur=null;sayOnce("That is a shop link");setOut("error",alertH("That Is A Shop Link","This link opens a seller's whole shop, not one item. Open the item you want in the shop, then copy that link."));return;}
if(r.pending){nodet();setOut("loading",'<div class="tk-res" aria-hidden="true"><span class="tk-skel line"></span><span class="tk-skel big"></span></div>');PCCAT.load(function(){if(inp.value.trim()===v)run(true);});return;}
var su=!r.id&&shortOf(v);if(su){nodet();cur=null;setOut("loading",'<div class="tk-res"><p class="tk-res-k">Opening the share link</p><span class="tk-skel big" aria-hidden="true"></span></div>');resolveShort(su,function(d){if(inp.value.trim()!==v)return;if(d){inp.value=d.url;TK.say("Share link opened");run(true);}else{sayOnce("Share link not opened");setOut("error",alertH("We Could Not Open That Share Link","Open it in your browser or the Taobao app, then copy the full product link from the address bar."));}});return;}
if(!r.id){nodet();cur=null;sayOnce(r.short?"That is a share link":"No item ID found");setOut("error",r.short?alertH("That Is A Share Link","Open it in your browser first, then copy the full product link from the address bar."):alertH("No Item ID Found","Paste the full product or agent link, or just the item ID."));return;}
var ov=pick&&pick.id===r.id&&pick.v===v?pick.p:"",p=ov||r.platform,g=r.source==="guess"&&!ov;det(r,p,!!ov,v);
cur={p:p,id:r.id};L=ag(p,r.id);var o=orig(p,r.id),me=L[0];sayOnce(L.length+" agent links ready for "+PL[p]+" "+r.id);
var opt=function(a){return '<div class="tk-opt"><div class="tk-opt-main">'+esc(a.name)+'</div><div class="tk-opt-act"><a class="btn sm" href="'+esc(a.url)+'" data-agent="'+a.id+'" target="_blank" rel="sponsored nofollow noopener" aria-label="Open in '+esc(a.name)+'">Open</a>'+cpBtn("Copy",'data-copy="'+esc(a.url)+'" aria-label="Copy the '+esc(a.name)+' link"')+'</div></div>';};
setOut("success",'<div class="tk-res"><div class="tk-res-top"><p class="tk-res-k">'+esc(PL[p]+" · "+r.id)+(g?' <span class="tk-badge">Guessed</span>':'')+'</p>'+cpBtn("Copy Item Link",'data-copy="'+esc(o)+'" data-msg="Item link copied"')+'</div>'+
'<div id="fnd" data-k="pc.find.'+esc(p+"."+r.id)+'" hidden></div>'+
'<div class="tk-buy"><a class="btn primary lg" href="'+esc(me.url)+'" data-agent="'+me.id+'" target="_blank" rel="sponsored nofollow noopener">Buy On '+esc(me.name)+'</a>'+cpBtn("Copy",'data-copy="'+esc(me.url)+'" data-msg="'+esc(me.name)+' link copied" aria-label="Copy the '+esc(me.name)+' link"')+(me.mine?'<span class="tk-badge">Your Agent</span>':'')+'</div>'+
'<p class="tk-sub">Other agents</p>'+L.slice(1,5).map(opt).join("")+(L.length>5?'<div id="agx" style="margin-top:8px" hidden>'+L.slice(5).map(opt).join("")+'</div><button type="button" class="btn ghost sm" id="agxb" style="margin-top:8px">See more agents</button>':"")+
'<div class="tk-actions"><a class="btn" href="/tools/qc-checker?u='+encodeURIComponent(v.slice(0,500))+'">Check QC Photos</a><a class="btn" id="opc" href="/product/'+esc(r.pid||r.id)+'" hidden>Open On Puro Classico</a>'+cpBtn("Copy All Links",'data-copy="*" data-msg="All links copied"')+'</div>'+
'<details class="tk-more"><summary>Show All Links</summary><p>'+L.map(function(a){return esc(a.name)+': <a href="'+esc(a.url)+'" data-agent="'+a.id+'" target="_blank" rel="sponsored nofollow noopener">'+esc(a.url)+'</a>';}).join("<br>")+'</p></details></div>');
var xb=$("agxb");if(xb)xb.addEventListener("click",function(){var x=$("agx");if(x)x.hidden=false;xb.remove();var f=x&&x.querySelector("a");if(f)f.focus();});TK.qs.set({u:v.length<=500?v:o});findCheck(p,r.id,r.pid);keep(cur);recent();}
$("lpdc").addEventListener("click",function(){if(!cur)return;chg=inp.value.trim();run(true);var b=$("lp").querySelector('[aria-checked="true"]');if(b)b.focus();});
var live=TK.debounce(function(){run();},200);
inp.addEventListener("input",live);inp.addEventListener("keydown",function(e){if(e.key==="Enter"){e.preventDefault();run(true);}});
clr.addEventListener("click",function(){inp.value="";pick=null;run();inp.focus();});
TK.pasteBtn(inp,$("lc-paste"));
$("out").addEventListener("click",function(e){var b=e.target.closest("[data-copy]");if(b){var c=b.getAttribute("data-copy");TK.copy(c==="*"?L.map(function(a){return a.name+": "+a.url;}).join("\\n"):c,b,b.getAttribute("data-msg")||"Link copied");return;}var x=e.target.closest("[data-ex]");if(x){inp.value=x.getAttribute("data-ex");run(true);}});
$("rl").addEventListener("click",function(e){var b=e.target.closest("[data-x]"),a=rq.list();if(b){rq.remove(+b.getAttribute("data-x"));recent();$("lc").focus();return;}b=e.target.closest("[data-r]");if(b){var x=a[+b.getAttribute("data-r")];if(x){inp.value=orig(x.p,x.id);run(true);inp.focus();}}});
$("rcx").addEventListener("click",function(){rq.clear();recent();});
var q=TK.qs.get("u");if(q){inp.value=q.slice(0,2000);run(true);}else recent();})();</script>`; },

  "qc-checker": () => { const ex = toolExamples();
    const empty = `<div class="tk-empty">${TK_I.image}<p>Search a product or paste a link to see real QC photos from earlier buyers.</p><div class="tk-chips"><span>Try:</span>${chip(ex.brand, ex.brand)}${chip("Weidian link", ex.w)}${chip("Taobao link", ex.t)}${chip("Item ID", ex.id)}</div></div>`;
    return `<section class="tk-card" aria-label="QC Photo Checker"><form id="qf" action="/tools/qc-checker" method="get" novalidate>${pasteField("qi", "Product name, link or item ID", "Search a product or paste a Weidian or Taobao link", "")}${platSeg("qp", true)}
<div class="tk-row"><button type="submit" class="btn primary lg" id="go"><span class="tk-spin" aria-hidden="true"></span><span class="l">Find QC Photos</span></button><span class="tk-kbd" aria-hidden="true"><kbd>Enter</kbd> to check</span></div></form>
<div class="tk-out" id="out" data-state="empty">${empty}</div></section>${recentBox("Recent Checks")}
<dialog class="tk-lightbox" id="lb" aria-label="QC photo viewer"><div class="tk-lb-fig" id="lbf"><img id="lbi" alt=""><button type="button" class="tk-lb-nav prev" id="lbp" aria-label="Previous photo">${TK_I.prev}</button><button type="button" class="tk-lb-nav next" id="lbn" aria-label="Next photo">${TK_I.next}</button></div>
<div class="tk-lb-bar"><span id="lbc" aria-live="polite"></span><div class="tk-actions"><a class="btn sm" id="lbo" href="#" target="_blank" rel="noopener">${TK_I.ext}Open Original</a><button type="button" class="btn sm" id="lbx">Close</button></div></div></dialog>
<script>(function(){${EXTRACT}${TK_JS}${AGENT_JS}${LINK_JS}${PASTE_JS}
var EMPTY=${JSON.stringify(empty)},inp=$("qi"),go=$("go"),clr=$("qi-clr"),pw=$("qpw"),busy=false,again=false,cur=null,lastK="",skT=0,qpick=null,chg=null,rq=TK.recent("pc.qc.recent",6),same=${sameItem};
var seg=TK.seg($("qp"),function(v){if(cur){qpick={id:cur.id,p:v,v:inp.value.trim()};run(true);}});
function det(r){if(!r||!r.id||r.pending){pw.hidden=true;$("qpd").hidden=true;$("qph").hidden=true;return;}var v=inp.value.trim(),known=!!r.platform&&r.source!=="guess",sw=!known||chg===v,ov=qpick&&qpick.id===r.id&&qpick.v===v,gh=!known&&!ov;
pw.hidden=!sw;if(sw)seg.set(ov?qpick.p:r.platform);$("qpd").hidden=!known||sw;if(known)$("qpdt").textContent="Detected: "+PL[r.platform];$("qph").hidden=!gh;if(gh)$("qph").textContent="We guessed "+PL[r.platform]+" from the ID length. Pick the right marketplace if it is wrong.";}
$("qpdc").addEventListener("click",function(){var r=parse(inp.value.trim());if(!r.id)return;chg=inp.value.trim();det(r);var b=$("qp").querySelector('[aria-checked="true"]');if(b)b.focus();});
function primary(on){go.classList.toggle("primary",on);}
function parse(v){return pcDetect(v,PCCAT.look);}
function sync(){var v=inp.value.trim(),r=v?parse(v):{};clr.hidden=!v;pbSync("qi-paste",v);det(r);}
function recent(){drawRecent(rq,cur,function(x){return x.th?'<img src="'+esc(x.th)+'" alt="" loading="lazy" onerror="this.style.visibility=\\'hidden\\'">':'<span class="tk-ic">'+I.image+'</span>';});}
function cnt(n){return n+" QC Photo"+(n===1?"":"s");}
function thumb(u){u=String(u);var o="https://www.puroclassico.com",k=u.indexOf(o+"/api/img?");return k===0?o+"/cdn-cgi/image/width=400,quality=75,format=auto"+u.slice(o.length):u;}
function idle(){busy=false;go.disabled=false;go.removeAttribute("aria-busy");go.querySelector(".l").textContent="Find QC Photos";$("out").removeAttribute("aria-busy");}
function skel(d){var h='<div class="tk-res" aria-hidden="true"><p class="tk-res-k">'+esc(PL[d.p]+" · "+d.id)+'</p><span class="tk-skel big"></span><div class="tk-gal">';for(var i=0;i<5;i++)h+='<span class="tk-skel"></span>';return h+'</div></div>';}
function show(d){var who=esc(PL[d.p]+" · "+d.id)+(d.g?' <span class="tk-badge">Guessed</span>':'');
if(d.s==="ok"){primary(false);TK.say(cnt(d.t.length)+" found");var a=ag(d.p,d.id)[0];
setOut("success",'<div class="tk-res"><p class="tk-res-k">'+who+'</p><p class="tk-big" id="qn">'+cnt(d.t.length)+'</p>'+(d.c>d.t.length?'<p class="tk-res-sub">Showing '+d.t.length+' of '+esc(d.c)+' QC photos on record</p>':'')+(d.n?'<p class="tk-res-sub">'+esc(d.n)+'</p>':'')+
'<div class="tk-gal" id="gal">'+d.t.map(function(u,i){return '<button type="button" data-u="'+esc(u)+'" aria-label="Open QC photo '+(i+1)+'"><img src="'+esc(thumb(u))+'" data-o="'+esc(u)+'" alt="QC photo '+(i+1)+'" loading="'+(i<5?"eager":"lazy")+'" decoding="async"></button>';}).join("")+'</div>'+'<div id="fnd" data-k="pc.find.'+esc(d.p+"."+d.id)+'" hidden></div>'+
'<div class="tk-actions"><a class="btn primary" href="'+esc(a.url)+'" data-agent="'+a.id+'" target="_blank" rel="sponsored nofollow noopener">Buy On '+esc(a.name)+'</a><a class="btn" id="opc" href="/product/'+esc(d.id)+'" hidden>Open On Puro Classico</a>'+cpBtn("Copy Link",'data-copy="share"')+'</div></div>');
[].forEach.call($("gal").querySelectorAll("img"),function(im){im.addEventListener("error",function(){if(im.getAttribute("data-o")&&im.src!==im.getAttribute("data-o")){im.src=im.getAttribute("data-o");im.removeAttribute("data-o");return;}var b=im.parentNode;if(b&&b.parentNode)b.parentNode.removeChild(b);var n=$("gal").children.length,q=$("qn");if(q)q.textContent=cnt(n);});});
findCheck(d.p,d.id,cur&&cur.id===d.id?cur.pid:null);rq.add({p:d.p,id:d.id,th:d.t[0]||"",t:Date.now()},same);recent();return;}
primary(true);
if(d.s==="none"){TK.say("No QC photos yet");setOut("none",alertH("No QC Photos Yet",who+'<br>Photos only exist once someone has bought this item through an agent. When you order, your agent takes QC photos of your own item before it ships, so you can still check it then.','<a class="btn sm" href="/tools/link-converter?u='+encodeURIComponent(orig(d.p,d.id))+'">Get Buy Links</a><a class="btn sm ghost" href="/guides/how-to-qc">How To Read QC</a>')+'<div id="fnd" data-k="pc.find.'+esc(d.p+"."+d.id)+'" hidden></div>');findCheck(d.p,d.id,null);recent();return;}
if(d.s==="busy")setOut("error",alertH("Too Many Checks Right Now","Try again in about 10 minutes.","",1));
else if(d.s==="bad")setOut("error",alertH("That ID Does Not Look Right","Paste the full product link instead.","",1));
else setOut("error",alertH("QC Service Not Reachable","Try again in a moment.",'<button type="button" class="btn sm" id="again">Try Again</button>',1));
lastK="";}
function searchQ(v){if(/https?:|www\\.|[a-z0-9-]\\.(?:com|cn|net|hk)\\b/i.test(v)||!/[a-z]/i.test(v))return "";var q=pcNorm(v);return q.length>=2?q:"";}
function img(u){u=String(u||"");if(!u)return "";if(u.charAt(0)==="/")return "/cdn-cgi/image/width=400,quality=75,format=auto"+u+(/^\\/img\\/rl\\/[^?]+$/.test(u)?"?c=1":"");return /\\.supabase\\.co\\/storage\\/v1\\/object\\/public\\//.test(u)?"/api/img?u="+encodeURIComponent(u):u;}
function hitCard(x){var o=orig(x.p,x.i),t=x.b&&x.t.toLowerCase().indexOf(x.b.toLowerCase())!==0?x.b+" "+x.t:x.t;
return '<a class="tk-find" style="margin-top:8px" href="/tools/qc-checker?u='+encodeURIComponent(o)+'" data-q="'+esc(o)+'"><img src="'+esc(img(x.u))+'" alt="" loading="lazy" decoding="async" onerror="this.style.visibility=\\'hidden\\'"><span><span class="t">'+esc(t)+'</span><span class="s">'+esc((x.usd>0?"$"+x.usd+" · ":"")+(x.qc>=2?x.qc+" QC photos on record":"QC photos on record")+" · "+(PL[x.p]||x.p))+'</span></span></a>';}
function search(q,v,force){var k="s:"+q;if(k===lastK&&!force)return;lastK=k;cur=null;det(null);primary(true);TK.qs.set({u:v});setOut("loading",'<div class="tk-res" aria-hidden="true"><span class="tk-skel line"></span><span class="tk-skel big"></span></div>');
PCCAT.load(function(){if(pcNorm(inp.value)!==q)return;var R=PCCAT.rows();if(!R){lastK="";setOut("error",alertH("Search Not Available Right Now","Paste the product link or item ID instead.","",1));return;}
var w=q.split(" "),hit=[],any=0;for(var i=0;i<R.length;i++){var x=R[i],ok=true;for(var j=0;j<w.length;j++)if((" "+x.s+" ").indexOf(w[j].length<3?" "+w[j]+" ":w[j])<0){ok=false;break;}if(!ok)continue;any++;if(x.qc>=1)hit.push(x);}
hit.sort(function(a,b){return (b.qc-a.qc)||(b.pop-a.pop);});
if(!hit.length){TK.say("No finds with QC photos");setOut("none",alertH("No QC Photos For That Search",esc(any?any+" finds match, but none of them has buyer QC photos on record yet.":"No finds match that search.")+" Try a brand or model name, or paste the product link.",'<a class="btn sm" href="/spreadsheet">Open The Spreadsheet</a><a class="btn sm ghost" href="/guides/how-to-qc">How To Read QC</a>'));return;}
TK.say(hit.length+" finds with QC photos");
setOut("success",'<div class="tk-res"><p class="tk-res-k">Search · '+esc(v)+'</p><p class="tk-big">'+hit.length+' Find'+(hit.length===1?'':'s')+' With QC Photos</p><p class="tk-res-sub">'+(hit.length>12?'The 12 with the most QC photos. ':'')+'Tap a find to load its QC photos here.</p><div>'+hit.slice(0,12).map(hitCard).join("")+'</div>'+(hit.length>12?'<div class="tk-actions"><a class="btn" href="/qc-spreadsheet">All Finds With QC Photos</a></div>':'')+'</div>');});}
function run(force){if(busy){again=true;return;}var v=inp.value.trim();sync();if(!v){cur=null;lastK="";primary(true);setOut("empty",EMPTY);TK.qs.set({u:null});recent();return;}
if(isShop(v)){cur=null;lastK="";det(null);primary(true);setOut("error",alertH("That Is A Shop Link","This link opens a seller's whole shop, not one item. Open the item you want, then paste that link.","",1));return;}
var r=parse(v);if(r.pending){det(null);clearTimeout(skT);setOut("loading",'<div class="tk-res" aria-hidden="true"><span class="tk-skel line"></span><span class="tk-skel big"></span></div>');PCCAT.load(function(){if(inp.value.trim()===v)run(true);});return;}
var su=!r.id&&shortOf(v);if(su){cur=null;lastK="";det(null);setOut("loading",'<div class="tk-res"><p class="tk-res-k">Opening the share link</p><span class="tk-skel big" aria-hidden="true"></span></div>');resolveShort(su,function(d){if(inp.value.trim()!==v)return;if(d){inp.value=d.url;TK.say("Share link opened");run(true);}else setOut("error",alertH("We Could Not Open That Share Link","Open it in your browser or the Taobao app, then copy the full product link from the address bar.","",1));});return;}
var sq=!r.id&&!r.short&&searchQ(v);if(sq){search(sq,v,force);return;}
if(!r.id){cur=null;lastK="";primary(true);setOut("error",r.short?alertH("That Is A Share Link","Open it in your browser first, then copy the full product link from the address bar.","",1):alertH("No Item ID Found","Paste the full product link, or the item ID on its own.","",1));return;}
var ov=qpick&&qpick.id===r.id&&qpick.v===v?qpick.p:"",known=!!r.platform&&r.source!=="guess",g=0,p;if(known)p=chg===v&&ov?ov:r.platform;else{p=ov||r.platform;g=ov?0:1;}det(r);
var k="pc.qc."+p+"."+r.id;if(k===lastK&&!force)return;lastK=k;cur={p:p,id:r.id,pid:r.pid||null};TK.qs.set({u:v.length<=500?v:orig(p,r.id)});
var c=TK.sess.get(k,null);if(c&&c.t){c.g=g;show(c);return;}
busy=true;go.disabled=true;go.setAttribute("aria-busy","true");go.querySelector(".l").textContent="Checking";$("out").setAttribute("aria-busy","true");
clearTimeout(skT);skT=setTimeout(function(){setOut("loading",skel(cur));},150);
var ctl=null;try{ctl=new AbortController();}catch(e){}var to=setTimeout(function(){if(ctl)ctl.abort();},10000);
fetch("/api/qc?storefront="+p+"&id="+encodeURIComponent(r.id),ctl?{signal:ctl.signal}:{}).then(function(res){
if(res.status===200)return res.json().then(function(d){var t=(d&&d.thumbnails)||[];return{s:t.length?"ok":"none",t:t.slice(0,12),c:d&&+d.qc_count>0?Math.round(+d.qc_count):0,n:d&&typeof d.name==="string"?d.name.slice(0,200):""};},function(){return{s:"down"};});
return{s:res.status===404?"none":res.status===429?"busy":res.status===400?"bad":"down"};},function(){return{s:"down"};}).then(function(d){
clearTimeout(to);clearTimeout(skT);idle();d.p=p;d.id=r.id;if(again){again=false;var nv=parse(inp.value.trim());if(!inp.value.trim()||(nv.id&&nv.id!==r.id)){if(d.s==="ok"||d.s==="none"){d.t=d.t||[];TK.sess.set(k,d);}run(true);return;}}if(d.s==="ok"||d.s==="none"){d.t=d.t||[];TK.sess.set(k,d);}d.g=g;if(cur&&cur.id===r.id&&cur.p===p)show(d);});}
var auto=TK.debounce(function(){var v=inp.value.trim(),r=parse(v);if(r.id&&!/^\\d+$/.test(v))run();else if(!r.id&&searchQ(v).length>=3)run();},350);
inp.addEventListener("input",function(){sync();auto();});
inp.addEventListener("paste",function(){setTimeout(function(){sync();var v=inp.value.trim();if(parse(v).id)run();},0);});
inp.addEventListener("tk:paste",function(){run();});
inp.addEventListener("blur",function(){var v=inp.value.trim();if(/^\\d{6,}$/.test(v))run();});
$("qf").addEventListener("submit",function(e){e.preventDefault();run(true);});
clr.addEventListener("click",function(){inp.value="";run();inp.focus();});
TK.pasteBtn(inp,$("qi-paste"));
var lb=$("lb"),li=$("lbi"),tiles=[],at=0,from=null;
function lbShow(i){at=(i+tiles.length)%tiles.length;var u=tiles[at].getAttribute("data-u");li.src=u;li.alt="QC photo "+(at+1)+" of "+tiles.length;$("lbo").href=u;$("lbc").textContent=(at+1)+" / "+tiles.length;$("lbp").hidden=$("lbn").hidden=tiles.length<2;}
function lbOpen(b){tiles=[].slice.call($("gal").querySelectorAll("button"));from=b;if(!lb.showModal){window.open(b.getAttribute("data-u"),"_blank","noopener");return;}lbShow(tiles.indexOf(b));lb.showModal();}
lb.addEventListener("close",function(){if(from&&from.isConnected)from.focus();});
lb.addEventListener("click",function(e){if(e.target===lb)lb.close();});
lb.addEventListener("keydown",function(e){if(e.key==="ArrowLeft"){e.preventDefault();lbShow(at-1);}else if(e.key==="ArrowRight"){e.preventDefault();lbShow(at+1);}});
$("lbp").addEventListener("click",function(){lbShow(at-1);});$("lbn").addEventListener("click",function(){lbShow(at+1);});$("lbx").addEventListener("click",function(){lb.close();});
var sx=0,sy=0;$("lbf").addEventListener("touchstart",function(e){sx=e.touches[0].clientX;sy=e.touches[0].clientY;},{passive:true});
$("lbf").addEventListener("touchend",function(e){var dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy))lbShow(at+(dx<0?1:-1));else if(dy>90)lb.close();},{passive:true});
$("out").addEventListener("click",function(e){var h=e.target.closest("[data-q]");if(h){e.preventDefault();inp.value=h.getAttribute("data-q");run(true);try{inp.scrollIntoView({block:"nearest"});}catch(x){}return;}var t=e.target.closest("#gal button");if(t){lbOpen(t);return;}var b=e.target.closest("[data-copy]");if(b){TK.copy(location.origin+"/tools/qc-checker?u="+encodeURIComponent(cur?orig(cur.p,cur.id):inp.value.trim()),b,"Link copied");return;}if(e.target.closest("#again")){run(true);return;}var x=e.target.closest("[data-ex]");if(x){inp.value=x.getAttribute("data-ex");run(true);}});
$("rl").addEventListener("click",function(e){var b=e.target.closest("[data-x]"),a=rq.list();if(b){rq.remove(+b.getAttribute("data-x"));recent();inp.focus();return;}b=e.target.closest("[data-r]");if(b){var x=a[+b.getAttribute("data-r")];if(x){inp.value=orig(x.p,x.id);run(true);inp.focus();}}});
$("rcx").addEventListener("click",function(){rq.clear();recent();});
var q=TK.qs.get("u");if(q){inp.value=q.slice(0,2000);run(true);}else{sync();recent();}})();</script>`; },
};
const TRUST = { "qc-checker": [TK_TRUST.free, TK_TRUST.nosign], "link-converter": [TK_TRUST.free, TK_TRUST.nosign, TK_TRUST.nostore] };
const TOOL_H1 = { "qc-checker": "Find Real QC Photos For Any Rep", "link-converter": "Any Link To Any Agent" };
// 22 Nov 2026 (SEO check): the QC tool is the page for "QC finder" searches, which want a tool that finds QC photos for a link
// (the pages ranking for it are such tools). The QC photos spreadsheet (/qc-spreadsheet) keeps "QC photos".
// 24 Nov 2026 (Search Console, 6 months to 22 Nov): "qc photos" 2,203 impressions, "qc checker" 1,328, "qc check" 671,
// "qc photo" 563, "qc pics" 421, all around position 8 to 9 with almost no clicks. Google showed /guides/how-to-qc for them
// (7,925 impressions, 0.28% CTR) and this tool not at all. So the tool is now the QC Photo Checker: its title, h1 and
// description use those words, it also searches the catalogue by product name (finds marked with QC photos, most photos
// first), and "QC finder" stays in its description and FAQ. Copy in content2.js (TOOLS) is unchanged: these win over it.
const TOOL_SEO = { "qc-checker": { name: "QC Photo Checker", title: "QC Checker: Find Real QC Photos & Pics for Any Rep Link",
  lead: "Search a product or paste a Weidian, Taobao or agent link to see real QC photos from people who already bought it.",
  desc: `Free QC photo checker and QC finder: search a product or paste a Weidian, Taobao or agent link to see real buyer QC pics. ${QC_PLUS} finds with QC photos.` } };
// FAQs on the tool pages (22 Nov 2026, SEO check): questions people search with the tool's name, shown under the tool and as
// FAQPage data.
const TOOL_FAQ = {
  "qc-checker": [["What are QC photos?", "QC (quality check) photos are real photos of an item taken at a shopping agent's warehouse in China after it arrives from the seller and before it ships to the buyer. They show the actual piece, not the seller's own pictures."],
    ["Can I search QC photos by product name?", "Yes. Type a brand or model, such as a brand name and an item type, and the checker lists the finds on our spreadsheet that are marked as having buyer QC photos, the ones with the most photos first. Tap one to load its photos."],
    ["What is a QC finder?", "A QC finder shows quality check photos of a listing: photos that shopping agents took of the same item when earlier buyers ordered it. Paste a Weidian, Taobao, 1688 or agent link, or the item ID, and it shows the photos it can find."],
    ["Where do the QC photos come from?", "From earlier orders of the same listing through shopping agents, which photograph every item at their warehouse. Nothing is taken from the seller's own photos."],
    ["Why does a link show no QC photos?", "Nobody has ordered that listing through an agent yet, or the photos are not public. New listings often have none. When you order, your agent photographs your own item before it ships."],
    ["Which links does the QC finder read?", "Weidian, Taobao, Tmall and 1688 product links, links from MyCNBox, KakoBuy, Oopbuy, LoveGoBuy, Sugargoo and other agents, and bare item IDs. Short links shared from an app have to be opened in a browser first."],
    ["Is the QC finder free?", "Yes. It needs no account and keeps no record of the links you check."]],
  "link-converter": [["How do I turn a Weidian link into an agent link?", "Paste the Weidian link into the converter. It reads the item ID and gives you a buy link for MyCNBox, KakoBuy, Oopbuy and the other agents, ready to open."],
    ["Which links can I convert?", "Weidian, Taobao, Tmall and 1688 product links, links from most shopping agents (including old CNFans and Pandabuy links) and bare item IDs."],
    ["Why does my link not convert?", "Short links shared from the Weidian or Taobao app hide the item ID. Open the link in a browser, copy the full link it leads to and paste that."],
    ["Is the link converter free?", "Yes, and it needs no account. Agent links are affiliate links: we may earn a commission if you order, at no extra cost to you."]] };
// Hub: the "before you buy" pair is wide and carries a real mini form; the flow strip is navigation only.
const HUB_FORM = { "qc-checker": ["Check", "Product link or item ID"], "link-converter": ["Convert", "Weidian, Taobao, 1688 or agent link"] };
const HUB_FLOW = [["Check The QC", "QC Checker", "/tools/qc-checker"], ["Get Your Buy Link", "Link Converter", "/tools/link-converter"],
  ["Price The Shipping", "Shipping Calculator", "/tools/shipping-calculator"], ["Track It Home", "Parcel Tracker", "/tools/parcel-tracker"]];
// Three feature pills per tool card (icon pass), each a fact the tool's own text states; the long description moves
// into a <details> in the card.
const TOOL_PILLS = {
  "qc-checker": [["store", "Weidian, Taobao, 1688"], ["hash", "Link or item ID"], ["image", "Buyer QC photos"]],
  "link-converter": [["store", "Weidian, Taobao, 1688"], ["users", "5 agents"], ["zap", "Instant"]],
  "shipping-calculator": [["globe", "Your country"], ["box", "Items or weight"], ["truck", "3 line types"]],
  "size-estimator": [["ruler", "Height and weight"], ["tee", "Tops to sneakers"], ["tag", "Asian and EU/US"]],
  "parcel-tracker": [["hash", "Any tracking number"], ["truck", "Carrier detected"], ["ext", "One-tap tracking"]] };
const TOOL_IC = { "qc-checker": "camera", "link-converter": "link", "shipping-calculator": "box", "size-estimator": "ruler", "parcel-tracker": "pin" };
export function renderTools() {
  const bc = crumbs([["Home", "/"], ["Tools", "/tools"]]);
  const cards = TOOL_LINKS.map(([t, u]) => { const k = u.replace(/^\/tools\//, ""), f = HUB_FORM[k];
    return `<article class="tk-hc${f ? " wide" : ""}"><span class="tk-ic">${TK_ICONS[k] || ""}</span><span class="tk-arrow">${TK_I.right}</span><h2><a href="${u}">${esc(t)}</a></h2>` +
      `<p class="one">${esc(TOOL_ONE[k] || "")}</p>` + (TOOL_PILLS[k] ? `<ul class="ic-row tight">${TOOL_PILLS[k].map(([n, x]) => `<li>${ic(n, "sm")}<span>${esc(x)}</span></li>`).join("")}</ul>` : "") +
      (own(TOOLS, k) ? more("Details", `<p class="long">${esc(TOOLS[k].desc)}</p>`) : "") +
      (f ? `<form action="${u}" method="get"><label class="vh" for="hub-${k}">${esc(f[1])}</label><input class="tk-in" id="hub-${k}" name="u" type="text" inputmode="url" autocomplete="off" spellcheck="false" placeholder="Paste a link" required><button class="btn primary" type="submit">${f[0]}</button></form>` : "") + `</article>`; }).join("");
  const body = `<div class="tk-page hub">${bc.html}${tkHero({ h1: "Free Rep Tools", lead: "Check QC photos, convert links, estimate shipping, find your size and track your parcel. Free, no sign-up.", trust: [TK_TRUST.free, TK_TRUST.nosign] })}
<div class="tk-hub">${cards}</div>
<h2>Your Haul In 4 Tools</h2><ol class="tk-flow">${HUB_FLOW.map(([s, n, u]) => `<li><a href="${u}">${icTile(TOOL_IC[u.replace(/^\/tools\//, "")] || "grid")}<b>${esc(s)}</b><span>${esc(n)}</span></a></li>`).join("")}</ol>
<p class="tk-flow-tip">${ic("ruler", "sm")}Not sure about the size? <a href="/tools/size-estimator">Size Estimator</a></p></div>`;
  const list = { "@context": "https://schema.org", "@type": "ItemList", name: "Free Rep Tools",
    itemListElement: TOOL_LINKS.map(([n, u], i) => ({ "@type": "ListItem", position: i + 1, name: n, url: SITE + u })) };
  return page({ title: "Free Rep Tools: QC Photo Finder, Link Converter & More · Puro Classico", desc: "Free tools for buying reps through agents: QC photo checker, link converter, shipping calculator, size estimator and parcel tracker.", path: "/tools", body, jsonld: [bc.data, list] });
}
// What each agent's warehouse check covers, from the same help-centre pages as the agent spreadsheets (content.js
// AGENT_INTRO: MyCNBox read 10 Oct 2026, Hipobuy 26 Nov 2026, the others 9 Nov 2026). Shown on the QC finder (23 Nov 2026, SEO pass).
const AGENT_QC = [
  ["mycnbox", "4 standard photos per item, within one business day of it reaching the warehouse", "Detailed and multi-angle photos are a paid add-on, picked when you order"],
  ["kakobuy", "The item's appearance: model, style and size", "Clothing, bags, suitcases and shoes are opened; sealed items are checked from the outside"],
  ["oopbuy", "Quantity, colour, size and other specifications, then the item is repacked", "Colour difference and size error are outside its check"],
  ["lovegobuy", "Colour, large damage, stains, size, model and version number", "Size is read from the label; exact measurements are outside the check"],
  ["sugargoo", "5 free photos; style, quantity, colour, size and model", "Sealed packages are not opened, only compared from the outside"],
  ["hipobuy", "Quantity, colour, size and other specifications; generally 3 photos (front, back, side or logo)", "Custom photos from the angles you choose cost ¥1 each"]];
// The QC finder's own data (23 Nov 2026, SEO pass): the searches for "qc finder" and "qc photos reps" are answered by tools
// with QC photo lookups and finds that have them. Under the tool: each agent's warehouse check, and the visible finds with
// the most buyer QC photos on record (p.qc >= 2 is the photo count stored when the row was imported, so "on record").
function qcFinderExtra() {
  const vis = idx().all.filter(p => p.qc >= 1 && findShown(p)), most = vis.filter(p => p.qc >= 2 && p.img).sort((a, b) => b.qc - a.qc || score(b) - score(a)).slice(0, 12);
  const agents = `<section class="prose">${hIc("h2", "users", "QC photos on each agent")}<p>Whichever agent you order through photographs your own item when it reaches its warehouse in China, before anything ships. What the check covers differs:</p>` +
    `<table><tr><th>Agent</th><th>What the warehouse check covers</th><th>Worth knowing</th></tr>${AGENT_QC.map(([k, what, note]) => `<tr><td><a href="/${k}-spreadsheet">${esc(AGENTS[k].name)}</a></td><td>${esc(what)}</td><td>${esc(note)}</td></tr>`).join("")}</table>` +
    `<p style="font-size:13px;color:var(--muted)">From each agent's help centre (MyCNBox read 10 Oct 2026, Hipobuy 26 Nov 2026, the others 9 Nov 2026). Our links to agents are affiliate links.</p></section>`;
  const finds = most.length ? `<section class="prose">${hIc("h2", "camera", "Finds with the most buyer QC photos")}<p>The finds on the spreadsheet with the most buyer QC photos on record. Open one and tap QC to see them, or browse all ${nf(vis.length)} finds with QC photos in the <a href="/qc-spreadsheet">QC spreadsheet</a>.</p>` +
    `<ul>${most.map(p => `<li><a href="${productUrl(p)}#qc">${p.brand && !p.title.toLowerCase().startsWith(p.brand.toLowerCase()) ? esc(p.brand) + " " : ""}${esc(p.title)}</a>: ${nf(p.qc)} QC photos on record, ${money(p.cny)}</li>`).join("")}</ul></section>` : "";
  // 24 Nov 2026 (owner): the pages built for search send visitors on to the spreadsheet itself (/spreadsheet).
  const cta = `<section class="prose">${hIc("h2", "sheet", "Shop finds with QC photos")}<p>Every find on the spreadsheet shows its price and opens on MyCNBox, KakoBuy, Oopbuy, LoveGoBuy or Sugargoo in one tap. ${esc(QC_PLUS)} of them are marked as having buyer QC photos from earlier orders.</p>${SP_CTA}</section>`;
  return cta + agents + finds;
}
export function renderTool(s) {
  if (own(TOOL_UI9, s)) return toolPage9(s, TOOL_CSS);
  const t = own(TOOLS, s) && own(TOOL_UI, s) ? TOOLS[s] : null; if (!t) return null;
  const path = "/tools/" + s; const bc = crumbs([["Home", "/"], ["Tools", "/tools"], [t.name, path]]);
  const app = { "@context": "https://schema.org", "@type": "WebApplication", name: t.name + ": Puro Classico", url: SITE + path, applicationCategory: "UtilitiesApplication", operatingSystem: "Any", offers: { "@type": "Offer", price: "0", priceCurrency: "USD" }, description: t.desc };
    const seo = TOOL_SEO[s] || {};
  const faq = TOOL_FAQ[s] || null;
  return toolShell({ slug: s, name: seo.name || t.name, h1: TOOL_H1[s] || t.name, lead: seo.lead || t.lead, trust: TRUST[s] || [], ui: TOOL_UI[s](), about: t.about,
    faq: faq ? faqHtml(faq) : "", title: fitTitle(seo.title || t.title), desc: seo.desc || t.desc, jsonld: [bc.data, app].concat(faq ? [faqLd(faq)] : []), bc: bc.html,
    extra: s === "qc-checker" ? qcFinderExtra() : "" });
}

// ------------------------------------------------------------------ guides
// Guides hub groups (icon pass): every GUIDE_LINKS entry lands in exactly one group, in GUIDE_LINKS order; anything not
// listed goes to "More Guides". GUIDE_IC: the icon of each guide (cards, "More guides" chips).
const GUIDE_GROUPS = [["Start Here", "book", ["/how-to-order", "/guides/what-is-a-rep-spreadsheet", "/guides/how-to-find-reps", "/guides/rep-glossary"]],
  ["Buy From China", "store", ["/guides/how-to-buy-from-weidian", "/guides/how-to-buy-from-taobao", "/guides/how-to-buy-from-1688", "/guides/pandabuy-alternatives"]],
  ["Agents And Coupons", "users", ["/guides/best-shopping-agent", "/guides/mycnbox-review", "/guides/kakobuy-vs-mycnbox", "/guides/mycnbox-coupon-code", "/guides/kakobuy-coupon-code", "/guides/agent-coupons"]],
  ["QC, Sizing And Shipping", "camera", ["/guides/how-to-qc", "/guides/sizing", "/guides/shipping-lines"]]];
const GUIDE_IC = { "/how-to-order": "play", "/guides/how-to-buy-from-weidian": "store", "/guides/how-to-buy-from-taobao": "store", "/guides/how-to-buy-from-1688": "store",
  "/guides/how-to-qc": "camera", "/guides/sizing": "ruler", "/guides/best-shopping-agent": "users", "/guides/mycnbox-review": "shield", "/guides/kakobuy-vs-mycnbox": "split",
  "/guides/shipping-lines": "truck", "/guides/what-is-a-rep-spreadsheet": "sheet", "/guides/pandabuy-alternatives": "refresh", "/guides/rep-glossary": "book",
  "/guides/how-to-find-reps": "search", "/guides/how-we-check": "shield" };
const guideIcon = u => GUIDE_IC[u] || (/coupon/.test(u) ? "gift" : "book");
export function renderGuides() {
  const bc = crumbs([["Home", "/"], ["Guides", "/guides"]]);
  // 26 Nov 2026 (owner): the hub lists every guide as a compact row, icon and title only, 3 columns (all links kept).
  const row = ([t, u]) => { const k = u.replace(/^\/guides\//, ""), g = u.startsWith("/guides/") && own(GUIDES, k) ? GUIDES[k] : null;
    return `<a href="${u}">${icTile(guideIcon(u))}<span class="gl-t"><b>${esc(g ? g.h1 : t)}</b></span></a>`; };
  const listed = new Set(GUIDE_GROUPS.flatMap(x => x[2])), rest = GUIDE_LINKS.filter(([, u]) => !listed.has(u));
  const groups = GUIDE_GROUPS.map(([h, n, us]) => [h, n, GUIDE_LINKS.filter(([, u]) => us.includes(u))]).concat(rest.length ? [["More Guides", "book", rest]] : []);
  // 25 Nov 2026 (SEO pass): the guides' hero buttons and facts (renderGuide), so the index sends readers to the spreadsheet too
  const facts = [["sheet", `${FINDS_PLUS} finds`], ["camera", `${QC_PLUS} with QC photos`], ...(LINKS_CHECKED ? [["refresh", "Links checked weekly"]] : [])];
  const body = `${bc.html}<h1>Guides</h1><p class="lead">Everything you need to order your first finds from China: agents, QC photos, sizing and shipping.</p>
<div class="ga-cta"><a class="btn primary lg" href="/spreadsheet">Open the spreadsheet${ic("arrow-right", "sm")}</a><a class="btn lg" href="/how-to-order">${ic("play", "sm")}How to order (video)</a></div><ul class="ga-facts">${facts.map(([n, t]) => `<li>${ic(n, "sm")}${esc(t)}</li>`).join("")}</ul>
${groups.filter(x => x[2].length).map(([h, n, l]) => `${hIc("h2", n, esc(h))}<div class="gl gl-list">${l.map(row).join("")}</div>`).join("\n")}`;
  return page({ title: "Rep Buying Guides: Agents, QC, Sizing & Shipping · Puro Classico", desc: "Step-by-step guides: buy from Weidian, Taobao and 1688 through a shopping agent, read QC photos, pick your size and choose a shipping line.", path: "/guides", body, jsonld: [bc.data] });
}

// Guide icons (icon pass): h2s by heading text, steps by their leading words (first match wins). Text is unchanged.
const H2_IC = [[/GL or RL|QC|photo|checklist/i, "camera"], [/siz|measure/i, "ruler"], [/ship|volumetric|line/i, "truck"], [/cost|fee|price|charges|save|what it costs/i, "coins"],
  [/coupon|bonus|claim|cover/i, "gift"], [/\bvs\b|side by side|compare|choose|which/i, "split"], [/agent/i, "users"], [/step|how ordering|how to use|how to move|order/i, "list"],
  [/tip|rules of thumb|before you buy|using them well|test an agent/i, "bulb"], [/link check|links working|weekly/i, "refresh"], [/what is|main types|types/i, "book"],
  [/search|reverse image|find/i, "search"], [/seller|store/i, "store"], [/drawback|closed|paused|correction/i, "alert"], [/affiliate/i, "info"],
  [/facts|popularity|top picks|finds and prices|what is in/i, "chart"], [/weidian|taobao|1688/i, "store"]];
const STEP_IC = [[/account|sign up|register/i, "user-plus"], [/find|search|link/i, "search"], [/pay|checkout|buy|order/i, "cart"], [/QC|photo|check/i, "camera"],
  [/size|measure/i, "ruler"], [/ship|parcel|line/i, "truck"], [/track/i, "pin"], [/warehouse/i, "warehouse"], [/coupon|bonus/i, "gift"], [/logo|print/i, "type"],
  [/stitch/i, "scissors"], [/colou?r/i, "palette"], [/defect/i, "alert"]];
const plain = h => h.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&");
// <ol class="steps"> in a guide body: each step keeps its text; an icon tile (with the step number as a badge, ds.css) leads it.
const iconSteps = html => html.replace(/<ol class="steps">([\s\S]*?)<\/ol>/g, (m, inner) => `<ol class="steps ic-steps-list">${inner.replace(/<li>([\s\S]*?)(?=<\/li>)/g, (x, li) => {
  const lead = (li.match(/^\s*<strong>([\s\S]*?)<\/strong>/) || [])[1]; return `<li>${icTile(firstIcon(STEP_IC, plain(lead || li).slice(0, 80), "list"))}${li}`; })}</ol>`);
// A callout keeps its text; a tile on the left says what it is (a tip or a note).
const iconNotes = html => html.replace(/<div class="note">/g, (m, at) => `<div class="note has-ic">${icTile(/^\s*Tip/.test(plain(html.slice(at + m.length, at + m.length + 40))) ? "bulb" : "info")}`);
// Shorter titles for guides whose own title (content*.js) is over 60 characters and does not fit by dropping the year.
// Used only while that title is too long, so a shorter title written in content*.js wins.
const GUIDE_FIT = {
  "best-shopping-agent": "Best Shopping Agent 2026: MyCNBox, KakoBuy, Oopbuy, Sugargoo",
  "how-to-buy-from-1688": "How to Buy from 1688 (Factory Prices) with a Shopping Agent",
  "shipping-lines": "Shipping Lines Explained: Economy, Tax-Free, EMS & Express",
  "how-we-check": "How We Check the Spreadsheet: Link Checks & Affiliate Links",
  "mycnbox-coupon-code": "MyCNBox Coupon Code & Invite Code 2026: Up to $500 Coupons",
  "agent-coupons": "Shopping Agent Coupons & Sign-Up Bonuses 2026",
};
// Every guide sends readers to the spreadsheet itself (owner, 24 Nov 2026: "people look for the spreadsheet, nothing
// else"). Guide layout v12 (25 Nov 2026, SEO pass; owner: "make the blogs / seo pages look better and convert better"):
//   hero: the Guide pill (with the date), h1, lead, byline (reading time, How we check), "Open the spreadsheet" plus one
//     page or tool that fits the guide (GUIDE_NEXT), and three facts from the catalogue (finds, QC photos, link check);
//   from 1024px a side column that stays in view: "On this page" (the section being read is marked) and the spreadsheet
//     card. Below 1024px "On this page" folds into one row under the hero, and the product page's bar (.buybar) rises
//     from the bottom with the spreadsheet button once the hero button has scrolled away, gone again at the closing panel;
//   in the text: the guide's finds (8 cards, as before) after its second section, the QC photo examples on the QC guide
//     (g.qcEx), the FAQ, "How we check this guide" and a closing panel with the spreadsheet button;
//   under it: related guides as cards (same group first) and every guide as chips.
// Text, heading ids, icons and structured data are as they were; the finds grid that closed the page moved into the text.
const GUIDE_NEXT = {
  "how-to-qc": ["Find QC photos for a link", "/tools/qc-checker", "camera"],
  "how-to-buy-from-weidian": ["Weidian spreadsheet", "/weidian-spreadsheet", "store"],
  "how-to-buy-from-taobao": ["Taobao spreadsheet", "/taobao-spreadsheet", "store"],
  "how-to-buy-from-1688": ["1688 spreadsheet", "/1688-spreadsheet", "store"],
  "sizing": ["Size estimator", "/tools/size-estimator", "ruler"],
  "shipping-lines": ["Shipping calculator", "/tools/shipping-calculator", "box"],
  "pandabuy-alternatives": ["Convert a Pandabuy link", "/tools/link-converter", "link"],
  "how-to-find-reps": ["Link converter", "/tools/link-converter", "link"],
  "what-is-a-rep-spreadsheet": ["QC photos spreadsheet", "/qc-spreadsheet", "camera"],
  "how-we-check": ["About Puro Classico", "/about", "info"],
};
const GUIDE_NEXT_DEFAULT = ["How to order (video)", "/how-to-order", "play"];
const SP_CTA = `<p class="sp-cta"><a class="btn primary" href="/spreadsheet">Open the spreadsheet${ic("arrow-right", "sm")}</a></p>`;   // the QC finder's closing button (qcFinderExtra)
const dayLong = d => new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
// Real buyer QC photos on the QC guide (g.qcEx in content.js): [find id, number of photos in the QC bank, what to check].
// The photos are the find's own banked QC photos (products/qc/<platform>-<item id>-<n>.webp, the files /api/qc serves for
// it), shown only while the find is on the spreadsheet and in the bank (QC_BANKED). A photo that fails to load is removed.
const QC_PUB = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/qc/";
function qcExamples(list) {
  const { byId } = idx();
  const sets = (list || []).map(([id, n, what]) => [byId.get(id), n, what]).filter(([p]) => p && findShown(p) && QC_BANKED[p.id]);
  if (!sets.length) return "";
  return `<h2>Real QC photos, and what to check in them</h2><p>These are buyer QC photos from earlier orders of finds on the spreadsheet, as the warehouse took them: on a measuring mat, from several sides, with the labels close up. Tap a set to see the find, its price and every agent's buy link.</p>` +
    sets.map(([p, n, what]) => {
      const u = productUrl(p), name = (p.brand && !p.title.toLowerCase().startsWith(p.brand.toLowerCase()) ? p.brand + " " : "") + p.title;
      const tiles = Array.from({ length: Math.min(n, 5) }, (_, i) => { const src = SITE + "/api/img?u=" + encodeURIComponent(`${QC_PUB}${p.platform}-${p.itemId || p.id}-${i}.webp?b=2`);
        return `<a href="${u}#qc"><img src="${esc(thumbSrc(src))}" alt="QC photo ${i + 1} of ${esc(name)}" width="200" height="200" loading="lazy" decoding="async" onerror="this.parentNode.remove()"></a>`; }).join("");
      return `<figure class="ga-qc"><div class="ga-qc-r">${tiles}</div><figcaption><a href="${u}">${esc(name)}</a>, ${money(p.cny)}. ${esc(what)}</figcaption></figure>`;
    }).join("");
}
export function renderGuide(s) {
  const g = own(GUIDES, s) ? GUIDES[s] : null; if (!g) return null;
  const path = "/guides/" + s; const bc = crumbs([["Home", "/"], ["Guides", "/guides"], [g.h1, path]]);
  const { all, byCat } = idx();
  // A guide shows a date only when it stores its own (g.updated = the day its text was last revised and its facts
  // re-checked, set by hand in content*.js). The catalogue build date says nothing about a guide's text.
  // What is in the catalogue (28 Oct 2026), counted when the page renders, on the rep spreadsheet guide only: the guides that
  // outrank it for "rep spreadsheet" show their counts by category; ours are first-party numbers. The table takes its
  // styles (hairlines, tabular numbers) from ds.css. Toys are left out, as in the hubs' category chips.
  let stats = "";
  const vis = all.filter(findShown);
  if (s === "what-is-a-rep-spreadsheet") {
    const half = l => { const u = l.filter(p => !isPH(p.cny)).sort((x, y) => x.cny - y.cny); return u.length ? money(u[Math.floor((u.length - 1) / 2)].cny) : "Ask seller"; };
    // 23 Nov 2026 (SEO pass): the page Google shows for "rep spreadsheet", so it opens with the spreadsheet itself: its most
    // viewed finds (with buy buttons) right under the intro, then the counts (finds a visitor can see), then this week's new
    // finds. The "Popular finds" grid of other guides is left out here.
    const rows = Object.entries(CATS).filter(([, m]) => m.slug !== "toys").map(([c, m]) => [m, (byCat.get(c) || []).filter(findShown)]).filter(([, l]) => l.length >= 20).sort((x, y) => y[1].length - x[1].length);
    const fresh = freshAbout()[0];
    stats = `<h2>Popular finds right now</h2><p>The top of the spreadsheet in its Most popular order, where views in the last 30 days count most. Tap Buy to open a find in MyCNBox, or open it to see the other agents and its QC photos.</p><div class="ga-finds">${grid(vis.slice(0, 8))}</div><p><a class="btn" href="/spreadsheet">Open all ${nf(vis.length)} finds${ic("arrow-right", "sm")}</a></p>` +
      `<h2>What is in this rep spreadsheet</h2><p>Counted from the catalogue, last updated ${dayLong(BUILT)}: ${nf(vis.length)} finds, ${nf(vis.filter(p => p.qc >= 1).length)} of them marked as having buyer QC photos from earlier orders.` +
      (LINKS_CHECKED ? ` Our weekly link check last ran on ${dayLong(LINKS_CHECKED)} and found ${nf(GONE_COUNTS.dead)} Weidian listings gone, which the spreadsheet hides, and ${nf(GONE_COUNTS.sold)} sold out.` : "") + `</p>` +
      `<div class="ga-tw"><table><tr><th>Category</th><th>Finds</th><th>Half listed at or under</th><th>Marked with QC photos</th></tr>` +
      rows.map(([m, l]) => `<tr><td><a href="/category/${m.slug}">${ic(CAT_SLUG_IC[m.slug] || "grid", "sm")}${esc(m.name)}</a></td><td>${nf(l.length)}</td><td>${half(l)}</td><td>${nf(l.filter(p => p.qc >= 1).length)}</td></tr>`).join("") + `</table></div>` +
      (fresh ? `<h2>${esc(fresh[0])}</h2>${fresh[1]}` : "");
  }
  // The lead goes to the hero; an in-text spreadsheet button is left out (the hero, side column, bar and closing panel carry it).
  const leadM = g.body.match(/^\s*<p class="lead">([\s\S]*?)<\/p>/);
  let body = (leadM ? g.body.slice(leadM[0].length) : g.body).replace(/<p><a class="btn light" href="\/spreadsheet">[^<]*<\/a><\/p>\s*/g, "");
  if (stats) body = body.replace("<h2>", stats + "<h2>");
  // Inserted before the n-th <h2> of the text (0 = before the first), or at its end: the QC photo examples after the first
  // section (the QC guide: after the checklist) and the agents side by side (g.compare, g.compareAt) on the agent guides.
  const beforeH2 = (html, n) => { let at = -1; for (let i = 0; i <= n; i++) { at = body.indexOf("<h2>", at + 1); if (at < 0) break; } body = at >= 0 ? body.slice(0, at) + html + body.slice(at) : body + html; };
  const qcx = g.qcEx ? qcExamples(g.qcEx) : "";
  if (qcx) beforeH2(qcx, 1);
  if (g.compare) { const c = agentCompare(g.compare); beforeH2(`<h2>${esc(g.compareTitle || "The agents side by side")}</h2>${c.facts}${c.ship ? `<h2>Shipping a 1 kg parcel: the cheapest line</h2>${c.ship}` : ""}`, g.compareAt || 0); }
  // Table of contents (28 Oct 2026): ids on the guide's h2s and, with 3 or more, an "On this page" list, so long guides
  // can be skimmed and Google can offer "Jump to" links.
  const ids = new Set(), toc = [];
  let text = iconNotes(iconSteps(body.replace(/<h2>([\s\S]*?)<\/h2>/g, (_, h) => { let id = slug(h.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&")) || "section"; while (ids.has(id)) id += "-2"; ids.add(id);
    const n = firstIcon(H2_IC, plain(h), "book"); toc.push([id, h.replace(/<[^>]+>/g, ""), n]); return hIc("h2", n, h, ` id="${id}"`); })));
  // Wide tables scroll inside their own box on phones instead of widening the page.
  text = text.replace(/<table>/g, '<div class="ga-tw"><table>').replace(/<\/table>/g, "</table></div>").replace(/<div class="ga-tw"><div class="ga-tw">/g, '<div class="ga-tw">').replace(/<\/table><\/div><\/div>/g, "</table></div>");
  // The guide's finds (g.finds: a marketplace or QC photos), 8 cards with buy buttons, after the second section.
  let finds = "";
  if (s !== "what-is-a-rep-spreadsheet") {
    // g.finds: a marketplace, QC photos or (25 Nov 2026) a category, so the guides without one stop showing the same 8 finds
    const w = g.finds || {}, cm = w.cat && CATS[w.cat] ? CATS[w.cat] : null;
    const l = all.filter(p => (!w.platform || p.platform === w.platform) && (!w.qc || p.qc >= w.qc) && (!cm || p.cat === w.cat) && findShown(p)), list = (l.length >= 8 ? l : vis).slice(0, 8);
    const pn = w.platform ? ({ weidian: "Weidian", taobao: "Taobao", "1688": "1688" }[w.platform] || w.platform) : "";
    // 23 Nov 2026: the link names the marketplace spreadsheet ("Open the Weidian spreadsheet"), the words that page is searched by
    const allL = w.platform && PLAT_HUBS[w.platform] ? [`Open the ${PLAT_HUBS[w.platform].name} spreadsheet: ${nf(l.length)} finds`, `/${w.platform}-spreadsheet`] : w.qc ? ["QC photos spreadsheet", "/qc-spreadsheet"]
      : cm ? [`All ${nf(l.length)} ${cm.name.toLowerCase()}`, `/category/${cm.slug}`] : [`All ${nf(vis.length)} finds`, "/spreadsheet"];
    const what = pn ? `${pn} finds` : cm ? cm.name.toLowerCase() : "finds";
    finds = `<section class="ga-finds" aria-labelledby="ga-finds-h"><div class="ga-sh"><h2 id="ga-finds-h">${w.qc ? "Popular finds with QC photos" : pn || cm ? `Popular ${esc(what)}` : "Popular finds right now"}</h2><a href="${allL[1]}">${esc(allL[0])}${ic("arrow-right", "sm")}</a></div>` +
      `<p>The most viewed ${esc(what)} on the spreadsheet${w.qc ? " that have buyer QC photos" : ""}. Tap Buy to open one in MyCNBox, or open a find for every agent${w.qc ? "" : " and its QC photos"}.</p>${grid(list)}</section>`;
    // before the third section, or the first section after the agents' side-by-side tables (g.compare)
    const h2s = [...text.matchAll(/<h2 id=/g)].map(m => m.index), at = g.compare ? (g.compareAt || 0) + 3 : 2;
    text = h2s.length > at ? text.slice(0, h2s[at]) + finds + text.slice(h2s[at]) : text + finds;
  }
  const words = plain(g.body).split(/\s+/).filter(Boolean).length + (g.faq ? plain(g.faq.flat().join(" ")).split(/\s+/).length : 0);
  const mins = Math.max(2, Math.round(words / 230));
  const upd = g.updated && ISO_DAY.test(g.updated) ? dayLong(g.updated) : g.updated;
  const updTxt = upd ? (ISO_DAY.test(g.updated) ? `${ic("clock", "sm")}<time datetime="${esc(g.updated)}">Updated ${esc(upd)}</time>` : `${ic("clock", "sm")}Updated ${esc(upd)}`) : "";
  const how = s !== "how-we-check" && own(GUIDES, "how-we-check");
  const next = GUIDE_NEXT[s] || GUIDE_NEXT_DEFAULT;
  const facts = [["sheet", `${FINDS_PLUS} finds`], ["camera", `${QC_PLUS} with QC photos`], ...(LINKS_CHECKED ? [["refresh", "Links checked weekly"]] : [])];
  const hero = `<header class="ga-hero"><span class="eyebrow pill">Guide${updTxt ? ` · ${updTxt}` : ""}</span><h1>${esc(g.h1)}</h1>${leadM ? `<p class="lead">${leadM[1]}</p>` : ""}` +
    `<p class="ga-by">By Puro Classico<span aria-hidden="true"> · </span>${mins} min read${how ? `<span aria-hidden="true"> · </span><a href="/guides/how-we-check">${ic("shield", "sm")}How we check</a>` : ""}</p>` +
    `<div class="ga-cta"><a class="btn primary lg" href="/spreadsheet">Open the spreadsheet${ic("arrow-right", "sm")}</a><a class="btn lg" href="${next[1]}">${ic(next[2], "sm")}${esc(next[0])}</a></div>` +
    `<ul class="ga-facts">${facts.map(([n, t]) => `<li>${ic(n, "sm")}${esc(t)}</li>`).join("")}</ul></header>`;
  const tocList = toc.map(([id, h, n]) => `<li><a href="#${id}">${ic(n, "sm")}${h}</a></li>`).join("");
  const side = `<aside class="ga-side" aria-label="Guide">${toc.length >= 3 ? `<nav class="toc ga-toc" aria-label="On this page"><span class="eyebrow">${ic("list", "sm")}On this page</span><ol>${tocList}</ol></nav>` : ""}` +
    `<div class="ga-card"><span class="ga-card-k">The spreadsheet</span><b>${FINDS_PLUS} finds</b><span>From Weidian, Taobao and 1688, ${QC_PLUS} with buyer QC photos. Free to browse.</span><a class="btn primary" href="/spreadsheet">Open the spreadsheet${ic("arrow-right", "sm")}</a></div></aside>`;
  const tocM = toc.length >= 3 ? `<details class="ga-toc-m"><summary>${ic("list", "sm")}On this page<span>${toc.length} sections</span>${ic("chevron-down", "sm")}</summary><nav class="toc" aria-label="On this page"><ol>${tocList}</ol></nav></details>` : "";
  const howBox = `<aside class="ga-how">${icTile("shield")}<div><b>How we check this guide</b><p>${upd ? `Revised ${esc(upd)}. ` : ""}Finds, prices and counts come from our catalogue (updated ${dayLong(BUILT)})${LINKS_CHECKED ? `, and every Weidian link is checked weekly (last on ${dayLong(LINKS_CHECKED)})` : ""}. Agent facts come from the agents' own pages, dated where we use them. Buy buttons are affiliate links, at no extra cost to you.${how ? ` <a href="/guides/how-we-check">How we check</a>` : ""}</p></div></aside>`;
  const end = `<section class="ga-end" aria-labelledby="ga-end-h"><h2 id="ga-end-h">Find it on the spreadsheet</h2><p>${FINDS_PLUS} finds from Weidian, Taobao and 1688 in one searchable spreadsheet, ${QC_PLUS} with buyer QC photos, each with one-tap buy links for MyCNBox, KakoBuy and every other agent. Free to browse.</p>` +
    `<div class="ga-cta"><a class="btn primary lg" href="/spreadsheet">Open the spreadsheet${ic("arrow-right", "sm")}</a><a class="btn lg" href="${next[1]}">${ic(next[2], "sm")}${esc(next[0])}</a></div></section>`;
  // Related guides: the others in this guide's group (GUIDE_GROUPS), then the most searched ones (FOOTER_GUIDES), 3 in all.
  const grp = (GUIDE_GROUPS.find(x => x[2].includes(path)) || [, , []])[2];
  const rel = [...new Set(grp.concat(FOOTER_GUIDES))].filter(u => u !== path).slice(0, 3);
  const relCard = u => { const k = u.replace(/^\/guides\//, ""), gg = u.startsWith("/guides/") && own(GUIDES, k) ? GUIDES[k] : null, t = (GUIDE_LINKS.find(x => x[1] === u) || [u])[0];
    const d = gg ? gg.desc : u === "/how-to-order" ? "A 56-second walkthrough: find an item, check out, check QC photos, submit packing and track your parcel." : "";
    return `<a href="${u}">${icTile(guideIcon(u))}<span class="gl-t"><b>${esc(gg ? gg.h1 : t)}</b>${d ? `<span class="gl-d">${esc(d)}</span>` : ""}</span></a>`; };
  const moreHtml = `<section class="ga-more" aria-labelledby="ga-more-h">${hIc("h2", "book", "Keep reading", ' id="ga-more-h"')}<div class="gl">${rel.map(relCard).join("")}</div>` +
    `<div class="chips">${GUIDE_LINKS.filter(([, u]) => u !== path && !rel.includes(u)).map(([t, u]) => `<a href="${u}">${ic(guideIcon(u), "sm")}${esc(t)}</a>`).join("")}<a href="/guides">${ic("arrow-right", "sm")}All guides</a></div></section>`;
  const bar = `<div class="buybar ga-bar" aria-hidden="true"><div class="bb-price">${FINDS_PLUS} finds<small>Free to browse</small></div><a class="bb-buy" href="/spreadsheet" tabindex="-1">Open the spreadsheet</a></div>`;
  // The bar shows while neither the hero button nor the closing panel is on screen (and not past the panel); the side
  // column's "On this page" marks the last heading above the top fifth of the screen. Both only with IntersectionObserver.
  const js = `<script>(function(){var d=document,b=d.querySelector(".ga-bar"),h=d.querySelector(".ga-hero .ga-cta"),e=d.querySelector(".ga-end");if(!b||!h||!window.IntersectionObserver)return;d.body.classList.add("has-buybar");var hv=1,ev=0,l=b.querySelector("a");` +
    `function s(){var on=!hv&&!ev;b.classList.toggle("on",on);b.setAttribute("aria-hidden",on?"false":"true");l.tabIndex=on?0:-1}` +
    `new IntersectionObserver(function(x){var r=x[0];hv=r.isIntersecting||r.boundingClientRect.top>0?1:0;s()}).observe(h);` +
    `if(e)new IntersectionObserver(function(x){var r=x[0];ev=r.isIntersecting||r.boundingClientRect.bottom<0?1:0;s()}).observe(e)})();` +
    `(function(){var d=document,a=[].slice.call(d.querySelectorAll(".ga-toc a"));if(!a.length||!window.requestAnimationFrame)return;var hs=a.map(function(x){return d.getElementById(x.getAttribute("href").slice(1))}),c=-1,t=0;` +
    `function u(){t=0;var y=innerHeight*.2,i=-1;for(var k=0;k<hs.length;k++){if(hs[k]&&hs[k].getBoundingClientRect().top<=y)i=k}if(i!==c){if(c>=0)a[c].removeAttribute("aria-current");if(i>=0)a[i].setAttribute("aria-current","true");c=i}}` +
    `addEventListener("scroll",function(){if(!t)t=requestAnimationFrame(u)},{passive:true});u()})();</script>`;
  const article = `<article class="ga">${hero}${side}<div class="prose ga-main">${tocM}${text}${g.faq ? faqHtml(g.faq) : ""}${howBox}${end}</div></article>`;
  const pageBody = `${bc.html}${article}${moreHtml}${bar}${js}`;
  const art = { "@context": "https://schema.org", "@type": "Article", headline: g.h1, description: g.desc, dateModified: g.updated || undefined, url: SITE + path,
    mainEntityOfPage: SITE + path, image: SITE + "/og.png", inLanguage: "en",
    author: { "@type": "Organization", name: "Puro Classico", url: SITE + "/" }, publisher: { "@type": "Organization", name: "Puro Classico", logo: { "@type": "ImageObject", url: SITE + "/logo-mark.png" } }, publishingPrinciples: own(GUIDES, "how-we-check") ? SITE + "/guides/how-we-check" : undefined };
  const ld = [bc.data, art]; if (g.faq) ld.push(faqLd(g.faq));
  return page({ title: fitTitle((g.title.length > 60 && GUIDE_FIT[s] ? GUIDE_FIT[s] : g.title) + " · Puro Classico"), desc: g.desc, path, body: pageBody, jsonld: ld, ogType: "article" });
}

// ------------------------------------------------------------------ sitemaps
// <lastmod> (9 Nov 2026), only from dates the page really shows or is built from, never "today":
//   - a guide: its own `updated` (content*.js); the rep spreadsheet guide also prints catalogue counts and the link check.
//     The guides hub: the latest guide date. A guide without `updated` gets none.
//   - catalogue pages (home, hubs, brand, category, best, agent and marketplace spreadsheets): the later of the catalogue
//     build (BUILT) and the weekly link check (LINKS_CHECKED), the two dates their lists and text come from.
//   - tools, terms, privacy and the how-to-order video page: none (no date is stored for them).
//   - a find: the later of the day its QC photos were stored (QC_BANKED) and, for Weidian finds, the link check, whose
//     result and date the page prints. A Taobao or 1688 find without stored QC photos gets none.
const xml = body => new Response(`<?xml version="1.0" encoding="UTF-8"?>\n${body}`, { headers: { "content-type": "application/xml; charset=utf-8", "cache-control": "public, max-age=3600" } });
export function sitemapIndex() {
  return xml(`<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>${SITE}/sitemap-pages.xml</loc></sitemap>
<sitemap><loc>${SITE}/sitemap-products.xml</loc></sitemap>
</sitemapindex>`);
}
// The finds a sitemap URL lists (its lastmod is the newest change among them), or null when unknown.
const _ld = new WeakMap();
function listDay(l) {
  if (_ld.has(l)) return _ld.get(l);
  let d = null; for (const p of l) { const r = rowDays(p); if (r && r.changed && (!d || r.changed > d)) d = r.changed; }
  _ld.set(l, d); return d;
}
function listFor(u) {
  const { byBrand, byCat, slugBrand } = idx(); let m;
  const base = u.replace(/\/\d+$/, "");
  if (base === "/new") return newest(NEW_MAX);
  if (["/", "/spreadsheet", "/brands", "/best", "/cnfans-spreadsheet"].includes(base) || (m = base.match(/^\/([a-z0-9]+)-spreadsheet$/)) && AGENT_INTRO[m[1]]) return P;
  if ((m = base.match(/^\/brand\/([a-z0-9-]+)$/))) return slugBrand.has(m[1]) ? brandFacts(slugBrand.get(m[1])).list : null;
  if ((m = base.match(/^\/category\/([a-z0-9-]+)$/))) return own(CAT_BY_SLUG, m[1]) ? (byCat.get(CAT_BY_SLUG[m[1]]) || []).filter(findShown) : null;
  if ((m = base.match(/^\/best\/([a-z0-9-]+)$/))) { const x = models().find(y => y.slug === m[1]); return x ? modelList(x) : null; }
  if ((m = base.match(/^\/(weidian|taobao|1688)-spreadsheet$/))) return platFacts(m[1]).list;
  if (base === "/old-money") { const set = new Set(OLD_MONEY.brands); return P.filter(p => set.has(p.brand)); }
  const spec = hubSpec(base); return spec ? hubList(spec).list : null;
}
export function sitemapPages() {
  const { brandSlug, byBrand, byCat } = idx();
  // Pages 2+ of the brand and category hubs (21 Oct 2026): real lists that were linked from nowhere. Agent and agent x brand
  // hubs are left out: their pages 2+ repeat the same finds with other buy buttons.
  const more = (base, n) => Array.from({ length: Math.max(0, Math.ceil(n / PER_PAGE) - 1) }, (_, i) => `${base}/${i + 2}`);
  const platN = k => P.filter(p => p.platform === k && findShown(p)).length;   // as renderPlat counts its pages (23 Nov 2026)
  const urls = ["/", "/spreadsheet", "/new", ...more("/new", NEW_MAX), "/how-to-order", "/brands", "/guides", "/old-money", "/stockholm-spreadsheet", "/grisch-spreadsheet", ...Object.keys(AGENT_INTRO).map(k => `/${k}-spreadsheet`), "/cnfans-spreadsheet", "/qc-spreadsheet",
    ...PLAT_KEYS.map(k => `/${k}-spreadsheet`), ...PLAT_KEYS.flatMap(k => more(`/${k}-spreadsheet`, platN(k))),
    ...AGENT_BRAND_AGENTS.flatMap(k => agentBrands().map(b => `/${k}-spreadsheet/${brandSlug.get(b)}`)).filter(u => !AGENT_BRAND_CANON.has(u)), ...AGENT_BRAND_AGENTS.flatMap(k => Object.keys(AGENT_STYLES).map(x => `/${k}-spreadsheet/${x}`)),
    ...Object.values(CATS).map(c => "/category/" + c.slug), ...[...brandSlug.values()].map(s => "/brand/" + s),
    ...[...brandSlug].flatMap(([b, s]) => more("/brand/" + s, brandFacts(b).n)),   // visible finds (25 Nov 2026), as renderBrand pages them
    ...Object.entries(CATS).flatMap(([c, m]) => more("/category/" + m.slug, (byCat.get(c) || []).filter(findShown).length)),
    ...Object.keys(GUIDES).map(s => "/guides/" + s), "/best", ...models().map(m => "/best/" + m.slug), "/tools", ...Object.keys(TOOLS).map(s => "/tools/" + s), "/about", "/terms", "/privacy"];
  // lastmod (12 Nov 2026, SEO check): 899 of 925 URLs said "today", which teaches Google to ignore the field. A list page now
  // gives the last day a find on its list was added or changed (rowdays.js); guides their own `updated` day; pages whose
  // change day is not known (tools, terms, how-to-order, a URL listFor() does not know) give none.
  const lastmod = u => { const m = u.match(/^\/guides\/([a-z0-9-]+)$/);
    if (m) return own(GUIDES, m[1]) ? (m[1] === "what-is-a-rep-spreadsheet" ? latestDay(GUIDES[m[1]].updated, listDay(P)) : latestDay(GUIDES[m[1]].updated)) : null;
    if (u === "/guides") return latestDay(...Object.values(GUIDES).map(g => g.updated));
    if (/^\/(tools|terms|privacy|how-to-order)(\/|$)/.test(u)) return null;
    const l = listFor(u); return l ? listDay(l) : null; };
  return xml(`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.map(u => { const d = lastmod(u); return `<url><loc>${SITE}${u}</loc>${d ? `<lastmod>${d}</lastmod>` : ""}</url>`; }).join("\n")}\n</urlset>`);
}
export function sitemapProducts(skip) {   // skip: ids removed after reports (their pages are noindex)
  const rows = P.filter(p => indexable(p) && !(skip && skip.has(String(p.id)))).map(p => {
    const src = imgSrc(p);
    // The day the find's row last changed (rowdays.js) or its QC photos were stored; the link check day only when that
    // check changed the page (the listing is gone or sold out). No known day: no lastmod.
    const rd = rowDays(p);
    const d = latestDay(rd && rd.changed, QC_BANKED[p.id], goneOf(p) ? LINKS_CHECKED : null);
    return `<url><loc>${SITE}${productUrl(p)}</loc>${d ? `<lastmod>${d}</lastmod>` : ""}${src ? `<image:image><image:loc>${esc(src)}</image:loc></image:image>` : ""}</url>`;
  });
  return xml(`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n${rows.join("\n")}\n</urlset>`);
}

// ------------------------------------------------------------------ hub pages as the catalogue app
// /mycnbox-spreadsheet, /kakobuy-spreadsheet/ralph-lauren, /brand/x and /category/x (page 1) are served as the homepage app
// with the filter already applied (functions/_middleware.js rewrites index.html with this spec). Little text on purpose:
// a short heading, then the spreadsheet itself, then a compact FAQ and links. Pages 2+ stay server-rendered lists.
// Style spreadsheets (19 Oct 2026): Google shows no real website for "stockholm spreadsheet" or "grisch spreadsheet", only
// Reddit and TikTok. Each is the spreadsheet app limited to the brands that define that look ("old money spreadsheet" is
// /old-money, so it gets no page here and the two never compete).
// CNFans has shown a maintenance page instead of its shop since 8 Oct 2026 (checked by hand on the date below).
// scripts/health_check.py warns when cnfans.com changes: then update this date and the /cnfans-spreadsheet copy, or remove it.
// 23 Nov 2026: the daily site check (scripts/health_check.py) found the maintenance page until 16 Nov 2026, and since
// 18 Nov 2026 cnfans.com has not loaded at all. That check now warns when the site loads again: then update this and the copy.
export const CNFANS = { maintenance: "8 Oct 2026", maintenanceTo: "16 Nov 2026", down: "18 Nov 2026", checked: "23 Nov 2026" };
const CNFANS_STATUS = `cnfans.com showed a maintenance page in our daily checks from ${CNFANS.maintenance} to ${CNFANS.maintenanceTo}, and since ${CNFANS.down} it has not loaded at all (last checked ${CNFANS.checked})`;
const CNFANS_FAQ = ["Does this spreadsheet work with CNFans?", `No. ${CNFANS_STATUS}. Every find here opens in MyCNBox, KakoBuy, Oopbuy, LoveGoBuy or Sugargoo, and our link converter turns old CNFans links into links for those agents.`];
const STYLE_HUBS = {
  stockholm: { name: "Stockholm style", h: "Stockholm Style Spreadsheet",
    brands: ["Ralph Lauren", "Moncler", "Stone Island", "Lacoste", "Acne Studios", "Ami", "Burberry", "Golden Goose", "Loro Piana", "Arc'teryx",
             "CP Company", "Canada Goose", "Maison Margiela", "Tommy Hilfiger", "Fred Perry"],
    sub: n => `${n} Stockholm style finds: quarter-zips, cable knits, gilets, clean sneakers.`,
    title: n => `Stockholm Style Reps Spreadsheet 2026: ${n} Finds | Puro Classico`,
    desc: n => `The Stockholm style reps spreadsheet: ${n} finds from Ralph Lauren, Moncler, Stone Island, Lacoste, Acne Studios and more, with one-tap agent links.`,
    faq: [["What is Stockholm style?", "The clean Scandinavian take on old money: Ralph Lauren cable knits and quarter-zips, Moncler gilets, Stone Island, Acne Studios basics, straight jeans and white leather sneakers. Neutral colours, small logos, good fit."],
          ["What should I buy first?", "A cable-knit or half-zip in navy, grey or cream, a quilted gilet and a pair of clean sneakers cover most outfits. Knitwear is light, so it is cheap to ship."],
          ["Do these finds fit like the real thing?", "Rep knitwear often runs a size small. Compare the listing's measurements with a sweater you own, and check the QC photos before you ship."],
          CNFANS_FAQ,
          ["Is the spreadsheet free?", "Yes. You pay your agent for the item and shipping only. Our links to agents are affiliate links: we may earn a commission if you order, at no extra cost to you."]] },
  grisch: { name: "Grisch", h: "Grisch Spreadsheet",
    brands: ["Ralph Lauren", "Moncler", "Lacoste", "Burberry", "Loro Piana", "Brunello Cucinelli", "Golden Goose", "Stone Island", "Jacob Cohen",
             "Hermes", "Rolex", "Cartier", "Tom Ford", "Zegna", "Barbour", "Canada Goose"],
    sub: n => `${n} grisch finds: Ralph, Moncler, Loro Piana, Lacoste and the rest of the look.`,
    title: n => `Grisch Spreadsheet 2026: ${n} Old Money Finds | Puro Classico`,
    desc: n => `The grisch spreadsheet: ${n} old money finds from Ralph Lauren, Moncler, Loro Piana, Lacoste, Burberry and more, with one-tap agent links.`,
    faq: [["What does grisch mean?", "Grisch is Scandinavian slang for the preppy old money look: Ralph Lauren polos and knits, Moncler, Loro Piana loafers, Lacoste, a good watch and Golden Goose or clean leather sneakers."],
          ["What are the hardest grisch pieces?", "Ralph Lauren cable knits and quarter-zips, Moncler gilets and puffers, Loro Piana suede loafers, Burberry check scarves and Golden Goose sneakers are the core of the look."],
          ["How do I order grisch reps?", "Open a find, tap the buy button for your agent (MyCNBox, KakoBuy, Oopbuy, LoveGoBuy or Sugargoo), pick your size and pay. Check the QC photos at the warehouse before you ship."],
          CNFANS_FAQ,
          ["Is the spreadsheet free?", "Yes. You pay your agent for the item and shipping only. Our links to agents are affiliate links: we may earn a commission if you order, at no extra cost to you."]] },
};
// The MyCNBox guides, linked from every agent spreadsheet page (24 Nov 2026, SEO pass: "mycnbox" had 1,260 impressions and
// 6 clicks in 6 months, and the guide Google shows for it, /guides/mycnbox-review, had few links from the spreadsheets).
const MCB_GUIDES = ["MyCNBox guide", [["MyCNBox review: is it legit?", "/guides/mycnbox-review"], ["MyCNBox coupons: up to $500", "/guides/mycnbox-coupon-code"]]];
// The guides for an agent spreadsheet's link lists (25 Nov 2026, SEO pass): its coupon guide, the comparisons, the QC guide.
const agentGuides = key => { const n = AGENTS[key].name;
  return key === "mycnbox" ? ["MyCNBox guides", MCB_GUIDES[1].concat([["KakoBuy vs MyCNBox", "/guides/kakobuy-vs-mycnbox"], ["Best shopping agent compared", "/guides/best-shopping-agent"]])]
    : [`${n} guides`, [...(COUPON_GUIDE[key] ? [[`${n} coupon code`, COUPON_GUIDE[key][1]]] : []), ...(key === "kakobuy" ? [["KakoBuy vs MyCNBox", "/guides/kakobuy-vs-mycnbox"]] : []),
      ["Best shopping agent compared", "/guides/best-shopping-agent"], ["How to read QC photos", "/guides/how-to-qc"], ["All agent sign-up bonuses", "/guides/agent-coupons"]]]; };
// More questions for the agent spreadsheets (25 Nov 2026, SEO pass). The pages that rank above ours for "kakobuy
// spreadsheet" and "sugargoo spreadsheet" answer what the spreadsheet is, whether it is free and official, how often it
// changes and what shipping costs; the agent's own FAQ (content.js) is about the agent. Each answer is worked out from
// the catalogue, the link check or shipping_lines.js, and a question the agent's FAQ already asks is left out.
function agentFaqMore(key, name, faq, N, qcN) {
  const has = re => faq.some(([q]) => re.test(q));
  const since = new Date(Date.now() - 7 * 864e5).toISOString().slice(0, 10);
  const added = idx().all.filter(p => { if (!findShown(p)) return false; const r = rowDays(p); return r && r.added && r.added >= since; }).length;
  const t = SHIP_LINES[key], to = { us: "the US", gb: "the UK", de: "Germany", se: "Sweden" };
  const cheap = t ? Object.keys(SHIP_TO).map(c => { const r = (t.rows[c] || []).slice().sort((x, y) => x[1] - y[1])[0]; return r ? `${usd(r[1])} to ${to[c]}` : ""; }).filter(Boolean) : [];
  return [
    ...(has(/^What is the .* spreadsheet\?$/i) ? [] : [[`What is the ${name} spreadsheet?`, `A free, searchable list of ${N} Weidian, Taobao and 1688 finds in which every Buy button opens the item on ${name}. Each find shows its listed price, and our catalogue marks ${nf(qcN)} of them as having buyer QC photos from earlier orders.`]]),
    ...(has(/^Is (the|this|it)\b.*\bfree\?$/i) ? [] : [[`Is the ${name} spreadsheet free?`, `Yes. Browsing is free and needs no account. You pay ${name} for what you order and for shipping. Our links to ${name} are affiliate links: we may earn a commission at no extra cost to you.`]]),
    ...(has(/official/i) ? [] : [[`Is this the official ${name} spreadsheet?`, `No. Puro Classico is an independent spreadsheet and is not affiliated with ${name}. Ordering, payment, QC photos and shipping all happen on ${name}.`]]),
    ...(has(/updated/i) ? [] : [[`How often is the ${name} spreadsheet updated?`, `Finds are added as we find them: ${nf(added)} in the last 7 days.${LINKS_CHECKED ? ` Every Weidian link is checked each week (last on ${dayLong(LINKS_CHECKED)}): deleted listings are hidden and sold-out ones are marked.` : ""} The order follows what visitors viewed in the last 30 days.`]]),
    ...(cheap.length && !has(/shipping cost|how much .*shipping/i) ? [[`How much is ${name} shipping?`, `For a 1 kg parcel, ${name}'s own estimator quoted ${andList(cheap)} on its cheapest lines on ${SHIP_READ}, before coupons. Prices change often, so check ${name}'s estimator before you send a parcel.`]] : []),
  ];
}
// Agent x style pages (22 Oct 2026): Google suggests "kakobuy spreadsheet grisch", "oopbuy spreadsheet grisch", "kakobuy
// spreadsheet old money", "old money spreadsheet sugargoo", "kakobuy spreadsheet shoes". Each is the style's finds with
// the buy button locked to that agent. Only the agents with agent x brand pages (AGENT_BRAND_AGENTS).
const AGENT_STYLES = {
  grisch: { name: "Grisch", brands: () => STYLE_HUBS.grisch.brands, parent: ["Grisch spreadsheet", "/grisch-spreadsheet"],
    first: "Ralph Lauren cable knits and quarter-zips, a Moncler gilet, Loro Piana style suede loafers and Golden Goose or clean leather sneakers are the core of the look." },
  "old-money": { name: "Old Money", brands: () => OLD_MONEY.brands, parent: ["Old money spreadsheet", "/old-money"],
    first: "A cable knit or quarter-zip in navy, grey or cream, a quilted gilet, straight trousers and clean leather sneakers or loafers cover most old money outfits." },
  shoes: { name: "Shoes", cat: "Shoes", parent: ["Sneakers and shoes", "/category/sneakers"],
    first: "Compare the size chart on the listing with a pair you own, in centimetres. Many rep sneakers fit a little small, so ask the seller through your agent if you are between sizes." },
  // 23 Oct 2026: Google suggests "kakobuy spreadsheet qc / with qc photos" and "kakobuy / oopbuy spreadsheet budget / cheap".
  // QC: finds the catalogue marks as having buyer QC photos. Budget: a listed-price filter (seller prices, not a claim).
  qc: { name: "QC photos", qc: 1, parent: ["QC checker", "/tools/qc-checker"],
    h: a => `${a} Spreadsheet with QC Photos`, title: (a, n) => `${a} Spreadsheet with QC Photos 2026: ${n} Finds | Puro Classico`,
    sub: (a, n) => `${n} finds marked as having buyer QC photos from earlier orders, each with a one-tap ${a} link.`,
    desc: (a, n) => `The ${a} spreadsheet with QC photos: ${n} rep finds marked as having buyer QC photos, with prices and one-tap ${a} buy links.`,
    faq: (a, n, n2) => [[`How do I order from the ${a} spreadsheet with QC photos?`, `Open a find, tap Buy via ${a}, pick your size and pay for the item plus delivery to the ${a} warehouse. ${a} photographs your exact item there, then you ship your parcel.`],
      ["Will I see the QC photos?", `Our catalogue marks these ${n} finds as having buyer QC photos from earlier orders and stores the photo count for ${n2} of them. Open a find and tap QC to load them. If they can't be loaded right now, ${a} still photographs your exact item at the warehouse before it ships.`]] },
  budget: { name: "Budget", pmax: 140, parent: ["Shipping calculator", "/tools/shipping-calculator"],
    h: a => `${a} Budget Spreadsheet`, title: (a, n) => `${a} Budget Spreadsheet 2026: ${n} Finds Under $20 | Puro Classico`,
    sub: (a, n) => `${n} finds listed at ¥140 or less (about $20), each with a one-tap ${a} link.`,
    desc: (a, n) => `The ${a} budget spreadsheet: ${n} rep finds listed at ¥140 or less (about $20), with QC photos where we have them and one-tap ${a} links.`,
    faq: a => [[`How do I order from the ${a} budget spreadsheet?`, `Open a find, tap Buy via ${a}, pick your size and pay for the item plus delivery to the ${a} warehouse. Check the QC photos there, then ship your parcel.`],
      ["Are these prices final?", `No. They are the sellers' listed prices from the last catalogue update. ${a} adds shipping, which is charged per parcel by weight, so on cheap items it can cost more than the item. Estimate it with our shipping calculator before you order.`]] },
};
const AGENT_STYLE_RE = new RegExp(`^/(${AGENT_BRAND_AGENTS.join("|")})-spreadsheet/(${Object.keys(AGENT_STYLES).join("|")})$`);
const inBudget = (p, max) => !isPH(p.cny) && p.cny <= max;

// ------------------------------------------------------------------ marketplace spreadsheets (9 Nov 2026)
// /weidian-spreadsheet, /taobao-spreadsheet and /1688-spreadsheet: the finds of one marketplace, most viewed first. An SEO
// audit found no page of ours in Google's top 20 for "weidian spreadsheet", while the Weidian guide had 2,086 impressions in
// 28 days, and about nine in ten finds are Weidian listings. Page 1 is the app (preset plat: index.html keeps only that
// marketplace's finds), pages 2+ are server-rendered lists (renderPlat). Every number is counted from the catalogue when
// the page renders. Facts only: no fees, delivery times or claims about agents beyond what the guides already say, the
// agents are never ranked, and MyCNBox stays the default buy button.
const PLAT_KEYS = ["weidian", "taobao", "1688"];
// Kept per catalogue index and hidden set (23 Nov 2026): the sitemap asks for it once per page of each marketplace list.
const _pf = new Map(); let _pfIdx = null, _pfVer = -1;
function platFacts(key) {
  if (_pfIdx !== idx() || _pfVer !== hiddenVer()) { _pf.clear(); _pfIdx = idx(); _pfVer = hiddenVer(); }
  if (!_pf.has(key)) _pf.set(key, platFactsNew(key));
  return _pf.get(key);
}
function platFactsNew(key) {
  const { brandSlug } = idx(), all = idx().all.filter(findShown);   // 23 Nov 2026: visible finds only, as the app shows them
  const list = all.filter(p => p.platform === key), n = list.length;
  const priced = list.map(p => p.cny).filter(x => !isPH(x)).sort((a, b) => a - b);
  const count = (get, ok) => { const m = new Map(); for (const p of list) { const k = get(p); if (ok(k)) m.set(k, (m.get(k) || 0) + 1); } return [...m].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]))); };
  return { key, list, n, total: all.length, pct: all.length ? Math.round(n / all.length * 100) : 0, q1: list.filter(p => p.qc >= 1).length,
    med: priced.length ? money(priced[Math.floor((priced.length - 1) / 2)]) : "",
    brands: count(p => p.brand, b => b && brandSlug.has(b)), cats: count(p => p.cat, c => CATS[c] && c !== "Toys"),
    idLen: count(p => String(p.itemId || p.id).length, () => true)[0] || [0, 0],
    top: list.find(p => !gone(p)) || list[0] || { id: "" } };
}
const STEPS_OL = '<ol style="margin:10px 0 0;padding-left:20px;color:var(--muted);font-size:14.5px;line-height:1.6">';
const agentLinks = () => andList(Object.keys(AGENT_INTRO).map(k => `<a href="/${k}-spreadsheet">${esc(AGENTS[k].name)}</a>`));
const platHowTo = (name, pick) => `${STEPS_OL}
<li><strong>Pick your agent.</strong> The Buy button on every find opens it in MyCNBox. The ${agentLinks()} spreadsheets open the same finds in that agent instead, and each find's own page has a buy button for all five.</li>
<li><strong>Open the find and tap Buy.</strong> The ${name} listing opens inside the agent, which translates the options. ${pick}</li>
<li><strong>Pay the agent.</strong> You pay for the item and the seller's delivery to the agent's warehouse in China. International shipping is paid later.</li>
<li><strong>Check your QC photos.</strong> The agent photographs your item when it arrives. If something is wrong, you can usually ask for a return or exchange before it ships; fees and time limits depend on the agent and the seller.</li>
<li><strong>Ship your parcel.</strong> Combine your items into one parcel, pick a shipping line and pay the international shipping.</li></ol>
<p>Prefer video? Watch <a href="/how-to-order">how to order</a>. Not sure which agent to use? Read <a href="/guides/best-shopping-agent">how to choose a shopping agent</a>.</p>`;
const platLinkTools = name => `The <a href="/tools/link-converter">link converter</a> turns a full ${name} link, or an agent link, into a buy link for every agent, and the <a href="/tools/qc-checker">QC photo finder</a> looks up buyer QC photos for it.`;
const platQc = (f, name) => `<p>QC photos are real photos of your own item, taken by your agent when it reaches the warehouse in China, before anything ships abroad. Our catalogue marks ${nf(f.q1)} of the ${nf(f.n)} ${name} finds as having buyer QC photos from earlier orders: open a find and tap QC to see them before you buy, or browse only those finds on the <a href="/qc-spreadsheet">QC finder spreadsheet</a>.</p>
<p>When your own photos arrive, compare the logo's shape, size and placement with retail photos, look for straight, even stitching, check the colour against the listing and make sure the size tag matches your order. Our guide on <a href="/guides/how-to-qc">how to read QC photos</a> goes through each check.</p>`;
const platSize = name => `<p>Many ${name} sellers use Asian sizing, which often runs about one size smaller than EU or US sizing, but not always. Go by centimetres, not the size letter: lay a garment you own that fits flat, measure it and compare it with the seller's size chart, which your agent translates. If the chart is unclear, ask the warehouse to measure the item in the QC photos. See the <a href="/guides/sizing">rep sizing guide</a> or try the <a href="/tools/size-estimator">size estimator</a>.</p>`;
const platShip = () => `<p>You pay for delivery twice. First the seller's delivery to your agent's warehouse in China, paid together with the item and often free or a few dollars. Then international shipping, paid when you send your parcel and charged on its weight and box size. Combining several finds into one parcel and leaving out shoe boxes you don't need keeps that cost down. Get a rough figure with the <a href="/tools/shipping-calculator">shipping calculator</a>, compare lines in <a href="/guides/shipping-lines">shipping lines explained</a>, and follow your country's import rules.</p>`;
function platNumbers(f, name) {
  const { brandSlug } = idx();
  return `<p>${nf(f.n)} ${name} finds, ${f.pct}% of the ${nf(f.total)} finds on the spreadsheet, ${nf(f.q1)} of them marked as having buyer QC photos from earlier orders.${f.med ? ` Half are listed at ${f.med} or less: the sellers' listed prices from the catalogue update on ${BUILT_DAY}, before shipping.` : ""}</p>` +
    (f.cats.length ? `<p>By category: ${andList(f.cats.slice(0, 4).map(([c, k]) => `<a href="/category/${CATS[c].slug}">${esc(CATS[c].name.toLowerCase())}</a> (${nf(k)})`))}.</p>` : "") +
    (f.brands.length ? `<p>Brands with the most ${name} finds: ${andList(f.brands.slice(0, 8).map(([b, k]) => `<a href="/brand/${brandSlug.get(b)}">${esc(b)}</a> (${nf(k)})`))}.</p>` : "");
}
const AFFILIATE = "Our links to agents are affiliate links: we may earn a commission if you order, at no extra cost to you.";
const PLAT_HUBS = {
  weidian: { name: "Weidian",
    desc: f => `The Weidian spreadsheet: ${nf(f.n)} rep finds from Weidian sellers, ${nf(f.q1)} marked as having buyer QC photos, with one-tap MyCNBox, KakoBuy and Oopbuy links.`,
    about: f => [
      ["What is Weidian?", `<p>Weidian (微店, "micro shop") is a Chinese shop platform, used mostly on phones, where independent sellers run their own small stores. It belongs to a different company from Taobao and 1688, which are part of Alibaba. Listings are in Chinese and most sellers only ship inside China, so buyers abroad order through a shopping agent: the agent buys the item, checks it at its warehouse and ships it on to you.</p>`],
      ["Why most rep sellers are on Weidian", `<p>Weidian is built for small independent shops run from a phone, and its item links are easy to share in chats and on social media. That suits the way many rep sellers work. On this spreadsheet ${nf(f.n)} of the ${nf(f.total)} finds (${f.pct}%) are Weidian listings; the rest are on <a href="/taobao-spreadsheet">Taobao</a> and <a href="/1688-spreadsheet">1688</a>.</p>`],
      ["What a Weidian link looks like", `<p>A Weidian listing link looks like <strong>weidian.com/item.html?itemID=${esc(f.top.itemId || f.top.id)}</strong> (the find at the top of this list). The number after itemID= is the item ID: ${nf(f.idLen[1])} of the ${nf(f.n)} Weidian IDs here are ${f.idLen[0]} digits long. Your agent needs the full link or that number.</p>
<p>Links shared from the Weidian app are often short links (youshop10.com) without the item ID. Open one in your browser first and copy the full weidian.com link it leads to. ${platLinkTools("Weidian")}</p>`],
      ["How to buy a Weidian find through any agent", platHowTo("Weidian", "Pick your size and colour.")],
      ["Reading the QC photos of a Weidian find", platQc(f, "Weidian")],
      ["Sizing on Weidian", platSize("Weidian")],
      ["Shipping your Weidian finds", platShip()],
      ["Weidian on the spreadsheet, in numbers", platNumbers(f, "Weidian") + (LINKS_CHECKED ? `<p>We check every Weidian find each week. The last check, on ${dayOf(LINKS_CHECKED)}, found ${nf(GONE_COUNTS.dead)} listings gone, which the spreadsheet hides, and ${nf(GONE_COUNTS.sold)} sold out, which their pages point out.</p>` : "")]],
    faq: f => [
      ["What is the Weidian spreadsheet?", `A list of the ${nf(f.n)} Weidian finds on Puro Classico, most viewed first, with the sellers' listed prices, buyer QC photos where our catalogue has them and a one-tap buy link for your shopping agent.`],
      ["Can I buy from Weidian without an agent?", "Rarely, if you live outside China. Most Weidian sellers only ship inside China, and sign-up and payment are built around Chinese phone numbers and payment apps. A shopping agent buys the item for you, photographs it at its warehouse and ships it abroad."],
      ["Where is the item ID in a Weidian link?", `It is the number after itemID= in a link like weidian.com/item.html?itemID=..., ${f.idLen[0]} digits long for ${nf(f.idLen[1])} of the ${nf(f.n)} finds here. A short link shared from the Weidian app has to be opened in a browser first to show the full link.`],
      ["Which agents can buy Weidian items?", `MyCNBox, KakoBuy, Oopbuy, LoveGoBuy and Sugargoo all take Weidian links. The Buy button on each find opens it in MyCNBox, and each find's page has buttons for 15 other agents. ${AFFILIATE}`],
      ["Do Weidian finds have QC photos?", `Our catalogue marks ${nf(f.q1)} of the ${nf(f.n)} Weidian finds as having buyer QC photos from earlier orders. Your agent also photographs your own item at its warehouse before it ships.`],
      LINKS_CHECKED ? ["Are the Weidian links still working?", `We check every Weidian find each week. The last check, on ${dayOf(LINKS_CHECKED)}, found ${nf(GONE_COUNTS.dead)} listings gone, which the spreadsheet hides, and ${nf(GONE_COUNTS.sold)} sold out, which their pages point out.`]
        : ["Are the prices live?", `No. They are the sellers' listed prices from the catalogue update on ${BUILT_DAY}. Check the price in your agent before you pay.`]] },
  taobao: { name: "Taobao",
    desc: f => `The Taobao spreadsheet: ${nf(f.n)} rep finds from Taobao shops, ${nf(f.q1)} marked as having buyer QC photos, with one-tap links for MyCNBox, KakoBuy, Oopbuy and more.`,
    about: f => [
      ["What is Taobao?", `<p>Taobao is China's biggest online marketplace, run by Alibaba, with millions of independent shops. The site and its listings are in Chinese, and most sellers only ship inside China, so buyers abroad use a shopping agent that buys the item, checks it at its warehouse and ships it on to them.</p>`],
      ["Taobao or Tmall?", `<p>Tmall is Taobao's branded-store side, where brands and large retailers run official stores, while Taobao itself is mostly independent shops. For you the difference is small: agents handle Tmall listings the same way, so a Tmall link opens in your agent just like a Taobao one.</p>`],
      ["What a Taobao link looks like", `<p>A Taobao listing link looks like <strong>item.taobao.com/item.htm?id=${esc(f.top.itemId || f.top.id)}</strong> (the find at the top of this list), and a Tmall one like <strong>detail.tmall.com/item.htm?id=</strong> followed by the item ID. The number after id= is the item ID: ${nf(f.idLen[1])} of the ${nf(f.n)} Taobao IDs here are ${f.idLen[0]} digits long, a little longer than a Weidian ID.</p>
<p>Links shared from the Taobao app are often short links (m.tb.cn) without the item ID. Open one in your browser first and copy the full link it leads to. ${platLinkTools("Taobao")}</p>`],
      ["Taobao, Weidian or 1688?", (() => { const w = platFacts("weidian").n, a = platFacts("1688").n;
        return `<p>Most rep sellers list on Weidian: ${nf(w)} of the ${nf(f.total)} finds here are <a href="/weidian-spreadsheet">Weidian listings</a>, against ${nf(f.n)} on Taobao and ${nf(a)} on <a href="/1688-spreadsheet">1688</a>. Taobao has the biggest range of shops, and quality varies from shop to shop, so check the shop's ratings and recent reviews inside your agent and look for buyer QC photos before you order.</p>`; })()],
      ["How to buy a Taobao find through any agent", platHowTo("Taobao", "Pick your size and colour.")],
      ["Reading the QC photos of a Taobao find", platQc(f, "Taobao")],
      ["Sizing on Taobao", platSize("Taobao")],
      ["Shipping your Taobao finds", platShip()],
      ["Taobao on the spreadsheet, in numbers", platNumbers(f, "Taobao")]],
    faq: f => [
      ["What is the Taobao spreadsheet?", `A list of the ${nf(f.n)} Taobao finds on Puro Classico, most viewed first, with the sellers' listed prices, buyer QC photos where our catalogue has them and a one-tap buy link for your shopping agent.`],
      ["Does Taobao ship internationally?", "Some items can be sent abroad through Taobao's own programme, but most sellers only ship inside China, so buyers abroad usually order through a shopping agent."],
      ["Is Tmall the same as Taobao?", "Tmall is Taobao's branded-store side, run by the same company. Agents handle Tmall and Taobao links the same way."],
      ["Where is the item ID in a Taobao link?", `It is the number after id= in a link like item.taobao.com/item.htm?id=..., ${f.idLen[0]} digits long for ${nf(f.idLen[1])} of the ${nf(f.n)} finds here. A short link shared from the Taobao app has to be opened in a browser first to show the full link.`],
      ["Do Taobao finds have QC photos?", `Our catalogue marks ${nf(f.q1)} of the ${nf(f.n)} Taobao finds as having buyer QC photos from earlier orders. Your agent also photographs your own item at its warehouse before it ships.`],
      ["Which agents can buy Taobao items?", `MyCNBox, KakoBuy, Oopbuy, LoveGoBuy and Sugargoo all take Taobao and Tmall links. The Buy button on each find opens it in MyCNBox, and each find's page has buttons for 15 other agents. ${AFFILIATE}`]] },
  "1688": { name: "1688",
    desc: f => `The 1688 spreadsheet: ${nf(f.n)} rep finds from 1688 wholesale sellers, ${nf(f.q1)} marked as having buyer QC photos, with one-tap links for MyCNBox, KakoBuy and more.`,
    about: f => [
      ["What is 1688?", `<p>1688.com is Alibaba's domestic wholesale marketplace, built for Chinese businesses that buy from factories and wholesalers. Prices are often close to factory prices, but the site is in Chinese and made for buyers inside China, so buyers abroad order through a shopping agent.</p>`],
      ["Minimum quantities and tiered prices", `<p>Some 1688 listings require several pieces per order, and prices are often tiered: cheaper per piece as the quantity goes up. Many clothing sellers allow single pieces, and your agent shows the minimum before you pay. Listing photos and titles are often plain, so buyer QC photos matter more here: our catalogue marks ${nf(f.q1)} of the ${nf(f.n)} 1688 finds as having them (the <a href="/qc-spreadsheet">QC finder spreadsheet</a> lists every find with QC photos).</p>`],
      ["What a 1688 link looks like", `<p>A 1688 listing link looks like <strong>detail.1688.com/offer/${esc(f.top.itemId || f.top.id)}.html</strong> (the find at the top of this list). The number after offer/ is the item ID: ${nf(f.idLen[1])} of the ${nf(f.n)} 1688 IDs here are ${f.idLen[0]} digits long. Links shared from the 1688 app (qr.1688.com) are short links: open one in your browser first and copy the full link. ${platLinkTools("1688")}</p>`],
      ["How to buy a 1688 find through any agent", platHowTo("1688", "Check the minimum quantity, then pick your size and colour.")],
      ["1688 on the spreadsheet, in numbers", platNumbers(f, "1688")]],
    faq: f => [
      ["What is the 1688 spreadsheet?", `A list of the ${nf(f.n)} 1688 finds on Puro Classico, most viewed first, with the sellers' listed prices, buyer QC photos where our catalogue has them and a one-tap buy link for your shopping agent.`],
      ["Can I buy a single item on 1688?", "Often yes for clothing and accessories, but some listings have a minimum order quantity. Your agent shows it before you pay."],
      ["Where is the item ID in a 1688 link?", `It is the number after offer/ in a link like detail.1688.com/offer/....html, ${f.idLen[0]} digits long for ${nf(f.idLen[1])} of the ${nf(f.n)} finds here.`],
      ["Do 1688 finds have QC photos?", `Our catalogue marks ${nf(f.q1)} of the ${nf(f.n)} 1688 finds as having buyer QC photos from earlier orders. Your agent also photographs your own item at its warehouse before it ships.`],
      ["Which agents can buy 1688 items?", `MyCNBox, KakoBuy, Oopbuy, LoveGoBuy and Sugargoo all take 1688 links. The Buy button on each find opens it in MyCNBox, and each find's page has buttons for 15 other agents. ${AFFILIATE}`]] },
};
const platOthers = key => PLAT_KEYS.filter(k => k !== key).map(k => [`${PLAT_HUBS[k].name} spreadsheet`, `/${k}-spreadsheet`]);
const PLAT_CHIPS = ["Spreadsheets by marketplace", PLAT_KEYS.map(k => [`${PLAT_HUBS[k].name} spreadsheet`, `/${k}-spreadsheet`])];
function platSpec(key) {
  const h = PLAT_HUBS[key], f = platFacts(key), N = nf(f.n), path = `/${key}-spreadsheet`, { brandSlug } = idx();
  return { path, preset: { plat: key }, h: `${h.name} Spreadsheet`,
    sub: `${N} finds from ${h.name}, most viewed first, each with a one-tap buy link for your shopping agent.`, linkCheck: key === "weidian",
    title: `${h.name} Spreadsheet 2026: ${N} Rep Finds | Puro Classico`, desc: h.desc(f),
    crumbs: [["Home", "/"], [`${h.name} spreadsheet`, path]],
    aboutTitle: `About ${h.name} finds`, about: h.about(f).concat(freshAbout(null, key)),
    chips: [[`Top brands on ${h.name}`, f.brands.slice(0, 16).map(([b, k]) => [`${b} (${nf(k)})`, `/brand/${brandSlug.get(b)}`])],
            [`Buy ${h.name} finds with your agent`, Object.keys(AGENT_INTRO).map(k => [`${AGENTS[k].name} spreadsheet`, `/${k}-spreadsheet`]).concat([["How to order", "/how-to-order"], [`How to buy from ${h.name}`, `/guides/how-to-buy-from-${key}`]])],
            ["Spreadsheets by marketplace", platOthers(key).concat([["QC photos spreadsheet", "/qc-spreadsheet"], ["All finds", "/"]])]],
    faq: h.faq(f), f };
}
// Pages 2+ of a marketplace spreadsheet (page 1 is the app, hubSpec). Same list and order as the app's first page.
export function renderPlat(key, n) {
  if (!PLAT_KEYS.includes(key)) return null;
  const s = platSpec(key), f = s.f, name = PLAT_HUBS[key].name, { brandSlug } = idx(), pr = priceRange(f.list);
  const filters = f.brands.slice(0, 16).map(([b]) => [b, `/brand/${brandSlug.get(b)}`])
    .concat(platOthers(key), [["QC photos spreadsheet", "/qc-spreadsheet"], [`How to buy from ${name}`, `/guides/how-to-buy-from-${key}`]]);
  return hub({ path: s.path, n, list: f.list, title: s.title,
    desc: n > 1 ? `Page ${n} of the ${nf(f.n)} ${name} rep finds on Puro Classico${pr ? `, with prices (${pr})` : ""}. Open any listing on MyCNBox, KakoBuy, Oopbuy or your agent.` : s.desc,
    h1: s.h, lead: s.sub, trail: s.crumbs, filters, faq: s.faq, idxFirst: true, full: name, key: `${name} Spreadsheet`, ldCount: f.n,
    shop: { links: s.chips[1][1] }, groups: s.chips, aboutTitle: `About ${name} finds` });
}

// ------------------------------------------------------------------ agent and marketplace pages: shipping lines, new finds
// (23 Nov 2026, SEO pass) Each agent spreadsheet gets that agent's own shipping lines and prices (shipping_lines.js, read
// from its estimator) or, for MyCNBox, the delivery figures it publishes; and the agent and marketplace spreadsheets say how
// many finds were added in the last 7 days, with the newest ones (opened on that agent on its own page).
const usd = x => "$" + (+x).toFixed(2);
const dayRange = (a, b, unit) => (a === b ? `${a}` : `${a} to ${b}`) + " " + unit;
function shipAbout(key, name) {
  const t = SHIP_LINES[key];
  if (t) {
    const rows = Object.entries(SHIP_TO).filter(([c]) => (t.rows[c] || []).length).map(([c, to]) => t.rows[c].map((r, i) => `<tr>${i ? "<td></td>" : `<td>${esc(to)}</td>`}<td>${esc(r[0])}</td><td>${usd(r[1])}</td><td>${dayRange(r[2], r[3], t.days)}</td></tr>`).join("")).join("");
    return [[`${name} shipping lines and prices`, `<p>What ${esc(t.src)} quoted on ${SHIP_READ} for ${esc(t.what)}: the three cheapest lines to each country and the fastest one. List prices in US dollars before coupons; a bulky parcel can cost more on lines that charge for box size.</p>` +
      `<table><tr><th>To</th><th>Line</th><th>1 kg</th><th>Delivery</th></tr>${rows}</table>` +
      `<p>Prices and lines change often, so check ${esc(name)}'s estimator before you send a parcel. For other weights, the <a href="/tools/shipping-calculator">shipping calculator</a> gives a ballpark and <a href="/guides/shipping-lines">shipping lines explained</a> says what tax-free, EMS and express lines mean.</p>`]];
  }
  if (key === "mycnbox") {
    const m = MYCNBOX_SHIP;
    return [["MyCNBox shipping: real parcels and times", `<p>MyCNBox publishes its own delivery figures on its homepage. On ${m.read} they read: ${m.avgDays} days from dispatch to delivery on average (${m.china} in China, ${m.customs} in customs, ${m.dest} in the destination country), ${usd(m.perKg)} per kg on parcels averaging ${m.avgKg} kg, ${m.inspected}% of parcels inspected by customs and ${m.delivered}% delivered.</p>` +
      `<table><tr><th>To</th><th>Line</th><th>Parcel</th><th>Per kg</th><th>Days</th></tr>${m.samples.map(([to, line, price, d, kg]) => `<tr><td>${esc(to)}</td><td>${esc(line)}</td><td>${usd(price)}</td><td>${usd(kg)}</td><td>${d}</td></tr>`).join("")}</table>` +
      `<p>These are parcels MyCNBox shows as real samples. In the week of ${m.week.from} to ${m.week.to}, its figures show sellers dispatching ${m.week.purchaseH} hours after MyCNBox paid, on average, items reaching the warehouse ${m.week.toWarehouseH} hours later, the QC check taking about ${Math.round(m.week.qcMin)} minutes and parcels packed ${m.week.packedH} hours after they were submitted.</p>` +
      `<p>MyCNBox's own shipping calculator needs an account. For a ballpark without one, try our <a href="/tools/shipping-calculator">shipping calculator</a>.</p>`]];
  }
  return [];
}
// Agents side by side (25 Nov 2026, SEO pass) for the best shopping agent and KakoBuy vs MyCNBox guides (g.compare in
// content*.js). Every cell repeats a fact from that agent's spreadsheet copy (content.js AGENT_INTRO, which names each
// source) or shipping_lines.js, with the same dates; nothing is ranked. Change them together.
const AGENT_FACTS = {
  mycnbox: { fee: "None on purchases", parcel: "Not stated", qc: "4 photos per item", store: "90 days", offer: "Coupons up to $500 (code AACPYA)", read: "10 Oct 2026" },
  kakobuy: { fee: "No handling fee", parcel: "Customs declaration, generally ¥8", qc: "Appearance, model, style and size", store: "100 days", offer: "Coupons up to $410 (code w5war)", read: "9 Nov 2026" },
  oopbuy: { fee: "None beyond item and shipping", parcel: "Customs declaration, generally ¥8", qc: "Quantity, colour and size", store: "90 days", offer: "¥3,500 coupon bundle, 15% off shipping", read: "9 Nov 2026" },
  lovegobuy: { fee: "None beyond item and shipping", parcel: "Customs declaration, generally ¥8", qc: "Colour, damage, size and model", store: "60 days", offer: "Shipping coupons up to $141", read: "9 Nov 2026" },
  sugargoo: { fee: "None beyond item and shipping", parcel: "Packing fee, ¥8", qc: "5 free photos per item", store: "100 days", offer: "¥800 in shipping coupons", read: "9 Nov 2026" },
  hipobuy: { fee: "Free agent service", parcel: "Customs declaration, generally ¥10", qc: "Generally 3 photos per item", store: "90 days", offer: "Coupon pack: 25% off, ¥100", read: "26 Nov 2026" },
};
// The agents on the best shopping agent guide, as a word for "All six agents" on each agent spreadsheet.
const CMP_WORD = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"][(GUIDES1["best-shopping-agent"].compare || []).length] || String((GUIDES1["best-shopping-agent"].compare || []).length);
function agentCompare(keys, here = "") {   // here: the page's own agent, whose name is not linked
  const ks = keys.filter(k => AGENT_FACTS[k] && AGENTS[k]);
  const head = `<tr><th></th>${ks.map(k => `<th>${k === here ? esc(AGENTS[k].name) : `<a href="/${k}-spreadsheet">${esc(AGENTS[k].name)}</a>`}</th>`).join("")}</tr>`;
  const row = (label, f) => `<tr><td>${label}</td>${ks.map(k => `<td>${esc(f(AGENT_FACTS[k]))}</td>`).join("")}</tr>`;
  const facts = `<table>${head}${row("Fee on purchases", x => x.fee)}${row("Per parcel", x => x.parcel)}${row("Warehouse check", x => x.qc)}${row("Free storage", x => x.store)}${row("New users", x => x.offer)}</table>` +
    `<p style="font-size:14px;color:var(--muted)">From each agent's help centre, home page and sign-up offer, read on ${andList(ks.map(k => `${AGENT_FACTS[k].read} (${esc(AGENTS[k].name)})`))}${ks.includes("oopbuy") ? " (Oopbuy's offer on 23 Nov 2026)" : ""}. Coupons come with minimum spends.${here ? "" : ` More on each agent: ${andList(ks.map(k => `<a href="/${k}-spreadsheet">${esc(AGENTS[k].name)} spreadsheet</a>`))}.`}</p>`;
  // Shipping: the cheapest line each agent's estimator quoted for 1 kg (shipping_lines.js); MyCNBox's estimator needs an account.
  const sk = ks.filter(k => SHIP_LINES[k]);
  const cheap = (k, c) => { const r = (SHIP_LINES[k].rows[c] || []).slice().sort((a, b) => a[1] - b[1])[0]; return r ? `${usd(r[1])}, ${dayRange(r[2], r[3], SHIP_LINES[k].days)}` : "Not quoted"; };
  const ship = sk.length ? `<table><tr><th>1 kg parcel to</th>${sk.map(k => `<th>${esc(AGENTS[k].name)}</th>`).join("")}</tr>${Object.entries(SHIP_TO).map(([c, to]) => `<tr><td>${esc(to)}</td>${sk.map(k => `<td>${cheap(k, c)}</td>`).join("")}</tr>`).join("")}</table>` +
    `<p style="font-size:14px;color:var(--muted)">The cheapest line each agent's own estimator quoted on ${SHIP_READ} for a 1 kg parcel, list prices in US dollars before coupons. ${ks.includes("mycnbox") ? `MyCNBox's estimator needs an account; its homepage showed ${usd(MYCNBOX_SHIP.perKg)} per kg on parcels averaging ${MYCNBOX_SHIP.avgKg} kg and ${MYCNBOX_SHIP.avgDays} days from dispatch to delivery (read ${MYCNBOX_SHIP.read}). ` : ""}${ks.includes("lovegobuy") ? "LoveGoBuy's site sits behind a browser check, so it is not in the table. " : ""}Prices change often: check the estimator before you send a parcel.</p>` : "";
  return { facts, ship };
}
// New finds of the last 7 days (rowdays.js: the day a row first appeared in the catalogue), counted among the finds a
// visitor can see, and the 8 newest. agent: each find also gets a buy link for that agent.
function freshAbout(agent = null, plat = null) {
  const now = Date.now(), since = new Date(now - 7 * 864e5).toISOString().slice(0, 10);
  const pool = idx().all.filter(p => findShown(p) && (!plat || p.platform === plat));
  const added = pool.filter(p => { const r = rowDays(p); return r && r.added && r.added >= since; });
  const days = [...new Set(added.map(p => rowDays(p).added))].sort().map(dayOf);
  const list = newest(8, null, null, plat).filter(findShown);
  if (!list.length) return [];
  const a = agent && AGENTS[agent], what = plat ? `${PLAT_HUBS[plat] ? PLAT_HUBS[plat].name + " " : ""}finds` : "finds";
  const lead = added.length ? `<p>${nf(added.length)} ${what} were added to the spreadsheet in the last 7 days (on ${andList(days)}). The newest:</p>` : `<p>No ${what} were added in the last 7 days. The newest:</p>`;
  return [[plat ? `New ${PLAT_HUBS[plat] ? PLAT_HUBS[plat].name : ""} finds this week` : "New finds this week", lead +
    `<ul>${list.map(p => `<li><a href="${productUrl(p)}">${p.brand && !p.title.toLowerCase().startsWith(p.brand.toLowerCase()) ? esc(p.brand) + " " : ""}${esc(p.title)}</a>, ${money(p.cny)}${a ? ` · <a href="${esc(a.build(p))}" target="_blank" rel="sponsored nofollow noopener">open on ${esc(a.name)}</a>` : ""}</li>`).join("")}</ul>` +
    `<p><a href="/new">All new finds</a></p>`]];
}

export function hubSpec(path) {
  const { all, slugBrand, byBrand, brandSlug, byCat } = idx();
  const nf = n => n.toLocaleString("en-US");
  let m;
  if ((m = path.match(/^\/(weidian|taobao|1688)-spreadsheet$/))) { const { f, ...spec } = platSpec(m[1]); return spec; }
  if ((m = path.match(/^\/(stockholm|grisch)-spreadsheet$/))) {
    const st = STYLE_HUBS[m[1]], have = st.brands.filter(b => byBrand.has(b));
    const n = nf(have.reduce((t, b) => t + byBrand.get(b).length, 0));
    const other = Object.entries(STYLE_HUBS).filter(([k]) => k !== m[1]).map(([k, v]) => [`${v.h}`, `/${k}-spreadsheet`]);
    return { path, preset: { brands: have.map(b => slug(b)) }, h: st.h, sub: st.sub(n), title: st.title(n), desc: st.desc(n),
      crumbs: [["Home", "/"], ["Old money", "/old-money"], [st.h, path]],
      chips: [[`Brands in the ${st.name.toLowerCase()} look`, have.filter(b => brandSlug.has(b)).map(b => [`${b} reps`, `/brand/${brandSlug.get(b)}`])],
              ...(m[1] === "grisch" ? [["Grisch on your agent", AGENT_BRAND_AGENTS.map(k => [AGENTS[k].name, `/${k}-spreadsheet/grisch`])]] : []),
              ["More old money", other.concat([["Old money spreadsheet", "/old-money"], ["MyCNBox spreadsheet", "/mycnbox-spreadsheet"]])]],
      faq: st.faq };
  }
  // QC photos spreadsheet (25 Oct 2026): Search Console showed "qc photos" 391 times in 28 days at position 8.4 with no
  // clicks, and no page answered it directly. Finds the catalogue marks as having buyer QC photos, on every agent.
  if (path === "/qc-spreadsheet") {
    const vis = all.filter(p => p.qc >= 1 && findShown(p)), q1 = vis.length, q2 = vis.filter(p => p.qc >= 2).length, n = nf(q1);
    // 22 Nov 2026 (SEO check): the QC photos spreadsheet. "QC finder" searches go to the QC finder tool, which is what they
    // want (/tools/qc-checker); this page links to it.
    // 23 Nov 2026 (SEO pass): it is the page for "qc spreadsheet" (title and h1 start with those words), it counts only the
    // finds a visitor can see, and its About block has the QC checklist for each item type and its finds by category.
    const byCatQ = Object.entries(CATS).filter(([c, m]) => m.slug !== "toys" && CAT_QC[c]).map(([c, m]) => [c, m, vis.filter(p => p.cat === c)]).filter(([, , l]) => l.length).sort((a, b) => b[2].length - a[2].length);
    return { path, preset: { qc: 1 }, h: "QC Spreadsheet: Finds With Buyer QC Photos",
      sub: `${n} finds with buyer QC photos from earlier orders. Tap QC on a find to see real photos of the item before you buy.`,
      title: `QC Spreadsheet 2026: ${n} Finds With Buyer QC Photos | Puro Classico`,
      desc: `The QC spreadsheet: ${n} rep finds with buyer QC photos from earlier orders, with prices, agent links and what to check for each item type.`,
      crumbs: [["Home", "/"], ["QC spreadsheet", path]],
      aboutTitle: "About the QC spreadsheet",
      about: [["What is in the QC spreadsheet", `<p>${n} finds that our catalogue marks as having buyer QC photos from earlier orders, ${nf(q2)} of them with the number of photos on record. By category: ${andList(byCatQ.map(([, m, l]) => `<a href="/category/${m.slug}">${esc(m.name.toLowerCase())}</a> (${nf(l.length)})`))}. For a link that is not on the spreadsheet, paste it into the <a href="/tools/qc-checker">QC finder</a>.</p>`],
        ...byCatQ.slice(0, 6).map(([c, m]) => [`What to check in QC photos of ${m.name.toLowerCase()}`, `<ul>${CAT_QC[c].map(x => `<li>${esc(x)}</li>`).join("")}</ul>`])],
      chips: [["QC photos on your agent", AGENT_BRAND_AGENTS.map(k => [AGENTS[k].name, `/${k}-spreadsheet/qc`])],
              ["Check QC photos yourself", [["How to read QC photos", "/guides/how-to-qc"], ["QC finder for any link", "/tools/qc-checker"]]],
              ["Agent spreadsheets", Object.keys(AGENT_INTRO).map(k => [`${AGENTS[k].name} spreadsheet`, `/${k}-spreadsheet`])], PLAT_CHIPS],
      faq: [["What are QC photos?", "QC (quality check) photos are real photos of the exact item a buyer ordered, taken by the shopping agent when it reaches the warehouse in China. They show the stitching, logos, colour and size tag before you pay for international shipping."],
            ["Where do these QC photos come from?", `From earlier buyers' orders of the same listing. Our catalogue marks ${n} finds as having them and stores the photo count for ${nf(q2)} of them. Open a find and tap QC to load them.`],
            ["Will I get QC photos of my own item?", "Yes. Your agent photographs your exact item at its warehouse before it ships, so you can return or exchange it if something is wrong."],
            ["Can I find QC photos for a link that is not here?", "Yes. Paste a Weidian, Taobao, 1688 or shopping agent link, or just the item ID, into our QC finder. It shows buyer QC photos from earlier orders when anyone has bought that listing through an agent."],
            ["What should I check in QC photos?", "Logo shape and placement, stitching, colour against retail photos, the size tag and any measurements. Our guide on how to read QC photos goes through it step by step."],
            ["Is the spreadsheet free?", "Yes. You only pay your agent for what you order and for shipping. Our links to agents are affiliate links: we may earn a commission if you order, at no extra cost to you."]] };
  }
  if (path === "/cnfans-spreadsheet") {
    const N = FINDS_PLUS;
    // 23 Nov 2026 (SEO pass): what happened to CNFans, with dates, and the agents to use instead, side by side with the
    // facts their spreadsheets already give (content.js AGENT_INTRO: help centres read 9 Nov 2026, MyCNBox 10 Oct 2026).
    const ALT = [["mycnbox", "4 photos per item", "90 days", "Coupons up to $500 with invite code AACPYA"], ["kakobuy", "Model, style and size checked", "100 days", "Coupons up to $410 with invite code w5war"],
      ["oopbuy", "Quantity, colour and size checked", "90 days", "¥3,500 coupon bundle and 15% off shipping"], ["lovegobuy", "Colour, damage, size and model checked", "60 days", "Shipping coupons up to $141"],
      ["sugargoo", "5 free photos per item", "100 days", "¥800 coupon pack"],
      ["hipobuy", "Generally 3 photos per item", "90 days", "Coupon pack with 25% off and ¥100"]];
    return { path, preset: {}, h: "CNFans Spreadsheet",
      sub: `cnfans.com has not loaded since ${CNFANS.down}. All ${N} finds here open in MyCNBox, KakoBuy, Oopbuy, LoveGoBuy or Sugargoo.`,
      title: `CNFans Spreadsheet 2026: ${N} Finds for Working Agents | Puro Classico`,
      desc: `CNFans has not loaded since ${CNFANS.down}. ${N} finds that open in MyCNBox, KakoBuy, Oopbuy and other agents, the agents compared, and a link converter.`,   // 25 Nov 2026: was 177 characters once liveCopy widened the agent list
      crumbs: [["Home", "/"], ["CNFans spreadsheet", path]],
      aboutTitle: "CNFans and the agents to use instead",
      about: [["What happened to CNFans", `<p>${CNFANS_STATUS[0].toUpperCase() + CNFANS_STATUS.slice(1)}. We check it every day and will update this page when that changes. This page cannot help with orders or balances already on CNFans; it shows where the same finds can be ordered now.</p>`],
        ["Where to order instead", `<p>Every find on this spreadsheet opens in these agents. What each one says about its warehouse check, free storage and new-user offer:</p>` +
          `<table><tr><th>Agent</th><th>QC check</th><th>Free storage</th><th>New users</th></tr>${ALT.map(([k, qc, st, off]) => `<tr><td><a href="/${k}-spreadsheet">${esc(AGENTS[k].name)}</a></td><td>${esc(qc)}</td><td>${esc(st)}</td><td>${esc(off)}</td></tr>`).join("")}</table>` +
          `<p style="font-size:13px;color:var(--muted)">From each agent's help centre and sign-up offer (MyCNBox read 10 Oct 2026, Hipobuy 26 Nov 2026, the others 9 Nov 2026). Coupons come with minimum spends. Our links to agents are affiliate links.</p>`],
        ["Your old CNFans links", `<p>A CNFans product link holds the Weidian, Taobao or 1688 item it points to. Paste it into the <a href="/tools/link-converter">link converter</a> and it gives you the same item on MyCNBox, KakoBuy, Oopbuy and the other agents. Agents that closed or paused before CNFans are listed in <a href="/guides/pandabuy-alternatives">Pandabuy alternatives</a>.</p>`]],
      chips: [["Use your old CNFans links", [["Link converter", "/tools/link-converter"], ["Agents that closed or paused", "/guides/pandabuy-alternatives"]]],
              ["Agent spreadsheets that open every find", Object.keys(AGENT_INTRO).map(k => [`${AGENTS[k].name} spreadsheet`, `/${k}-spreadsheet`])],
              ["Spreadsheets by style", [["Grisch spreadsheet", "/grisch-spreadsheet"], ["Stockholm style spreadsheet", "/stockholm-spreadsheet"], ["Old money spreadsheet", "/old-money"]]], MCB_GUIDES, PLAT_CHIPS],
      faq: [["Is CNFans down?", `Yes, as far as we can see: ${CNFANS_STATUS}. We will update this page when that changes.`],
            ["Do my old CNFans links still work?", "Paste an old CNFans product link into our link converter. It reads the Weidian, Taobao or 1688 item from the link and opens the same item in another agent."],
            ["How do I switch from CNFans to another agent?", "Open a find, tap the buy button for the agent you want, create a free account there and pay for the item plus delivery to the warehouse. The seller and the item stay the same; only the agent that buys, checks and ships it changes."],
            ["Is this the official CNFans spreadsheet?", "No. Puro Classico is an independent spreadsheet and is not affiliated with CNFans. Our links to other agents are affiliate links: we may earn a commission if you order, at no extra cost to you."]] };
  }
  if ((m = path.match(AGENT_STYLE_RE))) {
    const key = m[1], s = m[2], a = AGENTS[key], st = AGENT_STYLES[s];
    const have = st.brands ? st.brands().filter(b => byBrand.has(b)) : null;
    const count = have ? have.reduce((t, b) => t + byBrand.get(b).length, 0) : st.qc ? all.filter(p => p.qc >= st.qc && findShown(p)).length
      : st.pmax ? all.filter(p => inBudget(p, st.pmax) && findShown(p)).length : (byCat.get(st.cat) || []).filter(findShown).length;
    const n = nf(count), low = s === "shoes" ? "shoe" : st.name.toLowerCase();
    const preset = have ? { agent: key, brands: have.map(b => slug(b)) } : st.qc ? { agent: key, qc: st.qc } : st.pmax ? { agent: key, pmax: st.pmax } : { agent: key, cat: st.cat };
    return { path, preset,
      h: st.h ? st.h(a.name) : `${st.name} on ${a.name}`, sub: st.sub ? st.sub(a.name, n) : `${n} ${low} finds with one-tap ${a.name} links.`,
      title: st.title ? st.title(a.name, n) : `${st.name} ${a.name} Spreadsheet 2026: ${n} Finds | Puro Classico`,
      desc: st.desc ? st.desc(a.name, n) : `The ${low} ${a.name} spreadsheet: ${n} rep finds with prices and one-tap ${a.name} buy links.`,
      crumbs: [["Home", "/"], [`${a.name} spreadsheet`, `/${key}-spreadsheet`], [st.name, path]],
      chips: [[`${st.name} on other agents`, AGENT_BRAND_AGENTS.filter(k => k !== key).map(k => [AGENTS[k].name, `/${k}-spreadsheet/${s}`]).concat([st.parent])],
              [`More on ${a.name}`, Object.keys(AGENT_STYLES).filter(x => x !== s).map(x => [AGENT_STYLES[x].name, `/${key}-spreadsheet/${x}`]).concat([[`${a.name} spreadsheet`, `/${key}-spreadsheet`]])], MCB_GUIDES], cta: 1,
      faq: (st.faq ? st.faq(a.name, n, nf(all.filter(p => p.qc >= 2 && findShown(p)).length)) : [[`How do I order ${low} reps on ${a.name}?`, `Open a find, tap Buy via ${a.name}, pick your size and pay for the item plus delivery to the ${a.name} warehouse. Check the QC photos there, then ship your parcel.`],
            [s === "shoes" ? `How do I get the right size on ${a.name}?` : "What should I buy first?", st.first]])
            .concat([["Is the spreadsheet free?", `Yes. You only pay ${a.name} for what you order and for shipping. Our links to agents are affiliate links: we may earn a commission if you order, at no extra cost to you.`]]) };
  }
  if ((m = path.match(/^\/(mycnbox|kakobuy|oopbuy|lovegobuy|sugargoo|hipobuy)-spreadsheet$/))) {
    const key = m[1], a = AGENTS[key], meta = AGENT_INTRO[key]; if (!a || !meta) return null;
    const N = FINDS_PLUS, brands = AGENT_BRAND_AGENTS.includes(key) ? agentBrands() : [];
    // Agent hubs bring most of the search clicks, but page 1 (this app view) carried 3 short answers while the written intro
    // and how-to only reached pages 2+ (22 Oct 2026). They go in the block under the app, numbers worked out here.
    const day = d => new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
    const qc1 = all.filter(p => p.qc >= 1 && findShown(p)).length, qc2 = all.filter(p => p.qc >= 2 && findShown(p)).length, weidian = all.filter(p => p.platform === "weidian").length;
    const howTo = agentHowTo({ ...a, key }).replace(/^\s*<h2>[^<]*<\/h2>\s*/, "")
      .replace('<ol class="steps">', '<ol style="margin:10px 0 0;padding-left:20px;color:var(--muted);font-size:14.5px;line-height:1.6">');
    // The MyCNBox intro says "our most-used agent" and repeats the coupon offer; how agents are ranked is the owner's call,
    // so this page uses a plain description for it.
    const what = key === "mycnbox" ? "<p>MyCNBox is a shopping agent: you pay MyCNBox for the item and the short delivery to its warehouse in China, it buys from the Weidian, Taobao or 1688 seller, takes QC photos when the item arrives, and ships your items together in one parcel when you are ready. Each find here opens the exact listing inside MyCNBox.</p><p>Is it legit, what does it charge and how do the coupons work? Read our <a href=\"/guides/mycnbox-review\">MyCNBox review</a>.</p>" : meta.body;
    // 25 Nov 2026 (SEO pass): the day of the last catalogue update in the subtitle (the middleware adds the link check), and
    // this agent next to MyCNBox (MyCNBox next to KakoBuy) from the facts of both spreadsheets (agentCompare), as the second section.
    const vs = key === "mycnbox" ? "kakobuy" : "mycnbox", cmp = AGENT_FACTS[key] && AGENT_FACTS[vs] ? agentCompare([key, vs], key).facts : "";
    const side = cmp ? [[`${a.name} and ${AGENTS[vs].name} side by side`, cmp + `<p>All ${CMP_WORD} agents, with their cheapest shipping lines: <a href="/guides/best-shopping-agent">best shopping agent compared</a>${key === "kakobuy" || key === "mycnbox" ? ` · <a href="/guides/kakobuy-vs-mycnbox">KakoBuy vs MyCNBox</a>` : ""}.</p>`]] : [];
    return { path, preset: { agent: key }, h: `${a.name} Spreadsheet`, sub: `${N} finds, each with a one-tap ${a.name} buy button. Updated ${BUILT_DAY}.`,
      aboutTitle: `How the ${a.name} spreadsheet works`, about: [[`What is ${a.name}?`, what]].concat(side, meta.about || [[`How to order from the ${a.name} spreadsheet`, howTo]], shipAbout(key, a.name), freshAbout(key)),
      title: `${meta.title}: ${N} Finds | Puro Classico`, desc: meta.desc ? meta.desc(N, nf(qc1)) : `The ${a.name} spreadsheet: ${N} rep finds with prices and one-tap ${a.name} links, ${nf(qc1)} marked as having buyer QC photos.${LINKS_CHECKED ? " Weidian links checked every week." : ""}`,
      crumbs: [["Home", "/"], [`${a.name} spreadsheet`, path]],
      chips: [...(AGENT_BRAND_AGENTS.includes(key) ? [[`Browse on ${a.name}`, Object.keys(AGENT_STYLES).map(x => [AGENT_STYLES[x].name, `${path}/${x}`])]] : []),
              [`Popular brands on ${a.name}`, brands.slice(0, 16).map(b => [`${b} (${nf(brandFacts(b).n)})`, `${path}/${brandSlug.get(b)}`])],
              ["Other agent spreadsheets", Object.keys(AGENT_INTRO).filter(k => k !== key).map(k => [`${AGENTS[k].name} spreadsheet`, `/${k}-spreadsheet`]).concat([["CNFans spreadsheet", "/cnfans-spreadsheet"], ["QC photos spreadsheet", "/qc-spreadsheet"]])], agentGuides(key), ...(key === "mycnbox" ? [] : [MCB_GUIDES]), PLAT_CHIPS],
      faq: (meta.faq ? meta.faq.concat(agentFaqMore(key, a.name, meta.faq, N, qc1)) : null) || [[`What is the ${a.name} spreadsheet?`, `A searchable list of ${N} Weidian, Taobao and 1688 finds. Every find opens directly in ${a.name}, so there is nothing to copy or translate.`],
            [`How do I order with ${a.name}?`, `Open a find, tap Buy via ${a.name}, pick your size and pay for the item plus delivery to the warehouse. Check the QC photos, then ship your parcel.`],
            [`Is this the official ${a.name} spreadsheet?`, `No. Puro Classico is an independent spreadsheet. Ordering, payment, QC photos and shipping all happen on ${a.name}. Our links to ${a.name} are affiliate links: we may earn a commission if you order, at no extra cost to you.`],
            ["How many finds have QC photos?", `Our catalogue marks ${nf(qc1)} of the ${N} finds as having buyer QC photos from earlier orders, and stores the photo count for ${nf(qc2)} of them.`],
            ...(LINKS_CHECKED ? [["Are the links still working?", `Every week we check all ${nf(weidian)} Weidian listings. The last check, on ${day(LINKS_CHECKED)}, found ${nf(GONE_COUNTS.dead)} gone, which the spreadsheet hides, and ${nf(GONE_COUNTS.sold)} sold out, which their pages point out.`]] : []),
            ["Are the prices live?", `No. They are the sellers' listed prices from the last catalogue update on ${day(BUILT)}. Check the price on ${a.name} before you pay.`],
            [`Is it free?`, `Yes. You only pay ${a.name} for what you order and for shipping. Our links to agents are affiliate links: we may earn a commission if you order, at no extra cost to you.`]] };
  }
  if ((m = path.match(new RegExp(`^/(${AGENT_BRAND_AGENTS.join("|")})-spreadsheet/([a-z][a-z0-9-]*)$`)))) {
    const key = m[1], s = m[2], a = AGENTS[key], b = slugBrand.get(s);
    if (!a || !b || !agentBrands().includes(b)) return null;
    const f = brandFacts(b), n = nf(f.n), range = priceRange(f.list), ab = agentBrandCopy(key, b, s, f.list);   // visible finds only (25 Nov 2026)
    // Page 1 is the app view: renderAgentBrand's how-to and FAQ were page-1 only and so shown nowhere (the agent hubs got the same fix on 22 Oct 2026).
    const howTo = agentHowTo({ ...a, key }).replace(/^\s*<h2>[^<]*<\/h2>\s*/, "")
      .replace('<ol class="steps">', '<ol style="margin:10px 0 0;padding-left:20px;color:var(--muted);font-size:14.5px;line-height:1.6">');
    // canonical (22 Nov 2026, SEO check): agent x brand pages without Google visitors point at the brand page (seo_canon.js)
    return { path, canonical: AGENT_BRAND_CANON.has(path) ? `/brand/${s}` : undefined, preset: { agent: key, brand: s }, h: `${b} on ${a.name}`, sub: `${n} ${b} finds with one-tap ${a.name} links.`,
      aboutTitle: `How to buy ${b} on ${a.name}`, about: ab ? ab.about : [[`Ordering ${b} reps through ${a.name}, step by step`, howTo]],
      title: `${b} ${a.name} Spreadsheet 2026: ${n} Finds | Puro Classico`, desc: ab ? ab.desc : `${n} ${b} rep finds with one-tap ${a.name} buy links${f.med ? `, half listed at ${money(f.med.cny)} or less` : ""}${f.q1 ? `, ${nf(f.q1)} marked as having QC photos` : ""}.${LINKS_CHECKED ? " Weidian links checked every week." : ""}`,
      crumbs: [["Home", "/"], [`${a.name} spreadsheet`, `/${key}-spreadsheet`], [b, path]],
      chips: [[`${b} on other agents`, AGENT_BRAND_AGENTS.filter(k => k !== key).map(k => [AGENTS[k].name, `/${k}-spreadsheet/${s}`]).concat([[`All ${b} reps`, `/brand/${s}`]])],
              [`More brands on ${a.name}`, agentBrands().filter(x => x !== b).slice(0, 14).map(x => [x, `/${key}-spreadsheet/${brandSlug.get(x)}`])], MCB_GUIDES], cta: 1,
      faq: ab ? ab.faq : [[`How do I buy ${b} reps on ${a.name}?`, `Open a find, tap Buy via ${a.name}, choose your size and pay. ${a.name} sends QC photos when it reaches the warehouse; check them, then ship.`],
            ...(range ? [[`How much do ${b} reps cost on ${a.name}?`, `${b} finds here are listed at ${range} before international shipping. These are the sellers' listed prices from the last catalogue update, so check the price on ${a.name} before you pay.`]] : []),
            [`Do these ${b} finds have QC photos?`, f.q1 ? `Our catalogue marks ${nf(f.q1)} of the ${n} as having buyer QC photos from earlier orders. Open a find and tap QC to load them. ${a.name} also photographs your own item at its warehouse before it ships.` : `Our catalogue does not mark any of them as having buyer QC photos yet. ${a.name} photographs your own item at its warehouse before it ships.`],
            [`Are these ${b} finds only for ${a.name}?`, `No. The same finds open on ${andList(AGENT_BRAND_AGENTS.filter(k => k !== key).map(k => AGENTS[k].name))}; each find has a button for every agent.`]] };
  }
  if ((m = path.match(/^\/brand\/([a-z0-9-]+)$/))) {
    const s = m[1], b = slugBrand.get(s); if (!b) return null;
    const list = brandFacts(b).list, n = nf(list.length);   // visible finds only (25 Nov 2026), as the listing
    const rel = relatedBrands(b).slice(0, 12);
    const ag = agentBrands().includes(b) ? AGENT_BRAND_AGENTS.map(k => [`${b} on ${AGENTS[k].name}`, `/${k}-spreadsheet/${s}`]) : [];
    // Page 1 of a brand hub is this app view, so what renderBrand wrote for page 1 (the brand intro and QC checks, the facts
    // worked out from its rows, its model pages and the brand FAQ) reached no page (28 Oct 2026). It goes in the block under
    // the app, as the agent hubs' intro did on 22 Oct. Title and description keep to catalogue data (rules above brandFacts):
    // the half-way listed price (the lowest listed price is often a deposit or placeholder), the main item type when it is
    // more than half the list, and how many finds are marked as having QC photos (no QC words when there are none).
    const f = brandFacts(b), bm = models().filter(x => modelOnBrand(x, b));
    const t0 = f.types[0], share = t0 && !t0[0].startsWith("other") ? t0[1].length / f.n : 0;
    const half = f.med ? `, half listed at ${money(f.med.cny)} or less` : "", qcN = f.q1 ? `, ${nf(f.q1)} marked as having QC photos` : "";
    const main = share === 1 ? `, all ${t0[0]}` : share > 0.5 ? `, mostly ${t0[0]}` : "", tail = " Buy via MyCNBox, KakoBuy, Oopbuy or your agent.";
    const lead = `${n} ${b} rep find${f.n === 1 ? "" : "s"}${half}`;
    const bDesc = [`${lead}${main}${qcN}.${tail}`, `${lead}${qcN}.${tail}`, `${lead}${qcN}.`].find(x => x.length <= 160) || `${n} ${b} rep finds.`;
    return { path, preset: { brand: s }, h: `${b} Reps`, sub: `${n} ${b} finds from Weidian, Taobao and 1688.`,
      title: `${b} Reps Spreadsheet 2026: ${n} Finds | Puro Classico`, desc: bDesc,
      crumbs: [["Home", "/"], ["Brands", "/brands"], [b, path]],
      aboutTitle: `About ${b} reps`,
      about: [[`What to check on ${b} reps`, BRAND_INTRO[b] || ""], [`${b} on the spreadsheet, in numbers`, brandFactsHtml(f)]].filter(([, h]) => h),
      chips: [...(bm.length ? [["Best reps by model", bm.map(x => [`Best ${MODEL_TERM[x.slug] || x.name} reps`, `/best/${x.slug}`])]] : []),
              ...(ag.length ? [[`Buy ${b} with your agent`, ag]] : []), ["Related brands", rel.map(x => [x, `/brand/${brandSlug.get(x)}`]).concat([["All brands", "/brands"]])]],
      faq: brandFaq(f, bestHub(f)) };
  }
  if ((m = path.match(/^\/category\/([a-z0-9-]+)$/))) {
    const s = m[1], c = own(CAT_BY_SLUG, s) ? CAT_BY_SLUG[s] : null; if (!c) return null;
    const list = (byCat.get(c) || []).filter(findShown), meta = CATS[c], n = nf(list.length), q1 = list.filter(p => p.qc >= 1).length;
    const top = [...new Set(list.map(p => p.brand))].filter(b => brandSlug.has(b)).slice(0, 16);
    return { path, preset: { cat: c }, h: meta.h, sub: `${n} finds, most viewed first.`,
      title: `Rep ${meta.name} Spreadsheet 2026: ${n} Finds | Puro Classico`, desc: `${n} ${meta.name.toLowerCase()} rep finds${q1 ? `, ${nf(q1)} marked as having buyer QC photos` : ""}, most viewed first. Buy via MyCNBox, KakoBuy, Oopbuy or your agent.`,
      crumbs: [["Home", "/"], [meta.name, path]],
      chips: [[`Top brands in ${meta.name.toLowerCase()}`, top.map(b => [b, `/brand/${brandSlug.get(b)}`])],
              // 23 Nov 2026: the model pages of this category (the best X reps pages), so each one is linked from its hub
              ...(() => { const bm = modelsInCat(c); return bm.length ? [["Best reps by model", bm.map(x => [`Best ${MODEL_TERM[x.slug] || x.name} reps`, `/best/${x.slug}`]).concat([["All models", "/best"]])]] : []; })(),
              ["Other categories", Object.values(CATS).filter(x => x.slug !== s && x.slug !== "toys").map(x => [x.name, `/category/${x.slug}`])]],
      // CAT_INTRO was only on renderCategory's page 1, which this app view replaced (28 Oct 2026).
      aboutTitle: `About ${meta.name.toLowerCase()} reps`, about: CAT_INTRO[c] ? [[`Buying ${meta.name.toLowerCase()} reps`, CAT_INTRO[c]]] : [],
      faq: [] };
  }
  return null;
}
// The HTML pieces the middleware puts into index.html for a hub spec. `more` (the links to pages 2+) opens the block.
// Icons for the hub-seo block (styles: index.html): h2s by title, about summaries by question.
const HUB_H2_IC = [[/^About/, "info"], [/Best reps by model/, "award"], [/with your agent|on your agent|agents?\b/i, "users"], [/Related brands|Top brands|Brands in the/, "tag"],
  [/Other categories/, "grid"], [/Browse page by page/, "layers"], [/More old money|More /, "layers"], [/marketplace/i, "store"], [/^FAQ$/, "help"]];
const HUB_SUM_IC = [[/shipping lines and prices|shipping: real parcels/i, "truck"], [/^New .*finds this week$/, "flame"], [/^What to check/, "camera"], [/in numbers/, "chart"], [/^Buying|^Ordering|order from|step by step/i, "cart"], [/^What is/, "info"],
  [/link looks like/, "link"], [/^How to buy/, "cart"], [/QC photos/, "camera"], [/^Sizing/, "ruler"], [/^Shipping/, "truck"], [/^Minimum/, "box"], [/^Why|^Taobao or|^Taobao, /, "store"]];
export function hubParts(spec, more = "", skip = null) {
  const bc = crumbs(spec.crumbs);
  const crumbHtml = `<nav class="hub-bc" aria-label="Breadcrumb">${spec.crumbs.map((c, i) => i < spec.crumbs.length - 1 ? `<a href="${c[1]}">${esc(c[0])}</a><span aria-hidden="true">›</span>` : `<span aria-current="page">${esc(c[0])}</span>`).join("")}</nav>`;
  // v10 (12 Nov 2026): under the subtitle (`after`), one row of related links and the agent logo row: a link to another
  // agent's page goes to the logo row (one per agent), every other chip link to the related row (at most 24 there; all of
  // them stay in the About lists). Before the footer (`seo`), the About section: the about copy open as text, the link
  // groups as lists, the FAQ as <details>, the links to pages 2+ (`more`, appPager).
  const me = spec.preset.agent || null, shopL = [], quick = [], seenA = new Set();
  for (const [, links] of spec.chips) for (const l of links) { const k = agentOf(l[1]); if (k && k !== me && !seenA.has(k)) { seenA.add(k); shopL.push(l); } else quick.push(l); }
  // spec.cta (24 Nov 2026, owner): agent x brand and agent x style pages send visitors on to the whole spreadsheet (/spreadsheet).
  const cta = spec.cta ? `<p class="sp-cta" style="margin:12px 0 0"><a class="btn primary" href="/spreadsheet">Open the spreadsheet${ic("arrow-right", "sm")}</a></p>` : "";
  const after = `<div class="hx hx-app hx-hero">${cta}${hxRow(quick.slice(0, 24))}${hxShop(shopL, me ? "Other agents" : "Shop this on")}</div>`;
  const main = (spec.about || []).filter(([, html]) => html).map(([q, html]) => `<h3>${esc(q)}</h3>${html}`).join("");
  // Brand hubs: that brand's newest finds as plain links (newFindsHtml), under the About columns.
  const b = spec.preset.brand && !spec.preset.agent ? idx().slugBrand.get(spec.preset.brand) : null;
  const fresh = b ? newFindsHtml(newest(NEW_LINKS, b, skip), `New ${b} finds`) : "";
  const seo = `<div class="hx hx-app">${hxAbout({ title: spec.aboutTitle || `About ${spec.h.split(":")[0]}`, main, faq: spec.faq, groups: spec.chips, tail: more, after: fresh })}</div>`;
  const ld = [bc.data]; if (spec.faq.length) ld.push(faqLd(spec.faq));
  const page = { h: spec.h, sub: spec.sub, agent: spec.preset.agent || null, brand: spec.preset.brand || null, cat: spec.preset.cat || null, brands: spec.preset.brands || null,
    qc: spec.preset.qc || null, pmax: spec.preset.pmax || null, ...(spec.preset.plat ? { plat: spec.preset.plat } : {}) };
  const head = `<script>window.PC_PAGE=${JSON.stringify(page).replace(/</g, "\\u003c")};document.documentElement.classList.add("hub"${page.agent ? ',"agent-lock"' : ""}${page.brand || page.cat ? ',"af-pre"' : ""}${page.cat ? ',"sub-pre"' : ""});</script>` +
    ld.map(o => '<script type="application/ld+json">' + JSON.stringify(o).replace(/</g, "\\u003c") + "</script>").join("") + HX_CSS;
  return { crumbHtml, seo, head, after };
}

// ------------------------------------------------------------------ server cards on the app pages (21 Oct 2026)
// The homepage and the hub pages are the catalogue app, whose cards only existed after JavaScript ran: the HTML had one
// product link, AI search bots (which run no scripts) saw no finds, and pages 2+ of a hub were linked from nowhere. The
// first APP_CARDS finds now arrive in #grid as the app's own card markup, in popularity order (score(), the same numbers
// as the app's default "Most popular" sort), and brand and category hubs link their pages 2+. index.html keeps these
// finds first, in this order, in its first render (pinSsr), so the app taking over does not reshuffle the screen.
export const APP_CARDS = PER_PAGE;
// The finds of an app page in popularity order, and the base URL of its server-rendered pages 2+ (null when it has none
// worth linking). No spec is the homepage.
export function hubList(spec) {
  const { all, byBrand, byCat, slugBrand } = idx();
  const pr = spec ? spec.preset : {};
  if (pr.plat) return { list: all.filter(p => p.platform === pr.plat && findShown(p)), base: `/${pr.plat}-spreadsheet` };
  if (pr.qc) return { list: all.filter(p => p.qc >= pr.qc && findShown(p)), base: null };
  if (pr.pmax) return { list: all.filter(p => inBudget(p, pr.pmax) && findShown(p)), base: null };
  if (pr.brands) { const want = new Set(pr.brands); return { list: [...byBrand].filter(([b]) => want.has(slug(b))).flatMap(([, l]) => l).sort((a, b) => score(b) - score(a)), base: null }; }
  // 25 Nov 2026 (speed and SEO check): a brand hub lists and pages the finds a visitor can see, as renderBrand pages them
  // (brandFacts). Its "Browse page by page" links counted every row, so 60 brand hubs linked 61 pages past the end
  // (/brand/moncler/6 and /7, ...) that 301 back to the hub (rescue() in the middleware). Agent x brand hubs keep every row.
  if (pr.brand) { const b = slugBrand.get(pr.brand); return { list: pr.agent ? byBrand.get(b) || [] : b ? brandFacts(b).list : [], base: pr.agent ? null : "/brand/" + pr.brand }; }
  if (pr.cat) return { list: (byCat.get(pr.cat) || []).filter(findShown), base: !pr.agent && CATS[pr.cat] ? "/category/" + CATS[pr.cat].slug : null };
  return { list: all, base: null };
}
// Same markup as card() in index.html (English, USD), plus data-ssr; v9 adds the .card-acts row (QC pill + black Buy pill). Image URLs are built the way the app builds them
// (imgSrc: Supabase photos through SITE/api/img), so the app's cards reuse the images the browser already has.
// The app's ICON(name) markup (index.html): a <use> of its #pc-icons sprite, byte for byte, so these cards match the
// cards the app draws and stay small (60 per page).
const useIcon = n => `<svg class="ic" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><use href="#i-${n}"/></svg>`;
const HEART = useIcon("star");
const appAlt = p => { const t = p.title || "", b = p.brand || ""; return (b && !t.toLowerCase().startsWith(b.toLowerCase()) ? b + " " : "") + t + " rep"; };
const CAM = useIcon("camera");
const PALETTE = useIcon("palette");
// 24 Nov 2026 (calm loading): the same srcset and sizes as the app's card() (index.html thumbSet), so on retina screens the
// browser loads one copy (720 px) for the server's card and the app's card that takes over its photo, not 400 px then 720 px.
const APP_SIZES = "(max-width:640px) 48vw, (max-width:1100px) 31vw, 290px";
const appSet = s => { const a = thumbSrc(s); return a === s ? "" : a + " 400w, " + a.replace("/cdn-cgi/image/width=400,quality=75,", "/cdn-cgi/image/width=720,quality=80,") + " 720w"; };
const APP_IMG_FALLBACK = `onerror="if(this.dataset.o){this.removeAttribute('srcset');this.src=this.dataset.o;this.dataset.o=''}else this.remove()"`;
export function appCards(list, qcMin = 1, agent = "mycnbox", off = 0) {   // qcMin: the QC pill threshold (1: finds marked as having QC photos, like the app and server cards). off: added to the index for the eager/high image slots (8 on the homepage, where the grid sits below the v9 sections)
  const a = AGENTS[agent] || AGENTS.mycnbox;
  return list.map((p, i) => {
    const img = imgSrc(p), id = esc(p.id), url = productUrl(p);
    return `<div class="card" data-ssr="${id}"><div class="thumb${cutCls(p)}"><canvas aria-hidden="true"></canvas>` +
      (img ? `<img class="pimg" src="${esc(thumbSrc(img))}"${appSet(img) ? ` srcset="${esc(appSet(img))}" sizes="${APP_SIZES}"` : ""} data-o="${esc(img)}" alt="${esc(appAlt(p))}" loading="${i + off < 8 ? "eager" : "lazy"}"${i + off < 4 ? ' fetchpriority="high"' : ""} decoding="async" ${APP_IMG_FALLBACK}>` : "") +
      `<button class="fav" data-fav="${id}" aria-pressed="false" aria-label="Save ${esc(p.title)}">${HEART}</button><span class="tbadges">${colourBadge(p, PALETTE)}${(p.qc || 0) >= qcMin && QC_BANKED[p.id] ? `<a class="cbadge qcb" href="${url}#qc" aria-label="QC photos of ${esc(p.title)}">${CAM}</a>` : ""}</span></div>` +
      `<div class="body">${p.brand ? `<span class="brand-line">${esc(p.brand)}</span>` : ""}<a class="title" href="${url}">${esc(p.title)}</a>` +
      `<span class="price-row"><span class="price">${money(p.cny)}</span>` +
      `<span class="starcount" data-sc="${id}"></span><span class="cat">${esc(p.cat)}</span></span>` +
      `<span class="card-acts">` +
      `<a class="buy-pill" href="${esc(a.build(p))}" data-agent="${esc(AGENTS[agent] ? agent : "mycnbox")}" target="_blank" rel="sponsored nofollow noopener" aria-label="Buy via ${esc(a.name)}: ${esc(p.title)}">Buy</a></span></div></div>`;
  }).join("");
}
// Links to pages 2+ (the first 12, then the last), for the block under the app.
export function appPager(base, n) {
  const pages = Math.ceil(n / PER_PAGE); if (!base || pages < 2) return "";
  const nums = []; for (let k = 2; k <= Math.min(pages, 12); k++) nums.push(k);
  if (pages > 12) nums.push(pages);
  return `<div class="hx-group"><h3>Browse page by page</h3><div class="hx-pages">${nums.map(k => `<a href="${base}/${k}" aria-label="Page ${k}">${k}</a>`).join("")}</div></div>`;
}
