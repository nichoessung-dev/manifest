/**
 * Cloudflare Pages Function — QC photo proxy for qualit.ly
 * Route: GET /api/qc?storefront=<weidian|taobao|1688>&id=<listing_id>
 *        GET /api/qc?usage=1   -> qualit.ly quota usage (minute/month counters only, for the /admin dashboard;
 *                                 when ADMIN_TOKEN is set it needs a matching x-admin-token header)
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

import { P } from "../_lib/site.js";

const STOREFRONTS = new Set(["weidian", "taobao", "1688"]);
const UPSTREAM = "https://backend.qualit.ly/api/v1";
const CACHE_TTL = 60 * 60 * 24 * 7; // 7 days
const MISS_TTL = 60 * 60 * 24;      // 1 day for "no QC" / upstream errors that aren't transient
const ERR_TTL = 120;                // transient upstream errors (429/5xx/timeouts): short negative cache
const USAGE_TTL = 300;
// Per-IP throttle (per isolate, best effort) for uncached lookups of IDs that aren't in the catalogue.
const RL_WINDOW = 10 * 60 * 1000, RL_MAX = 20;
const rl = new Map();
let catIds = null;
function inCatalog(storefront, id) {
  if (!catIds) catIds = new Set(P.map(p => p.platform + "/" + String(p.itemId || p.id).replace(/^0+/, "")));
  return catIds.has(storefront + "/" + id);
}
function throttled(ip) {
  const now = Date.now(), e = rl.get(ip);
  if (!e || now - e.t > RL_WINDOW) { if (rl.size > 5000) rl.clear(); rl.set(ip, { t: now, n: 1 }); return false; }
  return ++e.n > RL_MAX;
}

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

  const cache = caches.default;
  if (url.searchParams.get("usage")) {
    if (env.ADMIN_TOKEN && request.headers.get("x-admin-token") !== env.ADMIN_TOKEN) return json({ error: "unauthorized" }, 401, { "cache-control": "no-store" });
    const usageKey = new Request("https://qc-cache.internal/usage", { method: "GET" });
    const hit = await cache.match(usageKey);
    if (hit) return new Response(hit.body, { status: 200, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "private, no-store" } });
    try {
      const u = await upstreamJSON("/usage", env);
      if (!u.data) return json({ error: "unavailable", status: u.status }, 502, { "cache-control": "no-store" });
      const pick = o => o && typeof o === "object" ? { limit: o.limit, used: o.used, remaining: o.remaining, reset_at: o.reset_at } : undefined;
      const out = { minute: pick(u.data.minute), month: pick(u.data.month) };
      context.waitUntil(cache.put(usageKey, json(out, 200, { "cache-control": `public, max-age=${USAGE_TTL}` })));
      return json(out, 200, { "cache-control": "private, no-store" });
    } catch (e) { return json({ error: "unavailable" }, 502, { "cache-control": "no-store" }); }
  }

  const storefront = (url.searchParams.get("storefront") || "").toLowerCase().trim();
  const id = (url.searchParams.get("id") || "").trim().replace(/^0+/, "");   // 00123456 and 123456 share one cache entry
  // --- validate input (defend against the proxy being used as an open relay) ---
  if (!STOREFRONTS.has(storefront)) return json({ error: "invalid storefront" }, 400);
  if (!/^[1-9][0-9]{5,19}$/.test(id)) return json({ error: "invalid id" }, 400);

  // --- edge cache: one qualit.ly call per (storefront,id) per week across all visitors ---
  const cacheKey = new Request(`https://qc-cache.internal/v2/${storefront}/${id}`, { method: "GET" });
  const cached = await cache.match(cacheKey);
  if (cached) return cached;
  if (!inCatalog(storefront, id) && throttled(request.headers.get("cf-connecting-ip") || "?"))
    return json({ error: "rate limited" }, 429, { "cache-control": "no-store", "retry-after": "600" });

  const fail = (st) => {   // negative cache: "not found" for a day, transient errors for 2 minutes
    const res = json({ error: st === 404 ? "upstream error" : "upstream unavailable", status: st }, st, { "cache-control": `public, max-age=${st === 404 ? MISS_TTL : ERR_TTL}` });
    context.waitUntil(cache.put(cacheKey, res.clone()));
    return res;
  };
  let d = null, thumbs = [];
  try {
    const p = await upstreamJSON(`/products/${storefront}/${id}`, env);   // up to 5 qc_preview thumbs
    let q = null;
    if (p.data) { d = p.data; thumbs = urlsFrom(d.qc_preview).concat(urlsFrom(d.thumbnails)); }
    if (!thumbs.length && p.status !== 429 && (!p.data || (d && d.qc_count > 0))) {   // fallback: older endpoint (3 thumbs), only when there is QC to find (never while rate-limited)
      q = await upstreamJSON(`/qc/${storefront}/${id}`, env);
      if (q.data) { d = Object.assign({}, q.data, d || {}); thumbs = urlsFrom(q.data.thumbnails).concat(urlsFrom(q.data.qc_preview)); }
    }
    if (!d) {
      const sts = [p.status, q ? q.status : 0];
      const transient = sts.some(s => s === 429 || s >= 500);              // a 429/5xx must never be cached as "not found"
      return fail(!transient && sts.includes(404) ? 404 : 502);
    }
  } catch (e) {
    return fail(502);
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
