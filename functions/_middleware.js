// Routes the server-rendered SEO pages (hubs, guides, sitemaps) and turns the SPA's catch-all
// "200 + homepage" for unknown paths into a real 404, so Google doesn't see soft-404 duplicates.
import { notFound, ensureStats, BRAND_ALIAS, slug } from "./_lib/site.js";
import { renderBrand, renderCategory, renderAgent, renderOldMoney, renderBrands, renderGuides, renderGuide, renderModels, renderModel, renderTools, renderTool,
  sitemapIndex, sitemapPages, sitemapProducts } from "./_lib/pages.js";

// Real static HTML pages (everything else that comes back as HTML is the SPA fallback -> 404).
const STATIC_HTML = new Set(["/", "/index.html", "/privacy", "/privacy.html", "/terms", "/terms.html", "/stats", "/stats.html",
  "/how-to-order", "/how-to-order.html", "/admin", "/admin.html"]);
const VERIFY = { "/googleaea131de20fbf72e.html": "google-site-verification: googleaea131de20fbf72e.html" };
// Paths answered by real Functions (exact shapes only, so /api/nope, /product/ or /product/<id>/x still 404).
const PASS = /^\/api\/(qc|img|geo)$|^\/r\/[^/]+$|^\/product\/[^/]+$|^\/unsubscribe$/;
// Repo-internal files that Pages would otherwise serve from the repo root.
const PRIVATE = /^\/(scripts|\.github|functions)(\/|$)|^\/(readme\.md|discord_posted\.json|nonsb\.txt)$/i;
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

export async function onRequest(ctx) {
  const { request } = ctx;
  if (request.method !== "GET" && request.method !== "HEAD") return ctx.next();
  const url = new URL(request.url);
  const path = url.pathname;
  // The old *.pages.dev address still resolves: send everything to the real domain so traffic and ranking are not split.
  if (url.hostname.endsWith(".pages.dev")) return Response.redirect("https://www.puroclassico.com" + path + url.search, 301);
  // Search-engine ownership files, answered here so Pages' ".html -> pretty URL" redirect can't get in the way.
  if (VERIFY[path]) return new Response(VERIFY[path], { headers: { "content-type": "text/html; charset=utf-8" } });
  if (PRIVATE.test(path)) return notFound(path);
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
  if (/^\/(brand|category|brands|old-money|guides|best)|^\/[a-z]+-spreadsheet/.test(path)) await ensureStats(url.origin);
  if (path === "/sitemap.xml") return sitemapIndex();
  if (path === "/sitemap-pages.xml") return sitemapPages();
  if (path === "/sitemap-products.xml") return sitemapProducts();
  if (path === "/brands") res = renderBrands();
  else if (path === "/guides") res = renderGuides();
  else if ((m = path.match(/^\/guides\/([a-z0-9-]+)$/))) res = renderGuide(m[1]);
  else if (path === "/best") res = renderModels();
  else if ((m = path.match(/^\/best\/([a-z0-9-]+)(?:\/(\d+))?$/))) res = paged(renderModel, m[1], m[2], url.origin + "/best/" + m[1]);
  else if (path === "/tools") res = renderTools();
  else if ((m = path.match(/^\/tools\/([a-z0-9-]+)$/))) res = renderTool(m[1]);
  else if ((m = path.match(/^\/brand\/([a-z0-9-]+)(?:\/(\d+))?$/)) && BRAND_MOVED[m[1]]) return Response.redirect(url.origin + "/brand/" + BRAND_MOVED[m[1]], 301);
  else if (m) res = paged(renderBrand, m[1], m[2], url.origin + "/brand/" + m[1]);
  else if ((m = path.match(/^\/category\/([a-z0-9-]+)(?:\/(\d+))?$/))) res = paged(renderCategory, m[1], m[2], url.origin + "/category/" + m[1]);
  else if ((m = path.match(/^\/(mycnbox|kakobuy|oopbuy|lovegobuy|sugargoo)-spreadsheet(?:\/(\d+))?$/))) res = paged(renderAgent, m[1], m[2], url.origin + `/${m[1]}-spreadsheet`);
  else if ((m = path.match(/^\/old-money(?:\/(\d+))?$/))) res = paged((_, n) => renderOldMoney(n), null, m[1], url.origin + "/old-money");
  if (res !== undefined) return res || notFound(path);

  const out = await ctx.next();
  const ct = out.headers.get("content-type") || "";
  if (out.status === 200 && ct.includes("text/html") && !STATIC_HTML.has(path) && !/^\/google[0-9a-f]+\.html$/.test(path)) return notFound(path);
  return out;
}
