// Server-rendered SEO pages. Each renderer returns a Response (or null when the route doesn't exist -> 404).
import { SITE, MYCNBOX_INVITE, BUILT, P, idx, indexable, views, CATS, CAT_BY_SLUG, AGENTS, esc, slug, money, isPH, imgSrc, productUrl, brandUrl, catUrl,
  grid, crumbs, pager, page, card, GUIDE_LINKS, TOOL_LINKS } from "./site.js";
import { CAT_INTRO, AGENT_INTRO, OLD_MONEY, BRAND_INTRO as BRAND_INTRO1, GUIDES as GUIDES1 } from "./content.js";
import { BRAND_INTRO2, MODELS as MODELS2, GUIDES2, TOOLS } from "./content2.js";
import { MODELS3, GUIDES3, MODEL_TERM } from "./content3.js";
const MODELS = MODELS2.concat(MODELS3);
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

const PER_PAGE = 60;
const faqLd = faq => ({ "@context": "https://schema.org", "@type": "FAQPage",
  mainEntity: faq.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) });
const faqHtml = faq => `<h2>FAQ</h2><div class="faq">${faq.map(([q, a]) => `<details><summary>${esc(q)}</summary><p>${esc(a)}</p></details>`).join("")}</div>`;
const listLd = (name, url, items, count = items.length) => ({ "@context": "https://schema.org", "@type": "CollectionPage", name, url: SITE + url,
  mainEntity: { "@type": "ItemList", numberOfItems: count,
    itemListElement: items.slice(0, 30).map((p, i) => ({ "@type": "ListItem", position: i + 1, url: SITE + productUrl(p), name: p.title })) } });
const priceRange = l => { const u = l.map(p => p.cny).filter(x => !isPH(x)).sort((a, b) => a - b); return u.length ? `${money(u[0])}–${money(u[u.length - 1])}` : ""; };

// ------------------------------------------------------------------ product
// Part of the edge-cache key in functions/product/[id].js, next to BUILT. BUILT only moves when the catalogue data
// changes, so without this a change to the product page's HTML could stay hidden behind cached copies for up to a day.
// Give it a new value (w1 -> w2 ...) in the same deploy as any change to the product page that must show at once.
export const PRODUCT_TPL = "w7";
async function qcThumbs(origin, p) {
  if (p.qc < 1) return [];
  try {
    const r = await Promise.race([
      fetch(`${origin}/api/qc?storefront=${p.platform}&id=${encodeURIComponent(p.itemId || p.id)}`),
      new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), 1500)),
    ]);
    if (!r.ok) return [];
    const d = await r.json();
    return (Array.isArray(d.thumbnails) ? d.thumbnails : []).filter(u => /^https:\/\//.test(u)).slice(0, 8);
  } catch (e) { return []; }
}

export async function renderProduct(id, origin) {
  const { byId, byBrand, byCat } = idx();
  const p = byId.get(id);
  if (!p) return null;
  const qcs = await qcThumbs(origin, p);
  const bUrl = brandUrl(p.brand), cUrl = catUrl(p.cat), cat = CATS[p.cat] || { name: p.cat };
  const trail = [["Home", "/"]];
  if (cUrl) trail.push([cat.name, cUrl]);
  if (bUrl) trail.push([p.brand, bUrl]);
  trail.push([p.title, productUrl(p)]);
  const bc = crumbs(trail);
  const variants = p.variants ? p.variants.split("|") : [];
  const src = imgSrc(p);
  const agents = Object.entries(AGENTS).map(([k, a], i) =>
    `<a class="${i === 0 ? "first" : ""}" data-agent="${k}" href="${esc(a.build(p))}" target="_blank" rel="sponsored nofollow noopener">Buy via ${a.name}${i === 0 ? "<small>Most popular</small>" : ""}</a>`).join("");
  const plat = { weidian: "Weidian", taobao: "Taobao", "1688": "1688" }[p.platform] || p.platform;
  const realSeller = p.seller && !/marketplace/i.test(p.seller) && p.seller.trim().toLowerCase() !== plat.toLowerCase() ? p.seller : "";   // "Weidian" as seller is just the platform
  const catLc = (cat.name || "").toLowerCase();
  const dup = (idx().titleCount.get(((p.brand || "") + "|" + p.title).toLowerCase()) || 1) > 1;
  const tName = dup ? `${p.title} (${plat}, ${money(p.cny)})` : p.title;
  // p.qc >= 1 is a flag from import ("QC photos exist for this listing"); the photos themselves come from a live
  // lookup that can fail. So title, description and text may say photos are on record, never that this page shows them.
  const desc = `${p.title} rep ${isPH(p.cny) ? "(ask the seller for the price)" : `for about ${money(p.cny)} (¥${p.cny})`} on ${plat}` + (dup && realSeller ? ` from seller ${realSeller}` : "") +
    (p.qc ? ", a listing with buyer QC photos on record" : "") + `. Open it on MyCNBox, KakoBuy, Oopbuy or any shopping agent.`;
  const sameBrand = bUrl ? (byBrand.get(p.brand) || []).filter(x => x.id !== p.id).slice(0, 8) : [];
  const sameCat = (byCat.get(p.cat) || []).filter(x => x.id !== p.id && x.brand !== p.brand).slice(0, 8);
  const about = `<p>The <strong>${esc(p.title)}</strong> is ${/^[aeiou]/.test(catLc) ? "an" : "a"} ${esc(catLc)} find${p.brand ? ` in the ${esc(p.brand)} style` : ""} listed on ${plat}` +
    (realSeller ? ` by ${esc(realSeller)}` : "") + (isPH(p.cny) ? `. The seller shows a placeholder price (¥${p.cny}), so ask them for the real price before ordering` : `. The listed price is ¥${p.cny} (about ${money(p.cny)}) before shipping`) +
    (variants.length ? `, and it comes in ${variants.length} option${variants.length > 1 ? "s" : ""}: ${esc(variants.slice(0, 8).join(", "))}${variants.length > 8 ? "…" : ""}` : "") + `.</p>` +
    (p.qc ? `<p>Our catalogue data marks this listing as having <strong>buyer QC photos</strong>: warehouse photos taken for earlier orders. When we can load them, they are shown on this page. Either way, once your own order reaches the warehouse your agent photographs your exact item, so you can check logos, stitching and colour before it ships.</p>`
          : `<p>There are no buyer QC photos for this listing yet, once you order, your agent photographs your exact item at the warehouse before it ships, so you can still check it before paying for shipping.</p>`) +
    `<p>International shipping isn't included in the price; you pay it when you ship your parcel, and it depends on weight and your country.</p>`;
  const body = `${bc.html}
<div class="pd">
  <div><div class="pimg">${src ? `<img src="${esc(src)}" alt="${esc(p.title)}" width="600" height="600" fetchpriority="high">` : ""}</div>
    ${qcs.length ? `<h2 style="font-size:18px;margin:18px 0 0">Real QC photos</h2><div class="qcs">${qcs.map((u, i) => `<a href="${esc(u)}" target="_blank" rel="noopener"><img src="${esc(u)}" alt="${esc(p.title)} QC photo ${i + 1}" width="96" height="96" loading="lazy" onerror="this.parentNode.remove()"></a>`).join("")}</div>` : ""}
  </div>
  <div>
    ${bUrl ? `<a href="${bUrl}" style="color:var(--muted);text-decoration:none;letter-spacing:.08em;text-transform:uppercase;font-size:13px">${esc(p.brand)}</a>` : (p.brand ? `<span style="color:var(--muted);letter-spacing:.08em;text-transform:uppercase;font-size:13px">${esc(p.brand)}</span>` : "")}
    <h1>${esc(p.title)}</h1>
    <div class="price">${money(p.cny)}<small>${isPH(p.cny) ? "placeholder price · ask seller" : `¥${p.cny} · before shipping`}</small></div>
    <div class="buy">${agents}</div><script>try{var a=(JSON.parse(localStorage.getItem("manifest.state")||"{}")||{}).agent,b=document.currentScript.previousElementSibling,e=a&&b.querySelector('a[data-agent="'+String(a).replace(/[^a-z0-9]/g,"")+'"]');if(e&&e!==b.firstElementChild){b.firstElementChild.classList.remove("first");e.classList.add("first");b.insertBefore(e,b.firstElementChild);}}catch(_){}</script>
    <p class="eyebrow" style="margin:6px 0 0">Spreadsheets: ${AGENT_BRAND_AGENTS.map(k => { const bs = p.brand && agentBrands().includes(p.brand) ? idx().brandSlug.get(p.brand) : null; return `<a href="/${k}-spreadsheet${bs ? "/" + bs : ""}" style="color:var(--muted)">${esc(AGENTS[k].name)}</a>`; }).join(" · ")}</p>
    <dl class="kv"><dt>Marketplace</dt><dd>${plat}</dd><dt>Category</dt><dd>${cUrl ? `<a href="${cUrl}">${esc(cat.name)}</a>` : esc(p.cat)}</dd>
      ${variants.length ? `<dt>Options</dt><dd>${esc(variants.slice(0, 12).join(" · "))}</dd>` : ""}<dt>QC photos</dt><dd>${qcs.length ? qcs.length + " shown" : (p.qc ? "On record" : "None yet")}</dd><dt>Item ID</dt><dd>${esc(p.itemId || p.id)}</dd></dl>
    <p><a href="/#p/${encodeURIComponent(p.id)}" style="color:var(--accent)">Open in the catalogue →</a></p>
  </div>
</div>
<h2>About this find</h2><div class="prose">${about}</div>
<h2>How to buy it</h2><ol class="steps prose"><li>Tap <strong>Buy via MyCNBox</strong> (or your agent). The listing opens pre-filled.</li><li>Pick your size and colour, check our <a href="/guides/sizing">sizing guide</a>, and pay for the item plus delivery to the warehouse.</li><li>Check the QC photos (<a href="/guides/how-to-qc">what to look for</a>), then combine items into one parcel and ship. <a href="/how-to-order">Watch the 1:47 video</a>.</li></ol>
${(() => { const m = modelFor(p); return m ? `<div class="note" style="margin-top:22px">Comparing batches? See all <a href="/best/${m.slug}" style="color:var(--accent)">${m.list.length} ${esc(m.name)} rep listings</a> ranked by views.</div>` : ""; })()}
${sameBrand.length ? `<h2>More ${esc(p.brand)} finds</h2>${grid(sameBrand)}<p><a href="${bUrl}" style="color:var(--accent)">All ${byBrand.get(p.brand).length.toLocaleString("en-US")} ${esc(p.brand)} reps on the spreadsheet →</a></p>` : ""}
${sameCat.length ? `<h2>Similar ${esc((cat.name || p.cat).toLowerCase())}</h2>${grid(sameCat)}${cUrl ? `<p><a href="${cUrl}" style="color:var(--accent)">All ${esc((cat.name || p.cat).toLowerCase())} →</a></p>` : ""}` : ""}`;
  const pageLd = { "@context": "https://schema.org", "@type": "ItemPage", name: p.title, url: SITE + productUrl(p), description: desc,
    primaryImageOfPage: src ? { "@type": "ImageObject", contentUrl: src } : undefined, isPartOf: { "@type": "WebSite", name: "Puro Classico", url: SITE + "/" } };
  const res = page({ title: `${tName} Rep: ${p.qc ? "Price, QC & Agent Links" : "Price & Where to Buy"} · Puro Classico`, desc, path: productUrl(p), body,
    jsonld: [bc.data, pageLd], image: src || undefined, robots: indexable(p) ? "index,follow,max-image-preview:large" : "noindex,follow" });
  if (p.qc >= 1 && !qcs.length) res.headers.set("x-qc-miss", "1");   // QC lookup failed/timed out: product/[id].js caches this render only briefly
  return res;
}

// ------------------------------------------------------------------ hubs
function hub({ path, n, list, title, desc, h1, intro, trail, chips = "", top = "", extra = "", faq = null, total = null, ldCount = undefined }) {
  const pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
  if (n < 1 || n > pages) return null;
  const slice = list.slice((n - 1) * PER_PAGE, n * PER_PAGE);
  const url = n === 1 ? path : `${path}/${n}`;
  const bc = crumbs(trail.concat(n > 1 ? [[`Page ${n}`, url]] : []));
  const qcTotal = list.reduce((s, p) => s + (p.qc || 0), 0);
  const body = `${bc.html}<h1>${esc(h1)}${n > 1 ? ` <small style="color:var(--muted);font-size:.5em">page ${n}</small>` : ""}</h1>
${n === 1 ? `<div class="prose">${intro}</div>` : ""}
<div class="facts"><span>${(total || list.length).toLocaleString("en-US")} finds</span>${priceRange(list) ? `<span>${priceRange(list)}</span>` : ""}<span>Catalogue updated ${BUILT}</span></div>
${chips}
${n === 1 ? top : ""}${grid(slice, n === 1 ? 4 : 0)}
${pager(path, n, pages)}
${n === 1 ? extra : ""}${n === 1 && faq && faq.length ? faqHtml(faq) : ""}`;
  const ld = [bc.data, listLd(h1, url, slice, ldCount)]; if (n === 1 && faq && faq.length) ld.push(faqLd(faq));
  return page({ title: n > 1 ? `${title}: Page ${n}` : title, desc, path: url, body, jsonld: ld,
    image: slice[0] ? imgSrc(slice[0]) : undefined });
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
// Item type of a find, read from the words of its title (first match wins), else from its catalogue category.
const ITEM_TYPES = [
  ["", /\bbox set\b/i],
  ["caps and beanies", /\bcaps?\b|\bhats?\b|\bbeanies?\b|\bbalaclavas?\b|\bvisors?\b/i],
  ["scarves", /\bscar(f|ves)\b/i],
  ["sunglasses", /\bsunglasses\b|\bglasses\b/i],
  ["suitcases", /\bsuitcases?\b|\bluggage\b/i],
  ["bags", /\bbags?\b|\bbackpacks?\b|\btotes?\b|\bduff(le|el)s?\b|\bpouch(es)?\b|\bkeepall\b|\bhandbags?\b|\bbriefcases?\b|\bspeedy\b/i],
  ["wallets and cardholders", /\bwallets?\b|\bcard ?holders?\b/i],
  ["belts", /\bbelts?\b/i],
  ["watches", /\bwatch(es)?\b|\bdial\b/i],
  ["jewellery", /\brings?\b|\bnecklaces?\b|\bbracelets?\b|\bchains?\b|\bpendants?\b|\bearrings?\b/i],
  ["socks and underwear", /\bsocks\b|\bboxers\b|\bunderwear\b|\bbriefs\b/i],
  ["perfumes", /\bperfumes?\b|\bfragrances?\b|\bcologne\b/i],
  ["boots", /\bboots?\b|\bbooties?\b/i],
  ["loafers", /\bloafers?\b/i],
  ["sandals and slides", /\bsandals?\b|\bslides?\b|\bslippers?\b|\bclogs?\b|\bflip flops?\b|\bmules\b/i],
  ["heels", /\bheels?\b|\bpumps\b/i],
  ["sneakers and shoes", /\bsneakers?\b|\btrainers?\b|\brunners?\b|\bshoes?\b|\bhigh-?tops?\b/i],
  ["dresses and skirts", /\bdress(es)?\b|\bskirts?\b/i],
  ["tracksuits and sets", /\btracksuits?\b|\btrack suits?\b|\bsets?\b/i],
  ["shorts", /\bshorts\b/i],
  ["jeans", /\bjeans\b/i],
  ["pants and joggers", /\bpants\b|\btrousers\b|\bjoggers\b|\bsweatpants\b|\bleggings\b|\bcargos?\b|\boveralls\b/i],
  ["vests and gilets", /\bvests?\b(?! top)|\bgilets?\b/i],
  ["puffer jackets", /\bpuffers?\b|(?:^| )down(?: |$)/i],   // "Down Jacket", not "Button-Down"
  ["jackets and coats", /\bjackets?\b|\bcoats?\b|\bparkas?\b|\bwindbreakers?\b|\bbombers?\b|\bovershirts?\b|\bblazers?\b/i],
  ["hoodies", /\bhoodies?\b/i],
  ["quarter-zips", /\bquarter.?zips?\b|\bhalf.?zips?\b/i],
  // "Polo" alone is also part of a brand name ("Polo Sweatshirt"), so it only counts as the garment when it is the last word before the colour
  ["polo shirts", /\bpolo shirts?\b|\bpolos?(?: (?:light |dark )?(?:black|white|grey|gray|navy|blue|cream|green|brown|pink|red|beige|tan|yellow|orange|purple|burgundy|olive|khaki|camel))?$/i],
  ["T-shirts and tops", /\bt-?shirts?\b|\btees?\b|\blong.?sleeves?\b|\btank tops?\b|\bvest tops?\b/i],
  ["sweaters and cardigans", /\bsweaters?\b|\bcardigans?\b|\bknit(ted|wear)?\b|\bjumpers?\b/i],
  ["sweatshirts and crewnecks", /\bsweatshirts?\b|\bcrewnecks?\b/i],
  ["jerseys", /\bjerseys?\b/i],
  ["shirts", /\bshirts?\b|\bblouses?\b/i],
  ["fleeces", /\bfleeces?\b/i],
  ["ties", /\bties?\b(?![ -]?dye)/i],
];
const ACCESSORY_ONLY = new Set(["jewellery", "ties"]);
const CAT_TYPE = { Tops: "other tops", Outerwear: "other outerwear", Shoes: "sneakers and shoes", Pants: "pants and joggers", Shorts: "shorts", Bags: "bags",
  Accessories: "other accessories", Headwear: "caps and beanies", Toys: "building sets and toys" };
const _itemType = new WeakMap();   // a find's item type never changes, so it is worked out once per server instance, not after every stats refresh
export function itemType(p) {
  let t = _itemType.get(p);
  if (t === undefined) { t = itemTypeOf(p); _itemType.set(p, t); }
  return t;
}
function itemTypeOf(p) {
  let t = p.title || "";
  if (p.brand && t.toLowerCase().startsWith(p.brand.toLowerCase() + " ")) t = t.slice(p.brand.length + 1);
  if (p.cat !== "Toys")   // set names ("TIE Fighter", "Lord of the Rings") are not item types
    for (const [label, re] of ITEM_TYPES) {
      if (!re.test(t)) continue;
      if (!label) break;                                             // "box set": use the category
      if (ACCESSORY_ONLY.has(label) && p.cat !== "Accessories") continue;   // "Chain Logo T-Shirt" is not jewellery, "Tie-Dye" is not a tie
      return label;
    }
  return CAT_TYPE[p.cat] || "other finds";
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

let _bf = null, _bfIdx = null;
export function brandFacts(b) {
  const ix = idx();
  if (_bfIdx !== ix) { _bf = new Map(); _bfIdx = ix; }
  if (_bf.has(b)) return _bf.get(b);
  const list = ix.byBrand.get(b) || [];
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
const agentList = AGENT_NAMES.slice(0, -1).join(", ") + " and " + AGENT_NAMES[AGENT_NAMES.length - 1];
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
const BRAND_CSS = `<style>.pk .ci{box-shadow:inset 0 0 0 1px var(--accent)}.pkw{display:block;font-size:12.5px;line-height:1.35;color:var(--ink-2)}.pkw b{color:var(--accent);font-weight:700}.pkq{font-size:12.5px;color:var(--muted)}.pkn{color:var(--muted);font-size:14px;max-width:780px;margin:0 0 4px}</style>`;
function pickCard({ p, why, doubt }, eager) {
  const src = imgSrc(p);
  // A price we do not vouch for (priceDoubt in brandFacts) is shown as the seller lists it, in yuan, without our dollar figure.
  const price = doubt ? `Listed at ¥${p.cny} <small>check the listing</small>` : `${money(p.cny)}${isPH(p.cny) ? "" : ` <small>¥${p.cny}</small>`}`;
  return `<a class="c" href="${productUrl(p)}"><span class="ci">${src ? `<img src="${esc(src)}" alt="${esc(p.title)}" width="300" height="375"${eager ? "" : ' loading="lazy"'} decoding="async" onerror="this.remove()">` : ""}</span>` +
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
  if (range) faq.push([`How much do ${b} reps cost?`, `Listings on this page range from ${range} before international shipping, which depends on weight and your country.` +
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
  const bm = models().filter(m => m.list.some(p => p.brand === b));
  let related = relatedBrands(b), relTitle = "Related brands", relNote = `<p class="pkn">Brands on the spreadsheet with a similar mix of item types and prices.</p>`;
  if (related.length < 4) {   // nothing really similar (a watch or toy brand, say): the largest hubs, under a heading that does not claim more
    related = [...brandSlug.keys()].filter(x => x !== b).sort((x, y) => byBrand.get(y).length - byBrand.get(x).length).slice(0, 10); relTitle = "Other brands"; relNote = "";
  }
  const extra = `<h2>How to buy ${esc(b)} reps</h2><div class="prose"><p>Open a find, tap <strong>Buy via MyCNBox</strong> (or your agent), pick your size and pay for the item plus delivery to the warehouse. Check the QC photos before shipping, see <a href="/guides/how-to-qc">how to read QC photos</a>, then combine your items into one parcel. New to this? <a href="/how-to-order">Watch the how-to-order video</a>.</p></div>
<h2>${relTitle}</h2>${relNote}<div class="chips">${related.map(x => `<a href="/brand/${brandSlug.get(x)}">${esc(x)} reps</a>`).join("")}${OLD_MONEY_ALL.has(b) ? `<a href="/old-money">Old money reps</a>` : ""}<a href="/brands">All brands →</a></div>`;
  // Title and description: catalogue data only (see the rules above), so they are the same whether or not the stats were read.
  const qcBit = f.q1 ? `, ${nf(f.q1)} marked as having QC photos` : "";
  const t0 = f.types[0], share = t0 && !t0[0].startsWith("other") ? t0[1].length / f.n : 0;
  const main = share === 1 ? `, all ${t0[0]}` : share > 0.5 ? `, mostly ${t0[0]}` : "";   // only when one item type is more than half the list
  const desc = n > 1 ? `Page ${n} of the ${N} ${b} rep finds on Puro Classico${range ? `, with prices${rb}` : ""}. Open any listing on MyCNBox, KakoBuy, Oopbuy or your agent.`
    : best ? `Best ${b} reps by the numbers: ${N} finds${rb}, ${nf(f.q2)} with a stored QC photo count. Picks by views and QC photos, with MyCNBox, KakoBuy and Oopbuy links.`
    : `${N} ${b} rep find${f.n === 1 ? "" : "s"}${range ? ` with prices${rb}` : ""}${main}${qcBit}. Open any listing on MyCNBox, KakoBuy, Oopbuy or your agent.`;
  return hub({ path: "/brand/" + s, n, list, title: `${n === 1 && best ? "Best " : ""}${b} Reps Spreadsheet 2026: ${N} Finds · Puro Classico`, desc,
    h1: `${b} reps spreadsheet`, intro, trail: [["Home", "/"], ["Brands", "/brands"], [b, "/brand/" + s]],
    chips: (bm.length ? `<div class="chips">${bm.map(m => `<a href="/best/${m.slug}" style="border-color:var(--accent)">Best ${esc(MODEL_TERM[m.slug] || m.name)} reps</a>`).join("")}</div>` : "") + (cats.length > 1 ? `<div class="chips">${cats.map(c => `<a href="${catUrl(c)}">${esc(CATS[c].name)}</a>`).join("")}</div>` : ""),
    top: BRAND_CSS + brandPicksHtml(f, best), extra, faq: brandFaq(f, best), ldCount: f.n });
}

export function renderCategory(s, n) {
  const c = own(CAT_BY_SLUG, s) ? CAT_BY_SLUG[s] : null; if (!c) return null;
  const { byCat, byBrand, brandSlug } = idx(); const list = byCat.get(c) || [];
  const topBrands = [...new Set(list.map(p => p.brand))].filter(b => brandSlug.has(b)).slice(0, 24);   // was 18: room for the allow-listed hubs without dropping a brand that was linked before
  const meta = CATS[c], q1 = list.filter(p => p.qc >= 1).length;
  const extra = `<h2>Top brands in ${esc(meta.name.toLowerCase())}</h2><div class="chips">${topBrands.map(b => `<a href="/brand/${brandSlug.get(b)}">${esc(b)}</a>`).join("")}</div>
<h2>Other categories</h2><div class="chips">${Object.values(CATS).filter(x => x.slug !== s && x.slug !== "toys").map(x => `<a href="/category/${x.slug}">${esc(x.name)}</a>`).join("")}</div>`;
  return hub({ path: "/category/" + s, n, list, title: `${meta.h}: ${list.length.toLocaleString("en-US")} Finds (2026) · Puro Classico`,
    desc: `${list.length.toLocaleString("en-US")} ${meta.name.toLowerCase()} rep finds with prices and agent links${q1 ? `, ${q1.toLocaleString("en-US")} marked as having buyer QC photos` : ""}, sorted by most viewed.`,
    h1: meta.h, intro: CAT_INTRO[c] || "", trail: [["Home", "/"], [meta.name, "/category/" + s]], extra });
}

// ------------------------------------------------------------------ agent spreadsheets (+ brand pages per agent)
// Brand x agent pages (/kakobuy-spreadsheet/ralph-lauren): only for the largest brand hubs and the agents people search
// together with a brand name, so every page has a real list behind it instead of thousands of near-empty variations.
export const AGENT_BRAND_AGENTS = ["mycnbox", "kakobuy", "oopbuy", "sugargoo"];
export const AGENT_BRAND_MIN = 40, AGENT_BRAND_MAX = 30;
let _agentBrands = null;
export function agentBrands() {
  if (_agentBrands) return _agentBrands;
  const { byBrand, brandSlug } = idx();
  return (_agentBrands = [...brandSlug.keys()].filter(b => byBrand.get(b).length >= AGENT_BRAND_MIN)
    .sort((a, b) => byBrand.get(b).length - byBrand.get(a).length).slice(0, AGENT_BRAND_MAX));
}
const COUPON_GUIDE = { mycnbox: ["MyCNBox coupon code", "/guides/mycnbox-coupon-code"], kakobuy: ["KakoBuy coupon code", "/guides/kakobuy-coupon-code"] };
function agentHowTo(a) {
  return `<h2>How to order from the ${a.name} spreadsheet</h2>
<ol class="steps">
<li><strong>Make a free ${a.name} account.</strong> Sign-up bonuses differ per agent; see <a href="${(COUPON_GUIDE[a.key] || ["", "/guides/agent-coupons"])[1]}">${esc((COUPON_GUIDE[a.key] || ["all agent sign-up bonuses"])[0])}</a>.</li>
<li><strong>Find an item here.</strong> Search or filter the spreadsheet by brand, category, colour or price, and open the find you like.</li>
<li><strong>Tap "Buy via ${a.name}".</strong> The listing opens inside ${a.name}. Pick your size and colour, then pay for the item and the short delivery to the warehouse.</li>
<li><strong>Check your QC photos.</strong> When the item reaches the warehouse, ${a.name} photographs it. Compare logos, stitching and the size tag; read <a href="/guides/how-to-qc">how to read QC photos</a>.</li>
<li><strong>Ship your parcel.</strong> Combine your items, pick a shipping line and pay international shipping. <a href="/guides/shipping-lines">Shipping lines explained</a> · <a href="/tools/weight-estimator">weight estimator</a>.</li>
</ol>`;
}
export function renderAgent(key, n) {
  const a = AGENTS[key], meta = AGENT_INTRO[key]; if (!a || !meta) return null;
  const { all, brandSlug } = idx(); const path = `/${key}-spreadsheet`; const N = all.length.toLocaleString("en-US");
  const faq = [[`What is the ${a.name} spreadsheet?`, `A list of Weidian, Taobao and 1688 finds that open directly in ${a.name}. Puro Classico's spreadsheet has ${N} finds, each with ${a.name} buy links, prices and buyer QC photo counts where we have them.`],
               [`How do I order from the ${a.name} spreadsheet?`, `Open a find, tap Buy via ${a.name}, choose your size and pay for the item plus delivery to the warehouse. After the QC photos arrive, submit your parcel and pay international shipping.`],
               [`Is the ${a.name} spreadsheet free?`, `Yes. Browsing, searching and saving finds on Puro Classico is free. You only pay ${a.name} for the items you order and for shipping. Links to agents may be affiliate links.`],
               [`Can I use the spreadsheet with another agent?`, `Yes. The catalogue is the same for every agent: each product page has buy links for MyCNBox, KakoBuy, Oopbuy, LoveGoBuy and Sugargoo, and the link converter turns any Weidian, Taobao or 1688 link into a link for your agent.`],
               [`How often is the ${a.name} spreadsheet updated?`, `New finds are added to the catalogue regularly; the date of the last catalogue update is shown on this page (${BUILT}).`]];
  const brands = AGENT_BRAND_AGENTS.includes(key) ? agentBrands() : [];
  const brandBlock = brands.length ? `<h2>Popular brands on the ${a.name} spreadsheet</h2><div class="chips">${brands.map(b => `<a href="${path}/${brandSlug.get(b)}">${esc(b)}</a>`).join("")}<a href="/brands">All brands →</a></div>` : "";
  const coupon = COUPON_GUIDE[key];
  return hub({ path, n, list: all, title: `${meta.title}: ${N} Finds · Puro Classico`,
    desc: `The ${a.name} spreadsheet: ${N} rep finds with prices, QC photo counts and direct ${a.name} links. Updated ${BUILT}.`,
    h1: meta.title, intro: `<p class="lead">${esc(meta.lede)}</p>${meta.body}${key === "mycnbox" ? `<p><a class="btn red" href="${MYCNBOX_INVITE}" target="_blank" rel="sponsored noopener">Claim your MyCNBox new-user coupons</a></p>` : ""}`,
    trail: [["Home", "/"], [meta.title, path]], faq, chips: brands.length ? `<div class="chips">${brands.slice(0, 12).map(b => `<a href="${path}/${brandSlug.get(b)}">${esc(b)} on ${esc(a.name)}</a>`).join("")}</div>` : "",
    extra: `<div class="prose">${agentHowTo({ ...a, key })}${coupon ? `<p>Before your first order, check the <a href="${coupon[1]}">${esc(coupon[0])}</a> guide for the current sign-up bonus.</p>` : ""}</div>
${brandBlock}
<p><a class="btn light" href="/">Browse all ${N} finds →</a></p><h2>Other agent spreadsheets</h2><div class="chips">${Object.keys(AGENT_INTRO).filter(k => k !== key).map(k => `<a href="/${k}-spreadsheet">${esc(AGENT_INTRO[k].title.replace(/ 2026$/, ""))}</a>`).join("")}<a href="/guides/best-shopping-agent">Which agent is best?</a></div>` });
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
               [`Are these ${b} finds only for ${a.name}?`, `No. The same finds open on ${others.map(k => AGENTS[k].name).join(", ")} and LoveGoBuy; each product page has a button for every agent.`]];
  return hub({ path, n, list, title: `${b} ${a.name} Spreadsheet 2026: ${N} Finds · Puro Classico`,
    desc: `${N} ${b} rep finds with one-tap ${a.name} buy links${range ? `, ${range}` : ""}. Prices and QC photo counts on every find.`,
    h1: `${b} on ${a.name}`, intro, trail: [["Home", "/"], [meta.title, `/${key}-spreadsheet`], [b, path]], faq,
    chips: `<div class="chips">${others.map(k => `<a href="/${k}-spreadsheet/${s}">${esc(b)} on ${esc(AGENTS[k].name)}</a>`).join("")}<a href="/brand/${s}">All ${esc(b)} reps</a></div>`,
    extra: `<div class="prose">${agentHowTo({ ...a, key })}</div><h2>More brands on ${esc(a.name)}</h2><div class="chips">${agentBrands().filter(x => x !== b).slice(0, 16).map(x => `<a href="/${key}-spreadsheet/${brandSlug.get(x)}">${esc(x)}</a>`).join("")}</div>`,
    ldCount: list.length });
}

export function renderOldMoney(n) {
  const { all, brandSlug } = idx(); const set = new Set(OLD_MONEY.brands);
  const list = all.filter(p => set.has(p.brand));
  const brands = OLD_MONEY.brands.concat(OLD_MONEY.linked).filter(b => brandSlug.has(b));   // `linked` brands get a chip; their finds are not part of this page's list
  return hub({ path: "/old-money", n, list, title: `Old Money Spreadsheet 2026: ${list.length.toLocaleString("en-US")} Quiet Luxury Rep Finds | Puro Classico`,
    desc: `Old money and quiet luxury reps: ${list.length.toLocaleString("en-US")} finds from Ralph Lauren, Loro Piana, Lacoste, Moncler, Golden Goose and more.`,
    h1: "Old money & quiet luxury reps", intro: OLD_MONEY.intro, trail: [["Home", "/"], ["Old money", "/old-money"]],
    chips: `<div class="chips">${brands.map(b => `<a href="/brand/${brandSlug.get(b)}">${esc(b)}</a>`).join("")}<a href="/stockholm-spreadsheet">Stockholm style spreadsheet</a><a href="/grisch-spreadsheet">Grisch spreadsheet</a></div>`,
    faq: [["What are old money reps?", "Replica finds in the understated 'old money' or quiet-luxury style: knitwear, polos, loafers and clean sneakers from brands like Ralph Lauren, Loro Piana and Brunello Cucinelli, without big logos."],
          ["What should I check in QC for old money pieces?", "Knit texture and ribbing, the density of small chest-logo embroidery, collar shape on polos, and leather grain and stitching on shoes and belts."]] });
}

export function renderBrands() {
  const { byBrand, brandSlug } = idx();
  const hubs = [...brandSlug.keys()].sort((a, b) => a.localeCompare(b));
  const groups = {};
  for (const b of hubs) { const L = /[a-z]/i.test(b[0]) ? b[0].toUpperCase() : "#"; (groups[L] = groups[L] || []).push(b); }
  const bc = crumbs([["Home", "/"], ["Brands", "/brands"]]);
  const body = `${bc.html}<h1>Rep brands A–Z</h1><p class="lead">The ${hubs.length} brands with their own page on Puro Classico, with the number of finds for each.</p>
${Object.keys(groups).sort().map(L => `<h2>${L}</h2><div class="chips">${groups[L].map(b => `<a href="/brand/${brandSlug.get(b)}">${esc(b)} <span style="color:var(--muted)">${byBrand.get(b).length}</span></a>`).join("")}</div>`).join("")}`;
  return page({ title: "Rep Brands A–Z: Every Brand on the Spreadsheet · Puro Classico", desc: `Browse ${hubs.length} brands on the Puro Classico rep spreadsheet, from Corteiz and Nike to Ralph Lauren and Moncler.`,
    path: "/brands", body, jsonld: [bc.data] });
}

// ------------------------------------------------------------------ model pages ("best X rep")
export function renderModels() {
  const bc = crumbs([["Home", "/"], ["Best reps", "/best"]]);
  const ms = models().slice().sort((a, b) => b.list.length - a.list.length);
  const body = `${bc.html}<h1>Best reps by model</h1><p class="lead">Every listing of the most popular models side by side, ranked by what buyers actually view. Compare batches, prices and QC before you order.</p>
<div class="g">${ms.map(m => { const p = m.list[0]; const src = imgSrc(p); return `<a class="c" href="/best/${m.slug}"><span class="ci">${src ? `<img src="${esc(src)}" alt="${esc(m.name)}" loading="lazy" onerror="this.remove()">` : ""}</span><span class="cb"><span class="ct">${esc(m.name)}</span><span class="cbr">${m.list.length} listings</span></span></a>`; }).join("")}</div>`;
  return page({ title: "Best Reps by Model (2026): Compare Batches & QC · Puro Classico", desc: "Compare every listing of the most popular rep models: Air Jordan 1, Samba, Golden Goose, Moncler, Nuptse and more, ranked by views.", path: "/best", body, jsonld: [bc.data] });
}
export function renderModel(s, n) {
  const m = models().find(x => x.slug === s); if (!m) return null;
  const list = m.list;
  const intro = `<p>${esc(m.intro)}</p><p>Below are all ${list.length} ${esc(m.name)} listings on Puro Classico, ranked by how often buyers view them. Prices run from ${priceRange(list)} before shipping.</p>
<h3>What to check in QC</h3><ul>${m.qc.map(q => `<li>${esc(q)}</li>`).join("")}</ul>`;
  const others = models().filter(x => x.slug !== s).slice(0, 14);
  const t = MODEL_TERM[s] || m.name;
  // Link up to the hub of each brand these listings belong to (a brand needs 3 of them, or all of them; at most 6 brands).
  const { byBrand, brandSlug } = idx();
  const bn = new Map(); for (const p of list) if (brandSlug.has(p.brand)) bn.set(p.brand, (bn.get(p.brand) || 0) + 1);
  const hubs = [...bn].filter(([, c]) => c >= Math.min(3, list.length)).sort((x, y) => y[1] - x[1]).slice(0, 6).map(x => x[0]);
  const hubLinks = hubs.length ? `<h2>${hubs.length === 1 ? `More ${esc(hubs[0])}` : "Brands on this page"}</h2><div class="chips">${hubs.map(x => `<a href="/brand/${brandSlug.get(x)}">All ${byBrand.get(x).length.toLocaleString("en-US")} ${esc(x)} reps</a>`).join("")}</div>` : "";
  const faq = [[`Where can I buy ${t} reps?`, `Puro Classico lists ${list.length} ${m.name} listings from Weidian, Taobao and 1688. Each opens directly in MyCNBox, KakoBuy, Oopbuy or another shopping agent.`],
               [`Which ${m.name} listing is best?`, `Start with the most-viewed listings at the top and compare their buyer QC photos. Check ${m.qc.join(", ")}.`]];
  return hub({ path: "/best/" + s, n, list, title: `Best ${t} Reps (2026): ${list.length} Listings Compared · Puro Classico`,
    desc: `Compare ${list.length} ${m.name} rep listings ranked by views, with prices (${priceRange(list)}) and what to check in QC.`,
    h1: `Best ${t} reps`, intro, trail: [["Home", "/"], ["Best reps", "/best"], [m.name, "/best/" + s]], faq,
    extra: `${hubLinks}<h2>More models</h2><div class="chips">${others.map(x => `<a href="/best/${x.slug}">${esc(x.name)}</a>`).join("")}<a href="/best">All models →</a></div>` });
}

// ------------------------------------------------------------------ tools
const TOOL_CSS = `<style>.tool{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px;max-width:760px;margin:18px 0}.tool label{display:block;color:var(--muted);font-size:13px;margin:0 0 6px}.tool input,.tool select{width:100%;background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:12px;padding:12px 14px;font:inherit}.tool .out{margin-top:14px;font-size:15px;color:var(--ink-2);white-space:pre-line}.tool .out a{color:var(--accent);word-break:break-all}.tool .row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.tool .qct{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.tool .qct img{width:110px;height:110px;object-fit:cover;border-radius:10px;border:1px solid var(--line)}.tool table{width:100%;border-collapse:collapse}.tool td{padding:6px 4px}</style>`;
const EXTRACT = `function pcExtract(u){u=(u||"").trim();if(!u)return{};for(var k=0;k<3;k++){var d;try{d=decodeURIComponent(u);}catch(e){break;}if(d===u)break;u=d;}var pl=null,v,m,i;var st=u.match(/[?&#](?:shop_type|platform|source|channel|mall_?type)=([a-z0-9_]+)/i);if(st){v=st[1].toLowerCase();if(/^(?:wd|weidian)/.test(v))pl="weidian";else if(/^(?:1688|ali)/.test(v))pl="1688";else if(/^(?:tb|tao|tmall)/.test(v))pl="taobao";}if(!pl){m=u.match(/\\/product\\/(weidian|taobao|tmall|1688)\\//i);if(m){v=m[1].toLowerCase();pl=v==="tmall"?"taobao":v;}}if(!pl){var H=[["weidian",/(?:^|[\\/.@])(?:weidian\\.com|youshop10\\.com)/i],["taobao",/(?:^|[\\/.@])(?:taobao\\.com|tmall\\.com|tmall\\.hk|tb\\.cn)/i],["1688",/(?:^|[\\/.@])(?:1688\\.com|alibaba\\.com)/i]],b=-1;for(i=0;i<H.length;i++){m=H[i][1].exec(u);if(m&&(b<0||m.index<b)){b=m.index;pl=H[i][0];}}}if(!pl){if(/weidian/i.test(u))pl="weidian";else if(/taobao|tmall/i.test(u))pl="taobao";else if(/alibaba/i.test(u))pl="1688";}var id=null,ps=[/(?:^|[?&#\\/])item_?id=(\\d{6,})/i,/(?:^|[?&#])offer_?id=(\\d{6,})/i,/[?&#]id=(\\d{6,})/i,/\\/offer\\/(\\d{6,})/i,/\\/i(\\d{6,})\\.htm/i,/\\/product\\/(?:weidian|taobao|tmall|1688)\\/(\\d{6,})/i,/\\/item\\/(\\d{6,})/i,/\\/(\\d{9,})\\.html?\\b/i];for(i=0;i<ps.length;i++){m=u.match(ps[i]);if(m){id=m[1];break;}}if(!id&&/^\\d{6,}$/.test(u))id=u;var sh=!id&&/(?:^|[\\/.])(?:m\\.tb\\.cn|e\\.tb\\.cn|youshop10\\.com|qr\\.1688\\.com)/i.test(u);if(!id&&!sh){m=u.replace(/(?:spm|memberId|referId|affcode|invite_?code|scm|pvid|ut_sk|sku_?id)=[^&#]*/gi,"").match(/(\\d{9,})/);if(m)id=m[1];}return{platform:pl,id:id,short:sh};}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c];});}`;
const TOOL_UI = {
  "link-converter": () => `<div class="tool"><label for="lc">Weidian, Taobao, 1688 or agent link</label><input id="lc" placeholder="https://weidian.com/item.html?itemID=…"><div class="row"><button class="btn red" id="go">Convert</button></div><div class="out" id="out">Your buy links will appear here.</div></div>
<script>${EXTRACT}
var PCID=new Set(${JSON.stringify(P.map(p => p.id))});
var R={mycnbox:"LHYDVW",kakobuy:"w5war",lovegobuy:"9WJ54Y",oopbuy:"LHQC0OS8O",sugargoo:"3751749728009774836"};
function orig(p,id){return p==="taobao"?"https://item.taobao.com/item.htm?id="+id:p==="1688"?"https://detail.1688.com/offer/"+id+".html":"https://weidian.com/item.html?itemID="+id;}
var A=[["MyCNBox",function(p,id){return "https://mycnbox.com/goodsDetail?mallType="+p+"&itemId="+id+"&referId="+R.mycnbox}],["KakoBuy",function(p,id){return "https://www.kakobuy.com/item/details?url="+encodeURIComponent(orig(p,id))+"&affcode="+R.kakobuy}],["Oopbuy",function(p,id){return "https://oopbuy.com/product/"+p+"/"+id+"?inviteCode="+R.oopbuy}],["LoveGoBuy",function(p,id){return "https://www.lovegobuy.com/product?platform="+p+"&id="+id+"&invite_code="+R.lovegobuy}],["Sugargoo",function(p,id){return "https://www.sugargoo.com/#/home/productDetail?productLink="+encodeURIComponent(orig(p,id))+"&memberId="+R.sugargoo}]];
function run(){var r=pcExtract(document.getElementById("lc").value),o=document.getElementById("out");if(!r.id){o.textContent=r.short?"That is a short share link. Open it in your browser first, then paste the full product link it opens.":"Couldn't find an item ID in that link. Paste a full product or agent link.";return;}var p=r.platform||(r.id.length<=10?"weidian":"taobao");o.innerHTML="<b>"+esc(p)+(r.platform?"":" (guessed)")+" · "+esc(r.id)+"</b>\\n"+A.map(function(a){var u=a[1](p,r.id);return esc(a[0])+': <a href="'+esc(u)+'" target="_blank" rel="sponsored noopener">'+esc(u)+"</a>";}).join("\\n")+(PCID.has(r.id)?'\\n\\nOn Puro Classico: <a href="/product/'+esc(r.id)+'">/product/'+esc(r.id)+"</a>":"");}
document.getElementById("go").onclick=run;document.getElementById("lc").onkeydown=function(e){if(e.key==="Enter")run();};</script>`,
  "qc-checker": () => `<div class="tool"><label for="qi">Product link or item ID</label><input id="qi" placeholder="https://weidian.com/item.html?itemID=… or 7231806587"><label for="qp" style="margin-top:10px">Marketplace (if you paste only an ID)</label><select id="qp"><option value="">Auto-detect</option><option value="weidian">Weidian</option><option value="taobao">Taobao</option><option value="1688">1688</option></select><div class="row"><button class="btn red" id="go">Check QC photos</button></div><div class="out" id="out">QC photos will appear here.</div><div class="qct" id="th"></div></div>
<script>${EXTRACT}
var PCID=new Set(${JSON.stringify(P.map(p => p.id))});
async function run(){var v=document.getElementById("qi").value,r=pcExtract(v),o=document.getElementById("out"),th=document.getElementById("th");th.innerHTML="";if(!r.id&&/^\\d{6,}$/.test(v.trim()))r={id:v.trim()};if(!r.id){o.textContent=r.short?"That is a short share link. Open it in your browser first, then paste the full product link it opens.":"Couldn't find an item ID. Paste a full link or the numeric ID.";return;}var p=r.platform||document.getElementById("qp").value||(r.id.length<=10?"weidian":"taobao");o.textContent="Checking "+p+" · "+r.id+"…";
try{var res=await fetch("/api/qc?storefront="+p+"&id="+encodeURIComponent(r.id));var d=res.ok?await res.json():null;var t=(d&&d.thumbnails)||[];if(t.length){o.innerHTML="Real QC photos for <b>"+esc(p)+" · "+esc(r.id)+"</b> ("+t.length+" shown)."+(PCID.has(r.id)?" <a href=\\"/product/"+esc(r.id)+"\\">Open on Puro Classico →</a>":"");th.innerHTML=t.map(function(u){return '<a href="'+esc(u)+'" target="_blank" rel="noopener"><img src="'+esc(u)+'" alt="QC photo" loading="lazy" onerror="this.parentNode.remove()"></a>';}).join("");}else o.textContent="No QC photos found yet for "+p+" · "+r.id+". Photos only exist once someone has bought it through an agent.";}catch(e){o.textContent="Couldn't reach the QC service, try again in a moment.";}}
document.getElementById("go").onclick=run;document.getElementById("qi").onkeydown=function(e){if(e.key==="Enter")run();};</script>`,
  "weight-estimator": () => `<div class="tool"><table id="wt"></table><div class="out" id="out"></div></div>
<script>var W=[["T-shirt",250],["Shirt / polo",330],["Shorts",350],["Hoodie / sweater",700],["Pants / jeans",600],["Light jacket",700],["Puffer / heavy jacket",1100],["Sneakers (no box)",900],["Sneakers (with box)",1300],["Bag",550],["Cap / beanie",220],["Belt / small accessory",200]];
var t=document.getElementById("wt");t.innerHTML=W.map(function(w,i){return '<tr><td>'+w[0]+' <span style="color:var(--muted)">~'+w[1]+' g</span></td><td style="width:90px"><input type="number" min="0" value="0" data-i="'+i+'"></td></tr>';}).join("");
function run(){var g=0,n=0;t.querySelectorAll("input").forEach(function(x){var q=Math.max(0,parseInt(x.value)||0);g+=q*W[+x.dataset.i][1];n+=q;});document.getElementById("out").innerHTML=n?("Estimated shipped weight: <b>~"+(g/1000).toFixed(2)+" kg</b> for "+n+" item"+(n>1?"s":"")+". <a href=\\"/tools/shipping-calculator?kg="+(g/1000).toFixed(2)+"\\">Estimate shipping →</a>"):"Add quantities to see a total.";}
t.addEventListener("input",run);run();</script>`,
  "shipping-calculator": () => `<div class="tool"><label for="co">Destination</label><select id="co"></select><label for="kg" style="margin-top:10px">Parcel weight (kg)</label><input id="kg" type="number" min="0" step="0.1" placeholder="e.g. 2.5"><div class="out" id="out">Pick a destination and weight.</div></div>
<script>var Z={"United States":"na","Canada":"na","United Kingdom":"eu","Germany":"eu","France":"eu","Netherlands":"eu","Italy":"eu","Spain":"eu","Poland":"eu","Ireland":"eu","Norway":"nordic","Sweden":"nordic","Denmark":"nordic","Finland":"nordic","Rest of Europe":"eu","Australia":"oce","New Zealand":"oce","Rest of world":"row"};
var RT={nordic:[["Economy",5,7],["Registered / special line",7,10],["Express (DHL/EMS)",9,15]],eu:[["Economy",5,6.5],["Registered / special line",7,9.5],["Express (DHL/EMS)",8,14]],na:[["Economy",6,8],["Registered / special line",8,11],["Express (DHL/EMS)",9,16]],oce:[["Economy",6,9],["Registered / special line",8,12],["Express (DHL/EMS)",10,17]],row:[["Economy",6,9],["Registered / special line",8,12],["Express (DHL/EMS)",10,18]]};
var co=document.getElementById("co"),kg=document.getElementById("kg");co.innerHTML=Object.keys(Z).map(function(k){return "<option>"+k+"</option>";}).join("");var q=new URLSearchParams(location.search).get("kg");if(q)kg.value=q;
function run(){var k=parseFloat(kg.value),o=document.getElementById("out");if(!k||k<=0){o.textContent="Pick a destination and weight.";return;}if(k>30){o.textContent="Too heavy for a parcel estimate (over 30 kg). Split it into several parcels or ask your agent for a freight quote.";return;}o.innerHTML=RT[Z[co.value]].map(function(l){var lo=Math.round(l[1]+l[2]*k*0.85),hi=Math.round(l[1]+l[2]*k*1.2);return l[0]+": <b>~$"+(lo===hi?lo.toLocaleString("en-US"):lo.toLocaleString("en-US")+"–"+hi.toLocaleString("en-US"))+"</b>";}).join("\\n")+"\\n\\n<span style=\\"color:var(--muted)\\">Ballpark only. Check your agent's estimator for the real price.</span>";}
co.onchange=run;kg.oninput=run;run();</script>`,
};
export function renderTools() {
  const bc = crumbs([["Home", "/"], ["Tools", "/tools"]]);
  const body = `${bc.html}<h1>Free rep tools</h1><p class="lead">Convert links, check QC photos and estimate weight and shipping before you order.</p>
<div class="chips" style="flex-direction:column;align-items:flex-start">${TOOL_LINKS.map(([t, u]) => `<a href="${u}" style="font-size:17px">${esc(t)} →</a>`).join("")}</div>`;
  return page({ title: "Free Rep Tools: Link Converter, QC Checker, Shipping Calculator · Puro Classico", desc: "Free tools for buying reps through agents: link converter, QC photo checker, weight estimator and shipping calculator.", path: "/tools", body, jsonld: [bc.data] });
}
export function renderTool(s) {
  const t = own(TOOLS, s) && own(TOOL_UI, s) ? TOOLS[s] : null; if (!t) return null;
  const path = "/tools/" + s; const bc = crumbs([["Home", "/"], ["Tools", "/tools"], [t.name, path]]);
  const app = { "@context": "https://schema.org", "@type": "WebApplication", name: t.name + ": Puro Classico", url: SITE + path, applicationCategory: "UtilitiesApplication", operatingSystem: "Any", offers: { "@type": "Offer", price: "0", priceCurrency: "USD" }, description: t.desc };
  const body = `${bc.html}${TOOL_CSS}<h1>${esc(t.name)}</h1><p class="lead">${esc(t.lead)}</p>${TOOL_UI[s]()}<div class="prose">${t.about}</div>
<h2>More tools</h2><div class="chips">${TOOL_LINKS.filter(([, u]) => u !== path).map(([n, u]) => `<a href="${u}">${esc(n)}</a>`).join("")}<a href="/how-to-order">How to order</a></div>`;
  return page({ title: t.title, desc: t.desc, path, body, jsonld: [bc.data, app] });
}

// ------------------------------------------------------------------ guides
export function renderGuides() {
  const bc = crumbs([["Home", "/"], ["Guides", "/guides"]]);
  const body = `${bc.html}<h1>Guides</h1><p class="lead">Everything you need to order your first finds from China: agents, QC photos, sizing and shipping.</p>
<div class="chips" style="flex-direction:column;align-items:flex-start">${GUIDE_LINKS.map(([t, u]) => `<a href="${u}" style="font-size:17px">${esc(t)} →</a>`).join("")}</div>`;
  return page({ title: "Rep Buying Guides: Agents, QC, Sizing & Shipping · Puro Classico", desc: "Step-by-step guides for buying from Weidian, Taobao and 1688 through a shopping agent.", path: "/guides", body, jsonld: [bc.data] });
}

export function renderGuide(s) {
  const g = own(GUIDES, s) ? GUIDES[s] : null; if (!g) return null;
  const path = "/guides/" + s; const bc = crumbs([["Home", "/"], ["Guides", "/guides"], [g.h1, path]]);
  const { all } = idx();
  // A guide shows a date only when it stores its own (g.updated = the day its text was last revised and its facts
  // re-checked, set by hand in content*.js). The catalogue build date says nothing about a guide's text.
  const body = `${bc.html}<article class="prose"><h1>${esc(g.h1)}</h1><p style="color:var(--muted);font-size:14px">${g.updated ? `Updated ${esc(g.updated)} · ` : ""}Puro Classico</p>${g.body}${g.faq ? faqHtml(g.faq) : ""}</article>
<h2>Popular finds</h2>${grid(all.slice(0, 8))}
<h2>More guides</h2><div class="chips">${GUIDE_LINKS.filter(([, u]) => u !== path).map(([t, u]) => `<a href="${u}">${esc(t)}</a>`).join("")}</div>`;
  const art = { "@context": "https://schema.org", "@type": "Article", headline: g.h1, description: g.desc, dateModified: g.updated || undefined, url: SITE + path,
    author: { "@type": "Organization", name: "Puro Classico", url: SITE + "/" }, publisher: { "@type": "Organization", name: "Puro Classico", logo: { "@type": "ImageObject", url: SITE + "/logo-mark.png" } } };
  const ld = [bc.data, art]; if (g.faq) ld.push(faqLd(g.faq));
  return page({ title: g.title + " · Puro Classico", desc: g.desc, path, body, jsonld: ld });
}

// ------------------------------------------------------------------ sitemaps
// No <lastmod>: the only date the site has is the catalogue build date, which is not the date any one page changed.
// Add it back only from a real per-page date (a guide's `updated`, a per-find date once the catalogue stores one).
const xml = body => new Response(`<?xml version="1.0" encoding="UTF-8"?>\n${body}`, { headers: { "content-type": "application/xml; charset=utf-8", "cache-control": "public, max-age=3600" } });
export function sitemapIndex() {
  return xml(`<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>${SITE}/sitemap-pages.xml</loc></sitemap>
<sitemap><loc>${SITE}/sitemap-products.xml</loc></sitemap>
</sitemapindex>`);
}
export function sitemapPages() {
  const { brandSlug } = idx();
  const urls = ["/", "/how-to-order", "/brands", "/guides", "/old-money", "/stockholm-spreadsheet", "/grisch-spreadsheet", ...Object.keys(AGENT_INTRO).map(k => `/${k}-spreadsheet`), ...AGENT_BRAND_AGENTS.flatMap(k => agentBrands().map(b => `/${k}-spreadsheet/${brandSlug.get(b)}`)),
    ...Object.values(CATS).map(c => "/category/" + c.slug), ...[...brandSlug.values()].map(s => "/brand/" + s),
    ...Object.keys(GUIDES).map(s => "/guides/" + s), "/best", ...models().map(m => "/best/" + m.slug), "/tools", ...Object.keys(TOOLS).map(s => "/tools/" + s), "/terms", "/privacy"];
  return xml(`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.map(u => `<url><loc>${SITE}${u}</loc></url>`).join("\n")}\n</urlset>`);
}
export function sitemapProducts() {
  const rows = P.filter(indexable).map(p => {
    const src = imgSrc(p);
    return `<url><loc>${SITE}${productUrl(p)}</loc>${src ? `<image:image><image:loc>${esc(src)}</image:loc></image:image>` : ""}</url>`;
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
const STYLE_HUBS = {
  stockholm: { name: "Stockholm style", h: "Stockholm Style Spreadsheet",
    brands: ["Ralph Lauren", "Moncler", "Stone Island", "Lacoste", "Acne Studios", "Ami", "Burberry", "Golden Goose", "Loro Piana", "Arc'teryx",
             "CP Company", "Canada Goose", "Maison Margiela", "Tommy Hilfiger", "Fred Perry"],
    sub: n => `${n} Stockholm style finds: quarter-zips, cable knits, gilets, clean sneakers.`,
    title: n => `Stockholm Style Spreadsheet 2026: ${n} Finds | Puro Classico`,
    desc: n => `The Stockholm style reps spreadsheet: ${n} finds from Ralph Lauren, Moncler, Stone Island, Lacoste, Acne Studios and more, with QC photos and one-tap agent links.`,
    faq: [["What is Stockholm style?", "The clean Scandinavian take on old money: Ralph Lauren cable knits and quarter-zips, Moncler gilets, Stone Island, Acne Studios basics, straight jeans and white leather sneakers. Neutral colours, small logos, good fit."],
          ["What should I buy first?", "A cable-knit or half-zip in navy, grey or cream, a quilted gilet and a pair of clean sneakers cover most outfits. Knitwear is light, so it is cheap to ship."],
          ["Do these finds fit like the real thing?", "Rep knitwear often runs a size small. Compare the listing's measurements with a sweater you own, and check the QC photos before you ship."],
          ["Is the spreadsheet free?", "Yes. You pay your agent for the item and shipping only. Links may be affiliate links."]] },
  grisch: { name: "Grisch", h: "Grisch Spreadsheet",
    brands: ["Ralph Lauren", "Moncler", "Lacoste", "Burberry", "Loro Piana", "Brunello Cucinelli", "Golden Goose", "Stone Island", "Jacob Cohen",
             "Hermes", "Rolex", "Cartier", "Tom Ford", "Zegna", "Barbour", "Canada Goose"],
    sub: n => `${n} grisch finds: Ralph, Moncler, Loro Piana, Lacoste and the rest of the look.`,
    title: n => `Grisch Spreadsheet 2026: ${n} Old Money Finds | Puro Classico`,
    desc: n => `The grisch spreadsheet: ${n} old money finds from Ralph Lauren, Moncler, Loro Piana, Lacoste, Burberry and more, with QC photos and one-tap agent links.`,
    faq: [["What does grisch mean?", "Grisch is Scandinavian slang for the preppy old money look: Ralph Lauren polos and knits, Moncler, Loro Piana loafers, Lacoste, a good watch and Golden Goose or clean leather sneakers."],
          ["What are the hardest grisch pieces?", "Ralph Lauren cable knits and quarter-zips, Moncler gilets and puffers, Loro Piana suede loafers, Burberry check scarves and Golden Goose sneakers are the core of the look."],
          ["How do I order grisch reps?", "Open a find, tap the buy button for your agent (MyCNBox, KakoBuy, Oopbuy, LoveGoBuy or Sugargoo), pick your size and pay. Check the QC photos at the warehouse before you ship."],
          ["Is the spreadsheet free?", "Yes. You pay your agent for the item and shipping only. Links may be affiliate links."]] },
};

export function hubSpec(path) {
  const { all, slugBrand, byBrand, brandSlug, byCat } = idx();
  const nf = n => n.toLocaleString("en-US");
  let m;
  if ((m = path.match(/^\/(stockholm|grisch)-spreadsheet$/))) {
    const st = STYLE_HUBS[m[1]], have = st.brands.filter(b => byBrand.has(b));
    const n = nf(have.reduce((t, b) => t + byBrand.get(b).length, 0));
    const other = Object.entries(STYLE_HUBS).filter(([k]) => k !== m[1]).map(([k, v]) => [`${v.h}`, `/${k}-spreadsheet`]);
    return { path, preset: { brands: have.map(b => brandSlug.get(b)) }, h: st.h, sub: st.sub(n), title: st.title(n), desc: st.desc(n),
      crumbs: [["Home", "/"], ["Old money", "/old-money"], [st.h, path]],
      chips: [[`Brands in the ${st.name.toLowerCase()} look`, have.map(b => [`${b} reps`, `/brand/${brandSlug.get(b)}`])],
              ["More old money", other.concat([["Old money spreadsheet", "/old-money"], ["MyCNBox spreadsheet", "/mycnbox-spreadsheet"]])]],
      faq: st.faq };
  }
  if ((m = path.match(/^\/(mycnbox|kakobuy|oopbuy|lovegobuy|sugargoo)-spreadsheet$/))) {
    const key = m[1], a = AGENTS[key], meta = AGENT_INTRO[key]; if (!a || !meta) return null;
    const N = nf(all.length), brands = AGENT_BRAND_AGENTS.includes(key) ? agentBrands() : [];
    return { path, preset: { agent: key }, h: `${a.name} Spreadsheet`, sub: `${N} finds, each with a one-tap ${a.name} buy button.`,
      title: `${meta.title}: ${N} Finds | Puro Classico`, desc: `The ${a.name} spreadsheet: ${N} rep finds with prices, QC photos and one-tap ${a.name} links. Search, filter and buy in one place.`,
      crumbs: [["Home", "/"], [`${a.name} spreadsheet`, path]],
      chips: [[`Popular brands on ${a.name}`, brands.slice(0, 16).map(b => [b, `${path}/${brandSlug.get(b)}`])],
              ["Other agent spreadsheets", Object.keys(AGENT_INTRO).filter(k => k !== key).map(k => [`${AGENTS[k].name} spreadsheet`, `/${k}-spreadsheet`])]],
      faq: [[`What is the ${a.name} spreadsheet?`, `A searchable list of ${N} Weidian, Taobao and 1688 finds. Every find opens directly in ${a.name}, so there is nothing to copy or translate.`],
            [`How do I order with ${a.name}?`, `Open a find, tap Buy via ${a.name}, pick your size and pay for the item plus delivery to the warehouse. Check the QC photos, then ship your parcel.`],
            [`Is it free?`, `Yes. You only pay ${a.name} for what you order and for shipping. Links may be affiliate links.`]] };
  }
  if ((m = path.match(/^\/(mycnbox|kakobuy|oopbuy|sugargoo)-spreadsheet\/([a-z][a-z0-9-]*)$/))) {
    const key = m[1], s = m[2], a = AGENTS[key], b = slugBrand.get(s);
    if (!a || !b || !agentBrands().includes(b)) return null;
    const n = nf(byBrand.get(b).length);
    return { path, preset: { agent: key, brand: s }, h: `${b} on ${a.name}`, sub: `${n} ${b} finds with one-tap ${a.name} links.`,
      title: `${b} ${a.name} Spreadsheet 2026: ${n} Finds | Puro Classico`, desc: `${n} ${b} rep finds with prices, QC photos and one-tap ${a.name} buy links.`,
      crumbs: [["Home", "/"], [`${a.name} spreadsheet`, `/${key}-spreadsheet`], [b, path]],
      chips: [[`${b} on other agents`, AGENT_BRAND_AGENTS.filter(k => k !== key).map(k => [AGENTS[k].name, `/${k}-spreadsheet/${s}`]).concat([[`All ${b} reps`, `/brand/${s}`]])],
              [`More brands on ${a.name}`, agentBrands().filter(x => x !== b).slice(0, 14).map(x => [x, `/${key}-spreadsheet/${brandSlug.get(x)}`])]],
      faq: [[`How do I buy ${b} reps on ${a.name}?`, `Open a find, tap Buy via ${a.name}, choose your size and pay. ${a.name} sends QC photos when it reaches the warehouse; check them, then ship.`]] };
  }
  if ((m = path.match(/^\/brand\/([a-z0-9-]+)$/))) {
    const s = m[1], b = slugBrand.get(s); if (!b) return null;
    const list = byBrand.get(b), n = nf(list.length);
    const rel = relatedBrands(b).slice(0, 12);
    const ag = agentBrands().includes(b) ? AGENT_BRAND_AGENTS.map(k => [`${b} on ${AGENTS[k].name}`, `/${k}-spreadsheet/${s}`]) : [];
    return { path, preset: { brand: s }, h: `${b} Reps`, sub: `${n} ${b} finds from Weidian, Taobao and 1688.`,
      title: `${b} Reps Spreadsheet 2026: ${n} Finds | Puro Classico`, desc: `${n} ${b} rep finds with prices, QC photos and links for MyCNBox, KakoBuy, Oopbuy and more.`,
      crumbs: [["Home", "/"], ["Brands", "/brands"], [b, path]],
      chips: [...(ag.length ? [[`Buy ${b} with your agent`, ag]] : []), ["Related brands", rel.map(x => [x, `/brand/${brandSlug.get(x)}`]).concat([["All brands", "/brands"]])]],
      faq: [[`Where can I buy ${b} reps?`, `Every ${b} find here opens in MyCNBox, KakoBuy, Oopbuy, LoveGoBuy or Sugargoo. Pick your agent on the find, choose your size and check the QC photos before you ship.`]] };
  }
  if ((m = path.match(/^\/category\/([a-z0-9-]+)$/))) {
    const s = m[1], c = own(CAT_BY_SLUG, s) ? CAT_BY_SLUG[s] : null; if (!c) return null;
    const list = byCat.get(c) || [], meta = CATS[c], n = nf(list.length);
    const top = [...new Set(list.map(p => p.brand))].filter(b => brandSlug.has(b)).slice(0, 16);
    return { path, preset: { cat: c }, h: meta.h, sub: `${n} finds, most viewed first.`,
      title: `${meta.h}: ${n} Finds (2026) | Puro Classico`, desc: `${n} ${meta.name.toLowerCase()} rep finds with prices, QC photos and one-tap agent links, sorted by most viewed.`,
      crumbs: [["Home", "/"], [meta.name, path]],
      chips: [[`Top brands in ${meta.name.toLowerCase()}`, top.map(b => [b, `/brand/${brandSlug.get(b)}`])],
              ["Other categories", Object.values(CATS).filter(x => x.slug !== s && x.slug !== "toys").map(x => [x.name, `/category/${x.slug}`])]],
      faq: [] };
  }
  return null;
}
// The HTML pieces the middleware puts into index.html for a hub spec.
export function hubParts(spec) {
  const bc = crumbs(spec.crumbs);
  const crumbHtml = `<nav class="hub-bc" aria-label="Breadcrumb">${spec.crumbs.map((c, i) => i < spec.crumbs.length - 1 ? `<a href="${c[1]}">${esc(c[0])}</a><span>›</span>` : `<span aria-current="page">${esc(c[0])}</span>`).join("")}</nav>`;
  const seo = `<section class="hub-seo">${spec.chips.filter(c => c[1].length).map(([t, links]) => `<h2>${esc(t)}</h2><div class="hub-chips">${links.map(([n, u]) => `<a href="${u}">${esc(n)}</a>`).join("")}</div>`).join("")}${spec.faq.length ? `<h2>FAQ</h2>${spec.faq.map(([q, a]) => `<details><summary>${esc(q)}</summary><p>${esc(a)}</p></details>`).join("")}` : ""}</section>`;
  const ld = [bc.data]; if (spec.faq.length) ld.push(faqLd(spec.faq));
  const page = { h: spec.h, sub: spec.sub, agent: spec.preset.agent || null, brand: spec.preset.brand || null, cat: spec.preset.cat || null, brands: spec.preset.brands || null };
  const head = `<script>window.PC_PAGE=${JSON.stringify(page).replace(/</g, "\\u003c")};document.documentElement.classList.add("hub"${page.agent ? ',"agent-lock"' : ""});</script>` +
    ld.map(o => '<script type="application/ld+json">' + JSON.stringify(o).replace(/</g, "\\u003c") + "</script>").join("");
  return { crumbHtml, seo, head };
}
