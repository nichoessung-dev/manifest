/**
 * Cloudflare Pages Function: search the catalogue with a photo (owner, 8 Nov 2026: "add a reverse image search").
 * Route: POST /api/image-search  {"img": "data:image/jpeg;base64,..."}  (the page shrinks the photo to 768 px first)
 *   -> 200 {"query": "moncler puffer jacket", "label": "Moncler puffer jacket, black", "n": 14}
 * Claude looks at the photo once and names the item (brand only when a logo or signature design is visible); the words
 * are tried against the catalogue the way the site's search box matches (every word at a word start of the title, brand or
 * category), most specific first, dropping colour, model and brand until something matches.
 * The page puts "query" in the search box, so the results are the site's own search results.
 * The photo is not stored or logged. Limits: body <= 600 KB, same-origin only, 10 photos per IP per 10 minutes.
 * Env: ANTHROPIC_API_KEY (already set for the chat), IMAGE_SEARCH_MODEL (optional).
 */
import { P } from "../_lib/site.js";

const API = "https://api.anthropic.com/v1/messages";
const DEFAULT_MODEL = "claude-haiku-5-5";
const MAX_BODY = 600 * 1024;
const LIMIT = 10, WINDOW = 10 * 60 * 1000;
const J = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
const json = (status, body) => new Response(JSON.stringify(body), { status, headers: J });
const seen = new Map();

const PROMPT = "This photo shows a fashion item (clothing, shoes, bag or accessory) someone wants to find. Reply with JSON only: " +
  "{\"item\": \"1 to 3 plain words for the item type, e.g. puffer jacket, sneakers, hoodie, crossbody bag, watch\", " +
  "\"brand\": \"the brand ONLY if its logo, monogram, patch or a signature design is clearly visible, else empty\", " +
  "\"model\": \"a well-known model name only if you are sure (e.g. air jordan 4, dunk low, keepall, datejust), else empty\", " +
  "\"colour\": \"main colour in one word\", \"fashion\": true or false (false when there is no clothing, shoe, bag or accessory)}. " +
  "Never guess a brand from colour or shape alone. Lowercase words, no punctuation.";

async function limited(ip) {
  if (!ip) return false;
  const now = Date.now();
  if (seen.size > 5000) for (const [k, v] of seen) if (now - v.t > WINDOW) seen.delete(k);
  let v = seen.get(ip);
  if (!v || now - v.t > WINDOW) { v = { t: now, n: 0 }; seen.set(ip, v); }
  v.n++;
  let n = v.n;
  try {
    const d = new TextEncoder().encode(ip), h = [...new Uint8Array(await crypto.subtle.digest("SHA-256", d))].slice(0, 8).map(b => b.toString(16).padStart(2, "0")).join("");
    const cache = caches.default, key = new Request("https://img-search-rl.internal/" + h + "/" + Math.floor(now / WINDOW));
    const hit = await cache.match(key);
    const c = (hit ? parseInt(await hit.text(), 10) || 0 : 0) + 1;
    await cache.put(key, new Response(String(c), { headers: { "cache-control": "max-age=" + Math.ceil(WINDOW / 1000) } }));
    n = Math.max(n, c);
  } catch (e) {}
  return n > LIMIT;
}

const fold = s => String(s == null ? "" : s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/['’`]/g, "").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
const STOP = new Set(["the", "a", "an", "and", "of", "with", "for", "mens", "womens"]);
let HAY = null;   // " title brand category " per find, folded, built once per isolate
const hay = () => HAY || (HAY = P.map(p => " " + fold([p.title, p.brand, p.cat].join(" ")) + " "));
const clean = s => String(s == null ? "" : s).toLowerCase().replace(/[^\p{L}\p{N}' -]+/gu, " ").replace(/\s+/g, " ").trim().slice(0, 40);

// The search words, most specific first; the first that finds something wins.
function tries(v) {
  const b = clean(v.brand), m = clean(v.model), it = clean(v.item), c = clean(v.colour);
  const m2 = m.split(" ").length > 2 ? m.split(" ").slice(1).join(" ") : "";   // "air jordan 4" -> "jordan 4" (titles often skip the first word)
  const out = [[b, m, it, c], [b, m, it], [b, m], [m, it], [m], [m2, it], [m2], [b, it, c], [b, it], [it, c], [b], [it]]
    .map(a => a.filter(Boolean).join(" ").trim()).filter(Boolean);
  return [...new Set(out)];
}

export async function onRequestPost({ request, env }) {
  if (!env || !env.ANTHROPIC_API_KEY) return json(503, { error: "Photo search is not available right now." });
  let oh = ""; try { oh = new URL(request.headers.get("origin") || "").host; } catch (e) {}
  if (!oh || oh !== new URL(request.url).host) return json(403, { error: "forbidden" });
  if ((+request.headers.get("content-length") || 0) > MAX_BODY) return json(413, { error: "That photo is too large." });
  if (await limited(request.headers.get("cf-connecting-ip") || "")) return json(429, { error: "Too many photo searches. Try again in a few minutes." });
  let body; try { const t = await request.text(); if (t.length > MAX_BODY) return json(413, { error: "That photo is too large." }); body = JSON.parse(t); } catch (e) { return json(400, { error: "bad request" }); }
  const m = /^data:(image\/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$/.exec(String(body && body.img || ""));
  if (!m) return json(400, { error: "Send a JPEG, PNG or WebP photo." });

  let v = null;
  try {
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 20000);
    const r = await fetch(API, { method: "POST", signal: ctl.signal,
      headers: { "x-api-key": env.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({ model: env.IMAGE_SEARCH_MODEL || DEFAULT_MODEL, max_tokens: 300,
        messages: [{ role: "user", content: [{ type: "image", source: { type: "base64", media_type: m[1], data: m[2] } }, { type: "text", text: PROMPT }] }] }) });
    clearTimeout(timer);
    if (!r.ok) return json(502, { error: "Photo search is busy. Try again in a moment." });
    const d = await r.json();
    const text = ((d.content || []).find(c => c.type === "text") || {}).text || "";
    const j = /\{[\s\S]*\}/.exec(text);
    v = j ? JSON.parse(j[0]) : null;
  } catch (e) { return json(502, { error: "Photo search is busy. Try again in a moment." }); }
  if (!v || v.fashion === false || !clean(v.item)) return json(200, { query: "", label: "", n: 0, none: true });

  let query = "", n = 0;
  for (const q of tries(v)) {
    const words = fold(q).split(" ").filter(w => w && !STOP.has(w));
    if (!words.length) continue;
    const c = hay().reduce((k, h) => k + (words.every(w => h.indexOf(" " + w) >= 0) ? 1 : 0), 0);
    if (c > 0) { query = words.join(" "); n = c; break; }
  }
  const brand = clean(v.brand), item = clean(v.item), colour = clean(v.colour), model = clean(v.model);
  const label = [brand && brand.replace(/\b\w/g, c => c.toUpperCase()), model, item].filter(Boolean).join(" ") + (colour ? ", " + colour : "");
  return json(200, { query, label: label.charAt(0).toUpperCase() + label.slice(1), n });
}

export async function onRequest() { return json(405, { error: "POST a photo" }); }
