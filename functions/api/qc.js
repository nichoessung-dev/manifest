/**
 * Cloudflare Pages Function — QC photo proxy for qualit.ly
 * Route: GET /api/qc?storefront=<weidian|taobao|1688>&id=<listing_id>
 *        GET /api/qc?usage=1   -> qualit.ly quota usage (numbers only, for the /admin dashboard)
 *
 * The qualit.ly API key lives ONLY here, in an environment variable, and is
 * never sent to the browser. Set it in the Cloudflare dashboard:
 *   Pages project → Settings → Environment variables → QUALITLY_KEY = qc_live_...
 *
 * Uses GET /products/{storefront}/{id}, which returns up to 5 qc_preview thumbnails
 * (the older /qc/{storefront}/{id} endpoint returns 3 and is kept as a fallback).
 * Dead thumbnails (qualit.ly CDN 404s) are dropped before caching.
 *
 * Returns: { qc_count, thumbnails: [url,...] }  (also passes through name/price/product_url when present)
 * Responses are edge-cached for 7 days (misses for 1 day) to protect the monthly API quota.
 */

const STOREFRONTS = new Set(["weidian", "taobao", "1688"]);
const UPSTREAM = "https://backend.qualit.ly/api/v1";
const CACHE_TTL = 60 * 60 * 24 * 7; // 7 days
const MISS_TTL = 60 * 60 * 24;      // 1 day for "no QC" / upstream errors that aren't transient

function json(body, status, extraHeaders) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: Object.assign({ "content-type": "application/json; charset=utf-8" }, extraHeaders || {}),
  });
}

function withTimeout(p, ms) {
  return Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms))]);
}

// qc_preview / thumbnails may be plain URL strings or objects with a url field.
function urlsFrom(list) {
  if (!Array.isArray(list)) return [];
  return list.map(x => typeof x === "string" ? x : (x && (x.url || x.src || x.image || x.thumbnail)) || "")
             .filter(u => /^https:\/\//.test(u));
}

async function upstreamJSON(path, env) {
  const r = await withTimeout(fetch(UPSTREAM + path, {
    headers: { Authorization: `Bearer ${env.QUALITLY_KEY}`, Accept: "application/json" },
  }), 8000);
  if (!r.ok) return { status: r.status, data: null };
  const payload = await r.json().catch(() => null);
  return { status: 200, data: payload && payload.data ? payload.data : payload };
}

// Keep only thumbnails that actually load (qualit.ly's CDN 404s some of them).
async function liveOnly(urls) {
  const checks = await Promise.all(urls.map(u =>
    withTimeout(fetch(u, { method: "HEAD" }), 2500).then(r => r.ok ? u : null).catch(() => u)   // on timeout keep it; the browser hides failures
  ));
  return checks.filter(Boolean);
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  if (!env.QUALITLY_KEY) return json({ error: "server not configured" }, 500);

  if (url.searchParams.get("usage")) {
    try {
      const u = await upstreamJSON("/usage", env);
      return json(u.data || { error: "unavailable", status: u.status }, u.data ? 200 : 502, { "cache-control": "public, max-age=300" });
    } catch (e) { return json({ error: "unavailable" }, 502); }
  }

  const storefront = (url.searchParams.get("storefront") || "").toLowerCase().trim();
  const id = (url.searchParams.get("id") || "").trim();
  // --- validate input (defend against the proxy being used as an open relay) ---
  if (!STOREFRONTS.has(storefront)) return json({ error: "invalid storefront" }, 400);
  if (!/^[0-9]{4,20}$/.test(id)) return json({ error: "invalid id" }, 400);

  // --- edge cache: one qualit.ly call per (storefront,id) per week across all visitors ---
  const cacheKey = new Request(`https://qc-cache.internal/v2/${storefront}/${id}`, { method: "GET" });
  const cache = caches.default;
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  let d = null, thumbs = [];
  try {
    const p = await upstreamJSON(`/products/${storefront}/${id}`, env);   // up to 5 qc_preview thumbs
    if (p.data) { d = p.data; thumbs = urlsFrom(d.qc_preview).concat(urlsFrom(d.thumbnails)); }
    if (!thumbs.length && (!p.data || (d && d.qc_count > 0))) {             // fallback: older endpoint (3 thumbs), only when there is QC to find
      const q = await upstreamJSON(`/qc/${storefront}/${id}`, env);
      if (q.data) { d = Object.assign({}, q.data, d || {}); thumbs = urlsFrom(q.data.thumbnails).concat(urlsFrom(q.data.qc_preview)); }
      else if (!p.data) {
        const st = q.status === 404 || p.status === 404 ? 404 : 502;
        const res = json({ error: "upstream error", status: st }, st, st === 404 ? { "cache-control": `public, max-age=${MISS_TTL}` } : {});
        if (st === 404) context.waitUntil(cache.put(cacheKey, res.clone()));
        return res;
      }
    }
  } catch (e) {
    return json({ error: "upstream unreachable" }, 502);
  }

  thumbs = await liveOnly([...new Set(thumbs)].slice(0, 8));
  const out = {
    storefront,
    listing_id: id,
    qc_count: (d && d.qc_count) || 0,
    thumbnails: thumbs,
  };
  if (d && d.name) out.name = d.name;
  if (d && d.price) out.price = d.price;
  if (d && d.product_url) out.product_url = d.product_url;

  const res = json(out, 200, { "cache-control": `public, max-age=${thumbs.length ? CACHE_TTL : MISS_TTL}` });
  context.waitUntil(cache.put(cacheKey, res.clone()));
  return res;
}
