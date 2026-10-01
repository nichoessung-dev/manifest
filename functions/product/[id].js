// /product/<id> — a fully server-rendered product page (H1, price, QC photos, agent links, related finds),
// so every find is a real, fast, indexable page. Finds without QC photos are noindex,follow.
// Unknown/removed ids get a real 404.
import { renderProduct } from "../_lib/pages.js";
import { notFound, ensureStats, BUILT } from "../_lib/site.js";

const PAGE_TTL = 60 * 60 * 24;     // 1 day
const QC_MISS_TTL = 60 * 15;       // 15 min when the QC lookup failed
const BROWSER_CC = "public, max-age=300, s-maxage=3600";

export async function onRequestGet(context) {
  const { request, params } = context;
  const url = new URL(request.url);
  let id;
  try { id = decodeURIComponent(params.id || ""); } catch (e) { return notFound(url.pathname); }  // malformed %-escape
  if (!/^[0-9A-Za-z_-]{1,40}$/.test(id)) return notFound(url.pathname);
  // Edge-cache the rendered page (per catalogue build) so crawls don't trigger a live /api/qc lookup on every render.
  const cache = caches.default;
  const key = new Request(`https://ssr-cache.internal/product/${BUILT}/${encodeURIComponent(id)}`, { method: "GET" });
  const hit = await cache.match(key);
  if (hit) { const r = new Response(hit.body, hit); r.headers.set("cache-control", BROWSER_CC); r.headers.set("x-ssr-cache", "HIT"); return r; }
  await ensureStats(url.origin);
  const res = await renderProduct(id, url.origin);
  if (!res) return notFound(url.pathname);
  const ttl = res.headers.get("x-qc-miss") ? QC_MISS_TTL : PAGE_TTL;   // a render without its QC photos is retried soon
  res.headers.delete("x-qc-miss");
  const stored = new Response(res.clone().body, res);
  stored.headers.set("cache-control", `public, max-age=${ttl}`);
  context.waitUntil(cache.put(key, stored));
  return res;
}

// Pages doesn't route HEAD to onRequestGet (it would fall through to the SPA's 200 text/html).
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
