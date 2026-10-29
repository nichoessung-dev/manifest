// Shared server-side rendering for the SEO pages (product pages, hubs, guides, sitemaps, 404).
// Everything here is plain HTML + a little CSS so Google sees real content without running JS.
import { ROWS, PREFIX, BUILT } from "./catalog.js";
import * as SIG from "./signals.js";
const { CHECKED, DEMAND, DEAD, SOLD_OUT } = SIG;
// QC photo bank results (scripts/gen_signals.py from data/qc_bank.json, 28 Oct 2026), read through the namespace so a
// signals.js written before these lists existed still loads. QC_BANKED: { id: "YYYY-MM-DD" }, the finds whose QC photos
// are stored and the day they were. NO_QC: finds the catalogue only flags as having QC photos (qc 1) that the bank looked
// up and found none for. They count as finds without QC photos everywhere: page text and title, indexing, hub counts.
export const QC_BANKED = SIG.QC_BANKED || {};
const NO_QC = new Set(SIG.NO_QC || []);

export const SITE = "https://www.puroclassico.com";
export const MYCNBOX_INVITE = "https://mycnbox.com/login/main-login?inviteCode=AACPYA";
// The Discord invite lives here and nowhere else. Every page, static file and email links to /discord on our own
// domain, and functions/_middleware.js redirects that address to this URL: a new invite is a change to this one line.
export const DISCORD_INVITE = "https://discord.gg/Pf3zpG3E4";
export { BUILT };

// ------------------------------------------------------------------ data
// Brand spelling variants -> one name (same map as scripts/clean_catalog.py and loadProducts() in index.html).
// The catalogue is cleaned at build time; this is the safety net for rows imported before the next clean run.
export const BRAND_ALIAS = { "Essential": "Essentials", "Arcteryx": "Arc'teryx", "Cp": "CP Company", "Cdg": "Comme des Garcons",
  "Comme Des Garcons": "Comme des Garcons", "Comme des Garçons": "Comme des Garcons", "Ami Paris": "Ami", "Alo": "Alo Yoga",
  "Purple": "Purple Brand", "Carhart": "Carhartt", "Merta": "Mertra", "Aime": "Aime Leon Dore", "PROJECT G/R": "Project GR",
  "Parajumper": "Parajumpers", "ERD": "Enfants Riches Déprimés", "Polo": "Ralph Lauren" };
function normBrand(p) {
  if (p.brand === "Uncategorized") { p.brand = ""; p.title = String(p.title).replace(/^Uncategorized\s+/, ""); }
  const nb = BRAND_ALIAS[p.brand];
  if (nb) { if (p.title.startsWith(p.brand + " ") && !p.title.toLowerCase().startsWith(nb.toLowerCase() + " ")) p.title = nb + p.title.slice(p.brand.length); p.brand = nb; }
  return p;
}
export const P = ROWS.map(r => normBrand({ id: r[0], title: r[1], brand: r[2], cat: r[3], platform: r[4], seller: r[5], usd: r[6], cny: r[7],
  qc: NO_QC.has(r[0]) ? 0 : r[8], best: r[9], views: r[10], img: r[11], g: r[12], itemId: r[13], variants: r[14] }));
// Real view stats (data/stats.json, refreshed every 6h by the Stats workflow): { id: [all, 30d, 7d, favourites] }
// VIEWS_VER counts the different stats files this server instance has loaded (0 = none yet); every cache derived from
// the numbers (idx(), and the model, brand-facts and related-brands caches in pages.js) is rebuilt when it moves.
let VIEWS = {}, VIEWS_AT = 0, VIEWS_VER = 0, VIEWS_GEN = null;
const STATS_TTL = 10 * 60 * 1000, STATS_RETRY = 30 * 1000;
export async function ensureStats(origin) {
  const loaded = VIEWS_VER > 0;
  if (loaded && Date.now() - VIEWS_AT < STATS_TTL) return;
  // Loaded before: one request refreshes and the others keep the numbers they have. Never loaded: every request waits
  // for its own read, so no page is rendered without view numbers just because another request got here first.
  // (The read is not shared between requests on purpose: Workers ties a fetch to the request that started it.)
  if (loaded) VIEWS_AT = Date.now();
  let ok = false;
  try {
    const r = await fetch(origin + "/data/stats.json");
    if (r.ok) { const s = await r.json(); if (s && s.p) { ok = true; VIEWS_AT = Date.now();
      // The file changes every 6 hours. Re-reading the same file (same `generated` stamp) keeps every derived cache.
      if (VIEWS_VER === 0 || !s.generated || s.generated !== VIEWS_GEN) { VIEWS = s.p; VIEWS_GEN = s.generated; VIEWS_VER++; } } }
  } catch (e) {}
  if (!ok && loaded) VIEWS_AT = Date.now() - STATS_TTL + STATS_RETRY;   // a failed refresh is retried after 30 s, not after 10 min
}
// False until a stats file has been read. functions/_middleware.js gives a page rendered in that state a short cache time.
export const statsLoaded = () => VIEWS_VER > 0;
// Popularity = views (30 days, last 7 days count double), then favourites, all-time views, curated best-of, QC count.
export const score = p => { const v = VIEWS[p.id] || [0, 0, 0, 0];
  return Math.min(v[1] + v[2], 99999) * 1e9 + Math.min(v[3], 999) * 1e6 + Math.min(v[0], 999) * 1e3 + p.best * 500 + Math.min(p.qc, 499); };
// The same numbers for pages that print them (the "top picks" on brand hubs): [views all time, last 30 days, last 7 days, favourites].
const NO_VIEWS = [0, 0, 0, 0];
export const views = p => VIEWS[p.id] || NO_VIEWS;
// Indexable product pages: real QC photos, hand-curated, or finds visitors already look at (DEMAND, see
// scripts/gen_signals.py), unless the weekly link check found the listing gone. The rest are noindex,follow.
const DEMAND_SET = new Set(DEMAND), GONE = new Map([...DEAD.map(i => [i, "dead"]), ...SOLD_OUT.map(i => [i, "sold_out"])]);
export const gone = p => GONE.get(p.id) || null;               // "dead" | "sold_out" | null
export const LINKS_CHECKED = CHECKED;                          // date of that link check (YYYY-MM-DD)
export const GONE_COUNTS = { dead: DEAD.length, sold: SOLD_OUT.length };   // what that check found, for page copy
export const indexable = p => !GONE.has(p.id) && (p.qc >= 1 || p.best === 1 || DEMAND_SET.has(p.id));

let _idx = null, _idxVer = -1;
export function idx() {
  if (_idx && _idxVer === VIEWS_VER) return _idx;
  _idxVer = VIEWS_VER;
  const byId = new Map(), byBrand = new Map(), byCat = new Map();
  for (const p of P) {
    byId.set(p.id, p);
    if (p.brand) { if (!byBrand.has(p.brand)) byBrand.set(p.brand, []); byBrand.get(p.brand).push(p); }
    if (!byCat.has(p.cat)) byCat.set(p.cat, []); byCat.get(p.cat).push(p);
  }
  const sortAll = m => { for (const l of m.values()) l.sort((a, b) => score(b) - score(a)); };
  sortAll(byBrand); sortAll(byCat);
  const all = P.slice().sort((a, b) => score(b) - score(a));
  const brandSlug = new Map(), slugBrand = new Map();
  for (const [b, l] of byBrand) if (l.length >= BRAND_MIN || l.length >= (BRAND_ALLOW.get(b) || Infinity)) { const s = slug(b); brandSlug.set(b, s); slugBrand.set(s, b); }
  const titleCount = new Map();   // listings sharing a title get a distinguishing suffix on their product page
  for (const p of P) { const k = ((p.brand || "") + "|" + p.title).toLowerCase(); titleCount.set(k, (titleCount.get(k) || 0) + 1); }
  _idx = { byId, byBrand, byCat, all, brandSlug, slugBrand, titleCount };
  return _idx;
}
export const BRAND_MIN = 20;   // a brand gets its own hub page from this many finds
// Brands under BRAND_MIN that get a hub anyway. This is a hand-kept list, not a lower limit: a brand goes on it only when
//   1. people search for it: it is in a Search Console query we already show for, or Google's autocomplete offers a
//      "<brand> ... spreadsheet" search (checked 10 Oct 2026); and
//   2. there is a real page to show: 10+ finds (5+ when the evidence is Search Console itself); and
//   3. visitors here look at it: 30+ views in the last 30 days, a little more than the median hub of a 20+ brand gets
//      (27.5 on 10 Oct 2026).
// As counted on 10 Oct 2026 (finds / marked as having QC photos / views in 30 days / search evidence):
//   Jacob Cohen 7 / 5 / 238 / Search Console: "jacob cohen spreadsheet", "jacob cohen reps", "jacob cohen kakobuy"
//   Tom Ford 16 / 5 / 60 / autocomplete "tom ford cnfans spreadsheet"      Comme des Garcons 16 / 4 / 34 / "comme des garcons spreadsheet"
//   Rimowa 11 / 2 / 41 / "rimowa spreadsheet"
//   Brunello Cucinelli 19 / 6 / 53 / none found: the one exception to rule 1, kept because it is one find short of
//   BRAND_MIN, has more views than most hubs, and /old-money names it in its text.
// Looked at and left off: Nocta (11 / 9 / 13, autocomplete "nocta spreadsheet") and Aime Leon Dore (18 / 14 / 14,
// autocomplete only for a spreadsheet of an agent that has closed). Both fail rule 3: no find of theirs has 5 views, so
// the hub would be the generated sentences and a short grid, with no picks. Add the name back when the views are there.
// Do not add the other small brands in bulk: a hub with a handful of finds and no demand is a thin page.
// The number is that brand's own floor (rule 2): under it the hub is gone again (404) instead of going thin.
// 5 where the evidence is Search Console itself, 10 everywhere else.
export const BRAND_ALLOW = new Map([["Jacob Cohen", 5], ["Brunello Cucinelli", 10], ["Tom Ford", 10], ["Comme des Garcons", 10], ["Rimowa", 10]]);
// Hubs the footer of every page links to: first the brands named in Search Console queries we already show for
// (28 Sep - 6 Oct 2026, most impressions first), then the largest hubs. Brands without a hub are skipped.
// Refresh the first list from Search Console (Performance > Queries) every month or two.
export const FOOTER_BRANDS = ["Ralph Lauren", "Golden Goose", "Arc'teryx", "Jacob Cohen", "Mertra", "Derschutze", "Goyard", "Chrome Hearts", "Maison Margiela",
  "Essentials", "Celine", "Burberry", "Corteiz", "Moncler", "Salomon", "Hoka", "Dior", "Acne Studios", "Stussy", "Givenchy"];
export const FOOTER_LARGEST = 14;   // ...plus the hubs with the most finds (the footer's whole list before the Search Console names were added)

export const CATS = {
  Tops:        { slug: "tops",        name: "Tops",               h: "Rep Tops: Hoodies, T-Shirts, Sweaters & Knitwear" },
  Outerwear:   { slug: "jackets",     name: "Jackets & Outerwear", h: "Rep Jackets, Coats & Outerwear" },
  Shoes:       { slug: "sneakers",    name: "Sneakers & Shoes",   h: "Rep Sneakers & Shoes" },
  Pants:       { slug: "pants",       name: "Pants & Jeans",      h: "Rep Pants, Jeans & Tracksuit Bottoms" },
  Shorts:      { slug: "shorts",      name: "Shorts",             h: "Rep Shorts" },
  Bags:        { slug: "bags",        name: "Bags",               h: "Rep Bags & Backpacks" },
  Accessories: { slug: "accessories", name: "Accessories",        h: "Rep Accessories: Belts, Jewellery, Wallets & More" },
  Headwear:    { slug: "hats",        name: "Hats & Headwear",    h: "Rep Hats, Caps & Beanies" },
  Toys:        { slug: "toys",        name: "Toys",               h: "Toy & Building-Set Finds" },
};
export const CAT_BY_SLUG = Object.fromEntries(Object.entries(CATS).map(([k, v]) => [v.slug, k]));

const REFS = { mycnbox: "LHYDVW", kakobuy: "w5war", lovegobuy: "9WJ54Y", oopbuy: "LHQC0OS8O", sugargoo: "3751749728009774836" };
export function origUrl(p) {
  const id = p.itemId || p.id;
  if (p.platform === "taobao") return `https://item.taobao.com/item.htm?id=${id}`;
  if (p.platform === "1688") return `https://detail.1688.com/offer/${id}.html`;
  return `https://weidian.com/item.html?itemID=${id}`;
}
export const AGENTS = {
  mycnbox:   { name: "MyCNBox",   build: p => `https://mycnbox.com/goodsDetail?mallType=${p.platform}&itemId=${p.itemId || p.id}&referId=${REFS.mycnbox}` },
  kakobuy:   { name: "KakoBuy",   build: p => `https://www.kakobuy.com/item/details?url=${encodeURIComponent(origUrl(p))}&affcode=${REFS.kakobuy}` },
  oopbuy:    { name: "Oopbuy",    build: p => `https://oopbuy.com/product/${p.platform}/${p.itemId || p.id}?inviteCode=${REFS.oopbuy}` },
  lovegobuy: { name: "LoveGoBuy", build: p => `https://www.lovegobuy.com/product?platform=${p.platform}&id=${p.itemId || p.id}&invite_code=${REFS.lovegobuy}` },
  sugargoo:  { name: "Sugargoo",  build: p => `https://www.sugargoo.com/#/home/productDetail?productLink=${encodeURIComponent(origUrl(p))}&memberId=${REFS.sugargoo}` },
};

// ------------------------------------------------------------------ helpers
export const esc = s => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
export const slug = s => String(s).toLowerCase().replace(/&/g, " and ").replace(/['’]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
// Prices: one source of truth, the CNY listing price × the same USD rate the SPA uses (CUR.USD.rate).
// Seller placeholder prices (¥1–4 "ask me", ¥99,999+ "not for sale") are not real prices.
export const USD_RATE = 0.14;
export const isPH = cny => !(cny >= 5 && cny < 99999);
export const money = cny => { const v = Math.round((+cny || 0) * USD_RATE); return isPH(cny) ? "Ask seller" : "$" + Math.max(1, v).toLocaleString("en-US"); };
export function rawImg(p) {
  const i = p.img || ""; const k = i.charAt(0);
  return PREFIX[k] && i.charAt(1) !== ":" ? PREFIX[k] + i.slice(1) : i;
}
export function imgSrc(p) {
  const r = rawImg(p); if (!r) return "";
  if (r.charAt(0) === "/") return SITE + r;            // images hosted on the site itself (/img/p/<id>.webp)
  return /\.supabase\.co\/storage\/v1\/object\/public\//.test(r) ? SITE + "/api/img?u=" + encodeURIComponent(r) : r;
}
// Grid thumbnails (22 Oct 2026): the cards show photos about 200 px wide, so they load a 400 px copy made by Cloudflare
// image resizing (AVIF/WebP, ~90% fewer bytes) instead of the 1000-1200 px original. Only our own paths can be resized
// (/img/p/... and the /api/img proxy for Supabase photos). The original stays in data-o for when resizing fails.
export const THUMB = "/cdn-cgi/image/width=400,quality=75,format=auto";
export function thumbSrc(src) {
  if (!src || src.indexOf(SITE + "/") !== 0) return src;
  const path = src.slice(SITE.length);
  return /^\/(img\/|api\/img\?)/.test(path) ? SITE + THUMB + path : src;
}
export const IMG_FALLBACK = `onerror="if(this.dataset.o){this.src=this.dataset.o;this.dataset.o=''}else this.remove()"`;
export const productUrl = p => "/product/" + encodeURIComponent(p.id);
export const brandUrl = b => { const s = idx().brandSlug.get(b); return s ? "/brand/" + s : null; };
export const catUrl = c => CATS[c] ? "/category/" + CATS[c].slug : null;
const ld = o => '<script type="application/ld+json">' + JSON.stringify(o).replace(/</g, "\\u003c") + "</script>";

export function card(p, lazy = true) {
  const src = imgSrc(p);
  return `<a class="c" href="${productUrl(p)}">` +
    `<span class="ci">${src ? `<img src="${esc(thumbSrc(src))}" data-o="${esc(src)}" alt="${esc(p.title)}" width="300" height="375"${lazy ? ' loading="lazy"' : ""} decoding="async" ${IMG_FALLBACK}>` : ""}` +
    `${p.qc >= 2 ? `<span class="qb">QC</span>` : ""}</span>` +
    `<span class="cb">${p.brand ? `<span class="cbr">${esc(p.brand)}</span>` : ""}<span class="ct">${esc(p.title)}</span><span class="cp">${money(p.cny)}${isPH(p.cny) ? "" : ` <small>¥${p.cny}</small>`}</span></span></a>`;
}
export const grid = (list, eager = 0) => `<div class="g">${list.map((p, i) => card(p, i >= eager)).join("")}</div>`;

export function crumbs(items) {
  const html = `<nav class="bc" aria-label="Breadcrumb">${items.map((it, i) => i < items.length - 1 ? `<a href="${it[1]}">${esc(it[0])}</a><span aria-hidden="true">›</span>` : `<span aria-current="page">${esc(it[0])}</span>`).join("")}</nav>`;
  const data = { "@context": "https://schema.org", "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({ "@type": "ListItem", position: i + 1, name: it[0], item: SITE + it[1] })) };
  return { html, data };
}

export function pager(base, page, pages) {
  if (pages <= 1) return "";
  const u = n => n === 1 ? base : `${base}/${n}`;
  let out = '<nav class="pg" aria-label="Pages">';
  if (page > 1) out += `<a href="${u(page - 1)}" rel="prev">← Previous</a>`;
  for (let n = 1; n <= pages; n++) {
    if (n === page) out += `<span aria-current="page">${n}</span>`;
    else if (n === 1 || n === pages || Math.abs(n - page) <= 2) out += `<a href="${u(n)}">${n}</a>`;
    else if (Math.abs(n - page) === 3) out += "<i>…</i>";
  }
  if (page < pages) out += `<a href="${u(page + 1)}" rel="next">Next →</a>`;
  return out + "</nav>";
}

// ------------------------------------------------------------------ layout
// Styles live in /ds.css (the design system, see DESIGN.md); bump DS_VER when that file changes so browsers fetch it again.
export const DS_VER = "12";

export const GUIDE_LINKS = [
  ["How to order (video)", "/how-to-order"],
  ["How to buy from Weidian", "/guides/how-to-buy-from-weidian"],
  ["How to read QC photos", "/guides/how-to-qc"],
  ["Rep sizing guide", "/guides/sizing"],
  ["Best shopping agent", "/guides/best-shopping-agent"],
  ["How to buy from Taobao", "/guides/how-to-buy-from-taobao"],
  ["How to buy from 1688", "/guides/how-to-buy-from-1688"],
  ["MyCNBox review", "/guides/mycnbox-review"],
  ["KakoBuy vs MyCNBox", "/guides/kakobuy-vs-mycnbox"],
  ["Shipping lines explained", "/guides/shipping-lines"],
  ["What is a rep spreadsheet?", "/guides/what-is-a-rep-spreadsheet"],
  ["Pandabuy alternatives", "/guides/pandabuy-alternatives"],
  ["Rep terms glossary (GL/RL, W2C…)", "/guides/rep-glossary"],
  ["W2C: how to find any rep", "/guides/how-to-find-reps"],
  ["MyCNBox coupon code ($500)", "/guides/mycnbox-coupon-code"],
  ["KakoBuy coupon code ($410)", "/guides/kakobuy-coupon-code"],
  ["All agent sign-up bonuses", "/guides/agent-coupons"],
];
// The guides in every footer (28 Oct 2026): the ones with the most Search Console impressions (28 days to 26 Oct: rep
// spreadsheet 3,689, Pandabuy alternatives 3,611, MyCNBox review 2,317, Weidian 2,086, QC 1,221, best agent 746), not the
// first 7 of GUIDE_LINKS, which gave site-wide links to Taobao (153) and 1688 and none to the top three.
export const FOOTER_GUIDES = ["/how-to-order", "/guides/what-is-a-rep-spreadsheet", "/guides/pandabuy-alternatives", "/guides/mycnbox-review",
  "/guides/how-to-buy-from-weidian", "/guides/how-to-qc", "/guides/best-shopping-agent"];
export const TOOL_LINKS = [["Link converter", "/tools/link-converter"], ["QC checker", "/tools/qc-checker"], ["Weight estimator", "/tools/weight-estimator"], ["Shipping calculator", "/tools/shipping-calculator"]];

function footer() {
  const { byBrand, brandSlug } = idx();
  const largest = [...brandSlug.keys()].sort((a, b) => byBrand.get(b).length - byBrand.get(a).length).slice(0, FOOTER_LARGEST);
  const searched = FOOTER_BRANDS.filter(b => brandSlug.has(b));
  const topBrands = searched.concat(largest.filter(b => !searched.includes(b))).map(b => [b + " reps", "/brand/" + brandSlug.get(b)]);
  const half = Math.ceil(topBrands.length / 2);
  const col = (t, links) => `<div><h4>${t}</h4>${links.map(([n, u]) => `<a href="${u}">${esc(n)}</a>`).join("")}</div>`;
  return `<footer class="f"><div class="w"><div class="cols">
${col("Categories", Object.values(CATS).filter(c => c.slug !== "toys").map(c => [c.name, "/category/" + c.slug]))}
${col("Brands", topBrands.slice(0, half))}
${col("More brands", topBrands.slice(half).concat([["All brands →", "/brands"]]))}
${col("Spreadsheets", [["MyCNBox spreadsheet", "/mycnbox-spreadsheet"], ["KakoBuy spreadsheet", "/kakobuy-spreadsheet"], ["Oopbuy spreadsheet", "/oopbuy-spreadsheet"], ["LoveGoBuy spreadsheet", "/lovegobuy-spreadsheet"], ["Sugargoo spreadsheet", "/sugargoo-spreadsheet"], ["Old money spreadsheet", "/old-money"], ["Stockholm style spreadsheet", "/stockholm-spreadsheet"], ["Grisch spreadsheet", "/grisch-spreadsheet"]])}
${col("Guides", FOOTER_GUIDES.map(u => GUIDE_LINKS.find(g => g[1] === u)).filter(Boolean).concat([["All guides →", "/guides"]]))}
${col("Tools & best reps", TOOL_LINKS.concat([["Best reps by model →", "/best"]]))}
${col("Puro Classico", [["Browse all finds", "/"], ["How we check", "/guides/how-we-check"], ["Discord community", "/discord"], ["Terms", "/terms"], ["Privacy", "/privacy"]])}
</div><p class="disc">Puro Classico is an independent directory of third-party listings on Weidian, Taobao and 1688. We don't sell, stock or ship any products, and we are not affiliated with, endorsed by or connected to any brand named on this site; brand names are used only to describe listings. Links to shopping agents are affiliate links: we may earn a commission if you order, at no extra cost to you. Prices are shown as listed by the seller and can change.</p><p class="legal">© Puro Classico</p></div></footer>`;
}

// v8 (28 Oct 2026): the two page states ds.css styles, set here because server pages run no app script. Each part is
// in its own try, so a browser without one of these APIs only misses that effect.
//   header.h.scrolled: past 8 px of scroll the glass bar firms up and shows its shadow. The listener is passive and
//     only touches the class when the state flips. how-to-order, privacy and terms carry the same header snippet.
//   .rv (scroll reveal): only on section headings and blocks whose top is below the first screen, so nothing visible
//     at load ever starts faded; never on product grids, the product photo or the QC heading. Only where ds.css can
//     drive it (animation-timeline: view()) and motion is not reduced. ds.css animates .rv only, and this list must
//     stay equal to the one in its "scroll reveal" comment. The positions are read once the web fonts have settled
//     (the first layout requests them, document.fonts.ready waits for them): with the fallback font a block can sit
//     just below the fold and then move up into view when Instrument Sans swaps in. A block inside one that is
//     already marked is skipped, so a nested heading or table never fades twice. Printing drops every .rv first (and
//     stops further marking): a scroll-scrubbed block below the scroll position would print in its faded start state.
const V8_JS = `<script>(function(){try{var h=document.querySelector("header.h");if(h){var on=null,f=function(){var s=(window.scrollY||window.pageYOffset||0)>8;if(s!==on){on=s;h.classList.toggle("scrolled",s)}};f();addEventListener("scroll",f,{passive:true})}}catch(e){}` +
  `try{if(window.CSS&&CSS.supports&&CSS.supports("animation-timeline","view()")&&!matchMedia("(prefers-reduced-motion: reduce)").matches&&!(function(){try{var n=performance.getEntriesByType("navigation")[0];return n&&/back_forward|reload/.test(n.type)}catch(e){return false}})()){var done=0,mark=function(){try{if(done)return;var H=innerHeight;` +
  `[].forEach.call(document.querySelectorAll("main h2:not(.qc-h),main .faq,main .steps,main .note,main .prose table"),function(e){if(e.getBoundingClientRect().top>H&&!e.parentElement.closest(".rv"))e.classList.add("rv")})}catch(e){}};` +
  `addEventListener("beforeprint",function(){try{done=1;[].forEach.call(document.querySelectorAll(".rv"),function(e){e.classList.remove("rv")})}catch(e){}});` +
  `requestAnimationFrame(function(){try{void document.body.offsetHeight;var F=document.fonts;if(F&&F.ready)F.ready.then(mark,mark);else mark()}catch(e){}})}}catch(e){}})();</script>`;

export function page({ title, desc, path, body, jsonld = [], robots = "index,follow,max-image-preview:large", image, status = 200, extraHead = "" }) {
  const url = SITE + path;
  if (title.length > 60) title = title.replace(/ [·|] Puro Classico$/, "");   // Google shows about 60 characters, and prints the site name above every result anyway
  const img = image || SITE + "/og.png";
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}">
<meta name="robots" content="${robots}">
${status === 200 ? `<link rel="canonical" href="${esc(url)}">` : ""}
<meta property="og:type" content="website"><meta property="og:site_name" content="Puro Classico">
<meta property="og:title" content="${esc(title)}"><meta property="og:description" content="${esc(desc)}">
<meta property="og:url" content="${esc(url)}"><meta property="og:image" content="${esc(img)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="${esc(title)}"><meta name="twitter:description" content="${esc(desc)}"><meta name="twitter:image" content="${esc(img)}">
<meta name="theme-color" content="#0B0D10"><link rel="icon" type="image/png" href="/favicon.png">
<script>try{var t=localStorage.getItem("manifest.theme");if(t==="light"){document.documentElement.setAttribute("data-theme","light");var m=document.querySelector('meta[name="theme-color"]');if(m)m.content="#F5F5F7";}}catch(e){}</script>
<link rel="preload" href="/fonts/instrument-sans-latin.woff2" as="font" type="font/woff2" crossorigin><style>@font-face{font-family:"Instrument Sans";font-style:normal;font-weight:400 700;font-display:swap;src:url(/fonts/instrument-sans-latin.woff2) format("woff2");unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}@font-face{font-family:"JetBrains Mono";font-style:normal;font-weight:400 500;font-display:swap;src:url(/fonts/jetbrains-mono-latin.woff2) format("woff2");unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}</style>
<link rel="stylesheet" href="/ds.css?v=${DS_VER}">
${jsonld.map(ld).join("\n")}
${extraHead}
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<header class="h"><div class="w"><a href="/" aria-label="Puro Classico home"><span class="logo" role="img" aria-label="Puro Classico"></span></a>
<nav aria-label="Main">${[["/", "Browse finds"], ["/brands", "Brands"], ["/best", "Best reps"], ["/old-money", "Old money"], ["/guides", "Guides"], ["/tools", "Tools"], ["/how-to-order", "How to order"]].map(([u, t]) => `<a href="${u}"${u !== "/" && (path === u || path.startsWith(u + "/")) ? ' aria-current="page"' : ""}>${t}</a>`).join("")}</nav>
<a class="btn red hcta" href="${MYCNBOX_INVITE}" target="_blank" rel="sponsored noopener">Claim $500 MyCNBox coupons</a></div></header>
<main id="main"><div class="w">
${body}
</div></main>
${footer()}
${V8_JS}
<script src="/track.js" defer></script>
</body>
</html>`;
  return new Response(html, { status, headers: { "content-type": "text/html; charset=utf-8",
    "cache-control": status === 200 ? "public, max-age=300, s-maxage=3600" : "public, max-age=60" } });
}

export function notFound(path) {
  const { all } = idx();
  const body = `<h1>Page not found</h1><p class="lead">That page doesn't exist (or the find was removed). Try one of these instead.</p>
<div class="chips"><a href="/">Browse all finds</a><a href="/brands">All brands</a><a href="/category/sneakers">Sneakers</a><a href="/category/jackets">Jackets</a><a href="/old-money">Old money</a><a href="/how-to-order">How to order</a></div>
<h2>Popular right now</h2>${grid(all.slice(0, 12))}`;
  return page({ title: "Page not found · Puro Classico", desc: "This page doesn't exist.", path, body, robots: "noindex,follow", status: 404 });
}
