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

// v9 product card (29 Oct 2026), the rep-find pattern: square photo well, brand, title (2 lines), price, then two
// small pills: "QC" (to the QC photos on the find's page, only for finds marked as having them) and a black "Buy"
// (the MyCNBox link; AGENT_SWAP_JS below points it at the visitor's own agent from the app's saved state).
// The card is a <div>: a link cannot hold the two pill links, so the photo and text are one link and the pills two more.
export const QC_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>';
export function card(p, lazy = true) {
  const src = imgSrc(p), u = productUrl(p), ag = AGENTS.mycnbox;
  return `<div class="c"><a class="cl" href="${u}">` +
    `<span class="ci">${src ? `<img src="${esc(thumbSrc(src))}" data-o="${esc(src)}" alt="${esc(p.title)}" width="300" height="300"${lazy ? ' loading="lazy"' : ""} decoding="async" ${IMG_FALLBACK}>` : ""}</span>` +
    `<span class="cb">${p.brand ? `<span class="cbr">${esc(p.brand)}</span>` : ""}<span class="ct">${esc(p.title)}</span><span class="cp">${money(p.cny)}${isPH(p.cny) ? "" : ` <small>¥${p.cny}</small>`}</span></span></a>` +
    `<span class="ca">${p.qc >= 1 ? `<a class="cq" href="${u}#qc" aria-label="QC photos: ${esc(p.title)}">${QC_ICON}QC</a>` : ""}` +
    `<a class="cbuy" href="${esc(ag.build(p))}" data-agent="mycnbox" data-pl="${esc(p.platform)}" data-iid="${esc(p.itemId || p.id)}" target="_blank" rel="sponsored nofollow noopener" aria-label="Buy ${esc(p.title)} via ${ag.name}">Buy</a></span></div>`;
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
export const DS_VER = "14";

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
export const TOOL_LINKS = [["QC Checker", "/tools/qc-checker"], ["Link Converter", "/tools/link-converter"], ["Shipping Calculator", "/tools/shipping-calculator"], ["Size Estimator", "/tools/size-estimator"], ["Parcel Tracker", "/tools/parcel-tracker"]];

function footer() {
  const { byBrand, brandSlug } = idx();
  const largest = [...brandSlug.keys()].sort((a, b) => byBrand.get(b).length - byBrand.get(a).length).slice(0, FOOTER_LARGEST);
  const searched = FOOTER_BRANDS.filter(b => brandSlug.has(b));
  const topBrands = searched.concat(largest.filter(b => !searched.includes(b))).map(b => [b + " reps", "/brand/" + brandSlug.get(b)]);
  const half = Math.ceil(topBrands.length / 2);
  const col = (t, links) => `<div><h4>${t}</h4>${links.map(([n, u]) => `<a href="${u}">${esc(n)}</a>`).join("")}</div>`;
  return `<footer class="f"><div class="w"><div class="ftop">
<div class="fbrand"><span class="logo" role="img" aria-label="Puro Classico"></span><p>The rep spreadsheet: finds from Weidian, Taobao and 1688 with prices, QC photos and one-tap agent links.</p><a class="btn sm" href="/discord">Join the Discord</a></div>
<div class="cols">
${col("Categories", Object.values(CATS).filter(c => c.slug !== "toys").map(c => [c.name, "/category/" + c.slug]))}
${col("Brands", topBrands.slice(0, half))}
${col("More brands", topBrands.slice(half).concat([["All brands →", "/brands"]]))}
${col("Spreadsheets", [["MyCNBox spreadsheet", "/mycnbox-spreadsheet"], ["KakoBuy spreadsheet", "/kakobuy-spreadsheet"], ["Oopbuy spreadsheet", "/oopbuy-spreadsheet"], ["LoveGoBuy spreadsheet", "/lovegobuy-spreadsheet"], ["Sugargoo spreadsheet", "/sugargoo-spreadsheet"], ["Old money spreadsheet", "/old-money"], ["Stockholm style spreadsheet", "/stockholm-spreadsheet"], ["Grisch spreadsheet", "/grisch-spreadsheet"]])}
${col("Guides", FOOTER_GUIDES.map(u => GUIDE_LINKS.find(g => g[1] === u)).filter(Boolean).concat([["All guides →", "/guides"]]))}
${col("Tools & best reps", TOOL_LINKS.concat([["Best reps by model →", "/best"]]))}
${col("Puro Classico", [["Browse all finds", "/"], ["How we check", "/guides/how-we-check"], ["Discord community", "/discord"], ["Terms", "/terms"], ["Privacy", "/privacy"]])}
</div></div><p class="disc">Puro Classico is an independent directory of third-party listings on Weidian, Taobao and 1688. We don't sell, stock or ship any products, and we are not affiliated with, endorsed by or connected to any brand named on this site; brand names are used only to describe listings. Links to shopping agents are affiliate links: we may earn a commission if you order, at no extra cost to you. Prices are shown as listed by the seller and can change.</p><p class="legal">© Puro Classico</p></div></footer>`;
}

// v9 (29 Oct 2026) page scripts. Server pages run no app script, so the few behaviours live here, each in its own try.
// THEME_HEAD runs in <head> before the first paint: the saved choice ("manifest.theme", the app's key) becomes
// data-theme on <html>; anything else is "system" (no attribute, ds.css follows prefers-color-scheme). data-theme-pref
// tells the toggle's icon which of the three it is, and "js" lets ds.css fold the phone nav into the menu button.
// how-to-order.html, privacy.html and terms.html carry copies of THEME_HEAD and PAGE_JS: change them together.
export const THEME_HEAD = `<script>(function(){var d=document.documentElement,t;try{t=localStorage.getItem("manifest.theme")}catch(e){}if(t!=="light"&&t!=="dark")t="system";d.setAttribute("data-theme-pref",t);if(t!=="system")d.setAttribute("data-theme",t);d.classList.add("js");try{var k=t==="dark"||(t==="system"&&matchMedia("(prefers-color-scheme: dark)").matches),m=document.querySelector('meta[name="theme-color"]');if(m)m.content=k?"#0A0A0A":"#FFFFFF"}catch(e){}})();</script>`;
// The theme button cycles system -> light -> dark -> system ("system" removes the key, as a first visit has none).
// The menu button opens the nav on phones (Escape or a tap outside closes it).
const PAGE_JS = `<script>(function(){var d=document.documentElement;try{var b=document.querySelector("[data-theme-toggle]"),L={system:"System",light:"Light",dark:"Dark"},` +
  `tc=function(){try{var t=d.getAttribute("data-theme-pref"),k=t==="dark"||(t==="system"&&matchMedia("(prefers-color-scheme: dark)").matches),m=document.querySelector('meta[name="theme-color"]');if(m)m.content=k?"#0A0A0A":"#FFFFFF"}catch(e){}},` +
  `lb=function(t){if(b){b.setAttribute("aria-label","Theme: "+L[t]+". Change theme");b.title="Theme: "+L[t]}};lb(d.getAttribute("data-theme-pref")||"system");` +
  `if(b)b.addEventListener("click",function(){var c=d.getAttribute("data-theme-pref")||"system",t=c==="system"?"light":c==="light"?"dark":"system";d.setAttribute("data-theme-pref",t);if(t==="system")d.removeAttribute("data-theme");else d.setAttribute("data-theme",t);` +
  `try{if(t==="system")localStorage.removeItem("manifest.theme");else localStorage.setItem("manifest.theme",t)}catch(e){}lb(t);tc()});` +
  `try{matchMedia("(prefers-color-scheme: dark)").addEventListener("change",tc)}catch(e){}}catch(e){}` +
  `try{var h=document.querySelector("header.h"),mb=h&&h.querySelector(".mbtn");if(mb){var set=function(o){h.classList.toggle("open",o);mb.setAttribute("aria-expanded",o?"true":"false")};` +
  `mb.addEventListener("click",function(e){e.stopPropagation();set(!h.classList.contains("open"))});document.addEventListener("click",function(e){if(!h.contains(e.target))set(false)});document.addEventListener("keydown",function(e){if(e.key==="Escape"&&h.classList.contains("open")){set(false);mb.focus()}})}}catch(e){}})();</script>`;
// The card "Buy" pills open MyCNBox; a visitor who picked another agent in the app (manifest.state.agent) gets that
// agent's link instead. The link formats and codes are the same as AGENTS above and the link converter's.
const AGENT_SWAP_JS = `<script>(function(){try{var a=String((JSON.parse(localStorage.getItem("manifest.state")||"{}")||{}).agent||"").replace(/[^a-z0-9]/g,"");if(!a||a==="mycnbox")return;` +
  `var o=function(p,i){return p==="taobao"?"https://item.taobao.com/item.htm?id="+i:p==="1688"?"https://detail.1688.com/offer/"+i+".html":"https://weidian.com/item.html?itemID="+i},` +
  `B={kakobuy:["KakoBuy",function(p,i){return "https://www.kakobuy.com/item/details?url="+encodeURIComponent(o(p,i))+"&affcode=${REFS.kakobuy}"}],oopbuy:["Oopbuy",function(p,i){return "https://oopbuy.com/product/"+p+"/"+i+"?inviteCode=${REFS.oopbuy}"}],` +
  `lovegobuy:["LoveGoBuy",function(p,i){return "https://www.lovegobuy.com/product?platform="+p+"&id="+i+"&invite_code=${REFS.lovegobuy}"}],sugargoo:["Sugargoo",function(p,i){return "https://www.sugargoo.com/#/home/productDetail?productLink="+encodeURIComponent(o(p,i))+"&memberId=${REFS.sugargoo}"}]}[a];if(!B)return;` +
  `[].forEach.call(document.querySelectorAll("a.cbuy[data-iid]"),function(l){l.href=B[1](l.getAttribute("data-pl"),l.getAttribute("data-iid"));l.setAttribute("data-agent",a);l.setAttribute("aria-label",(l.getAttribute("aria-label")||"").replace(/ via [A-Za-z]+$/," via "+B[0]))})}catch(e){}})();</script>`;
const ICON_SYS = '<svg class="i-sys" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>';
const ICON_LIGHT = '<svg class="i-light" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
const ICON_DARK = '<svg class="i-dark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/></svg>';
const ICON_MENU = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>';
export const NAV = [["/", "Finds"], ["/brands", "Brands"], ["/tools", "Tools"], ["/guides", "Guides"], ["/how-to-order", "How to Order"]];
// The header every server page shares (the static pages carry a copy). `path` marks the current section.
export function header(path = "") {
  return `<header class="h"><div class="w"><a href="/" aria-label="Puro Classico home"><span class="logo" role="img" aria-label="Puro Classico"></span></a>
<nav id="pc-nav" aria-label="Main">${NAV.map(([u, t]) => `<a href="${u}"${u !== "/" && (path === u || path.startsWith(u + "/")) ? ' aria-current="page"' : ""}>${t}</a>`).join("")}</nav>
<div class="hr"><a class="hcta" href="${MYCNBOX_INVITE}" target="_blank" rel="sponsored noopener">Claim $500 MyCNBox coupons</a><button class="ibtn tbtn" type="button" data-theme-toggle aria-label="Change theme">${ICON_SYS}${ICON_LIGHT}${ICON_DARK}</button><button class="ibtn mbtn" type="button" aria-expanded="false" aria-controls="pc-nav" aria-label="Menu">${ICON_MENU}</button></div></div></header>`;
}

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
<meta name="theme-color" content="#FFFFFF"><link rel="icon" type="image/png" href="/favicon.png">
${THEME_HEAD}
<link rel="preload" href="/fonts/inter-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/ds.css?v=${DS_VER}">
${jsonld.map(ld).join("\n")}
${extraHead}
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
${header(path)}
<main id="main"><div class="w">
${body}
</div></main>
${footer()}
${PAGE_JS}${body.indexOf('class="cbuy"') >= 0 ? AGENT_SWAP_JS : ""}
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
