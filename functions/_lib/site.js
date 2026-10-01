// Shared server-side rendering for the SEO pages (product pages, hubs, guides, sitemaps, 404).
// Everything here is plain HTML + a little CSS so Google sees real content without running JS.
import { ROWS, PREFIX, BUILT } from "./catalog.js";

export const SITE = "https://www.puroclassico.com";
export const MYCNBOX_INVITE = "https://mycnbox.com/login/main-login?inviteCode=AACPYA";
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
  qc: r[8], best: r[9], views: r[10], img: r[11], g: r[12], itemId: r[13], variants: r[14] }));
// Real view stats (data/stats.json, refreshed every 6h by the Stats workflow): { id: [all, 30d, 7d, favourites] }
let VIEWS = {}, VIEWS_AT = 0, VIEWS_VER = 0;
export async function ensureStats(origin) {
  if (Date.now() - VIEWS_AT < 10 * 60 * 1000) return;
  VIEWS_AT = Date.now();
  try { const r = await fetch(origin + "/data/stats.json"); if (r.ok) { const s = await r.json(); if (s && s.p) { VIEWS = s.p; VIEWS_VER++; } } } catch (e) {}
}
// Popularity = views (30 days, last 7 days count double), then favourites, all-time views, curated best-of, QC count.
export const score = p => { const v = VIEWS[p.id] || [0, 0, 0, 0];
  return Math.min(v[1] + v[2], 99999) * 1e9 + Math.min(v[3], 999) * 1e6 + Math.min(v[0], 999) * 1e3 + p.best * 500 + Math.min(p.qc, 499); };
// Only products with real QC photos (or hand-curated ones) are indexable; the rest are noindex,follow.
export const indexable = p => p.qc >= 1 || p.best === 1;

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
  for (const [b, l] of byBrand) if (l.length >= BRAND_MIN) { const s = slug(b); brandSlug.set(b, s); slugBrand.set(s, b); }
  const titleCount = new Map();   // listings sharing a title get a distinguishing suffix on their product page
  for (const p of P) { const k = ((p.brand || "") + "|" + p.title).toLowerCase(); titleCount.set(k, (titleCount.get(k) || 0) + 1); }
  _idx = { byId, byBrand, byCat, all, brandSlug, slugBrand, titleCount };
  return _idx;
}
export const BRAND_MIN = 20;   // a brand gets its own hub page from this many finds

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
// Prices: one source of truth — the CNY listing price × the same USD rate the SPA uses (CUR.USD.rate).
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
export const productUrl = p => "/product/" + encodeURIComponent(p.id);
export const brandUrl = b => { const s = idx().brandSlug.get(b); return s ? "/brand/" + s : null; };
export const catUrl = c => CATS[c] ? "/category/" + CATS[c].slug : null;
const ld = o => '<script type="application/ld+json">' + JSON.stringify(o).replace(/</g, "\\u003c") + "</script>";

export function card(p, lazy = true) {
  const src = imgSrc(p);
  return `<a class="c" href="${productUrl(p)}">` +
    `<span class="ci">${src ? `<img src="${esc(src)}" alt="${esc(p.title)}" width="300" height="375"${lazy ? ' loading="lazy"' : ""} decoding="async" onerror="this.remove()">` : ""}` +
    `${p.qc >= 2 ? `<span class="qb">QC</span>` : ""}</span>` +
    `<span class="cb">${p.brand ? `<span class="cbr">${esc(p.brand)}</span>` : ""}<span class="ct">${esc(p.title)}</span><span class="cp">${money(p.cny)}${isPH(p.cny) ? "" : ` <small>¥${p.cny}</small>`}</span></span></a>`;
}
export const grid = (list, eager = 0) => `<div class="g">${list.map((p, i) => card(p, i >= eager)).join("")}</div>`;

export function crumbs(items) {
  const html = `<nav class="bc" aria-label="Breadcrumb">${items.map((it, i) => i < items.length - 1 ? `<a href="${it[1]}">${esc(it[0])}</a><span>›</span>` : `<span aria-current="page">${esc(it[0])}</span>`).join("")}</nav>`;
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
const CSS = `:root{--bg:#0C1220;--bg2:#111A2E;--card:#141E34;--line:#26314D;--text:#F2F5FB;--muted:#94A0BD;--accent:#7B9AE0;--red:#E8322B}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 "Hanken Grotesk",system-ui,-apple-system,Segoe UI,sans-serif;-webkit-font-smoothing:antialiased}
a{color:inherit}img{max-width:100%}.w{max-width:1180px;margin:0 auto;padding:0 16px}
header.h{border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(12,18,32,.92);backdrop-filter:blur(10px);z-index:5}
header.h .w{display:flex;align-items:center;gap:18px;height:64px}header.h img{height:30px;width:auto;display:block}
header.h nav{display:flex;gap:16px;font-size:15px;color:var(--muted);flex:1;overflow-x:auto;white-space:nowrap}header.h nav a{text-decoration:none}header.h nav a:hover{color:var(--text)}
.btn{display:inline-flex;align-items:center;gap:8px;padding:11px 18px;border-radius:999px;font-weight:700;font-size:15px;text-decoration:none;border:1px solid var(--line)}
.btn.red{background:var(--red);border-color:var(--red);color:#fff}.btn.light{background:#EEF2FA;color:#0C1220;border-color:#EEF2FA}
.hcta{white-space:nowrap}@media(max-width:760px){.hcta{display:none}header.h nav{gap:12px;font-size:14px}header.h .w{flex-wrap:wrap;height:auto;padding:10px 16px;row-gap:6px}header.h nav{flex-basis:100%;order:3;flex-wrap:wrap;white-space:normal;overflow:visible;gap:6px 14px}}
main{padding:22px 0 60px}.bc{font-size:13.5px;color:var(--muted);display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px}.bc a{text-decoration:none}.bc a:hover{color:var(--text)}
h1{font-size:clamp(28px,4.4vw,44px);line-height:1.08;margin:0 0 12px;letter-spacing:-.01em}h2{font-size:24px;margin:34px 0 12px}h3{font-size:18px;margin:22px 0 8px}
.lead{color:#C9D2E6;font-size:17.5px;max-width:760px}.prose{max-width:780px;color:#D5DCEC}.prose p,.prose li{font-size:16.5px}.prose a{color:var(--accent)}
.facts{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 6px}.facts span{border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:13.5px;color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.chips a{border:1px solid var(--line);border-radius:999px;padding:7px 13px;font-size:14px;text-decoration:none;color:#C9D2E6}.chips a:hover{border-color:var(--accent)}
.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;margin:16px 0}@media(max-width:560px){.g{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.c{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden;text-decoration:none}.c:hover{border-color:#3A4870}
.ci{position:relative;aspect-ratio:4/5;background:#F3F4F7;display:block}.ci img{width:100%;height:100%;object-fit:contain;display:block}
.qb{position:absolute;left:8px;bottom:8px;background:rgba(12,16,28,.78);color:#fff;font-size:11px;font-weight:700;padding:3px 7px;border-radius:6px}
.cb{display:flex;flex-direction:column;gap:3px;padding:10px 12px 12px}.cbr{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}.ct{font-size:14.5px;line-height:1.3}.cp{font-weight:800;font-size:15px;margin-top:2px}.cp small{color:var(--muted);font-weight:500}
.pg{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}.pg a,.pg span{padding:8px 13px;border:1px solid var(--line);border-radius:10px;text-decoration:none;font-size:14px}.pg span{background:var(--accent);color:#0C1220;font-weight:700;border-color:var(--accent)}.pg i{padding:8px 4px;color:var(--muted)}
.pd{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:30px}@media(max-width:820px){.pd{grid-template-columns:1fr}}
.pimg{background:#F3F4F7;border-radius:20px;aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;overflow:hidden}.pimg img{width:100%;height:100%;object-fit:contain}
.qcs{display:flex;gap:8px;overflow-x:auto;margin:12px 0}.qcs a{flex:none}.qcs img{width:96px;height:96px;object-fit:cover;border-radius:10px;border:1px solid var(--line);display:block}
.price{font-size:30px;font-weight:800;margin:6px 0}.price small{font-size:16px;color:var(--muted);font-weight:500;margin-left:8px}
.buy{display:flex;flex-direction:column;gap:8px;margin:16px 0}.buy a{display:flex;justify-content:space-between;align-items:center;padding:13px 16px;border-radius:14px;border:1px solid var(--line);text-decoration:none;font-weight:700;background:var(--card)}
.buy a.first{background:#EEF2FA;color:#0C1220;border-color:#EEF2FA}.buy a small{font-weight:600;font-size:12px;color:#fff;background:var(--red);padding:3px 8px;border-radius:999px}
dl.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 16px;font-size:15px;margin:14px 0}dl.kv dt{color:var(--muted)}dl.kv dd{margin:0}
.steps{counter-reset:s;list-style:none;padding:0}.steps li{counter-increment:s;position:relative;padding-left:44px;margin:0 0 14px}.steps li:before{content:counter(s);position:absolute;left:0;top:0;width:30px;height:30px;border-radius:50%;background:var(--accent);color:#0C1220;font-weight:800;display:grid;place-items:center;font-size:14px}
.faq details{border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:0 0 10px;background:var(--card)}.faq summary{font-weight:700;cursor:pointer}.faq p{margin:10px 0 0;color:#C9D2E6}
.note{border:1px solid var(--line);background:var(--bg2);border-radius:14px;padding:14px 16px;color:#C9D2E6;font-size:15px}
footer.f{border-top:1px solid var(--line);padding:34px 0 40px;color:var(--muted);font-size:14px}footer.f .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:22px}
footer.f h4{color:var(--text);margin:0 0 8px;font-size:14px}footer.f a{display:block;text-decoration:none;padding:3px 0}footer.f a:hover{color:var(--text)}footer.f .disc{margin-top:26px;font-size:12.5px;line-height:1.6;max-width:900px}`;

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
  ["How to find reps", "/guides/how-to-find-reps"],
  ["MyCNBox coupon code ($500)", "/guides/mycnbox-coupon-code"],
  ["KakoBuy coupon code ($410)", "/guides/kakobuy-coupon-code"],
  ["All agent sign-up bonuses", "/guides/agent-coupons"],
];
export const TOOL_LINKS = [["Link converter", "/tools/link-converter"], ["QC checker", "/tools/qc-checker"], ["Weight estimator", "/tools/weight-estimator"], ["Shipping calculator", "/tools/shipping-calculator"]];

function footer() {
  const { byBrand, brandSlug } = idx();
  const topBrands = [...brandSlug.keys()].sort((a, b) => byBrand.get(b).length - byBrand.get(a).length).slice(0, 14);
  const col = (t, links) => `<div><h4>${t}</h4>${links.map(([n, u]) => `<a href="${u}">${esc(n)}</a>`).join("")}</div>`;
  return `<footer class="f"><div class="w"><div class="cols">
${col("Categories", Object.values(CATS).filter(c => c.slug !== "toys").map(c => [c.name, "/category/" + c.slug]))}
${col("Top brands", topBrands.map(b => [b + " reps", "/brand/" + brandSlug.get(b)]).concat([["All brands →", "/brands"]]))}
${col("Spreadsheets", [["MyCNBox spreadsheet", "/mycnbox-spreadsheet"], ["KakoBuy spreadsheet", "/kakobuy-spreadsheet"], ["Oopbuy spreadsheet", "/oopbuy-spreadsheet"], ["LoveGoBuy spreadsheet", "/lovegobuy-spreadsheet"], ["Sugargoo spreadsheet", "/sugargoo-spreadsheet"], ["Old money reps", "/old-money"]])}
${col("Guides", GUIDE_LINKS.slice(0, 7).concat([["All guides →", "/guides"]]))}
${col("Tools & best reps", TOOL_LINKS.concat([["Best reps by model →", "/best"]]))}
${col("Puro Classico", [["Browse all finds", "/"], ["Discord community", "https://discord.gg/Pf3zpG3E4"], ["Terms", "/terms"], ["Privacy", "/privacy"]])}
</div><p class="disc">Puro Classico is an independent directory of third-party listings on Weidian, Taobao and 1688. We don't sell, stock or ship any products, and we are not affiliated with, endorsed by or connected to any brand named on this site; brand names are used only to describe listings. Links to shopping agents may be affiliate links. Prices are shown as listed by the seller and can change. © Puro Classico</p></div></footer>`;
}

export function page({ title, desc, path, body, jsonld = [], robots = "index,follow,max-image-preview:large", image, status = 200, extraHead = "" }) {
  const url = SITE + path;
  if (title.length > 65 && title.endsWith(" · Puro Classico")) title = title.slice(0, -" · Puro Classico".length);   // keep long titles within what Google shows
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
<meta name="theme-color" content="#0C1220"><link rel="icon" type="image/png" href="/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>${CSS}</style>
${jsonld.map(ld).join("\n")}
${extraHead}
</head>
<body>
<header class="h"><div class="w"><a href="/" aria-label="Puro Classico home"><img src="/logo-wordmark.png" alt="Puro Classico" width="106" height="30"></a>
<nav><a href="/">Browse finds</a><a href="/brands">Brands</a><a href="/best">Best reps</a><a href="/old-money">Old money</a><a href="/guides">Guides</a><a href="/tools">Tools</a><a href="/how-to-order">How to order</a></nav>
<a class="btn red hcta" href="${MYCNBOX_INVITE}" target="_blank" rel="sponsored noopener">Claim $500 MyCNBox coupons</a></div></header>
<main><div class="w">
${body}
</div></main>
${footer()}
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
