/**
 * Cloudflare Pages Function: helper for the Link Converter and QC Checker (round 10 tools pass).
 * Route: GET /api/link?p=<weidian|taobao|1688>&id=<item id>  -> { find }   our catalogue's find for that listing, or null
 *        GET /api/link?u=<share link>                        -> { platform, id, url, find }
 *
 * Share links (m.tb.cn, e.tb.cn, Weidian's youshop10.com / koudai.com, qr.1688.com) can't be read in the browser: the
 * item only appears after a redirect or inside the page Taobao serves. This follows at most 4 hops, only ever to the
 * short-link and marketplace hosts below, and returns nothing but the marketplace and the item ID it found.
 * No keys, nothing stored. Results are edge-cached for a day (misses for 10 minutes).
 */
import { P, gone, imgSrc, thumbSrc, productUrl, money } from "../_lib/site.js";

const PLATS = new Set(["weidian", "taobao", "1688"]);
const SHORT = /(?:^|\.)(?:tb\.cn|youshop10\.com|koudai\.com|vdian\.com)$|^qr\.1688\.com$/;
const MARKET = [["weidian", /(?:^|\.)(?:weidian\.com|koudai\.com|vdian\.com|youshop10\.com)$/], ["taobao", /(?:^|\.)(?:taobao\.com|tmall\.com|tmall\.hk)$/], ["1688", /(?:^|\.)1688\.com$/]];
const UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";

const json = (body, status = 200, maxAge = 0) => new Response(JSON.stringify(body), { status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": maxAge ? `public, max-age=${maxAge}` : "no-store" } });
const withTimeout = (p, ms) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms))]);

// Catalogue lookup: "platform/id" -> find, built once per isolate. Both the listing ID and our own ID are keys.
let MAP = null;
function findOf(platform, id) {
  if (!MAP) {
    MAP = new Map();
    for (const p of P) {
      if (gone(p) === "dead") continue;
      const pl = p.platform || "weidian";
      for (const k of [p.itemId, p.id]) if (k && /^\d+$/.test(String(k))) { const key = pl + "/" + String(k).replace(/^0+/, ""); if (!MAP.has(key)) MAP.set(key, p); }
    }
  }
  const p = MAP.get(platform + "/" + String(id).replace(/^0+/, ""));
  if (!p) return null;
  return { pid: String(p.id), title: p.title, brand: p.brand || "", img: thumbSrc(imgSrc(p)), price: money(p.cny), qc: p.qc || 0,
    url: productUrl(p), sold: gone(p) === "sold_out" };
}

// Marketplace and item ID from a full listing URL (the subset of the client's pcExtract that redirects end on).
export function itemOf(u) {
  let x; try { x = new URL(u); } catch (e) { return null; }
  const host = x.hostname.toLowerCase(), m = MARKET.find(([, re]) => re.test(host));
  if (!m) return null;
  const s = x.pathname + x.search + x.hash;
  const r = s.match(/[?&#](?:item_?id|itemID)=(\d{6,})/i) || s.match(/[?&#](?:id|offer_?id)=(\d{6,})/i) || s.match(/\/offer\/(\d{6,})/i) ||
    s.match(/\/i(\d{6,})\.htm/i) || s.match(/\/item\/(\d{6,})/i) || s.match(/\/(\d{9,})\.html?\b/i);
  return r ? { platform: m[0], id: r[1] } : null;
}
// The target Taobao's share page names in its script (var url = '...'), else any listing URL in the page.
export function targetIn(html) {
  const a = html.match(/var\s+url\s*=\s*['"](https?:\/\/[^'"\s]+)['"]/);
  if (a && itemOf(a[1])) return a[1];
  const re = /https?:\/\/[a-z0-9.-]+\.(?:taobao\.com|tmall\.com|tmall\.hk|weidian\.com|1688\.com)\/[^'"\s<>\\]+/gi;
  let m; while ((m = re.exec(html))) if (itemOf(m[0])) return m[0];
  return null;
}

export async function resolve(start, fetcher = fetch) {
  let u = start;
  for (let hop = 0; hop < 4; hop++) {
    let x; try { x = new URL(u); } catch (e) { return null; }
    if (x.protocol !== "https:" && x.protocol !== "http:") return null;
    const it = itemOf(x.href); if (it) return Object.assign({ url: x.href }, it);
    if (!SHORT.test(x.hostname.toLowerCase())) return null;
    const r = await withTimeout(fetcher(x.href, { redirect: "manual", headers: { "user-agent": UA, accept: "text/html" } }), 4000);
    const loc = r.headers.get("location");
    if (r.status >= 300 && r.status < 400 && loc) { u = new URL(loc, x.href).href; continue; }
    if (r.status !== 200) return null;
    const html = (await r.text()).slice(0, 300000), t = targetIn(html);
    if (!t) return null;
    u = t;
  }
  return null;
}

export async function onRequestGet(context) {
  const url = new URL(context.request.url), q = url.searchParams;
  const p = (q.get("p") || "").toLowerCase(), id = (q.get("id") || "").trim();
  if (q.has("p")) {
    if (!PLATS.has(p) || !/^\d{6,20}$/.test(id)) return json({ error: "invalid" }, 400);
    return json({ find: findOf(p, id) }, 200, 3600);
  }
  const raw = (q.get("u") || "").trim().slice(0, 500);
  let x; try { x = new URL(raw); } catch (e) { return json({ error: "invalid" }, 400); }
  if (!SHORT.test(x.hostname.toLowerCase()) && !itemOf(x.href)) return json({ error: "not a share link" }, 400);
  const cache = caches.default, key = new Request("https://link-cache.internal/v1/" + encodeURIComponent(x.href));
  const hit = await cache.match(key); if (hit) return hit;
  let r = null; try { r = await resolve(x.href); } catch (e) { r = null; }
  const res = r ? json({ platform: r.platform, id: r.id, url: r.url, find: findOf(r.platform, r.id) }, 200, 86400) : json({ error: "unresolved" }, 404, 600);
  context.waitUntil(cache.put(key, res.clone()));
  return res;
}
