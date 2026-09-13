/**
 * Cloudflare Pages Function — QC photo proxy for qualit.ly
 * Route: GET /api/qc?storefront=<weidian|taobao|1688>&id=<listing_id>
 *
 * The qualit.ly API key lives ONLY here, in an environment variable, and is
 * never sent to the browser. Set it in the Cloudflare dashboard:
 *   Pages project → Settings → Environment variables → QUALITLY_KEY = qc_live_...
 *
 * Returns: { qc_count, thumbnails: [url,...] }  (also passes through name/price/product_url when present)
 * Responses are edge-cached for 24h to protect the monthly quota.
 */

const STOREFRONTS = new Set(["weidian", "taobao", "1688"]);
const UPSTREAM = "https://backend.qualit.ly/api/v1";
const CACHE_TTL = 60 * 60 * 24; // 24h

function json(body, status, extraHeaders) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: Object.assign(
      { "content-type": "application/json; charset=utf-8" },
      extraHeaders || {}
    ),
  });
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const storefront = (url.searchParams.get("storefront") || "").toLowerCase().trim();
  const id = (url.searchParams.get("id") || "").trim();

  // --- validate input (defend against the proxy being used as an open relay) ---
  if (!STOREFRONTS.has(storefront)) {
    return json({ error: "invalid storefront" }, 400);
  }
  if (!/^[0-9]{4,20}$/.test(id)) {
    return json({ error: "invalid id" }, 400);
  }
  if (!env.QUALITLY_KEY) {
    return json({ error: "server not configured" }, 500);
  }

  // --- edge cache: one qualit.ly call per (storefront,id) per day across all visitors ---
  const cacheKey = new Request(
    `https://qc-cache.internal/${storefront}/${id}`,
    { method: "GET" }
  );
  const cache = caches.default;
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  let upstream;
  try {
    upstream = await fetch(`${UPSTREAM}/qc/${storefront}/${id}`, {
      headers: {
        Authorization: `Bearer ${env.QUALITLY_KEY}`,
        Accept: "application/json",
      },
    });
  } catch (e) {
    return json({ error: "upstream unreachable" }, 502);
  }

  if (!upstream.ok) {
    // pass through the status but not the key-bearing details
    return json({ error: "upstream error", status: upstream.status }, upstream.status === 404 ? 404 : 502);
  }

  let payload;
  try {
    payload = await upstream.json();
  } catch (e) {
    return json({ error: "bad upstream response" }, 502);
  }

  const d = (payload && payload.data) ? payload.data : payload || {};
  const out = {
    storefront,
    listing_id: id,
    qc_count: d.qc_count || 0,
    thumbnails: Array.isArray(d.thumbnails) ? d.thumbnails
              : (Array.isArray(d.qc_preview) ? d.qc_preview : []),
  };
  if (d.name) out.name = d.name;
  if (d.price) out.price = d.price;
  if (d.product_url) out.product_url = d.product_url;

  const res = json(out, 200, {
    "cache-control": `public, max-age=${CACHE_TTL}`,
  });
  // store a clone in the edge cache (don't await — fire and forget)
  context.waitUntil(cache.put(cacheKey, res.clone()));
  return res;
}
