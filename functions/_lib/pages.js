// Server-rendered SEO pages. Each renderer returns a Response (or null when the route doesn't exist -> 404).
import { SITE, MYCNBOX_INVITE, BUILT, P, idx, indexable, CATS, CAT_BY_SLUG, AGENTS, esc, slug, money, imgSrc, productUrl, brandUrl, catUrl,
  grid, crumbs, pager, page, card, GUIDE_LINKS, BRAND_MIN } from "./site.js";
import { CAT_INTRO, AGENT_INTRO, OLD_MONEY, BRAND_INTRO, GUIDES } from "./content.js";

const PER_PAGE = 60;
const faqLd = faq => ({ "@context": "https://schema.org", "@type": "FAQPage",
  mainEntity: faq.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) });
const faqHtml = faq => `<h2>FAQ</h2><div class="faq">${faq.map(([q, a]) => `<details><summary>${esc(q)}</summary><p>${esc(a)}</p></details>`).join("")}</div>`;
const listLd = (name, url, items) => ({ "@context": "https://schema.org", "@type": "CollectionPage", name, url: SITE + url,
  mainEntity: { "@type": "ItemList", numberOfItems: items.length,
    itemListElement: items.slice(0, 30).map((p, i) => ({ "@type": "ListItem", position: i + 1, url: SITE + productUrl(p), name: p.title })) } });
const priceRange = l => { const u = l.map(p => p.usd).filter(x => x > 0).sort((a, b) => a - b); return u.length ? `${money(u[0])}–${money(u[u.length - 1])}` : ""; };

// ------------------------------------------------------------------ product
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
    `<a class="${i === 0 ? "first" : ""}" href="${esc(a.build(p))}" target="_blank" rel="sponsored nofollow noopener">Buy via ${a.name}${i === 0 ? "<small>Most popular</small>" : ""}</a>`).join("");
  const plat = { weidian: "Weidian", taobao: "Taobao", "1688": "1688" }[p.platform] || p.platform;
  const desc = `${p.title}${p.brand ? "" : ""} rep for about ${money(p.usd)} (¥${p.cny}) on ${plat}` +
    (p.qc ? ` with ${p.qc} buyer QC photos` : "") + `. Open it on MyCNBox, KakoBuy, Oopbuy or any shopping agent.`;
  const sameBrand = bUrl ? (byBrand.get(p.brand) || []).filter(x => x.id !== p.id).slice(0, 8) : [];
  const sameCat = (byCat.get(p.cat) || []).filter(x => x.id !== p.id && x.brand !== p.brand).slice(0, 8);
  const about = `<p>The <strong>${esc(p.title)}</strong> is a ${esc((cat.name || "").toLowerCase())} find${p.brand ? ` in the ${esc(p.brand)} style` : ""} listed on ${plat}` +
    (p.seller && !/marketplace/i.test(p.seller) ? ` by ${esc(p.seller)}` : "") + `. The listed price is ¥${p.cny} (about ${money(p.usd)}) before shipping` +
    (variants.length ? `, and it comes in ${variants.length} option${variants.length > 1 ? "s" : ""}: ${esc(variants.slice(0, 8).join(", "))}${variants.length > 8 ? "…" : ""}` : "") + `.</p>` +
    (p.qc ? `<p>Buyers have shared <strong>${p.qc} QC photo${p.qc > 1 ? "s" : ""}</strong> of this listing, so you can check logos, stitching and colour before you order. When yours reaches the warehouse, your agent takes QC photos of your exact item too.</p>`
          : `<p>There are no buyer QC photos for this listing yet — once you order, your agent photographs your exact item at the warehouse before it ships, so you can still check it before paying for shipping.</p>`) +
    `<p>International shipping isn't included in the price; you pay it when you ship your parcel, and it depends on weight and your country.</p>`;
  const body = `${bc.html}
<div class="pd">
  <div><div class="pimg">${src ? `<img src="${esc(src)}" alt="${esc(p.title)}" width="600" height="600" fetchpriority="high">` : ""}</div>
    ${qcs.length ? `<h2 style="font-size:18px;margin:18px 0 0">Real QC photos</h2><div class="qcs">${qcs.map((u, i) => `<a href="${esc(u)}" target="_blank" rel="noopener"><img src="${esc(u)}" alt="${esc(p.title)} QC photo ${i + 1}" width="96" height="96" loading="lazy" onerror="this.parentNode.remove()"></a>`).join("")}</div>` : ""}
  </div>
  <div>
    ${bUrl ? `<a href="${bUrl}" style="color:var(--muted);text-decoration:none;letter-spacing:.08em;text-transform:uppercase;font-size:13px">${esc(p.brand)}</a>` : (p.brand ? `<span style="color:var(--muted);letter-spacing:.08em;text-transform:uppercase;font-size:13px">${esc(p.brand)}</span>` : "")}
    <h1>${esc(p.title)}</h1>
    <div class="price">${money(p.usd)}<small>¥${p.cny} · before shipping</small></div>
    <div class="buy">${agents}</div>
    <dl class="kv"><dt>Marketplace</dt><dd>${plat}</dd><dt>Category</dt><dd>${cUrl ? `<a href="${cUrl}">${esc(cat.name)}</a>` : esc(p.cat)}</dd>
      ${variants.length ? `<dt>Options</dt><dd>${esc(variants.slice(0, 12).join(" · "))}</dd>` : ""}<dt>QC photos</dt><dd>${p.qc || "None yet"}</dd><dt>Item ID</dt><dd>${esc(p.itemId || p.id)}</dd></dl>
    <p><a href="/#p/${encodeURIComponent(p.id)}" style="color:var(--accent)">Open in the catalogue →</a></p>
  </div>
</div>
<h2>About this find</h2><div class="prose">${about}</div>
<h2>How to buy it</h2><ol class="steps prose"><li>Tap <strong>Buy via MyCNBox</strong> (or your agent). The listing opens pre-filled.</li><li>Pick your size and colour — check our <a href="/guides/sizing">sizing guide</a> — and pay for the item plus delivery to the warehouse.</li><li>Check the QC photos (<a href="/guides/how-to-qc">what to look for</a>), then combine items into one parcel and ship. <a href="/how-to-order">Watch the 1:47 video</a>.</li></ol>
${sameBrand.length ? `<h2>More ${esc(p.brand)} finds</h2>${grid(sameBrand)}<p><a href="${bUrl}" style="color:var(--accent)">All ${esc(p.brand)} reps →</a></p>` : ""}
${sameCat.length ? `<h2>Similar ${esc((cat.name || p.cat).toLowerCase())}</h2>${grid(sameCat)}${cUrl ? `<p><a href="${cUrl}" style="color:var(--accent)">All ${esc((cat.name || p.cat).toLowerCase())} →</a></p>` : ""}` : ""}`;
  const pageLd = { "@context": "https://schema.org", "@type": "ItemPage", name: p.title, url: SITE + productUrl(p), description: desc,
    primaryImageOfPage: src ? { "@type": "ImageObject", contentUrl: src } : undefined, isPartOf: { "@type": "WebSite", name: "Puro Classico", url: SITE + "/" } };
  return page({ title: `${p.title} Rep — QC Photos & Buy on Any Agent · Puro Classico`, desc, path: productUrl(p), body,
    jsonld: [bc.data, pageLd], image: src || undefined, robots: indexable(p) ? "index,follow,max-image-preview:large" : "noindex,follow" });
}

// ------------------------------------------------------------------ hubs
function hub({ path, n, list, title, desc, h1, intro, trail, chips = "", extra = "", faq = null, total = null }) {
  const pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
  if (n < 1 || n > pages) return null;
  const slice = list.slice((n - 1) * PER_PAGE, n * PER_PAGE);
  const url = n === 1 ? path : `${path}/${n}`;
  const bc = crumbs(trail.concat(n > 1 ? [[`Page ${n}`, url]] : []));
  const qcTotal = list.reduce((s, p) => s + (p.qc || 0), 0);
  const body = `${bc.html}<h1>${esc(h1)}${n > 1 ? ` <small style="color:var(--muted);font-size:.5em">page ${n}</small>` : ""}</h1>
${n === 1 ? `<div class="prose">${intro}</div>` : ""}
<div class="facts"><span>${(total || list.length).toLocaleString("en-US")} finds</span>${priceRange(list) ? `<span>${priceRange(list)}</span>` : ""}${qcTotal ? `<span>${qcTotal.toLocaleString("en-US")} buyer QC photos</span>` : ""}<span>Updated ${BUILT}</span></div>
${chips}
${grid(slice, n === 1 ? 4 : 0)}
${pager(path, n, pages)}
${n === 1 ? extra : ""}${n === 1 && faq ? faqHtml(faq) : ""}`;
  const ld = [bc.data, listLd(h1, url, slice)]; if (n === 1 && faq) ld.push(faqLd(faq));
  return page({ title: n > 1 ? `${title} — Page ${n}` : title, desc, path: url, body, jsonld: ld,
    image: slice[0] ? imgSrc(slice[0]) : undefined });
}

export function renderBrand(s, n) {
  const { slugBrand, byBrand, brandSlug } = idx();
  const b = slugBrand.get(s); if (!b) return null;
  const list = byBrand.get(b);
  const cats = [...new Set(list.map(p => p.cat))].filter(c => CATS[c]);
  const intro = BRAND_INTRO[b] || `<p>${list.length} ${esc(b)} finds from Weidian, Taobao and 1688 sellers, sorted with the most QC'd and most popular listings first. Prices run from ${priceRange(list)} before shipping.</p><p>Tap any find to see the listing details, buyer QC photos and buy links for MyCNBox, KakoBuy, Oopbuy, LoveGoBuy and Sugargoo.</p>`;
  const others = [...brandSlug.keys()].filter(x => x !== b).sort((a, c) => byBrand.get(c).length - byBrand.get(a).length).slice(0, 16);
  const extra = `<h2>How to buy ${esc(b)} reps</h2><div class="prose"><p>Open a find, tap <strong>Buy via MyCNBox</strong> (or your agent), pick your size and pay for the item plus delivery to the warehouse. Check the QC photos before shipping — see <a href="/guides/how-to-qc">how to read QC photos</a> — then combine your items into one parcel. New to this? <a href="/how-to-order">Watch the how-to-order video</a>.</p></div>
<h2>Other brands</h2><div class="chips">${others.map(x => `<a href="/brand/${brandSlug.get(x)}">${esc(x)}</a>`).join("")}<a href="/brands">All brands →</a></div>`;
  return hub({ path: "/brand/" + s, n, list, title: `${b} Reps Spreadsheet 2026 — ${list.length.toLocaleString("en-US")} ${b} Finds · Puro Classico`,
    desc: `${list.length.toLocaleString("en-US")} ${b} rep finds with prices (${priceRange(list)}) and buyer QC photos. Open any listing on MyCNBox, KakoBuy, Oopbuy or your agent.`,
    h1: `${b} reps`, intro, trail: [["Home", "/"], ["Brands", "/brands"], [b, "/brand/" + s]],
    chips: cats.length > 1 ? `<div class="chips">${cats.map(c => `<a href="${catUrl(c)}">${esc(CATS[c].name)}</a>`).join("")}</div>` : "", extra,
    faq: [[`Where can I buy ${b} reps?`, `Puro Classico lists ${list.length} ${b} finds from Weidian, Taobao and 1688. Each one opens directly in shopping agents like MyCNBox, KakoBuy and Oopbuy, which buy the item for you and ship it internationally.`],
          [`How much do ${b} reps cost?`, `Listings on this page range from ${priceRange(list)} before international shipping, which depends on weight and your country.`]] });
}

export function renderCategory(s, n) {
  const c = CAT_BY_SLUG[s]; if (!c) return null;
  const { byCat, byBrand, brandSlug } = idx(); const list = byCat.get(c) || [];
  const topBrands = [...new Set(list.map(p => p.brand))].filter(b => brandSlug.has(b)).slice(0, 18);
  const meta = CATS[c];
  const extra = `<h2>Top brands in ${esc(meta.name.toLowerCase())}</h2><div class="chips">${topBrands.map(b => `<a href="/brand/${brandSlug.get(b)}">${esc(b)}</a>`).join("")}</div>
<h2>Other categories</h2><div class="chips">${Object.values(CATS).filter(x => x.slug !== s && x.slug !== "toys").map(x => `<a href="/category/${x.slug}">${esc(x.name)}</a>`).join("")}</div>`;
  return hub({ path: "/category/" + s, n, list, title: `${meta.h} — ${list.length.toLocaleString("en-US")} Finds (2026) · Puro Classico`,
    desc: `${list.length.toLocaleString("en-US")} ${meta.name.toLowerCase()} rep finds with prices, buyer QC photos and agent links, sorted by most QC'd and most popular.`,
    h1: meta.h, intro: CAT_INTRO[c] || "", trail: [["Home", "/"], [meta.name, "/category/" + s]], extra });
}

export function renderAgent(key, n) {
  const a = AGENTS[key], meta = AGENT_INTRO[key]; if (!a || !meta) return null;
  const { all } = idx(); const path = `/${key}-spreadsheet`;
  const faq = [[`What is the ${a.name} spreadsheet?`, `A list of Weidian, Taobao and 1688 finds that open directly in ${a.name}. Puro Classico's spreadsheet has ${all.length.toLocaleString("en-US")} finds, each with ${a.name} buy links, prices and buyer QC photo counts.`],
               [`How do I order from the ${a.name} spreadsheet?`, `Open a find, tap Buy via ${a.name}, choose your size and pay for the item plus delivery to the warehouse. After the QC photos arrive, submit your parcel and pay international shipping.`]];
  return hub({ path, n, list: all.slice(0, 60), total: all.length, title: `${meta.title} — ${all.length.toLocaleString("en-US")} Finds · Puro Classico`,
    desc: `The ${a.name} spreadsheet: ${all.length.toLocaleString("en-US")} rep finds with prices, QC photo counts and direct ${a.name} links. Updated ${BUILT}.`,
    h1: meta.title, intro: `<p class="lead">${esc(meta.lede)}</p>${meta.body}${key === "mycnbox" ? `<p><a class="btn red" href="${MYCNBOX_INVITE}" target="_blank" rel="sponsored noopener">Claim your MyCNBox new-user coupons</a></p>` : ""}`,
    trail: [["Home", "/"], [meta.title, path]], faq,
    extra: `<p><a class="btn light" href="/">Browse all ${all.length.toLocaleString("en-US")} finds →</a></p><h2>Other agent spreadsheets</h2><div class="chips">${Object.keys(AGENT_INTRO).filter(k => k !== key).map(k => `<a href="/${k}-spreadsheet">${AGENTS[k].name} spreadsheet</a>`).join("")}<a href="/guides/best-shopping-agent">Which agent is best?</a></div>` });
}

export function renderOldMoney(n) {
  const { all, brandSlug } = idx(); const set = new Set(OLD_MONEY.brands);
  const list = all.filter(p => set.has(p.brand));
  const brands = OLD_MONEY.brands.filter(b => brandSlug.has(b));
  return hub({ path: "/old-money", n, list, title: `Old Money Reps — Quiet Luxury Spreadsheet (${list.length.toLocaleString("en-US")} Finds) · Puro Classico`,
    desc: `Old money and quiet luxury reps: ${list.length.toLocaleString("en-US")} finds from Ralph Lauren, Loro Piana, Lacoste, Moncler, Golden Goose and more.`,
    h1: "Old money & quiet luxury reps", intro: OLD_MONEY.intro, trail: [["Home", "/"], ["Old money", "/old-money"]],
    chips: `<div class="chips">${brands.map(b => `<a href="/brand/${brandSlug.get(b)}">${esc(b)}</a>`).join("")}</div>`,
    faq: [["What are old money reps?", "Replica finds in the understated 'old money' or quiet-luxury style: knitwear, polos, loafers and clean sneakers from brands like Ralph Lauren, Loro Piana and Brunello Cucinelli, without big logos."],
          ["What should I check in QC for old money pieces?", "Knit texture and ribbing, the density of small chest-logo embroidery, collar shape on polos, and leather grain and stitching on shoes and belts."]] });
}

export function renderBrands() {
  const { byBrand, brandSlug } = idx();
  const hubs = [...brandSlug.keys()].sort((a, b) => a.localeCompare(b));
  const groups = {};
  for (const b of hubs) { const L = /[a-z]/i.test(b[0]) ? b[0].toUpperCase() : "#"; (groups[L] = groups[L] || []).push(b); }
  const bc = crumbs([["Home", "/"], ["Brands", "/brands"]]);
  const body = `${bc.html}<h1>Rep brands A–Z</h1><p class="lead">Every brand with ${BRAND_MIN}+ finds on Puro Classico, with the number of finds for each.</p>
${Object.keys(groups).sort().map(L => `<h2>${L}</h2><div class="chips">${groups[L].map(b => `<a href="/brand/${brandSlug.get(b)}">${esc(b)} <span style="color:var(--muted)">${byBrand.get(b).length}</span></a>`).join("")}</div>`).join("")}`;
  return page({ title: "Rep Brands A–Z — Every Brand on the Spreadsheet · Puro Classico", desc: `Browse ${hubs.length} brands on the Puro Classico rep spreadsheet, from Corteiz and Nike to Ralph Lauren and Moncler.`,
    path: "/brands", body, jsonld: [bc.data] });
}

// ------------------------------------------------------------------ guides
export function renderGuides() {
  const bc = crumbs([["Home", "/"], ["Guides", "/guides"]]);
  const body = `${bc.html}<h1>Guides</h1><p class="lead">Everything you need to order your first finds from China: agents, QC photos, sizing and shipping.</p>
<div class="chips" style="flex-direction:column;align-items:flex-start">${GUIDE_LINKS.map(([t, u]) => `<a href="${u}" style="font-size:17px">${esc(t)} →</a>`).join("")}</div>`;
  return page({ title: "Rep Buying Guides — Agents, QC, Sizing & Shipping · Puro Classico", desc: "Step-by-step guides for buying from Weidian, Taobao and 1688 through a shopping agent.", path: "/guides", body, jsonld: [bc.data] });
}

export function renderGuide(s) {
  const g = GUIDES[s]; if (!g) return null;
  const path = "/guides/" + s; const bc = crumbs([["Home", "/"], ["Guides", "/guides"], [g.h1, path]]);
  const { all } = idx();
  const body = `${bc.html}<article class="prose"><h1>${esc(g.h1)}</h1><p style="color:var(--muted);font-size:14px">Updated ${BUILT} · Puro Classico</p>${g.body}${g.faq ? faqHtml(g.faq) : ""}</article>
<h2>Popular finds</h2>${grid(all.slice(0, 8))}
<h2>More guides</h2><div class="chips">${GUIDE_LINKS.filter(([, u]) => u !== path).map(([t, u]) => `<a href="${u}">${esc(t)}</a>`).join("")}</div>`;
  const art = { "@context": "https://schema.org", "@type": "Article", headline: g.h1, description: g.desc, dateModified: BUILT, url: SITE + path,
    author: { "@type": "Organization", name: "Puro Classico", url: SITE + "/" }, publisher: { "@type": "Organization", name: "Puro Classico", logo: { "@type": "ImageObject", url: SITE + "/logo-mark.png" } } };
  const ld = [bc.data, art]; if (g.faq) ld.push(faqLd(g.faq));
  return page({ title: g.title + " · Puro Classico", desc: g.desc, path, body, jsonld: ld });
}

// ------------------------------------------------------------------ sitemaps
const xml = body => new Response(`<?xml version="1.0" encoding="UTF-8"?>\n${body}`, { headers: { "content-type": "application/xml; charset=utf-8", "cache-control": "public, max-age=3600" } });
export function sitemapIndex() {
  return xml(`<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>${SITE}/sitemap-pages.xml</loc><lastmod>${BUILT}</lastmod></sitemap>
<sitemap><loc>${SITE}/sitemap-products.xml</loc><lastmod>${BUILT}</lastmod></sitemap>
</sitemapindex>`);
}
export function sitemapPages() {
  const { brandSlug } = idx();
  const urls = ["/", "/how-to-order", "/brands", "/guides", "/old-money", ...Object.keys(AGENT_INTRO).map(k => `/${k}-spreadsheet`),
    ...Object.values(CATS).map(c => "/category/" + c.slug), ...[...brandSlug.values()].map(s => "/brand/" + s),
    ...Object.keys(GUIDES).map(s => "/guides/" + s), "/terms", "/privacy"];
  return xml(`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.map(u => `<url><loc>${SITE}${u}</loc><lastmod>${BUILT}</lastmod></url>`).join("\n")}\n</urlset>`);
}
export function sitemapProducts() {
  const rows = P.filter(indexable).map(p => {
    const src = imgSrc(p);
    return `<url><loc>${SITE}${productUrl(p)}</loc><lastmod>${BUILT}</lastmod>${src ? `<image:image><image:loc>${esc(src)}</image:loc></image:image>` : ""}</url>`;
  });
  return xml(`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n${rows.join("\n")}\n</urlset>`);
}
