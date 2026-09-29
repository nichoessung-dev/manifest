// Image proxy — serves product and marketplace images from our origin with long Cloudflare edge caching.
// Usage: /api/img?u=<encoded image url>
// - Marketplace hosts are hotlink-protected, so they're fetched server-side with a browser-like Referer.
// - Supabase Storage is proxied so each photo is pulled from Supabase roughly once per edge location
//   instead of once per visitor (keeps Supabase egress low). Only public storage objects are allowed.
// Errors are never cached, so an upstream outage can't get stuck at the edge.
const ALLOW = ["si.geilicdn.com", "geilicdn.com", "img.alicdn.com", "alicdn.com", "cdn.qualit.ly"];
const SUPABASE = ["uptpghuduqjqmrxwatbm.supabase.co", "uiiegkpjqtgrkazccinf.supabase.co", "ckiynlgfmlvlyaozuduc.supabase.co"];

export async function onRequestGet({ request }) {
  const url = new URL(request.url);
  const u = url.searchParams.get("u");
  if (!u) return new Response("missing u", { status: 400 });
  let t;
  try { t = new URL(u); } catch (e) { return new Response("bad url", { status: 400 }); }
  if (t.protocol !== "https:") return new Response("bad protocol", { status: 400 });
  const host = t.hostname.toLowerCase();
  const isSupabase = SUPABASE.includes(host);
  if (isSupabase && !t.pathname.startsWith("/storage/v1/object/public/")) return new Response("forbidden path", { status: 403 });
  const ok = isSupabase || ALLOW.some(h => host === h || host.endsWith("." + h));
  if (!ok) return new Response("forbidden host", { status: 403 });

  const cache = caches.default;
  const ckey = new Request(url.toString(), { method: "GET" });
  const hit = await cache.match(ckey);
  if (hit) return hit;

  const headers = { "Accept": "image/avif,image/webp,image/apng,image/*,*/*" };
  if (!isSupabase) {
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36";
    headers["Referer"] = "https://weidian.com/";
  }

  let up;
  try {
    up = await fetch(t.toString(), {
      headers,
      cf: { cacheEverything: true, cacheTtlByStatus: { "200-299": 2592000, "300-599": 0 } }
    });
  } catch (e) {
    return new Response("fetch error", { status: 502, headers: { "cache-control": "no-store" } });
  }
  if (!up.ok) return new Response("upstream " + up.status, { status: 502, headers: { "cache-control": "no-store" } });
  const ct = up.headers.get("content-type") || "image/jpeg";
  if (!ct.startsWith("image/")) return new Response("not an image", { status: 502, headers: { "cache-control": "no-store" } });
  const body = await up.arrayBuffer();
  const resp = new Response(body, {
    status: 200,
    headers: {
      "content-type": ct,
      "cache-control": "public, max-age=604800, s-maxage=2592000",
      "access-control-allow-origin": "*",
      "x-content-type-options": "nosniff"
    }
  });
  try { await cache.put(ckey, resp.clone()); } catch (e) {}
  return resp;
}
