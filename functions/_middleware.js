// Routes the server-rendered SEO pages (hubs, guides, sitemaps) and turns the SPA's catch-all
// "200 + homepage" for unknown paths into a real 404, so Google doesn't see soft-404 duplicates.
import { notFound } from "./_lib/site.js";
import { renderBrand, renderCategory, renderAgent, renderOldMoney, renderBrands, renderGuides, renderGuide,
  sitemapIndex, sitemapPages, sitemapProducts } from "./_lib/pages.js";

// Real static HTML pages (everything else that comes back as HTML is the SPA fallback -> 404).
const STATIC_HTML = new Set(["/", "/index.html", "/privacy", "/privacy.html", "/terms", "/terms.html", "/stats", "/stats.html",
  "/how-to-order", "/how-to-order.html"]);
const PASS = /^\/(api|r|product)\/|^\/unsubscribe$/;

function paged(fn, arg, nStr, base) {
  if (nStr === "1") return Response.redirect(base, 301);          // /x/1 duplicates /x
  return fn(arg, nStr ? parseInt(nStr, 10) : 1);
}

export async function onRequest(ctx) {
  const { request } = ctx;
  if (request.method !== "GET" && request.method !== "HEAD") return ctx.next();
  const url = new URL(request.url);
  const path = url.pathname;
  if (PASS.test(path)) return ctx.next();
  if (path.length > 1 && path.endsWith("/")) return Response.redirect(url.origin + path.replace(/\/+$/, "") + url.search, 301);

  let m, res = undefined;
  if (path === "/sitemap.xml") return sitemapIndex();
  if (path === "/sitemap-pages.xml") return sitemapPages();
  if (path === "/sitemap-products.xml") return sitemapProducts();
  if (path === "/brands") res = renderBrands();
  else if (path === "/guides") res = renderGuides();
  else if ((m = path.match(/^\/guides\/([a-z0-9-]+)$/))) res = renderGuide(m[1]);
  else if ((m = path.match(/^\/brand\/([a-z0-9-]+)(?:\/(\d+))?$/))) res = paged(renderBrand, m[1], m[2], url.origin + "/brand/" + m[1]);
  else if ((m = path.match(/^\/category\/([a-z0-9-]+)(?:\/(\d+))?$/))) res = paged(renderCategory, m[1], m[2], url.origin + "/category/" + m[1]);
  else if ((m = path.match(/^\/(mycnbox|kakobuy|oopbuy|lovegobuy|sugargoo)-spreadsheet(?:\/(\d+))?$/))) res = paged(renderAgent, m[1], m[2], url.origin + `/${m[1]}-spreadsheet`);
  else if ((m = path.match(/^\/old-money(?:\/(\d+))?$/))) res = paged((_, n) => renderOldMoney(n), null, m[1], url.origin + "/old-money");
  if (res !== undefined) return res || notFound(path);

  const out = await ctx.next();
  const ct = out.headers.get("content-type") || "";
  if (out.status === 200 && ct.includes("text/html") && !STATIC_HTML.has(path) && !/^\/google[0-9a-f]+\.html$/.test(path)) return notFound(path);
  return out;
}
