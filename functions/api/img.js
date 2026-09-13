// Image proxy — fetches hotlink-protected marketplace images server-side (where they work)
// and serves them from our origin with long edge caching. Usage: /api/img?u=<encoded image url>
const ALLOW = ["si.geilicdn.com", "geilicdn.com", "img.alicdn.com", "alicdn.com", "cdn.qualit.ly"];

export async function onRequestGet({ request }) {
  const url = new URL(request.url);
  const u = url.searchParams.get("u");
  if (!u) return new Response("missing u", { status: 400 });
  let t;
  try { t = new URL(u); } catch (e) { return new Response("bad url", { status: 400 }); }
  if (t.protocol !== "https:") return new Response("bad protocol", { status: 400 });
  const host = t.hostname.toLowerCase();
  const ok = ALLOW.some(h => host === h || host.endsWith("." + h));
  if (!ok) return new Response("forbidden host", { status: 403 });

  const cache = caches.default;
  const ckey = new Request(url.toString(), { method: "GET" });
  let hit = await cache.match(ckey);
  if (hit) return hit;

  let up;
  try {
    up = await fetch(t.toString(), {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        "Referer": "https://weidian.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*"
      },
      cf: { cacheEverything: true, cacheTtl: 2592000 }
    });
  } catch (e) {
    return new Response("fetch error", { status: 502 });
  }
  if (!up.ok) return new Response("upstream " + up.status, { status: 502 });
  const ct = up.headers.get("content-type") || "image/jpeg";
  const body = await up.arrayBuffer();
  const resp = new Response(body, {
    status: 200,
    headers: {
      "content-type": ct,
      "cache-control": "public, max-age=604800, s-maxage=2592000, immutable",
      "access-control-allow-origin": "*"
    }
  });
  try { await cache.put(ckey, resp.clone()); } catch (e) {}
  return resp;
}
