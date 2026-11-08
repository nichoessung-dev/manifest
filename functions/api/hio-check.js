/**
 * Cloudflare Pages Function: HioBuy API trial test (owner, 8 Nov 2026). Owner-only (beta=1), read-only: no orders, no
 * payments. Checks whether HioBuy can read our finds (Taobao, Weidian, 1688), compares live price and stock with the
 * sheet, and tries an international shipping quote. Guarded to at most 80 billable units a day (the trial has 100).
 *   /api/hio-check?beta=1&mode=usage                      today's usage (free)
 *   /api/hio-check?beta=1&mode=detail&pid=<find id>       one find, live vs sheet (1 unit)
 *   /api/hio-check?beta=1&mode=sample&n=10                n finds, mixed platforms (n units, at most 15)
 *   /api/hio-check?beta=1&mode=quote&cc=NO&kg=1           shipping quote to a country
 * Env: HIOBUY_API_KEY (secret).
 */
import { P } from "../_lib/site.js";

const API = "https://api.hiobuy.com";
const DAY_CAP = 80;
const J = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
const json = (status, body) => new Response(JSON.stringify(body, null, 1), { status, headers: J });

async function hio(env, path, body) {
  const r = await fetch(API + path, { method: body ? "POST" : "GET",
    headers: { authorization: "Bearer " + env.HIOBUY_API_KEY, "content-type": "application/json", accept: "application/json" },
    body: body ? JSON.stringify(body) : undefined });
  let d = null; try { d = await r.json(); } catch (e) {}
  return { status: r.status, data: d };
}

// a simple per-day unit counter in the edge cache (best effort; one location)
async function spend(n) {
  const day = new Date().toISOString().slice(0, 10), key = new Request("https://hio-check.internal/units/" + day);
  let used = 0; try { const h = await caches.default.match(key); if (h) used = parseInt(await h.text(), 10) || 0; } catch (e) {}
  if (used + n > DAY_CAP) return false;
  try { await caches.default.put(key, new Response(String(used + n), { headers: { "cache-control": "max-age=90000" } })); } catch (e) {}
  return true;
}

const num = v => (typeof v === "number" ? v : parseFloat(v)) || null;
function brief(p, res) {
  const d = res.data && res.data.product;
  if (res.status !== 200 || !d) return { id: p.id, platform: p.platform, title: p.title, ok: false, status: res.status, error: res.data && (res.data.error || res.data.message || res.data.code) || null };
  const vs = d.variants || [];
  const prices = vs.map(v => num(v.price && (v.price.amount ?? v.price.value ?? v.price)) ).filter(Boolean);
  const stock = vs.map(v => num(v.stock ?? v.quantity ?? (v.inventory && v.inventory.quantity))).filter(v => v != null);
  const live = num(d.price && (d.price.amount ?? d.price.min ?? d.price.value)) || (prices.length ? Math.min(...prices) : null);
  return { id: p.id, platform: p.platform, title: p.title, ok: true,
    sheet_cny: num(p.cny), live_price: live, price_currency: d.price && (d.price.currency || d.price.monetary_unit) || null,
    variants: vs.length, in_stock_variants: stock.length ? stock.filter(s => s > 0).length : null, total_stock: stock.length ? stock.reduce((a, b) => a + b, 0) : null,
    live_title: d.title && (d.title.en || d.title.original || d.title.zh || Object.values(d.title)[0]) || null,
    images: (d.images || []).length, seller: d.seller && (d.seller.name || d.seller.shop_name || d.seller.id) || null,
    sample_variant: vs[0] ? JSON.stringify(vs[0]).slice(0, 300) : null, price_raw: d.price ? JSON.stringify(d.price).slice(0, 200) : null };
}
const req = p => ({ channel: p.platform, product_id: String(p.itemId || p.id), language: "en" });

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url), q = url.searchParams;
  if (q.get("beta") !== "1") return json(404, { error: "not found" });
  if (!env || !env.HIOBUY_API_KEY) return json(503, { error: "HIOBUY_API_KEY is not set (Cloudflare Pages > Settings > Variables and Secrets, Production)" });
  const mode = q.get("mode") || "usage";
  if (mode === "usage") { const r = await hio(env, "/v1/usage/today"); const a = await hio(env, "/v1/app"); return json(200, { usage: r, app: a }); }
  if (mode === "detail") {
    const p = P.find(x => String(x.id) === (q.get("pid") || ""));
    if (!p) return json(404, { error: "find not on the sheet" });
    if (!(await spend(1))) return json(429, { error: "daily test budget used" });
    const r = await hio(env, "/v1/products/detail", req(p));
    return json(200, { find: brief(p, r), raw_keys: r.data ? Object.keys(r.data.product || r.data) : null, raw_error: r.status !== 200 ? r.data : undefined });
  }
  if (mode === "sample") {
    const n = Math.max(1, Math.min(15, parseInt(q.get("n") || "10", 10) || 10));
    if (!(await spend(n))) return json(429, { error: "daily test budget used" });
    const by = { weidian: [], taobao: [], "1688": [] };
    P.filter(p => by[p.platform] && p.img && !String(p.title || "").match(/placeholder/i)).forEach(p => by[p.platform].push(p));
    const pick = [], order = ["weidian", "taobao", "weidian", "1688", "weidian", "taobao"];
    for (let i = 0; pick.length < n && i < 200; i++) { const L = by[order[i % order.length]]; if (L.length) pick.push(L.splice(Math.floor(L.length * ((i * 37 % 97) / 97)), 1)[0]); }
    const out = [];
    for (const p of pick) out.push(brief(p, await hio(env, "/v1/products/detail", req(p))));
    const sum = {}; out.forEach(o => { const s = sum[o.platform] = sum[o.platform] || { tried: 0, ok: 0 }; s.tried++; if (o.ok) s.ok++; });
    return json(200, { summary: sum, finds: out });
  }
  if (mode === "quote") {
    const cc = (q.get("cc") || "NO").toUpperCase().slice(0, 2), kg = Math.max(0.1, Math.min(30, parseFloat(q.get("kg") || "1") || 1));
    const ch = await hio(env, "/v1/fulfillment/shipping/channels");
    const r = await hio(env, "/v1/fulfillment/shipping/quotes", { destination: { country_code: cc }, weight_kg: kg });
    return json(200, { channels_status: ch.status, channels: ch.data && (ch.data.channels || ch.data.items || ch.data), quote_status: r.status, quote: r.data });
  }
  return json(400, { error: "mode: usage, detail, sample or quote" });
}
