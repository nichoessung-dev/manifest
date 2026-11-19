/**
 * Cloudflare Pages Function: the feedback pop-up (feedback.js, owner 19 Nov 2026: "only give feedback to people who has
 * spendt alot of time on the spreadsheet (top 5-10%)").
 *   POST /api/feedback  { r: 1..5, text, email?, page, min, days }   -> 200 {"ok":true} (also when dropped)
 *   GET  /api/feedback  header x-admin-token: ADMIN_TOKEN            -> {items: [...]} newest first (this and last month)
 * Stored in a private Supabase storage bucket "feedback" (made on first use), one JSON file per month (feedback/2026-11.json).
 * No IP or user agent is stored. Without ADMIN_TOKEN set nobody can read it back (401), the owner reads it on /admin.
 * Env: SUPABASE_SERVICE_KEY, ADMIN_TOKEN.
 */
const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";
const BUCKET = "feedback";
const ORIGIN = /^https:\/\/([a-z0-9-]+\.)*(puroclassico\.com|manifest-bq9\.pages\.dev)$|^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/;
const BOT = /bot|crawl|spider|headless|puppeteer|playwright|selenium|lighthouse|preview/i;
const MAX_BODY = 4096, MAX_PER_MONTH = 2000;
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
const OK = () => json({ ok: true });
const hdr = env => ({ authorization: "Bearer " + env.SUPABASE_SERVICE_KEY, apikey: env.SUPABASE_SERVICE_KEY });
const month = d => d.toISOString().slice(0, 7);
const burst = new Map();   // per isolate: at most 5 posts per IP per 10 minutes

async function readMonth(env, m) {
  const r = await fetch(`${SUPA}/storage/v1/object/authenticated/${BUCKET}/${m}.json?t=${Date.now()}`, { headers: hdr(env), cf: { cacheTtl: 0 } });
  if (!r.ok) return [];
  try { const j = await r.json(); return Array.isArray(j) ? j : []; } catch (e) { return []; }
}
async function write(env, m, list) {
  const put = () => fetch(`${SUPA}/storage/v1/object/${BUCKET}/${m}.json`, { method: "POST", body: JSON.stringify(list),
    headers: { ...hdr(env), "content-type": "application/json", "x-upsert": "true", "cache-control": "no-store" } });
  let r = await put();
  if (!r.ok) {   // the bucket is not there yet: make it (private) and try again
    await fetch(`${SUPA}/storage/v1/bucket`, { method: "POST", headers: { ...hdr(env), "content-type": "application/json" },
      body: JSON.stringify({ id: BUCKET, name: BUCKET, public: false }) });
    r = await put();
  }
  return r.ok;
}

export async function onRequestPost({ request, env }) {
  if (!env.SUPABASE_SERVICE_KEY) return OK();
  const o = request.headers.get("origin") || "";
  if (!ORIGIN.test(o) || BOT.test(request.headers.get("user-agent") || "")) return OK();
  const raw = await request.text(); if (raw.length > MAX_BODY) return OK();
  let b; try { b = JSON.parse(raw); } catch (e) { return OK(); }
  const ip = request.headers.get("cf-connecting-ip") || "", now = Date.now();
  const h = (burst.get(ip) || []).filter(t => now - t < 6e5); if (h.length >= 5) return OK(); h.push(now); burst.set(ip, h);
  const r = Math.round(+b.r);
  const text = String(b.text || "").replace(/[\u0000-\u0008\u000b-\u001f]/g, "").trim().slice(0, 1000);
  if (!(r >= 1 && r <= 5) && !text) return OK();
  const email = /^[^\s@]{1,64}@[^\s@]{1,190}\.[a-z]{2,}$/i.test(String(b.email || "").trim()) ? String(b.email).trim().slice(0, 200) : "";
  const item = { at: new Date(now).toISOString(), r: r >= 1 && r <= 5 ? r : null, text, email,
    page: String(b.page || "").slice(0, 200), min: Math.max(0, Math.min(100000, Math.round(+b.min || 0))),
    days: Math.max(0, Math.min(365, Math.round(+b.days || 0))), lang: String(b.lang || "").slice(0, 8),
    country: (request.cf && request.cf.country) || "" };
  const m = month(new Date(now)), list = await readMonth(env, m);
  if (list.length >= MAX_PER_MONTH) return OK();
  list.push(item);
  await write(env, m, list);
  return OK();
}

export async function onRequestGet({ request, env }) {
  if (!env.ADMIN_TOKEN || request.headers.get("x-admin-token") !== env.ADMIN_TOKEN) return json({ error: "unauthorized" }, 401);
  const d = new Date(), prev = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - 1, 1));
  const [a, b] = await Promise.all([readMonth(env, month(d)), readMonth(env, month(prev))]);
  return json({ items: b.concat(a).sort((x, y) => (y.at || "").localeCompare(x.at || "")) });
}
