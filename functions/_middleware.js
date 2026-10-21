// Routes the server-rendered SEO pages (hubs, guides, sitemaps) and turns the SPA's catch-all
// "200 + homepage" for unknown paths into a real 404, so Google doesn't see soft-404 duplicates.
import { notFound, ensureStats, statsLoaded, BRAND_ALIAS, slug, idx, DISCORD_INVITE, BUILT } from "./_lib/site.js";
import { renderBrand, renderCategory, renderAgent, renderAgentBrand, renderOldMoney, renderBrands, renderGuides, renderGuide, renderModels, renderModel, renderTools, renderTool,
  sitemapIndex, sitemapPages, sitemapProducts, mergedBest, hubSpec, hubParts, PRODUCT_TPL } from "./_lib/pages.js";

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

// Preview deployments are served as they are, so a change can be tried on Cloudflare before it goes live, but never
// indexed: every answer from one carries "x-robots-tag: noindex" (canonical tags point at www.puroclassico.com anyway).
export async function onRequest(ctx) {
  const res = await route(ctx);
  if (!new URL(ctx.request.url).hostname.endsWith("." + PAGES_DEV)) return res;
  const out = new Response(res.body, res);   // a copy, because the headers of a redirect or a static asset cannot be changed
  out.headers.set("x-robots-tag", "noindex");
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
const slimHtml = (res, ver) => new HTMLRewriter()
  .on("script#pc-catalog", { element(e) { e.replace(catalogTags(ver), { html: true }); } })
  .transform(res);

async function catalogJs(ctx, url) {
  const asset = await ctx.env.ASSETS.fetch(new Request(url.origin + "/", { method: "GET" }));
  if (!asset.ok) return new Response("/* catalogue unavailable */", { status: 502, headers: { "content-type": "application/javascript; charset=utf-8", "cache-control": "no-store" } });
  const type = { "content-type": "application/javascript; charset=utf-8" };
  // ?p=0..CATALOG_PARTS-1 is one part; no p is the whole catalogue (the app's fallback and pages cached before the split).
  const p = url.searchParams.get("p"), part = p === null ? -1 : Number(p);
  if (p !== null && !(Number.isInteger(part) && part >= 0 && part < CATALOG_PARTS)) return new Response("/* no such part */", { status: 404, headers: { ...type, "cache-control": "no-store" } });
  const ver = etagOf(asset);
  const cc = url.searchParams.get("v") === ver ? "public, max-age=31536000, immutable" : "public, max-age=300";
  const key = new Request(`https://ssr-cache.internal/catalog/${ver}/${part < 0 ? "all" : part}`, { method: "GET" });
  const hit = await caches.default.match(key);
  if (hit) { const r = new Response(hit.body, hit); r.headers.set("cache-control", cc); return r; }
  const html = await asset.text();
  const a = html.indexOf(CATALOG_TAG), b = a < 0 ? -1 : html.indexOf("</script>", a);
  if (a < 0 || b < 0) return new Response("/* catalogue not found */", { status: 500, headers: { ...type, "cache-control": "no-store" } });
  const json = html.slice(a + CATALOG_TAG.length, b);
  let body = "window.PC_CATALOG=" + json + ";";
  if (part >= 0) {
    const all = JSON.parse(json), n = Math.ceil(all.length / CATALOG_PARTS);
    body = "window.PC_CATALOG=(window.PC_CATALOG||[]).concat(" + JSON.stringify(all.slice(part * n, (part + 1) * n)) +
      ");window.PC_CATALOG_GOT=(window.PC_CATALOG_GOT||0)+1;";
  }
  ctx.waitUntil(caches.default.put(key, new Response(body, { headers: { ...type, "cache-control": "public, max-age=31536000" } })).catch(() => {}));
  return new Response(body, { headers: { ...type, "cache-control": cc } });
}

async function route(ctx) {
  const { request } = ctx;
  if (request.method !== "GET" && request.method !== "HEAD") return ctx.next();
  const url = new URL(request.url);
  const path = url.pathname;
  // The old pages.dev address still resolves: send everything to the real domain so traffic and ranking are not split.
  if (url.hostname === PAGES_DEV) return Response.redirect("https://www.puroclassico.com" + path + url.search, 301);
  if (path === "/catalog.js") return catalogJs(ctx, url);
  // Search-engine ownership files, answered here so Pages' ".html -> pretty URL" redirect can't get in the way.
  if (VERIFY[path]) return new Response(VERIFY[path], { headers: { "content-type": "text/html; charset=utf-8" } });
  // /discord (any case, with or without a trailing slash) is the one address the site, static pages and emails link to.
  // 302 + no-store, so a new invite in DISCORD_INVITE takes effect at once and is never cached as permanent.
  if (/^\/discord\/?$/i.test(path)) return new Response(null, { status: 302, headers: { location: DISCORD_INVITE, "cache-control": "no-store" } });
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
  if (to !== path) return Response.redirect(url.origin + to + url.search, 301);
  let m, res = undefined;
  // Edge cache for the hub and list pages (20 Oct 2026): building one takes 0.3-0.6 s (catalogue index + view stats), a
  // cached copy ~0.05 s. The key holds the catalogue build, the page template version and the homepage's ETag, so a
  // new deploy or a new catalogue never serves an old copy. The query string (utm tags) doesn't change the page.
  const pageCache = request.method === "GET" && /^\/(brand|category|brands|old-money|guides|best|tools)(\/|$)|^\/[a-z]+-spreadsheet(\/|$)/.test(path);
  let ckey = null;
  if (pageCache) {
    try {
      const a = await ctx.env.ASSETS.fetch(new Request(url.origin + "/", { method: "HEAD" }));
      const ver = (a.headers.get("etag") || "x").replace(/[^A-Za-z0-9]/g, "").slice(0, 32);
      ckey = new Request(`https://ssr-cache.internal/page/${BUILT}/${PRODUCT_TPL}/${ver}${path}`, { method: "GET" });
      const hit = await caches.default.match(ckey);
      if (hit) { const r = new Response(hit.body, hit); r.headers.set("x-ssr-cache", "HIT"); return r; }
    } catch (e) { ckey = null; }
  }
  const keep = r => {                      // store a good copy (only when the view stats were read, so the order is right)
    if (ckey && r && r.status === 200 && statsLoaded()) {
      const c = new Response(r.clone().body, r); c.headers.set("cache-control", "public, max-age=3600");
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
  else if (path === "/tools") res = renderTools();
  else if ((m = path.match(/^\/tools\/([a-z0-9-]+)$/))) res = renderTool(m[1]);
  // An old spelling redirects only when the brand it was merged into has a hub; otherwise it is a plain 404, not a 301 to a 404.
  else if ((m = path.match(/^\/brand\/([a-z0-9-]+)(?:\/(\d+))?$/)) && BRAND_MOVED[m[1]] && idx().slugBrand.has(BRAND_MOVED[m[1]])) return Response.redirect(url.origin + "/brand/" + BRAND_MOVED[m[1]], 301);
  else if (m) res = paged(renderBrand, m[1], m[2], url.origin + "/brand/" + m[1]);
  else if ((m = path.match(/^\/category\/([a-z0-9-]+)(?:\/(\d+))?$/))) res = paged(renderCategory, m[1], m[2], url.origin + "/category/" + m[1]);
  else if ((m = path.match(/^\/(mycnbox|kakobuy|oopbuy|lovegobuy|sugargoo)-spreadsheet(?:\/(\d+))?$/))) res = paged(renderAgent, m[1], m[2], url.origin + `/${m[1]}-spreadsheet`);
  else if ((m = path.match(/^\/(mycnbox|kakobuy|oopbuy|lovegobuy|sugargoo)-spreadsheet\/([a-z][a-z0-9-]*)(?:\/(\d+))?$/))) { const k = m[1], b = m[2]; res = paged((x, n) => renderAgentBrand(k, x, n), b, m[3], url.origin + `/${k}-spreadsheet/${b}`); }
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
  if ((path === "/" || path === "/index.html") && out.status === 200 && ct.includes("text/html")) return slimHtml(out, etagOf(out));
  if (out.status === 200 && ct.includes("text/html") && !STATIC_HTML.has(path) && !/^\/google[0-9a-f]+\.html$/.test(path)) return notFound(path);
  return out;
}

// A hub page served as the catalogue app: index.html with this page's title, meta, canonical, heading and filter preset
// (window.PC_PAGE), the homepage's own structured data swapped for this page's, and a compact FAQ/links block before the footer.
async function hubApp(ctx, url, spec) {
  const asset = await ctx.env.ASSETS.fetch(new Request(url.origin + "/", { method: "GET", headers: ctx.request.headers }));
  if (!asset.ok) return asset;
  const canon = "https://www.puroclassico.com" + spec.path;
  // Freshness (21 Oct 2026): the weekly dead-link check is real, so say when it last ran and give Google the same date.
  // The date goes into spec.sub, so the server-rendered subtitle and the app's copy (window.PC_PAGE.sub) match.
  let fresh = "";
  try {
    const lh = await (await ctx.env.ASSETS.fetch(new Request(url.origin + "/data/link_health.json"))).json();
    const d = new Date(lh.checked);
    if (!isNaN(d)) {
      spec = { ...spec, sub: `${spec.sub} Links checked ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })}.` };
      fresh = '<script type="application/ld+json">' + JSON.stringify({ "@context": "https://schema.org", "@type": "CollectionPage", name: spec.h, url: canon, dateModified: d.toISOString() }).replace(/</g, "\\u003c") + "</script>";
    }
  } catch (e) {}
  const { crumbHtml, seo, head } = hubParts(spec);
  const content = v => ({ element(e) { e.setAttribute("content", v); } });
  const out = new HTMLRewriter()
    .on("title", { element(e) { e.setInnerContent(spec.title); } })
    .on('meta[name="description"]', content(spec.desc))
    .on('meta[property="og:title"]', content(spec.title)).on('meta[name="twitter:title"]', content(spec.title))
    .on('meta[property="og:description"]', content(spec.desc)).on('meta[name="twitter:description"]', content(spec.desc))
    .on('meta[property="og:url"]', content(canon))
    .on('link[rel="canonical"]', { element(e) { e.setAttribute("href", canon); } })
    .on('script[type="application/ld+json"]', { element(e) { e.remove(); } })
    .on("script#pc-catalog", { element(e) { e.replace(catalogTags(etagOf(asset)), { html: true }); } })
    .on("meta[charset]", { element(e) { e.after(head + fresh, { html: true }); } })   // index.html has no <head> tag, so this is the first thing in it
    .on("h1.hero-h", { element(e) { e.setInnerContent(spec.h); e.before(crumbHtml, { html: true }); } })
    .on("p.hero-sub", { element(e) { e.setInnerContent(spec.sub); } })
    .on("footer", { element(e) { e.before(seo, { html: true }); } })
    .transform(asset);
  const res = new Response(out.body, { status: 200, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300, s-maxage=3600" } });
  return res;
}
