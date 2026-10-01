/**
 * Cloudflare Pages Function — visitor country for language/currency auto-select.
 * Route: GET /api/geo  ->  { "country": "NO" }
 * Cloudflare adds the CF-IPCountry header on every request; no external call.
 */
export async function onRequestGet(context) {
  const req = context.request;
  const country =
    req.headers.get("cf-ipcountry") ||
    (req.cf && req.cf.country) ||
    "";
  return new Response(JSON.stringify({ country }), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

// Pages doesn't route HEAD to onRequestGet (it would fall through to the SPA's 200 text/html).
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
