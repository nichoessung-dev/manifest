/**
 * Cloudflare Pages Function: one finished site search (sent by /track.js, window.pcSearch).
 * Route: POST /api/search  { q: query, n: results, o: 1 if a find was opened after, k: home | hub | product }  ->  204
 * Stores only the query (lowercased, trimmed, max 80 chars), the result count, opened yes/no and the page kind in
 * Supabase table search_log (OWNER_SQL.sql). No IP address, no user id, no cookie, no user agent, no country.
 * Requests without our Origin header, or with a body over 1 KB, are ignored.
 * Queries that look like an email, a phone or long number, or a link are dropped, here and in the browser.
 * The visitor's IP is used only in this isolate's memory, for a rate limit, and is never written anywhere.
 * POST is passed through by _middleware.js (only GET/HEAD are routed), so no PASS entry is needed; GET /api/search is a 404.
 * Env: SUPABASE_SERVICE_KEY (already set for /api/click). Without the key or before the table exists it still answers 204.
 */
const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";
const KINDS = new Set(["home", "hub", "product"]);
// Same people-vs-machines filter as functions/go/[agent].js.
const BOT = new RegExp("(?<!cu)bot|crawl|spider|slurp|preview|fetch|scan|check|monitor|proxy|compatible;|-user/" +
  "|headless|phantomjs|puppeteer|playwright|selenium|lighthouse|facebookexternalhit|meta-external" +
  "|mimecast|proofpoint|barracuda|symantec|sophos|fireeye|trendmicro|zscaler|safelinks|virustotal", "i");
// Anything that could identify a person or is not a product search: emails, links, 6+ digits in a row, and
// phone-like runs (digits split by spaces, dots, dashes or brackets with 8+ digits in all; "air force 1 07" stays).
const PII = /@|https?:|www\.|\.(com|net|org|cn|io|me|no)\b|\d{6,}/i;
const phoneLike = q => (q.match(/[+(]?\d[\d\s().+-]*\d/g) || []).some(r => r.replace(/\D/g, "").length >= 8);
const ORIGIN = /^https:\/\/([a-z0-9-]+\.)*(puroclassico\.com|manifest-bq9\.pages\.dev)$|^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/;

// Read at most MAX_BODY bytes of the request body; a larger body is ignored (returns null) without reading it all.
const MAX_BODY = 1024;
async function readSmall(request) {
  const len = +request.headers.get("content-length") || 0;
  if (len > MAX_BODY) return null;
  if (!request.body || !request.body.getReader) {                  // runtimes without a stream (tests): text() is still capped below
    const t = await request.text(); return t.length > MAX_BODY ? null : t;
  }
  const reader = request.body.getReader(), parts = []; let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY) { try { await reader.cancel(); } catch (e) {} return null; }   // chunked bodies carry no length
    parts.push(value);
  }
  const buf = new Uint8Array(size); let off = 0;
  for (const p of parts) { buf.set(p, off); off += p.byteLength; }
  return new TextDecoder().decode(buf);
}

// Rate limit: at most LIMIT searches per IP per minute, per isolate (in memory only; resets when the isolate recycles).
const LIMIT = 20, WINDOW = 60000, seen = new Map();
function limited(ip) {
  const now = Date.now();
  if (seen.size > 5000) for (const [k, v] of seen) if (now - v.t > WINDOW) seen.delete(k);
  const v = seen.get(ip);
  if (!v || now - v.t > WINDOW) { seen.set(ip, { t: now, n: 1 }); return false; }
  v.n++;
  return v.n > LIMIT;
}

// Length is counted in characters (code points), as Postgres char_length does, so "😀" is 1 and "über" is 4.
export function cleanQuery(raw) {
  const q = Array.from(String(raw == null ? "" : raw).toLowerCase().replace(/[\u0000-\u001f<>"`\\]/g, " ").replace(/\s+/g, " ").trim()).slice(0, 80).join("").trim();
  if (Array.from(q).length < 2 || PII.test(q) || phoneLike(q)) return "";
  return q;
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const done = new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
  try {
    if (!env || !env.SUPABASE_SERVICE_KEY) return done;
    const ua = request.headers.get("user-agent") || "";
    if (!ua || BOT.test(ua)) return done;
    const origin = request.headers.get("origin");
    if (!origin || !ORIGIN.test(origin)) return done;              // sendBeacon and fetch from our own pages always send our Origin
    const ip = request.headers.get("cf-connecting-ip") || "";
    if (ip && limited(ip)) return done;
    const text = await readSmall(request);
    if (text == null) return done;                                 // over 1 KB: not a search from our pages
    const b = JSON.parse(text || "{}");
    const q = cleanQuery(b.q);
    if (!q) return done;
    const n = Math.max(0, Math.min(100000, parseInt(b.n, 10) || 0));
    const row = { q, results: n, clicked: b.o === 1 || b.o === true || b.o === "1", page: KINDS.has(b.k) ? b.k : "other" };
    context.waitUntil(fetch(`${SUPA}/rest/v1/search_log`, {
      method: "POST",
      headers: { apikey: env.SUPABASE_SERVICE_KEY, Authorization: "Bearer " + env.SUPABASE_SERVICE_KEY, "Content-Type": "application/json", Prefer: "return=minimal" },
      body: JSON.stringify(row),
    }).catch(() => {}));
  } catch (e) {}
  return done;
}
