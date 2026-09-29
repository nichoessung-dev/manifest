// Server-rendered SEO pages. Each renderer returns a Response (or null when the route doesn't exist -> 404).
import { SITE, MYCNBOX_INVITE, BUILT, P, idx, indexable, CATS, CAT_BY_SLUG, AGENTS, esc, slug, money, imgSrc, productUrl, brandUrl, catUrl,
  grid, crumbs, pager, page, card, GUIDE_LINKS, TOOL_LINKS, BRAND_MIN } from "./site.js";
import { CAT_INTRO, AGENT_INTRO, OLD_MONEY, BRAND_INTRO as BRAND_INTRO1, GUIDES as GUIDES1 } from "./content.js";
import { BRAND_INTRO2, MODELS as MODELS2, GUIDES2, TOOLS } from "./content2.js";
import { MODELS3, GUIDES3, MODEL_TERM } from "./content3.js";
const MODELS = MODELS2.concat(MODELS3);
const BRAND_INTRO = Object.assign({}, BRAND_INTRO2, BRAND_INTRO1);
const GUIDES = Object.assign({}, GUIDES1, GUIDES2, GUIDES3);
// model pages: which catalogue items belong to each model (by brand + title)
let _models = null, _modelsIdx = null;
export function models() {
  const ix = idx();
  if (_models && _modelsIdx === ix) return _models;
  _modelsIdx = ix;
  const { all } = ix;
  _models = MODELS.map(m => { const re = new RegExp(m.rx, "i"); return Object.assign({}, m, { list: all.filter(p => re.test((p.brand || "") + " " + p.title)) }); })
                  .filter(m => m.list.length >= 5);
  return _models;
}
export function modelFor(p) { return models().find(m => m.list.some(x => x.id === p.id)) || null; }

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
    (p.qc ? " with buyer QC photos" : "") + `. Open it on MyCNBox, KakoBuy, Oopbuy or any shopping agent.`;
  const sameBrand = bUrl ? (byBrand.get(p.brand) || []).filter(x => x.id !== p.id).slice(0, 8) : [];
  const sameCat = (byCat.get(p.cat) || []).filter(x => x.id !== p.id && x.brand !== p.brand).slice(0, 8);
  const about = `<p>The <strong>${esc(p.title)}</strong> is a ${esc((cat.name || "").toLowerCase())} find${p.brand ? ` in the ${esc(p.brand)} style` : ""} listed on ${plat}` +
    (p.seller && !/marketplace/i.test(p.seller) ? ` by ${esc(p.seller)}` : "") + `. The listed price is ¥${p.cny} (about ${money(p.usd)}) before shipping` +
    (variants.length ? `, and it comes in ${variants.length} option${variants.length > 1 ? "s" : ""}: ${esc(variants.slice(0, 8).join(", "))}${variants.length > 8 ? "…" : ""}` : "") + `.</p>` +
    (p.qc ? `<p>Buyers have shared <strong>real QC photos</strong> of this listing, so you can check logos, stitching and colour before you order. When yours reaches the warehouse, your agent takes QC photos of your exact item too.</p>`
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
      ${variants.length ? `<dt>Options</dt><dd>${esc(variants.slice(0, 12).join(" · "))}</dd>` : ""}<dt>QC photos</dt><dd>${qcs.length ? qcs.length + " shown" : (p.qc ? "Yes" : "None yet")}</dd><dt>Item ID</dt><dd>${esc(p.itemId || p.id)}</dd></dl>
    <p><a href="/#p/${encodeURIComponent(p.id)}" style="color:var(--accent)">Open in the catalogue →</a></p>
  </div>
</div>
<h2>About this find</h2><div class="prose">${about}</div>
<h2>How to buy it</h2><ol class="steps prose"><li>Tap <strong>Buy via MyCNBox</strong> (or your agent). The listing opens pre-filled.</li><li>Pick your size and colour — check our <a href="/guides/sizing">sizing guide</a> — and pay for the item plus delivery to the warehouse.</li><li>Check the QC photos (<a href="/guides/how-to-qc">what to look for</a>), then combine items into one parcel and ship. <a href="/how-to-order">Watch the 1:47 video</a>.</li></ol>
${(() => { const m = modelFor(p); return m ? `<div class="note" style="margin-top:22px">Comparing batches? See all <a href="/best/${m.slug}" style="color:var(--accent)">${m.list.length} ${esc(m.name)} rep listings</a> ranked by views.</div>` : ""; })()}
${sameBrand.length ? `<h2>More ${esc(p.brand)} finds</h2>${grid(sameBrand)}<p><a href="${bUrl}" style="color:var(--accent)">All ${esc(p.brand)} reps →</a></p>` : ""}
${sameCat.length ? `<h2>Similar ${esc((cat.name || p.cat).toLowerCase())}</h2>${grid(sameCat)}${cUrl ? `<p><a href="${cUrl}" style="color:var(--accent)">All ${esc((cat.name || p.cat).toLowerCase())} →</a></p>` : ""}` : ""}`;
  const pageLd = { "@context": "https://schema.org", "@type": "ItemPage", name: p.title, url: SITE + productUrl(p), description: desc,
    primaryImageOfPage: src ? { "@type": "ImageObject", contentUrl: src } : undefined, isPartOf: { "@type": "WebSite", name: "Puro Classico", url: SITE + "/" } };
  return page({ title: `${p.title} Rep — ${p.qc ? "QC Photos & Buy on Any Agent" : "Price & Where to Buy"} · Puro Classico`, desc, path: productUrl(p), body,
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
<div class="facts"><span>${(total || list.length).toLocaleString("en-US")} finds</span>${priceRange(list) ? `<span>${priceRange(list)}</span>` : ""}<span>Updated ${BUILT}</span></div>
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
  const intro = BRAND_INTRO[b] || `<p>${list.length} ${esc(b)} finds from Weidian, Taobao and 1688 sellers, sorted with the most viewed listings first. Prices run from ${priceRange(list)} before shipping.</p><p>Tap any find to see the listing details, buyer QC photos and buy links for MyCNBox, KakoBuy, Oopbuy, LoveGoBuy and Sugargoo.</p>`;
  const bm = models().filter(m => m.list.some(p => p.brand === b));
  const others = [...brandSlug.keys()].filter(x => x !== b).sort((a, c) => byBrand.get(c).length - byBrand.get(a).length).slice(0, 16);
  const extra = `<h2>How to buy ${esc(b)} reps</h2><div class="prose"><p>Open a find, tap <strong>Buy via MyCNBox</strong> (or your agent), pick your size and pay for the item plus delivery to the warehouse. Check the QC photos before shipping — see <a href="/guides/how-to-qc">how to read QC photos</a> — then combine your items into one parcel. New to this? <a href="/how-to-order">Watch the how-to-order video</a>.</p></div>
<h2>Other brands</h2><div class="chips">${others.map(x => `<a href="/brand/${brandSlug.get(x)}">${esc(x)}</a>`).join("")}<a href="/brands">All brands →</a></div>`;
  return hub({ path: "/brand/" + s, n, list, title: `${b} Reps Spreadsheet 2026 — ${list.length.toLocaleString("en-US")} ${b} Finds · Puro Classico`,
    desc: `${list.length.toLocaleString("en-US")} ${b} rep finds with prices (${priceRange(list)}) and buyer QC photos. Open any listing on MyCNBox, KakoBuy, Oopbuy or your agent.`,
    h1: `${b} reps`, intro, trail: [["Home", "/"], ["Brands", "/brands"], [b, "/brand/" + s]],
    chips: (bm.length ? `<div class="chips">${bm.map(m => `<a href="/best/${m.slug}" style="border-color:var(--accent)">Best ${esc(m.name)} reps</a>`).join("")}</div>` : "") + (cats.length > 1 ? `<div class="chips">${cats.map(c => `<a href="${catUrl(c)}">${esc(CATS[c].name)}</a>`).join("")}</div>` : ""), extra,
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
    desc: `${list.length.toLocaleString("en-US")} ${meta.name.toLowerCase()} rep finds with prices, buyer QC photos and agent links, sorted by most viewed.`,
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

// ------------------------------------------------------------------ model pages ("best X rep")
export function renderModels() {
  const bc = crumbs([["Home", "/"], ["Best reps", "/best"]]);
  const ms = models().slice().sort((a, b) => b.list.length - a.list.length);
  const body = `${bc.html}<h1>Best reps by model</h1><p class="lead">Every listing of the most popular models side by side, ranked by what buyers actually view. Compare batches, prices and QC before you order.</p>
<div class="g">${ms.map(m => { const p = m.list[0]; const src = imgSrc(p); return `<a class="c" href="/best/${m.slug}"><span class="ci">${src ? `<img src="${esc(src)}" alt="${esc(m.name)}" loading="lazy" onerror="this.remove()">` : ""}</span><span class="cb"><span class="ct">${esc(m.name)}</span><span class="cbr">${m.list.length} listings</span></span></a>`; }).join("")}</div>`;
  return page({ title: "Best Reps by Model (2026) — Compare Batches & QC · Puro Classico", desc: "Compare every listing of the most popular rep models — Air Jordan 1, Samba, Golden Goose, Moncler, Nuptse and more — ranked by views.", path: "/best", body, jsonld: [bc.data] });
}
export function renderModel(s, n) {
  const m = models().find(x => x.slug === s); if (!m) return null;
  const list = m.list;
  const intro = `<p>${esc(m.intro)}</p><p>Below are all ${list.length} ${esc(m.name)} listings on Puro Classico, ranked by how often buyers view them — the top ones are usually the safest first pick. Prices run from ${priceRange(list)} before shipping.</p>
<h3>What to check in QC</h3><ul>${m.qc.map(q => `<li>${esc(q)}</li>`).join("")}</ul>`;
  const others = models().filter(x => x.slug !== s).slice(0, 14);
  const t = MODEL_TERM[s] || m.name;
  const faq = [[`Where can I buy ${t} reps?`, `Puro Classico lists ${list.length} ${m.name} listings from Weidian, Taobao and 1688. Each opens directly in MyCNBox, KakoBuy, Oopbuy or another shopping agent.`],
               [`Which ${m.name} listing is best?`, `Start with the most-viewed listings at the top and compare their buyer QC photos. Check ${m.qc.join(", ")}.`]];
  return hub({ path: "/best/" + s, n, list, title: `Best ${t} Reps (2026) — ${list.length} Listings Compared · Puro Classico`,
    desc: `Compare ${list.length} ${m.name} rep listings ranked by views, with prices (${priceRange(list)}) and what to check in QC.`,
    h1: `Best ${t} reps`, intro, trail: [["Home", "/"], ["Best reps", "/best"], [m.name, "/best/" + s]], faq,
    extra: `<h2>More models</h2><div class="chips">${others.map(x => `<a href="/best/${x.slug}">${esc(x.name)}</a>`).join("")}<a href="/best">All models →</a></div>` });
}

// ------------------------------------------------------------------ tools
const TOOL_CSS = `<style>.tool{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px;max-width:760px;margin:18px 0}.tool label{display:block;color:var(--muted);font-size:13px;margin:0 0 6px}.tool input,.tool select{width:100%;background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:12px;padding:12px 14px;font:inherit}.tool .out{margin-top:14px;font-size:15px;color:#D5DCEC;white-space:pre-line}.tool .out a{color:var(--accent);word-break:break-all}.tool .row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.tool .qct{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.tool .qct img{width:110px;height:110px;object-fit:cover;border-radius:10px;border:1px solid var(--line)}.tool table{width:100%;border-collapse:collapse}.tool td{padding:6px 4px}</style>`;
const EXTRACT = `function pcExtract(u){u=(u||"").trim();if(!u)return{};var pl=null;if(/weidian/i.test(u))pl="weidian";else if(/1688|alibaba/i.test(u))pl="1688";else if(/taobao|tmall/i.test(u))pl="taobao";var st=u.match(/(?:shop_type|platform|source|channel|mallType)=([a-z0-9_]+)/i);if(st){var v=st[1].toLowerCase();if(/wei|wd/.test(v))pl="weidian";else if(/1688|ali/.test(v))pl="1688";else if(/tao|tb|tmall/.test(v))pl="taobao";}var id=null,ps=[/itemID=(\\d{6,})/i,/[?&]id=(\\d{6,})/i,/itemId=(\\d{6,})/i,/offer\\/(\\d{6,})/i,/\\/(\\d{9,})(?:\\.html|\\b)/,/(\\d{9,})/];for(var i=0;i<ps.length;i++){var m=u.match(ps[i]);if(m){id=m[1];break;}}return{platform:pl,id:id};}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c];});}`;
const TOOL_UI = {
  "link-converter": () => `<div class="tool"><label for="lc">Weidian, Taobao, 1688 or agent link</label><input id="lc" placeholder="https://weidian.com/item.html?itemID=…"><div class="row"><button class="btn red" id="go">Convert</button></div><div class="out" id="out">Your buy links will appear here.</div></div>
<script>${EXTRACT}
var R={mycnbox:"LHYDVW",kakobuy:"w5war",lovegobuy:"9WJ54Y",oopbuy:"LHQC0OS8O",sugargoo:"3751749728009774836"};
function orig(p,id){return p==="taobao"?"https://item.taobao.com/item.htm?id="+id:p==="1688"?"https://detail.1688.com/offer/"+id+".html":"https://weidian.com/item.html?itemID="+id;}
var A=[["MyCNBox",function(p,id){return "https://mycnbox.com/goodsDetail?mallType="+p+"&itemId="+id+"&referId="+R.mycnbox}],["KakoBuy",function(p,id){return "https://www.kakobuy.com/item/details?url="+encodeURIComponent(orig(p,id))+"&affcode="+R.kakobuy}],["Oopbuy",function(p,id){return "https://oopbuy.com/product/"+p+"/"+id+"?inviteCode="+R.oopbuy}],["LoveGoBuy",function(p,id){return "https://www.lovegobuy.com/product?platform="+p+"&id="+id+"&invite_code="+R.lovegobuy}],["Sugargoo",function(p,id){return "https://www.sugargoo.com/#/home/productDetail?productLink="+encodeURIComponent(orig(p,id))+"&memberId="+R.sugargoo}]];
function run(){var r=pcExtract(document.getElementById("lc").value),o=document.getElementById("out");if(!r.id){o.textContent="Couldn't find an item ID in that link. Paste a full product or agent link.";return;}var p=r.platform||"weidian";o.innerHTML="<b>"+esc(p)+" · "+esc(r.id)+"</b>\\n"+A.map(function(a){var u=a[1](p,r.id);return esc(a[0])+': <a href="'+esc(u)+'" target="_blank" rel="sponsored noopener">'+esc(u)+"</a>";}).join("\\n")+'\\n\\nOn Puro Classico: <a href="/product/'+esc(r.id)+'">/product/'+esc(r.id)+"</a>";}
document.getElementById("go").onclick=run;document.getElementById("lc").onkeydown=function(e){if(e.key==="Enter")run();};</script>`,
  "qc-checker": () => `<div class="tool"><label for="qi">Product link or item ID</label><input id="qi" placeholder="https://weidian.com/item.html?itemID=… or 7231806587"><label for="qp" style="margin-top:10px">Marketplace (if you paste only an ID)</label><select id="qp"><option value="weidian">Weidian</option><option value="taobao">Taobao</option><option value="1688">1688</option></select><div class="row"><button class="btn red" id="go">Check QC photos</button></div><div class="out" id="out">QC photos will appear here.</div><div class="qct" id="th"></div></div>
<script>${EXTRACT}
async function run(){var v=document.getElementById("qi").value,r=pcExtract(v),o=document.getElementById("out"),th=document.getElementById("th");th.innerHTML="";if(!r.id&&/^\\d{6,}$/.test(v.trim()))r={id:v.trim()};if(!r.id){o.textContent="Couldn't find an item ID. Paste a full link or the numeric ID.";return;}var p=r.platform||document.getElementById("qp").value;o.textContent="Checking "+p+" · "+r.id+"…";
try{var res=await fetch("/api/qc?storefront="+p+"&id="+encodeURIComponent(r.id));var d=res.ok?await res.json():null;var t=(d&&d.thumbnails)||[];if(t.length){o.innerHTML="Real QC photos for <b>"+esc(p)+" · "+esc(r.id)+"</b> ("+t.length+" shown). <a href=\\"/product/"+esc(r.id)+"\\">Open on Puro Classico →</a>";th.innerHTML=t.map(function(u){return '<a href="'+esc(u)+'" target="_blank" rel="noopener"><img src="'+esc(u)+'" alt="QC photo" loading="lazy" onerror="this.parentNode.remove()"></a>';}).join("");}else o.textContent="No QC photos found yet for "+p+" · "+r.id+". Photos only exist once someone has bought it through an agent.";}catch(e){o.textContent="Couldn't reach the QC service, try again in a moment.";}}
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
function run(){var k=parseFloat(kg.value),o=document.getElementById("out");if(!k||k<=0){o.textContent="Pick a destination and weight.";return;}o.innerHTML=RT[Z[co.value]].map(function(l){var lo=l[1]+l[2]*k*0.85,hi=l[1]+l[2]*k*1.2;return l[0]+": <b>~$"+Math.round(lo)+"–"+Math.round(hi)+"</b>";}).join("\\n")+"\\n\\n<span style=\\"color:var(--muted)\\">Ballpark only. Check your agent's estimator for the real price.</span>";}
co.onchange=run;kg.oninput=run;run();</script>`,
};
export function renderTools() {
  const bc = crumbs([["Home", "/"], ["Tools", "/tools"]]);
  const body = `${bc.html}<h1>Free rep tools</h1><p class="lead">Convert links, check QC photos and estimate weight and shipping before you order.</p>
<div class="chips" style="flex-direction:column;align-items:flex-start">${TOOL_LINKS.map(([t, u]) => `<a href="${u}" style="font-size:17px">${esc(t)} →</a>`).join("")}</div>`;
  return page({ title: "Free Rep Tools — Link Converter, QC Checker, Shipping Calculator · Puro Classico", desc: "Free tools for buying reps through agents: link converter, QC photo checker, weight estimator and shipping calculator.", path: "/tools", body, jsonld: [bc.data] });
}
export function renderTool(s) {
  const t = TOOLS[s]; if (!t || !TOOL_UI[s]) return null;
  const path = "/tools/" + s; const bc = crumbs([["Home", "/"], ["Tools", "/tools"], [t.name, path]]);
  const app = { "@context": "https://schema.org", "@type": "WebApplication", name: t.name + " — Puro Classico", url: SITE + path, applicationCategory: "UtilitiesApplication", operatingSystem: "Any", offers: { "@type": "Offer", price: "0", priceCurrency: "USD" }, description: t.desc };
  const body = `${bc.html}${TOOL_CSS}<h1>${esc(t.name)}</h1><p class="lead">${esc(t.lead)}</p>${TOOL_UI[s]()}<div class="prose">${t.about}</div>
<h2>More tools</h2><div class="chips">${TOOL_LINKS.filter(([, u]) => u !== path).map(([n, u]) => `<a href="${u}">${esc(n)}</a>`).join("")}<a href="/how-to-order">How to order</a></div>`;
  return page({ title: t.title, desc: t.desc, path, body, jsonld: [bc.data, app] });
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
    ...Object.keys(GUIDES).map(s => "/guides/" + s), "/best", ...models().map(m => "/best/" + m.slug), "/tools", ...Object.keys(TOOLS).map(s => "/tools/" + s), "/terms", "/privacy"];
  return xml(`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.map(u => `<url><loc>${SITE}${u}</loc><lastmod>${BUILT}</lastmod></url>`).join("\n")}\n</urlset>`);
}
export function sitemapProducts() {
  const rows = P.filter(indexable).map(p => {
    const src = imgSrc(p);
    return `<url><loc>${SITE}${productUrl(p)}</loc><lastmod>${BUILT}</lastmod>${src ? `<image:image><image:loc>${esc(src)}</image:loc></image:image>` : ""}</url>`;
  });
  return xml(`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n${rows.join("\n")}\n</urlset>`);
}
