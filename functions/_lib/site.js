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

// ------------------------------------------------------------------ icons (v9 icon pass, 29 Oct 2026)
// ONE icon set for every page: 24px grid, 1.75 stroke, round caps and joins, currentColor, own paths in a lucide-like
// style (icons/SPEC.md section 1). ICONS maps a name to the inner markup; ic(name, cls) returns the whole <svg>. Icons are
// decorative (aria-hidden) and always sit next to a visible text label. index.html carries the same names and paths as
// <symbol id="i-NAME"> in its #pc-icons sprite: change both together (icons_check.py in the v9 scratchpad diffs them).
export const ICONS = {
  // reused from the code before the icon pass
  "camera": '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"/><circle cx="12" cy="13.5" r="3.5"/>',
  "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  "box": '<path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5Z"/><path d="M3 7.5 12 12l9-4.5"/><path d="M12 12v9"/>',
  "ruler": '<path d="M3 15.5 15.5 3 21 8.5 8.5 21Z"/><path d="m7 12 1.5 1.5"/><path d="m10 9 2 2"/><path d="m13 6 1.5 1.5"/>',
  "pin": '<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.5"/>',
  "check": '<path d="M20 6 9 17l-5-5"/>',
  "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
  "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 8v4.5"/><path d="M12 16h.01"/>',
  "x": '<path d="M18 6 6 18M6 6l12 12"/>',
  "share": '<path d="M12 3v12"/><path d="m7 8 5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>',
  "ext": '<path d="M14 4h6v6"/><path d="M20 4 10 14"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
  "arrow-right": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
  "chevron-left": '<path d="m15 6-6 6 6 6"/>',
  "chevron-right": '<path d="m9 6 6 6-6 6"/>',
  "chevron-down": '<path d="m6 9 6 6 6-6"/>',
  "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
  "plus": '<path d="M12 5v14M5 12h14"/>',
  "minus": '<path d="M5 12h14"/>',
  "paste": '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6v3H9z"/>',
  "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  "star": '<path d="M12 3.6l2.5 5.2 5.7.8-4.1 4 1 5.7L12 16.9 6.9 19.3l1-5.7-4.1-4 5.7-.8z"/>',
  "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  "moon": '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
  "monitor": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
  "shoe": '<path d="M2.5 9.5 6 10.5l2.5-2 2.5 2.5 2.5 2.5 5.5 1.5a2.5 2.5 0 0 1 2 2.5V18H2.5Z"/><path d="M2.5 15h19"/><path d="M9.5 11.5l1.5-1"/><path d="M11.5 13.5l1.5-1"/>',
  "tee": '<path d="M8.5 3.5 4 6 2.5 10l3.5 1.5V20.5h12V11.5L21.5 10 20 6l-4.5-2.5a3.5 3.5 0 0 1-7 0Z"/>',
  "jacket": '<path d="M8.5 3.5 4 6 2.5 10l3.5 1.5V20.5h12V11.5L21.5 10 20 6l-4.5-2.5L12 7Z"/><path d="M12 7v13.5"/><path d="M8.5 3.5 12 7l3.5-3.5"/>',
  "hoodie": '<path d="M8 4 3.5 7 5 11.5l2-.8V21h10V10.7l2 .8L20.5 7 16 4"/><path d="M8 4a4 4 0 0 0 8 0"/><path d="M10.5 8.5v3M13.5 8.5v3"/>',
  "pants": '<path d="M6.5 3h11l1 18h-5L12 10l-1.5 11h-5Z"/><path d="M6.5 6.5h11"/>',
  "shorts": '<path d="M5.5 5h13l1.5 10.5h-6L12 10.5l-2 5H4Z"/><path d="M5.5 8h13"/>',
  "bag": '<path d="M5 8.5h14l-1 12H6Z"/><path d="M9 8.5V7a3 3 0 0 1 6 0v1.5"/>',
  "watch": '<path d="M9 7.5 9.7 3h4.6l.7 4.5"/><path d="M9 16.5l.7 4.5h4.6l.7-4.5"/><path d="M12 10v2.2l1.4 1"/><circle cx="12" cy="12" r="5"/>',
  "cap": '<path d="M4 15.5a8 8 0 0 1 16 0Z"/><path d="M12 7.5V6"/><path d="M15 15.5h6.5"/>',
  // new in the icon pass
  "store": '<path d="M4 10v10h16V10"/><path d="M3 10 5 4h14l2 6a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0Z"/><path d="M10 20v-5h4v5"/>',
  "tag": '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9Z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  "coins": '<circle cx="9" cy="9" r="6"/><path d="M15.5 9.2A6 6 0 1 1 9.2 15.5"/><path d="M9 6.5v5M7.5 8h3"/>',
  "hash": '<path d="M5 9h14M5 15h14M10 4 8 20M16 4l-2 16"/>',
  "scale": '<path d="M6.5 8h11l2.5 12H4Z"/><circle cx="12" cy="5.5" r="2.5"/>',
  "chart": '<path d="M4 20V11M10 20V4M16 20v-6M3 20h18"/>',
  "layers": '<path d="m12 3 9 5-9 5-9-5Z"/><path d="m3 13 9 5 9-5"/>',
  "sheet": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v16"/>',
  "grid": '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
  "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>',
  "flame": '<path d="M12 21a6.5 6.5 0 0 0 6.5-6.5c0-4-3-6-3.5-9.5-2 1.5-3 3.5-3 5.5-1-1-1.5-2-1.5-3.5C8 9 5.5 11.5 5.5 14.5A6.5 6.5 0 0 0 12 21Z"/>',
  "award": '<circle cx="12" cy="9" r="6"/><path d="m8.5 14-1.5 7 5-2.5 5 2.5-1.5-7"/>',
  "truck": '<path d="M2.5 6.5h11v10h-11Z"/><path d="M13.5 10h4l3 3.5v3h-7"/><circle cx="7" cy="17.5" r="1.75"/><circle cx="17" cy="17.5" r="1.75"/>',
  "home": '<path d="M3.5 10.5 12 4l8.5 6.5V20H15v-5.5H9V20H3.5Z"/>',
  "warehouse": '<path d="M3 20V9l9-5 9 5v11"/><path d="M7 20v-7h10v7M7 16.5h10"/>',
  "user": '<circle cx="12" cy="8" r="3.5"/><path d="M5 20a7 7 0 0 1 14 0"/>',
  "user-plus": '<circle cx="10" cy="8" r="3.5"/><path d="M3.5 20a6.5 6.5 0 0 1 13 0"/><path d="M19 8v6M16 11h6"/>',
  "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.2a6.5 6.5 0 0 1 3.5 5.8"/>',
  "cart": '<circle cx="9" cy="20" r="1.25"/><circle cx="18" cy="20" r="1.25"/><path d="M2.5 3.5H5l2.5 12h11l2-8.5H6"/>',
  "card": '<rect x="2.5" y="5.5" width="19" height="13" rx="2"/><path d="M2.5 10h19M6.5 15h3"/>',
  "shield": '<path d="M12 3 5 6v5.5c0 4.2 3 7.8 7 9.5 4-1.7 7-5.3 7-9.5V6Z"/><path d="m9 12 2 2 4-4"/>',
  "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.5h.01"/>',
  "bulb": '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.4 1 1.1 1 1.8V16h5v-.3c0-.7.4-1.4 1-1.8A6 6 0 0 0 12 3Z"/>',
  "list": '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01"/>',
  "book": '<path d="M12 6.5C10.5 5 8 4.5 3 4.5v14c5 0 7.5.5 9 2 1.5-1.5 4-2 9-2v-14c-5 0-7.5.5-9 2Z"/><path d="M12 6.5v14"/>',
  "play": '<circle cx="12" cy="12" r="9"/><path d="m10 8.5 5 3.5-5 3.5Z"/>',
  "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.4"/><path d="M12 17h.01"/>',
  "message": '<path d="M4 5h16v11H9l-5 4Z"/>',
  "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  "zap": '<path d="M13 2.5 4.5 13.5H12l-1 8 8.5-11H12Z"/>',
  "gift": '<rect x="3.5" y="8" width="17" height="4" rx="1"/><path d="M5 12v8.5h14V12M12 8v12.5"/><path d="M12 8c-2 0-4.5-.6-4.5-2.6A1.9 1.9 0 0 1 9.4 3.5C11.3 3.5 12 8 12 8Zm0 0c2 0 4.5-.6 4.5-2.6a1.9 1.9 0 0 0-1.9-1.9C12.7 3.5 12 8 12 8Z"/>',
  "sliders": '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  "x-circle": '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
  "scissors": '<circle cx="6" cy="6.5" r="2.5"/><circle cx="6" cy="17.5" r="2.5"/><path d="M8 8.5 20 18M8 15.5 20 6"/>',
  "palette": '<path d="M12 3a9 9 0 0 0 0 18c1.1 0 1.5-.8 1.5-1.5 0-1.2-1-1.5-1-2.5s.7-1.5 1.5-1.5H16a5 5 0 0 0 5-5c0-4.1-4-7.5-9-7.5Z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7" r="1"/><circle cx="15" cy="7.5" r="1"/>',
  "type": '<path d="M5 6.5V4.5h14v2M12 4.5v15M9 19.5h6"/>',
  "split": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/>',
  "refresh": '<path d="M20 11a8 8 0 0 0-14.5-4.5L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.5 4.5L20 16"/><path d="M20 20v-4h-4"/>',
};
// ic("camera") -> <svg class="ic" ...>; ic("gift", "sm") is the 16px inline size; extra class names (i-sys, i-cp...) go
// in the same string. Fixed width/height attributes keep the layout still while ds.css loads.
export function ic(name, cls = "") {
  const sm = /(^|\s)sm(\s|$)/.test(cls), px = sm ? 16 : 20;
  return `<svg class="ic${cls ? " " + cls : ""}" width="${px}" height="${px}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${ICONS[name] || ICONS.info}</svg>`;
}
// A round muted tile holding an icon (the .v9-cat-ic / .tk-ic look): <span class="ic-tile">
export const icTile = (name, cls = "") => `<span class="ic-tile${cls ? " " + cls : ""}" aria-hidden="true">${ic(name)}</span>`;

// v9 product card (29 Oct 2026), the rep-find pattern: square photo well, brand, title (2 lines), price, then two
// small pills: "QC" (to the QC photos on the find's page, only for finds marked as having them) and a black "Buy"
// (the MyCNBox link; AGENT_SWAP_JS below points it at the visitor's own agent from the app's saved state).
// The card is a <div>: a link cannot hold the two pill links, so the photo and text are one link and the pills two more.
export const QC_ICON = ic("camera");
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
  if (page > 1) out += `<a href="${u(page - 1)}" rel="prev">${ic("chevron-left", "sm")}Previous</a>`;
  for (let n = 1; n <= pages; n++) {
    if (n === page) out += `<span aria-current="page">${n}</span>`;
    else if (n === 1 || n === pages || Math.abs(n - page) <= 2) out += `<a href="${u(n)}">${n}</a>`;
    else if (Math.abs(n - page) === 3) out += "<i>…</i>";
  }
  if (page < pages) out += `<a href="${u(page + 1)}" rel="next">Next${ic("chevron-right", "sm")}</a>`;
  return out + "</nav>";
}

// ------------------------------------------------------------------ layout
// Styles live in /ds.css (the design system, see DESIGN.md); bump DS_VER when that file changes so browsers fetch it again.
export const DS_VER = "18";

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

// ------------------------------------------------------------------ v9 tools kit (shared by pages.js and tools9.js)
// Markup helpers for the tool pages (styles: the "v9 tools kit" block in ds.css). One icon set for the homepage
// tool cards (index.html .v9-tool-ic), the tools hub and every tool page.
// Built from ICONS (stroke 1.75 everywhere); the names stay so pages.js and the inline scripts keep working.
export const TK_ICONS = { "qc-checker": ic("camera"), "link-converter": ic("link"), "shipping-calculator": ic("box"), "size-estimator": ic("ruler"), "parcel-tracker": ic("pin") };
// Small UI icons (16 to 20px in the kit). Use with class names from ds.css (.i-cp/.i-ok inside .tk-copy).
export const TK_I = { check: ic("check"), copy: ic("copy"), alert: ic("alert"), x: ic("x"), link: ic("link"), share: ic("share"), ext: ic("ext"),
  right: ic("arrow-right"), prev: ic("chevron-left"), next: ic("chevron-right"), image: ic("image") };
// One line per tool (the homepage v9_tool_*_d strings), for the hub and the "More Free Tools" cards.
export const TOOL_ONE = {
  "qc-checker": "See real buyer photos of any listing.",
  "link-converter": "Turn any seller link into agent buy links.",
  "shipping-calculator": "Ballpark your parcel cost by weight and country.",
  "size-estimator": "Find your size from height, weight and fit.",
  "parcel-tracker": "Spot the carrier and track your parcel.",
};
export const TK_TRUST = { free: "Free", nosign: "No sign-up", local: "Runs in your browser", nostore: "Nothing is stored" };
// <header class="tk-hero">: icon tile (omit slug for the hub), tool name above the h1, lead, trust facts.
export function tkHero({ slug = "", name = "", h1, lead, trust = [] }) {
  return `<header class="tk-hero">${slug && TK_ICONS[slug] ? `<span class="tk-hero-ic">${TK_ICONS[slug]}</span>` : ""}${name ? `<p class="tk-name">${esc(name)}</p>` : ""}` +
    `<h1>${esc(h1)}</h1><p class="lead">${esc(lead)}</p>` +
    (trust.length ? `<ul class="tk-trust">${trust.map(t => `<li>${TK_I.check}${esc(t)}</li>`).join("")}</ul>` : "") + `</header>`;
}
// "More Free Tools": the 4 other tools as compact cards, then the How to order link.
export function tkRelated(path) {
  return `<h2 class="h-ic">${icTile("grid")}More Free Tools</h2><div class="tk-related">${TOOL_LINKS.filter(([, u]) => u !== path).map(([n, u]) => { const k = u.replace(/^\/tools\//, "");
    return `<a href="${u}"><span class="tk-ic">${TK_ICONS[k] || ""}</span><span><b>${esc(n)}</b><span>${esc(TOOL_ONE[k] || "")}</span></span></a>`; }).join("")}</div>` +
    `<p><a class="more" href="/how-to-order">${ic("play", "sm")}How to order</a></p>`;
}
// A copy button for the kit (TK.copy swaps the icon and label for 1.5 s): <button class="btn sm tk-copy" data-copy="...">
export const tkCopyBtn = (label = "Copy", attrs = "") => `<button type="button" class="btn sm tk-copy"${attrs}>${ic("copy", "i-cp")}${ic("check", "i-ok")}<span class="l">${esc(label)}</span></button>`;
// "How It Works" (icon pass): three icon steps that restate the tool's own text, then that text (the SEO copy, with its
// links) in a <details> right under them. toolShell() and tools9.js toolPage9() both use it.
export const TOOL_HOW = {
  "qc-checker": [["link", "Paste link"], ["camera", "Buyer photos"], ["book", "QC guide"]],
  "link-converter": [["link", "Paste any link"], ["hash", "We read the item ID"], ["users", "Pick your agent"]],
  "shipping-calculator": [["globe", "Pick your country"], ["box", "Add items or weight"], ["coins", "See ballpark prices"]],
  "size-estimator": [["ruler", "Height and weight"], ["user", "Pick your fit"], ["tag", "Get your size label"]],
  "parcel-tracker": [["paste", "Paste the number"], ["truck", "Carrier detected"], ["ext", "Open tracking"]],
};
export const icSteps = steps => `<ol class="ic-steps">${steps.map(([n, t]) => `<li>${icTile(n)}<span>${esc(t)}</span></li>`).join("")}</ol>`;
export const more = (label, html) => `<details class="more"><summary>${esc(label)}${ic("chevron-down", "sm")}</summary>${html}</details>`;
export const howItWorks = (slug, about) => `<h2 class="h-ic">${icTile("list")}How It Works</h2>` + (TOOL_HOW[slug] ? icSteps(TOOL_HOW[slug]) + (about ? more("Details", `<div class="prose">${about}</div>`) : "") : `<div class="prose">${about}</div>`);
// The page every tool shares. ui = the tool's card markup + script. about = the SEO text (kept, shown under "How It Works").
// jsonld is passed through unchanged so the structured data stays byte-identical.
export function toolShell({ slug, name, h1, lead, trust = [], ui, about = "", faq = "", title, desc, jsonld = [], wide = false, bc }) {
  const path = "/tools/" + slug;
  const body = `<div class="tk-page${wide ? " wide" : ""}">${bc}${tkHero({ slug, name, h1, lead, trust })}${ui}` +
    `<div class="tk-below">${howItWorks(slug, about)}${faq}${tkRelated(path)}</div></div>`;
  return page({ title, desc, path, body, jsonld });
}
// Client helpers every tool page inlines once (ES5, no libraries): window.TK.
// TK.esc, TK.copy(text, btn, msg), TK.say(msg), TK.debounce(fn, ms), TK.qs.get(k) / TK.qs.set({k: v}) (replaceState,
// 300 ms debounce), TK.recent(key, max).list/add(item, same)/remove(i)/clear, TK.seg(el, onChange) (roving radiogroup),
// TK.pasteBtn(input, btn), TK.ago(t), TK.store(get|set) on localStorage and TK.sess on sessionStorage (all in try/catch).
export const TK_JS = String.raw`var TK=(function(){var D=document;
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c];});}
function say(m){var r=D.getElementById("tk-live");if(!r){r=D.createElement("div");r.id="tk-live";r.className="vh";r.setAttribute("aria-live","polite");D.body.appendChild(r);}r.textContent="";setTimeout(function(){r.textContent=m;},40);}
function copy(t,b,m){function ok(){if(b){var l=b.querySelector(".l");if(l&&!b.getAttribute("data-label"))b.setAttribute("data-label",l.textContent);b.classList.add("ok");if(l)l.textContent="Copied";clearTimeout(b._t);b._t=setTimeout(function(){b.classList.remove("ok");if(l)l.textContent=b.getAttribute("data-label");},1500);}say(m||"Copied");}
function fb(){var a=D.createElement("textarea"),d=false;a.value=t;a.setAttribute("readonly","");a.style.cssText="position:fixed;top:0;left:0;width:1px;height:1px;opacity:0";D.body.appendChild(a);a.select();try{d=D.execCommand("copy");}catch(e){}D.body.removeChild(a);if(d){ok();return;}var x=D.createElement("input");x.readOnly=true;x.value=t;x.className="tk-in tk-copyfb";x.setAttribute("aria-label","Copy this text");x.addEventListener("blur",function(){if(x.parentNode)x.parentNode.removeChild(x);});(b&&b.parentNode?b.parentNode:D.body).insertBefore(x,b?b.nextSibling:null);x.focus();x.select();say("Press Ctrl+C to copy");}
try{if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok,fb);return;}}catch(e){}fb();}
function debounce(f,ms){var h;return function(){var a=arguments,s=this;clearTimeout(h);h=setTimeout(function(){f.apply(s,a);},ms);};}
var pend={},qt;function qget(k){try{return new URLSearchParams(location.search).get(k);}catch(e){return null;}}
function qset(o){for(var k in o)pend[k]=o[k];clearTimeout(qt);qt=setTimeout(function(){try{var u=new URL(location.href);for(var k in pend){if(pend[k]==null||pend[k]==="")u.searchParams.delete(k);else u.searchParams.set(k,pend[k]);}pend={};history.replaceState(history.state,"",u.pathname+(u.search||"")+u.hash);}catch(e){}},300);}
function sget(S,k,d){try{var v=S.getItem(k);return v==null?d:JSON.parse(v);}catch(e){return d;}}function sset(S,k,v){try{if(v==null)S.removeItem(k);else S.setItem(k,JSON.stringify(v));}catch(e){}}
var LS,SS;try{LS=window.localStorage;}catch(e){}try{SS=window.sessionStorage;}catch(e){}
function recent(k,max){max=max||6;function list(){var a=sget(LS,k,[]);return Array.isArray(a)?a:[];}
return{list:list,add:function(it,same){var a=list().filter(function(x){return !same(x,it);});a.unshift(it);sset(LS,k,a.slice(0,max));},remove:function(i){var a=list();a.splice(i,1);sset(LS,k,a);},clear:function(){sset(LS,k,null);}};}
function seg(el,on){var bs=[].slice.call(el.querySelectorAll('[role="radio"]'));function pick(b,fire,focus){bs.forEach(function(x){var c=x===b;x.setAttribute("aria-checked",c?"true":"false");x.tabIndex=c?0:-1;});if(focus)b.focus();if(fire&&on)on(b.getAttribute("data-v"),b);}
bs.forEach(function(b,i){b.addEventListener("click",function(){pick(b,true);});b.addEventListener("keydown",function(e){var j=e.key==="ArrowRight"||e.key==="ArrowDown"?i+1:e.key==="ArrowLeft"||e.key==="ArrowUp"?i-1:e.key==="Home"?0:e.key==="End"?bs.length-1:null;if(j==null)return;e.preventDefault();j=(j+bs.length)%bs.length;pick(bs[j],true,true);});});
var cur=bs.filter(function(b){return b.getAttribute("aria-checked")==="true";})[0]||bs[0];pick(cur,false);
return{get:function(){var c=bs.filter(function(b){return b.getAttribute("aria-checked")==="true";})[0];return c?c.getAttribute("data-v"):"";},set:function(v,fire){var b=bs.filter(function(x){return x.getAttribute("data-v")===String(v);})[0];if(b)pick(b,!!fire);}};}
function pasteBtn(i,b){if(!b)return;try{if(!(navigator.clipboard&&navigator.clipboard.readText))return;}catch(e){return;}b.hidden=false;b.addEventListener("click",function(){navigator.clipboard.readText().then(function(t){t=String(t||"").trim();if(!t){say("Clipboard is empty");return;}i.value=t.slice(0,2000);i.dispatchEvent(new Event("input",{bubbles:true}));i.dispatchEvent(new CustomEvent("tk:paste"));},function(){i.focus();say("Paste with Ctrl+V");});});}
function ago(t){var s=Math.max(0,(Date.now()-t)/1000|0);if(s<60)return"Just now";if(s<3600)return(s/60|0)+" min ago";if(s<86400)return(s/3600|0)+" h ago";var d=s/86400|0;return d===1?"Yesterday":d+" days ago";}
return{esc:esc,say:say,copy:copy,debounce:debounce,qs:{get:qget,set:qset},recent:recent,seg:seg,pasteBtn:pasteBtn,ago:ago,store:{get:function(k,d){return sget(LS,k,d);},set:function(k,v){sset(LS,k,v);}},sess:{get:function(k,d){return sget(SS,k,d);},set:function(k,v){sset(SS,k,v);}}};})();`;

function footer() {
  const { byBrand, brandSlug } = idx();
  const largest = [...brandSlug.keys()].sort((a, b) => byBrand.get(b).length - byBrand.get(a).length).slice(0, FOOTER_LARGEST);
  const searched = FOOTER_BRANDS.filter(b => brandSlug.has(b));
  const topBrands = searched.concat(largest.filter(b => !searched.includes(b))).map(b => [b + " reps", "/brand/" + brandSlug.get(b)]);
  const half = Math.ceil(topBrands.length / 2);
  const FOOT_IC = { "Categories": "grid", "Brands": "tag", "More brands": "tag", "Spreadsheets": "sheet", "Guides": "book", "Tools & best reps": "award", "Puro Classico": "info" };
  const col = (t, links) => `<div><h4>${ic(FOOT_IC[t] || "info", "sm")}${t}</h4>${links.map(([n, u]) => `<a href="${u}">${/ →$/.test(n) ? esc(n.slice(0, -2)) + ic("arrow-right", "sm") : esc(n)}</a>`).join("")}</div>`;
  return `<footer class="f"><div class="w"><div class="ftop">
<div class="fbrand"><span class="logo" role="img" aria-label="Puro Classico"></span><p>The rep spreadsheet: finds from Weidian, Taobao and 1688 with prices, QC photos and one-tap agent links.</p><a class="btn sm" href="/discord">${ic("message", "sm")}Join the Discord</a></div>
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
export const THEME_HEAD = `<script>(function(){var d=document.documentElement,t;try{t=localStorage.getItem("manifest.theme")}catch(e){}if(t!=="light"&&t!=="dark")t="system";d.setAttribute("data-theme-pref",t);if(t!=="system")d.setAttribute("data-theme",t);d.classList.add("js","js-fade");var f=function(e){var i=e.target;if(i&&i.tagName==="IMG")i.classList.add("is-in")};document.addEventListener("load",f,true);document.addEventListener("error",f,true);try{var k=t==="dark"||(t==="system"&&matchMedia("(prefers-color-scheme: dark)").matches),m=document.querySelector('meta[name="theme-color"]');if(m)m.content=k?"#0A0A0A":"#FFFFFF"}catch(e){}})();</script>`;
// js-fade (round 4): ds.css hides a card photo until it has loaded and fades it in; the capture listeners above mark
// every <img> that loaded (or failed) with .is-in, and PAGE_JS marks the ones that were already complete. No JS, no fade.
// The theme button cycles system -> light -> dark -> system ("system" removes the key, as a first visit has none).
// The menu button opens the nav on phones (Escape or a tap outside closes it).
export const PAGE_JS = `<script>(function(){var d=document.documentElement;try{var b=document.querySelector("[data-theme-toggle]"),L={system:"System",light:"Light",dark:"Dark"},` +
  `tc=function(){try{var t=d.getAttribute("data-theme-pref"),k=t==="dark"||(t==="system"&&matchMedia("(prefers-color-scheme: dark)").matches),m=document.querySelector('meta[name="theme-color"]');if(m)m.content=k?"#0A0A0A":"#FFFFFF"}catch(e){}},` +
  `lb=function(t){if(b){b.setAttribute("aria-label","Theme: "+L[t]+". Change theme");b.title="Theme: "+L[t]}};lb(d.getAttribute("data-theme-pref")||"system");` +
  `if(b)b.addEventListener("click",function(){var c=d.getAttribute("data-theme-pref")||"system",t=c==="system"?"light":c==="light"?"dark":"system";d.setAttribute("data-theme-pref",t);if(t==="system")d.removeAttribute("data-theme");else d.setAttribute("data-theme",t);` +
  `try{if(t==="system")localStorage.removeItem("manifest.theme");else localStorage.setItem("manifest.theme",t)}catch(e){}lb(t);tc()});` +
  `try{matchMedia("(prefers-color-scheme: dark)").addEventListener("change",tc)}catch(e){}}catch(e){}` +
  `try{var h=document.querySelector("header.h"),mb=h&&h.querySelector(".mbtn");if(mb){var set=function(o){h.classList.toggle("open",o);mb.setAttribute("aria-expanded",o?"true":"false")};` +
  `mb.addEventListener("click",function(e){e.stopPropagation();set(!h.classList.contains("open"))});document.addEventListener("click",function(e){if(!h.contains(e.target))set(false)});document.addEventListener("keydown",function(e){if(e.key==="Escape"&&h.classList.contains("open")){set(false);mb.focus()}})}}catch(e){}` +
  `try{var tb=document.getElementById("tools-btn"),tm=document.getElementById("tools-menu");if(tb&&tm){var ts=function(o,f){tm.hidden=!o;tb.setAttribute("aria-expanded",o?"true":"false");if(!o&&f)tb.focus()};` +
  `tb.addEventListener("click",function(e){e.stopPropagation();ts(tm.hidden)});document.addEventListener("click",function(e){if(!tm.hidden&&!(e.target.closest&&e.target.closest(".tools-nav")))ts(false)});` +
  `document.addEventListener("keydown",function(e){if(e.key==="Escape"&&!tm.hidden)ts(false,true)})}}catch(e){}` +
  `try{var si=document.getElementById("pcs-hi"),sb=document.getElementById("pcs-hb"),kb=document.querySelector(".pcs-kbd"),mac=/Mac|iPhone|iPad|iPod/.test(navigator.platform||navigator.userAgent||"");if(kb)kb.textContent=mac?"\u2318K":"Ctrl K";` +
  `var go=function(){if(si&&si.getClientRects().length&&si.offsetParent){si.focus();try{si.select()}catch(e){}}else location.href="/?s=1"};if(sb)sb.addEventListener("click",go);` +
  `if(si&&si.form)si.form.addEventListener("submit",function(e){if(!si.value.trim()){e.preventDefault();si.focus()}});` +
  `document.addEventListener("keydown",function(e){var t=e.target,ty=t&&(t.isContentEditable||/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName||""));if(e.isComposing)return;` +
  `if((e.key==="k"||e.key==="K")&&(e.metaKey||e.ctrlKey)&&!e.altKey){e.preventDefault();go()}else if(e.key==="/"&&!ty&&!e.metaKey&&!e.ctrlKey&&!e.altKey){e.preventDefault();go()}})}catch(e){}` +
  `try{[].forEach.call(document.images,function(i){if(i.complete)i.classList.add("is-in")})}catch(e){}})();</script>`;
// The card "Buy" pills open MyCNBox; a visitor who picked another agent in the app (manifest.state.agent) gets that
// agent's link instead. The link formats and codes are the same as AGENTS above and the link converter's.
const AGENT_SWAP_JS = `<script>(function(){try{var a=String((JSON.parse(localStorage.getItem("manifest.state")||"{}")||{}).agent||"").replace(/[^a-z0-9]/g,"");if(!a||a==="mycnbox")return;` +
  `var o=function(p,i){return p==="taobao"?"https://item.taobao.com/item.htm?id="+i:p==="1688"?"https://detail.1688.com/offer/"+i+".html":"https://weidian.com/item.html?itemID="+i},` +
  `B={kakobuy:["KakoBuy",function(p,i){return "https://www.kakobuy.com/item/details?url="+encodeURIComponent(o(p,i))+"&affcode=${REFS.kakobuy}"}],oopbuy:["Oopbuy",function(p,i){return "https://oopbuy.com/product/"+p+"/"+i+"?inviteCode=${REFS.oopbuy}"}],` +
  `lovegobuy:["LoveGoBuy",function(p,i){return "https://www.lovegobuy.com/product?platform="+p+"&id="+i+"&invite_code=${REFS.lovegobuy}"}],sugargoo:["Sugargoo",function(p,i){return "https://www.sugargoo.com/#/home/productDetail?productLink="+encodeURIComponent(o(p,i))+"&memberId=${REFS.sugargoo}"}]}[a];if(!B)return;` +
  `[].forEach.call(document.querySelectorAll("a.cbuy[data-iid]"),function(l){l.href=B[1](l.getAttribute("data-pl"),l.getAttribute("data-iid"));l.setAttribute("data-agent",a);l.setAttribute("aria-label",(l.getAttribute("aria-label")||"").replace(/ via [A-Za-z]+$/," via "+B[0]))})}catch(e){}})();</script>`;
const ICON_SYS = ic("monitor", "i-sys"), ICON_LIGHT = ic("sun", "i-light"), ICON_DARK = ic("moon", "i-dark"), ICON_MENU = ic("menu");
export const NAV = [["/", "Finds"], ["/brands", "Brands"], ["/tools", "Tools"], ["/guides", "Guides"], ["/how-to-order", "How to Order"]];
// The section a path belongs to (round 4, 29 Oct 2026). index.html mirrors it: the homepage markup marks Finds, and
// _middleware.js hubApp() moves aria-current to navKey(spec.path) on the app hubs, so no page marks nothing by accident.
export function navKey(path = "") {
  const p = String(path || "/").replace(/[?#].*$/, "") || "/";
  if (p === "/brands" || p.startsWith("/brand/")) return "brands";
  if (p === "/tools" || p.startsWith("/tools/")) return "tools";
  if (p === "/guides" || p.startsWith("/guides/")) return "guides";
  if (p === "/how-to-order") return "how";
  if (p === "/" || p.startsWith("/category/") || /^\/[^/]*-spreadsheet/.test(p) || p.startsWith("/old-money") || p === "/best" || p.startsWith("/best/") || p.startsWith("/product/")) return "finds";
  return "";
}
const NAV_KEY = { "/": "finds", "/brands": "brands", "/tools": "tools", "/guides": "guides", "/how-to-order": "how" };
// The header search shell (the app's #pcs-hd has the same markup and sizes). Server pages have no catalogue: the form
// is a plain GET to /?q=..., and the button, Cmd/Ctrl+K and "/" focus the field when it shows, else open /?s=1 (PAGE_JS).
const SEARCH_SHELL = `<div class="pcs-hd" id="pcs-hd"><form class="pcs-hf" action="/" method="get" role="search">${ic("search", "sm")}` +
  `<input class="pcs-hi" id="pcs-hi" name="q" type="search" placeholder="Search finds" aria-label="Search finds" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" enterkeyhint="search">` +
  `<kbd class="pcs-kbd" aria-hidden="true">\u2318K</kbd></form><button class="pcs-hb" id="pcs-hb" type="button" aria-label="Search finds">${ic("search")}</button></div>`;
// The header every server page shares (the static pages carry a copy). `path` marks the current section. The nav is the
// app's nav, item for item: same sizes, a Tools link plus a chevron button for the tools menu, and one .nl-pill that sits
// under the active item (ds.css: anchor positioning, view-transition-name nav-pill, so it glides between pages).
export function header(path = "") {
  const on = navKey(path), cur = u => NAV_KEY[u] === on ? ' aria-current="page"' : "";
  const items = NAV.map(([u, t]) => u === "/tools"
    ? `<div class="tools-nav"><a href="/tools"${cur(u)}>${t}</a><button class="tools-btn" id="tools-btn" type="button" aria-expanded="false" aria-haspopup="true" aria-controls="tools-menu" aria-label="Tools menu">${ic("chevron-down", "sm")}</button>` +
      `<div class="tools-menu" id="tools-menu" hidden>${TOOL_LINKS.concat([["All tools", "/tools"]]).map(([n, l]) => `<a href="${l}">${esc(n)}</a>`).join("")}</div></div>`
    : `<a href="${u}"${cur(u)}>${t}</a>`).join("");
  return `<header class="h"><div class="w"><a href="/" aria-label="Puro Classico home"><span class="logo" role="img" aria-label="Puro Classico"></span></a>
<nav id="pc-nav" aria-label="Main">${items}<span class="nl-pill" aria-hidden="true"></span></nav>
${SEARCH_SHELL}<div class="hr"><a class="hcta" href="${MYCNBOX_INVITE}" target="_blank" rel="sponsored noopener">${ic("gift", "sm")}Claim $500 MyCNBox coupons</a><button class="ibtn tbtn" type="button" data-theme-toggle aria-label="Change theme">${ICON_SYS}${ICON_LIGHT}${ICON_DARK}</button><button class="ibtn mbtn" type="button" aria-expanded="false" aria-controls="pc-nav" aria-label="Menu">${ICON_MENU}</button></div></div></header>`;
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
<link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" href="/img/pwa/apple-touch-icon.png">
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
