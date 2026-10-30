// Routes the server-rendered SEO pages (hubs, guides, sitemaps) and turns the SPA's catch-all
// "200 + homepage" for unknown paths into a real 404, so Google doesn't see soft-404 duplicates.
import { notFound, ensureStats, statsLoaded, BRAND_ALIAS, slug, idx, DISCORD_INVITE, BUILT } from "./_lib/site.js";
import { renderBrand, renderCategory, renderAgent, renderAgentBrand, renderOldMoney, renderBrands, renderGuides, renderGuide, renderModels, renderModel, renderTools, renderTool,
  sitemapIndex, sitemapPages, sitemapProducts, mergedBest, hubSpec, hubParts, hubList, appCards, appPager, APP_CARDS, PRODUCT_TPL } from "./_lib/pages.js";
import { imgSrc, navKey } from "./_lib/site.js";

// Real static HTML pages (everything else that comes back as HTML is the SPA fallback -> 404).
const STATIC_HTML = new Set(["/", "/index.html", "/privacy", "/privacy.html", "/terms", "/terms.html", "/stats", "/stats.html",
  "/how-to-order", "/how-to-order.html", "/admin", "/admin.html", "/links", "/links.html"]);
const VERIFY = { "/googleaea131de20fbf72e.html": "google-site-verification: googleaea131de20fbf72e.html" };
// Paths answered by real Functions (exact shapes only, so /api/nope, /product/ or /product/<id>/x still 404).
const PASS = /^\/api\/(qc|img|geo)$|^\/r\/[^/]+$|^\/product\/[^/]+$|^\/unsubscribe$|^\/go\/[^/]+$/;
// Repo-internal files that Pages would otherwise serve from the repo root (scripts, workflows, the bots' state files).
// Tested on the path as sent and on its percent-decoded form: Pages decodes the path to find the file, so
// /%73cripts/x.py used to slip past a rule that only saw the encoded spelling.
const PRIVATE = /^\/+(scripts|\.github|functions)(\/|$)|^\/+(readme\.md|discord_posted\.json|discord_sent\.json|finds_used\.json|shorts_log\.json|nonsb\.txt)$/i;
const decoded = p => { try { return decodeURIComponent(p); } catch (e) { return p; } };
// The project's own *.pages.dev address. Its subdomains are preview deployments (<commit>.… and <branch>.…).
const PAGES_DEV = "manifest-bq9.pages.dev";
const json404 = () => new Response(JSON.stringify({ error: "not found" }), { status: 404, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

// Old hub URLs of merged brand spellings (/brand/essential -> /brand/essentials)
const BRAND_MOVED = {};
for (const [from, to] of Object.entries(BRAND_ALIAS)) if (slug(from) !== slug(to)) BRAND_MOVED[slug(from)] = slug(to);

function paged(fn, arg, nStr, base) {
  if (!nStr) return fn(arg, 1);
  const n = parseInt(nStr, 10);
  if (!(n >= 1)) return null;                                      // /x/0 -> 404
  if (n === 1 || String(n) !== nStr) return Response.redirect(n === 1 ? base : base + "/" + n, 301);  // /x/1, /x/01 duplicate /x, /x/02 -> /x/2
  return fn(arg, n);
}
// Like paged(), for a hub whose pages 2+ are retired: page 1 renders, /1 goes to the hub, and a page N that exists
// (rendered once to check) gets a single 301 to `to(n)`, also when spelled /02. Anything else is a 404 (null).
function retired(render, nStr, base, to) {
  if (!nStr) return render(1);
  const n = parseInt(nStr, 10);
  if (!(n >= 1)) return null;
  if (n === 1) return Response.redirect(base, 301);
  return render(n) ? Response.redirect(to(n), 301) : null;
}

// Preview deployments are served as they are, so a change can be tried on Cloudflare before it goes live, but never
// indexed: every answer from one carries "x-robots-tag: noindex" (canonical tags point at www.puroclassico.com anyway).
// Pages applies _headers only to files it serves itself. Everything a Function builds (hubs, guides, product pages, the
// 404 page, redirects) came back without them (checked 28 Oct 2026), so they are added here. Keep in step with _headers.
const SECURITY_HEADERS = {
  "strict-transport-security": "max-age=63072000; includeSubDomains; preload",
  "x-content-type-options": "nosniff",
  "x-frame-options": "DENY",
  "referrer-policy": "strict-origin-when-cross-origin",
  "permissions-policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
  "cross-origin-opener-policy": "same-origin-allow-popups",
  "content-security-policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://static.cloudflareinsights.com https://accounts.google.com/gsi/client; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com/gsi/style; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://*.supabase.co wss://*.supabase.co https://cloudflareinsights.com https://accounts.google.com/gsi/; frame-src https://*.supabase.co https://accounts.google.com https://appleid.apple.com; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests",
};
export async function onRequest(ctx) {
  const res = await route(ctx);
  const preview = new URL(ctx.request.url).hostname.endsWith("." + PAGES_DEV);
  const bare = !res.headers.has("x-content-type-options");   // built by a Function, so _headers never reached it
  if (!preview && !bare) return res;
  const out = new Response(res.body, res);   // a copy, because the headers of a redirect or a static asset cannot be changed
  if (bare) for (const [k, v] of Object.entries(SECURITY_HEADERS)) out.headers.set(k, v);
  if (preview) out.headers.set("x-robots-tag", "noindex");
  return out;
}

// Googlebot reads only the first 2 MB of each file, counted uncompressed (developers.google.com/search/docs/crawling-indexing/googlebot).
// index.html carries the whole catalogue inline (about 3 MB), so the app code after it was never seen. The repo keeps the
// inline catalogue (the catalogue scripts read and write it there), but visitors and crawlers get the page without it and
// load it as CATALOG_PARTS scripts of about 1 MB each, so no file passes the limit (21 Oct 2026). The version is index.html's ETag, so a new catalogue gets new URLs and browsers can
// cache the old ones for a year. PC_CATALOG_WANT lets the app notice a part that failed and fetch the whole file instead.
const CATALOG_TAG = '<script type="application/json" id="pc-catalog">';
const CATALOG_PARTS = 3;
const etagOf = r => (r.headers.get("etag") || "x").replace(/[^A-Za-z0-9]/g, "").slice(0, 32);
const catalogTags = ver => `<script>window.PC_CATALOG_WANT=${CATALOG_PARTS}</script>` +
  Array.from({ length: CATALOG_PARTS }, (_, i) => `<script src="/catalog.js?v=${ver}&amp;p=${i}"></script>`).join("");
const slimHtml = (res, ver, cards = "") => new HTMLRewriter()
  .on("script#pc-catalog", { element(e) { e.replace(catalogTags(ver), { html: true }); } })
  .on("#grid", { element(e) { if (cards) e.setInnerContent(cards, { html: true }); } })
  .transform(res);

// data/link_health.json (the weekly link check): when it last ran and which Weidian listings are dead. Kept for 10 minutes.
let _lh = null, _lhAt = 0;
async function linkHealth(ctx, origin) {
  if (_lh && Date.now() - _lhAt < 600000) return _lh;
  try {
    const h = await (await ctx.env.ASSETS.fetch(new Request(origin + "/data/link_health.json"))).json();
    _lh = { checked: h.checked, dead: new Set((h.dead || []).map(String)) }; _lhAt = Date.now();
  } catch (e) { if (!_lh) _lh = { checked: null, dead: new Set() }; }
  return _lh;
}
// The app's first cards as HTML (see appCards in pages.js), dead listings left out like the app does. Only once the view
// stats are read, so the order is the app's; without them the grid stays empty and the app fills it as before.
async function serverCards(ctx, origin, spec) {
  if (!statsLoaded()) return { cards: "", more: "" };
  const { list, base } = hubList(spec), { dead } = await linkHealth(ctx, origin);
  const live = [];
  for (const p of list) { if (!dead.has(String(p.id))) live.push(p); if (live.length >= APP_CARDS) break; }
  return { cards: appCards(live, 1, spec && spec.preset.agent, spec ? 0 : 8), more: spec ? appPager(base, list.length) : "", top: live[0] || null };
}

async function catalogJs(ctx, url) {
  const asset = await ctx.env.ASSETS.fetch(new Request(url.origin + "/", { method: "GET" }));
  if (!asset.ok) return new Response("/* catalogue unavailable */", { status: 502, headers: { "content-type": "application/javascript; charset=utf-8", "cache-control": "no-store" } });
  const type = { "content-type": "application/javascript; charset=utf-8" };
  // ?p=0..CATALOG_PARTS-1 is one part; no p is the whole catalogue (the app's fallback and pages cached before the split).
  const p = url.searchParams.get("p"), part = p === null ? -1 : Number(p);
  if (p !== null && !(Number.isInteger(part) && part >= 0 && part < CATALOG_PARTS)) return new Response("/* no such part */", { status: 404, headers: { ...type, "cache-control": "no-store" } });
  const ver = etagOf(asset);
  const cc = url.searchParams.get("v") === ver ? "public, max-age=31536000, immutable" : "public, max-age=300";
  const key = new Request(`https://ssr-cache.internal/catalog2/${ver}/${part < 0 ? "all" : part}`, { method: "GET" });   // catalog2: lean JSON.parse parts
  const hit = await caches.default.match(key);
  if (hit) { const r = new Response(hit.body, hit); r.headers.set("cache-control", cc); return r; }
  const html = await asset.text();
  const a = html.indexOf(CATALOG_TAG), b = a < 0 ? -1 : html.indexOf("</script>", a);
  if (a < 0 || b < 0) return new Response("/* catalogue not found */", { status: 500, headers: { ...type, "cache-control": "no-store" } });
  const json = html.slice(a + CATALOG_TAG.length, b);
  let body = "window.PC_CATALOG=" + json + ";";
  if (part >= 0) {
    const all = JSON.parse(json), n = Math.ceil(all.length / CATALOG_PARTS);
    // Leaner, faster parts (28 Oct 2026): the app never reads usd, and rating and views are 0 on every row (the app takes views from
    // stats.json), so they are left out (-10% bytes). The rows are sent as one JSON string for JSON.parse, which V8 reads about twice as
    // fast as the same data written as a JavaScript literal (80-92 ms -> 43-48 ms per part on a 4x slowed phone CPU).
    // In the single-quoted string only backslashes and apostrophes need escaping; U+2028/U+2029 are escaped as well, since
    // browsers older than ES2019 reject them raw in a string literal (and the whole part with them).
    const rows = all.slice(part * n, (part + 1) * n).map(p => { const q = { ...p }; delete q.usd; if (!q.rating) delete q.rating; if (!q.views) delete q.views; return q; });
    body = "window.PC_CATALOG=(window.PC_CATALOG||[]).concat(JSON.parse('" +
      JSON.stringify(rows).replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029") +
      "'));window.PC_CATALOG_GOT=(window.PC_CATALOG_GOT||0)+1;";
  }
  ctx.waitUntil(caches.default.put(key, new Response(body, { headers: { ...type, "cache-control": "public, max-age=31536000" } })).catch(() => {}));
  return new Response(body, { headers: { ...type, "cache-control": cc } });
}

// /search-index.json (round 6, item 10): the catalogue the header search on server pages loads on first use, and the
// QC checker / link converter read for a find's marketplace. Built by functions/_lib/search_index.js once per isolate
// (and per stats version), shared between isolates through caches.default. ?v=<BUILT> makes it immutable; ETag + 304.
async function searchIndexJson(ctx, url) {
  const SI = await import("./_lib/search_index.js");
  await ensureStats(url.origin);
  let ix = SI.cachedIndex(), body = ix && ix.body, etag = ix && ix.etag;
  const ver = ix ? ix.ver : SI.statsVersion();
  const key = new Request(`https://ssr-cache.internal/search-index/${BUILT}/${ver}`, { method: "GET" });
  if (!body) {
    const hit = await caches.default.match(key).catch(() => null);
    if (hit) { body = await hit.text(); etag = hit.headers.get("etag") || `"${BUILT}-${SI.fnv8(body)}"`; }
  }
  if (!body) {
    ix = SI.buildSearchIndex(); body = ix.body; etag = ix.etag;
    ctx.waitUntil(caches.default.put(key, new Response(body, { headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=31536000", etag } })).catch(() => {}));
  }
  const headers = { "content-type": "application/json; charset=utf-8", etag,
    "cache-control": url.searchParams.get("v") === BUILT ? "public, max-age=31536000, immutable" : "public, max-age=3600, stale-while-revalidate=86400" };
  const inm = ctx.request.headers.get("if-none-match") || "";
  if (inm && inm.split(",").some(t => t.trim().replace(/^W\//, "") === etag || t.trim() === "*")) return new Response(null, { status: 304, headers });
  return new Response(ctx.request.method === "HEAD" ? null : body, { headers });
}

async function route(ctx) {
  const { request } = ctx;
  if (request.method !== "GET" && request.method !== "HEAD") return ctx.next();
  const url = new URL(request.url);
  const path = url.pathname;
  // The old pages.dev address still resolves: send everything to the real domain so traffic and ranking are not split.
  if (url.hostname === PAGES_DEV) return Response.redirect("https://www.puroclassico.com" + path + url.search, 301);
  if (path === "/catalog.js") return catalogJs(ctx, url);
  if (path === "/search-index.json") return searchIndexJson(ctx, url);   // r6 GROUP C: header search index for server pages
  // Search-engine ownership files, answered here so Pages' ".html -> pretty URL" redirect can't get in the way.
  if (VERIFY[path]) return new Response(VERIFY[path], { headers: { "content-type": "text/html; charset=utf-8" } });
  // /discord (any case, with or without a trailing slash) is the one address the site, static pages and emails link to.
  // 302 + no-store, so a new invite in DISCORD_INVITE takes effect at once and is never cached as permanent.
  if (/^\/discord\/?$/i.test(path)) return new Response(null, { status: 302, headers: { location: DISCORD_INVITE, "cache-control": "no-store" } });
  // Browsers, Bing and feed readers ask for /favicon.ico whatever the page declares; without a file each request rendered the full 404 page.
  if (path === "/favicon.ico") return Response.redirect(url.origin + "/favicon.png", 301);
  if (PRIVATE.test(path) || PRIVATE.test(decoded(path))) return notFound(path);
  if (PASS.test(path)) {
    if (path.startsWith("/api/")) {
      if (request.method === "HEAD" && path === "/api/qc") return new Response(null, { status: 405, headers: { allow: "GET" } }); // don't spend QC quota
      const r = await ctx.next();
      return r.status === 200 && (r.headers.get("content-type") || "").includes("text/html") ? json404() : r;
    }
    return ctx.next();
  }
  if (/^\/api(\/|$)/.test(path)) return json404();
  // One 301 hop: strip the trailing slash and, for hub URLs (/brand/Fendi, /Best/X ...), lowercase.
  let to = path.length > 1 ? path.replace(/\/+$/, "") || "/" : path;
  if (/^\/(brand|category|brands|old-money|guides|best|tools)\b|^\/[a-z]+-spreadsheet/i.test(to)) to = to.toLowerCase();
  // v9: the weight estimator moved into the shipping calculator; one hop even from /tools/weight-estimator/.
  if (to === "/tools/weight-estimator") return Response.redirect(url.origin + "/tools/shipping-calculator", 301);
  if (to !== path) return Response.redirect(url.origin + to + url.search, 301);
  let m, res = undefined;
  // Edge cache for the hub and list pages (20 Oct 2026): building one takes 0.3-0.6 s (catalogue index + view stats), a
  // cached copy ~0.05 s. The key holds the catalogue build, the page template version and the homepage's ETag, so a
  // new deploy or a new catalogue never serves an old copy. The query string (utm tags) doesn't change the page.
  const pageCache = request.method === "GET" && (path === "/" || /^\/(brand|category|brands|old-money|guides|best|tools)(\/|$)|^\/[a-z]+-spreadsheet(\/|$)/.test(path));
  let ckey = null;
  if (pageCache) {
    try {
      const a = await ctx.env.ASSETS.fetch(new Request(url.origin + "/", { method: "HEAD" }));
      const ver = (a.headers.get("etag") || "x").replace(/[^A-Za-z0-9]/g, "").slice(0, 32);
      ckey = new Request(`https://ssr-cache.internal/page/${BUILT}/${PRODUCT_TPL}/${ver}${path}`, { method: "GET" });
      const hit = await caches.default.match(ckey);
      if (hit) {
        const r = new Response(hit.body, hit), cc = r.headers.get("x-browser-cc");
        if (cc) { r.headers.set("cache-control", cc); r.headers.delete("x-browser-cc"); }   // what the browser got on the first build
        r.headers.set("x-ssr-cache", "HIT"); return r;
      }
    } catch (e) { ckey = null; }
  }
  // Store a good copy (only when the view stats were read, so the order is right). "max-age=3600" is the edge copy's
  // lifetime; a HIT goes out with the page's own cache-control again (kept in x-browser-cc), so a browser does not hold
  // the homepage (normally max-age=0, must-revalidate) or a hub (max-age=300) for an hour after a deploy.
  const keep = r => {
    if (ckey && r && r.status === 200 && statsLoaded()) {
      const c = new Response(r.clone().body, r);
      c.headers.set("x-browser-cc", r.headers.get("cache-control") || "public, max-age=0, must-revalidate");
      c.headers.set("cache-control", "public, max-age=3600");
      ctx.waitUntil(caches.default.put(ckey, c).catch(() => {}));
    }
    return r;
  };
  const usesStats = /^\/(brand|category|brands|old-money|guides|best)|^\/[a-z]+-spreadsheet/.test(path);
  if (usesStats) await ensureStats(url.origin);
  if (path === "/sitemap.xml") return sitemapIndex();
  if (path === "/sitemap-pages.xml") return sitemapPages();
  if (path === "/sitemap-products.xml") return sitemapProducts();
  const spec = hubSpec(path);
  if (spec) return keep(await hubApp(ctx, url, spec));
  if (path === "/brands") res = renderBrands();
  else if (path === "/guides") res = renderGuides();
  else if ((m = path.match(/^\/guides\/([a-z0-9-]+)$/))) res = renderGuide(m[1]);
  else if (path === "/best") res = renderModels();
  else if ((m = path.match(/^\/best\/([a-z0-9-]+)(?:\/(\d+))?$/))) {
    // A "best" page that was merged into its brand hub (BEST_MERGED in pages.js): one 301 to the hub, page number dropped.
    const hubUrl = mergedBest(m[1]);
    if (hubUrl) return Response.redirect(url.origin + hubUrl, 301);
    res = paged(renderModel, m[1], m[2], url.origin + "/best/" + m[1]);
  }
  // v9: the weight estimator lives on inside the shipping calculator ("add items").
  else if (path === "/tools/weight-estimator") return Response.redirect(url.origin + "/tools/shipping-calculator", 301);
  else if (path === "/tools") res = renderTools();
  else if ((m = path.match(/^\/tools\/([a-z0-9-]+)$/))) res = renderTool(m[1]);
  // An old spelling redirects only when the brand it was merged into has a hub; otherwise it is a plain 404, not a 301 to a 404.
  else if ((m = path.match(/^\/brand\/([a-z0-9-]+)(?:\/(\d+))?$/)) && BRAND_MOVED[m[1]] && idx().slugBrand.has(BRAND_MOVED[m[1]])) return Response.redirect(url.origin + "/brand/" + BRAND_MOVED[m[1]], 301);
  else if (m) res = paged(renderBrand, m[1], m[2], url.origin + "/brand/" + m[1]);
  else if ((m = path.match(/^\/category\/([a-z0-9-]+)(?:\/(\d+))?$/))) res = paged(renderCategory, m[1], m[2], url.origin + "/category/" + m[1]);
  // Pages 2+ of the agent and agent x brand hubs (28 Oct 2026): linked from nowhere since page 1 became the app, and the
  // same finds as every other agent's page N, or as /brand/<x>/N (the same brand list, so the same number of 60-find
  // pages; brand pages 2+ put indexable finds first, so the order differs). A valid page N, however it is spelled (/2,
  // /02), gets one 301: to the agent hub, or to the same page of the brand hub. An invalid one stays a 404, so nothing
  // redirects to a missing page.
  else if ((m = path.match(/^\/(mycnbox|kakobuy|oopbuy|lovegobuy|sugargoo)-spreadsheet(?:\/(\d+))?$/))) { const k = m[1], base = url.origin + `/${k}-spreadsheet`;
    res = retired(n => renderAgent(k, n), m[2], base, () => base); }
  else if ((m = path.match(/^\/(mycnbox|kakobuy|oopbuy|lovegobuy|sugargoo)-spreadsheet\/([a-z][a-z0-9-]*)(?:\/(\d+))?$/))) { const k = m[1], b = m[2];
    res = retired(n => renderAgentBrand(k, b, n), m[3], url.origin + `/${k}-spreadsheet/${b}`, n => url.origin + `/brand/${b}/${n}`); }
  else if ((m = path.match(/^\/old-money(?:\/(\d+))?$/))) res = paged((_, n) => renderOldMoney(n), null, m[1], url.origin + "/old-money");
  if (res !== undefined) {
    if (!res) return notFound(path);
    // Rendered before any view stats could be read (a failed read on a fresh server instance): the finds are in a
    // different order and the view-based picks are missing. Correct, but not a copy to keep for an hour.
    if (usesStats && !statsLoaded() && res.status === 200) res.headers.set("cache-control", "public, max-age=60");
    return keep(res);
  }

  const out = await ctx.next();
  const ct = out.headers.get("content-type") || "";
  if ((path === "/" || path === "/index.html") && out.status === 200 && ct.includes("text/html")) {
    await ensureStats(url.origin);
    const home = slimHtml(out, etagOf(out), (await serverCards(ctx, url.origin, null)).cards);
    return path === "/" ? keep(home) : home;   // homepage from the same edge cache as the hubs (~0.22 s -> ~0.11 s TTFB)
  }
  if (out.status === 200 && ct.includes("text/html") && !STATIC_HTML.has(path) && !/^\/google[0-9a-f]+\.html$/.test(path)) return notFound(path);
  return out;
}

// A hub page served as the catalogue app: index.html with this page's title, meta, canonical, heading and filter preset
// (window.PC_PAGE), the homepage's own structured data swapped for this page's, and a compact FAQ/links block before the footer.
// Its hero is only the breadcrumb, the h1 and the subtitle: the homepage's other hero parts are removed below.
async function hubApp(ctx, url, spec) {
  const asset = await ctx.env.ASSETS.fetch(new Request(url.origin + "/", { method: "GET", headers: ctx.request.headers }));
  if (!asset.ok) return asset;
  const canon = "https://www.puroclassico.com" + spec.path;
  const { cards, more, top } = await serverCards(ctx, url.origin, spec);
  // The page's own first find (the first card shown, dead listings skipped) as its preview image (28 Oct 2026): Google
  // reads og:image and primaryImageOfPage as the preferred thumbnail, and the site banner says nothing about a KakoBuy or
  // brand spreadsheet. The alt text names that find. Without the view stats there are no server cards, and the banner stays.
  const img = top ? imgSrc(top) : "", alt = top ? ((top.brand && !String(top.title || "").toLowerCase().startsWith(top.brand.toLowerCase()) ? top.brand + " " : "") + (top.title || "")).trim() : "";
  // Freshness (21 Oct 2026): the weekly dead-link check is real, so say when it last ran and give Google the same date.
  // The date goes into spec.sub, so the server-rendered subtitle and the app's copy (window.PC_PAGE.sub) match.
  let fresh = "";
  try {
    const lh = await linkHealth(ctx, url.origin);
    const d = new Date(lh.checked);
    if (lh.checked && !isNaN(d)) {
      spec = { ...spec, sub: `${spec.sub} Links checked ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })}.` };
      fresh = '<script type="application/ld+json">' + JSON.stringify({ "@context": "https://schema.org", "@type": "CollectionPage", name: spec.h, url: canon, dateModified: d.toISOString(), primaryImageOfPage: img ? { "@type": "ImageObject", contentUrl: img } : undefined }).replace(/</g, "\\u003c") + "</script>";
    }
  } catch (e) {}
  const { crumbHtml, seo, head } = hubParts(spec, more);
  const content = v => ({ element(e) { e.setAttribute("content", v); } });
  // Same rule as page() in site.js: Google shows about 60 characters of a title, so a longer one drops the site name
  // (Google prints the site name above every result anyway).
  const title = spec.title.length > 60 ? spec.title.replace(/ [|·] Puro Classico$/, "") : spec.title;
  // Header (round 4): index.html marks Finds as the current section; a hub in another section (/brand/x -> Brands) gets
  // the mark moved here, before the first paint, so the active pill never jumps. Same map as the server pages (navKey).
  const navHref = { finds: "/", brands: "/brands", tools: "/tools", guides: "/guides", how: "/how-to-order" }[navKey(spec.path)] || "";
  const out = new HTMLRewriter()
    .on("nav.v9-nav a.v9-nl", { element(e) { if (e.getAttribute("href") === navHref) e.setAttribute("aria-current", "page"); else e.removeAttribute("aria-current"); } })
    .on("title", { element(e) { e.setInnerContent(title); } })
    .on('meta[name="description"]', content(spec.desc))
    .on('meta[property="og:title"]', content(title)).on('meta[name="twitter:title"]', content(title))
    .on('meta[property="og:description"]', content(spec.desc)).on('meta[name="twitter:description"]', content(spec.desc))
    .on('meta[property="og:url"]', content(canon))
    .on('meta[property="og:image"]', { element(e) { if (img) e.setAttribute("content", img); } })
    .on('meta[name="twitter:image"]', { element(e) { if (img) e.setAttribute("content", img); } })
    .on('meta[property="og:image:width"]', { element(e) { if (img) e.remove(); } })
    .on('meta[property="og:image:height"]', { element(e) { if (img) e.remove(); } })
    .on('meta[property="og:image:alt"]', { element(e) { if (img) e.setAttribute("content", alt || spec.h); } })
    .on('meta[name="twitter:image:alt"]', { element(e) { if (img) e.setAttribute("content", alt || spec.h); } })
    .on('link[rel="canonical"]', { element(e) { e.setAttribute("href", canon); } })
    .on('script[type="application/ld+json"]', { element(e) { e.remove(); } })
    .on("script#pc-catalog", { element(e) { e.replace(catalogTags(etagOf(asset)), { html: true }); } })
    .on("#grid", { element(e) { if (cards) e.setInnerContent(cards, { html: true }); } })
    .on("meta[charset]", { element(e) { e.after(head + fresh, { html: true }); } })   // index.html has no <head> tag, so this is the first thing in it
    // v8 hero parts (eyebrow, CTA row, stats, Trustpilot badge, agents strip, favourites strip) are no longer in the v9
    // index.html, so their removal rules are gone. The app code still checks for each element before using it.
    // v9 (29 Oct 2026): the homepage sections between the hero and the toolbar, the hero search, the hero buttons and the hero trust row
    // are homepage only. Removed here like the v8 hero parts; home.js no-ops when they are missing.
    .on("div#v9-home", { element(e) { e.remove(); } })
    .on("form#v9-hero-search", { element(e) { e.remove(); } })
    .on("div.v9-hero-actions", { element(e) { e.remove(); } })
    .on("div.v9-trust", { element(e) { e.remove(); } })
    .on("h1.hero-h", { element(e) { e.setInnerContent(spec.h); e.before(crumbHtml, { html: true }); } })
    .on("p.hero-sub", { element(e) { e.setInnerContent(spec.sub); } })
    .on("footer", { element(e) { e.before(seo, { html: true }); } })
    .transform(asset);
  const res = new Response(out.body, { status: 200, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300, s-maxage=3600" } });
  return res;
}
