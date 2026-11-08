/**
 * Cloudflare Pages Function: AI notes on a find's buyer QC photos (owner, 8 Nov 2026: BETA, the owner tests it before launch).
 * Route: GET /api/qc-check?storefront=weidian&id=123&pid=<find id>&beta=1
 *   -> 200 {"checks":[{"area":"logo","status":"good|watch|cant_tell","note":"..."}],"summary":"...","n":5,"model":"..."}
 * The photos are the QC bank's stored photos (data/qc_bank.json, the ones the site shows; no qualit.ly quota) plus
 * the listing photo for colour and shape. Claude only describes what it can see; it never says real or fake and never
 * promises quality. Answers kept for good in data/qc_ai.json (scripts/qc_ai.py) are served first; a find not done yet is
 * checked live and cached at the edge. 10 new checks per IP per 10 minutes.
 * Env: ANTHROPIC_API_KEY (set for the chat), QC_CHECK_MODEL (optional, default below).
 */
import { P } from "../_lib/site.js";

const API = "https://api.anthropic.com/v1/messages";
const DEFAULT_MODEL = "claude-sonnet-5-5";   // vision detail matters more here than in the photo search
const MAX_PHOTOS = 5, LIMIT = 10, WINDOW = 10 * 60 * 1000, TTL = 60 * 60 * 24 * 30;
const J = { "content-type": "application/json; charset=utf-8" };
const json = (status, body, cache) => new Response(JSON.stringify(body), { status, headers: { ...J, "cache-control": cache || "no-store" } });
const seen = new Map();

const PROMPT = (title) => "Image 1 is the seller's listing photo of: " + title + ". The other images are buyer quality-check (QC) photos " +
  "of the same item, taken at the agent's warehouse. Write short, careful notes a first-time buyer can use. Rules: only describe " +
  "what is clearly visible in the QC photos; if a detail is too small, blurry or not shown, use status cant_tell; never say the " +
  "item is real, fake, authentic or guaranteed; compare colour and shape with image 1; no brand history, no prices. Reply with " +
  "JSON only: {\"checks\": [{\"area\": \"logo|stitching|colour|shape|materials|hardware|tag|other\", \"status\": \"good|watch|cant_tell\", " +
  "\"note\": \"max 12 words, plain English\"}], \"summary\": \"one short sentence, what to ask the agent for if anything\"}. " +
  "3 to 6 checks. Use watch only for something visible that a buyer should look at more closely.";

async function limited(ip) {
  if (!ip) return false;
  const now = Date.now();
  if (seen.size > 5000) for (const [k, v] of seen) if (now - v.t > WINDOW) seen.delete(k);
  let v = seen.get(ip);
  if (!v || now - v.t > WINDOW) { v = { t: now, n: 0 }; seen.set(ip, v); }
  return ++v.n > LIMIT;
}

function b64(buf) {
  const u = new Uint8Array(buf); let s = "";
  for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
  return btoa(s);
}

// A photo as base64: the site's own copy (img/m, scripts/mirror_photos.py) through ASSETS when there is one, else the
// stored file itself. Never a fetch to our own domain: Cloudflare refuses a Function calling its own site (502).
const SB = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/";
function mirrorOf(u) {
  const m = /^https:\/\/uptpghuduqjqmrxwatbm\.supabase\.co\/storage\/v1\/object\/public\/products\/(pc|pc2|qc)\/([A-Za-z0-9_-]{1,80})\.webp(?:\?v=([A-Za-z0-9_-]{1,20}))?$/.exec(u || "");
  return m ? "/img/m/" + m[1] + "/" + m[2] + (m[3] ? ".v" + m[3] : "") + ".webp" : "";
}
async function photo(env, origin, url) {
  let u = String(url || "");
  const prox = /\/api\/img\?u=([^&]+)/.exec(u); if (prox) { try { u = decodeURIComponent(prox[1]); } catch (e) {} }
  const tries = [];
  const mp = mirrorOf(u); if (mp) tries.push(() => env.ASSETS.fetch(new Request(origin + mp)));
  if (/^\/img\//.test(u)) tries.push(() => env.ASSETS.fetch(new Request(origin + u)));
  if (/^https:\/\//.test(u)) tries.push(() => fetch(u, { cf: { cacheEverything: true, cacheTtl: 2592000 } }));
  for (const t of tries) {
    try {
      const r = await t();
      const ct = (r.headers.get("content-type") || "").split(";")[0];
      if (r.ok && /^image\/(jpeg|png|webp|gif)$/.test(ct)) { const b = await r.arrayBuffer(); if (b.byteLength > 500 && b.byteLength < 4.5e6) return { media_type: ct, data: b64(b) }; }
    } catch (e) {}
  }
  return null;
}
let bank = null, bankAt = 0, stored = null, storedAt = 0;
async function bankThumbs(env, origin, sf, id) {
  if (!bank || Date.now() - bankAt > 600000) {
    try { const r = await env.ASSETS.fetch(new Request(origin + "/data/qc_bank.json")); bank = r.ok ? ((await r.json()).items || {}) : {}; } catch (e) { bank = {}; }
    bankAt = Date.now();
  }
  const e = bank[sf + "/" + id]; const out = [];
  for (let k = 0; e && k < Math.min(MAX_PHOTOS, +e[1] || 0); k++) out.push(SB + "qc/" + sf + "-" + id + "-" + k + ".webp");
  return out;
}

const clean = (s, n) => String(s == null ? "" : s).replace(/[–—]/g, ",").replace(/\s+/g, " ").trim().slice(0, n);

export async function onRequestGet({ request, env }) {
  if (!env || !env.ANTHROPIC_API_KEY) return json(503, { error: "Not available right now." });
  const url = new URL(request.url);
  if (url.searchParams.get("beta") !== "1" && request.headers.get("x-pc-beta") !== "1") return json(404, { error: "not found" });   // beta only (the middleware drops custom headers)
  const sf = url.searchParams.get("storefront") || "", id = url.searchParams.get("id") || "", pid = url.searchParams.get("pid") || "";
  if (!/^(weidian|taobao|1688)$/.test(sf) || !/^[1-9][0-9]{5,19}$/.test(id) || !/^[0-9A-Za-z_-]{1,40}$/.test(pid)) return json(400, { error: "bad request" });
  const p = P.find(x => String(x.id) === pid);
  if (!p) return json(404, { error: "Find not on the sheet." });

  // Kept for good: data/qc_ai.json (scripts/qc_ai.py, daily) answers every find it has done, at no cost per visitor.
  if (!url.searchParams.get("fresh")) {
    try {
      if (!stored || Date.now() - storedAt > 600000) { const r = await env.ASSETS.fetch(new Request(url.origin + "/data/qc_ai.json")); stored = r.ok ? ((await r.json()).items || {}) : {}; storedAt = Date.now(); }
      const s = stored[pid]; if (s && Array.isArray(s.checks)) return json(200, { ...s, stored: true }, "public, max-age=3600");
    } catch (e) {}
  }
  const cache = caches.default, key = new Request("https://qc-check.internal/v1/" + sf + "/" + id);
  const hit = await cache.match(key);
  if (hit && !url.searchParams.get("fresh")) return hit;
  if (await limited(request.headers.get("cf-connecting-ip") || "")) return json(429, { error: "Too many checks. Try again in a few minutes." });

  const thumbs = await bankThumbs(env, url.origin, sf, id);   // only finds whose QC photos are stored (the ones the site shows)
  if (!thumbs.length) return json(404, { error: "No QC photos stored for this find yet." });

  const imgs = (await Promise.all([p.img ? photo(env, url.origin, p.img) : null, ...thumbs.map(t => photo(env, url.origin, t))]));
  const listing = imgs[0], qcs = imgs.slice(1).filter(Boolean);
  if (!qcs.length) return json(503, { error: "Could not load the QC photos." });
  const content = [];
  if (listing) content.push({ type: "image", source: { type: "base64", ...listing } });
  qcs.forEach(x => content.push({ type: "image", source: { type: "base64", ...x } }));
  content.push({ type: "text", text: (listing ? "" : "There is no listing photo; image 1 is a QC photo too. ") + PROMPT(clean(p.title, 120)) });

  let v = null, raw = ""; const model = env.QC_CHECK_MODEL || DEFAULT_MODEL;
  try {
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 45000);
    const r = await fetch(API, { method: "POST", signal: ctl.signal,
      headers: { "x-api-key": env.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({ model, max_tokens: 1200, messages: [{ role: "user", content }] }) });
    clearTimeout(timer);
    if (!r.ok) { let why = ""; try { why = ((await r.json()).error || {}).message || ""; } catch (e) {} return json(503, { error: "The check is busy. Try again in a moment.", status: r.status, why: String(why).slice(0, 160) }); }
    const out = await r.json();
    const text = ((out.content || []).find(c => c.type === "text") || {}).text || "";
    raw = text.slice(0, 300) + " | stop:" + (out.stop_reason || "");
    const m = /\{[\s\S]*\}/.exec(text); try { v = m ? JSON.parse(m[0]) : null; } catch (e) { v = null; }
  } catch (e) { return json(503, { error: "The check is busy. Try again in a moment.", why: String(e && e.message || e).slice(0, 160) }); }
  if (!v || !Array.isArray(v.checks)) return json(503, { error: "The check gave no answer. Try again.", why: raw });

  const AREAS = new Set(["logo", "stitching", "colour", "shape", "materials", "hardware", "tag", "other"]);
  const checks = v.checks.slice(0, 6).map(c => ({
    area: AREAS.has(c && c.area) ? c.area : "other",
    status: ["good", "watch", "cant_tell"].includes(c && c.status) ? c.status : "cant_tell",
    note: clean(c && c.note, 90) })).filter(c => c.note && !/\b(authentic|genuine|fake|legit|guarantee)/i.test(c.note));
  const res = json(200, { checks, summary: clean(v.summary, 160), n: qcs.length, listing: !!listing, model, at: new Date().toISOString().slice(0, 10) }, "public, max-age=" + TTL);
  try { await cache.put(key, res.clone()); } catch (e) {}
  return res;
}

export async function onRequest() { return json(405, { error: "GET only" }); }
