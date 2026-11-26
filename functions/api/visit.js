/**
 * Cloudflare Pages Function: the running totals of one visit (sent by /track.js, the visit timer, 26 Nov 2026).
 * Route: POST /api/visit  { s: visit id (random UUID from the tab's sessionStorage), a: active seconds, p: pages,
 *   f: finds opened, fs: seconds on finds, fn: finds timed, b: buy clicks, e: first page path, r: 1 returning, src: source }  ->  204
 * Written to Supabase table site_visits through log_visit() (scripts/site_visits.sql), which keeps the larger of the stored
 * and the sent number, so repeated or late beacons never lower a count. No IP address, no user id, no cookie, no user
 * agent and no country are stored. The IP is used only in this isolate's memory, for a rate limit.
 * Requests without our Origin header, from crawlers and headless browsers, or with a body over 1 KB are ignored.
 * POST is passed through by _middleware.js (only GET/HEAD are routed), so no PASS entry is needed.
 * Env: SUPABASE_SERVICE_KEY (already set). Without it, or before the owner has run the SQL, it still answers 204 and
 * nothing is stored.
 */
import { BOT } from "../_lib/views.js";

const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";
const ORIGIN = /^https:\/\/([a-z0-9-]+\.)*(puroclassico\.com|manifest-bq9\.pages\.dev)$|^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const MAX_BODY = 1024;

// At most LIMIT beacons per IP per minute, per isolate (a visit sends a few: on leaving a page, on hiding the tab, and
// every 2 minutes while it is in use). IPv6 is keyed by its /64.
const LIMIT = 40, WINDOW = 60000, seen = new Map();
function limited(ip) {
  if (!ip) return false;
  if (ip.includes(":")) ip = ip.split(":").slice(0, 4).join(":");
  const now = Date.now();
  if (seen.size > 5000) for (const [k, v] of seen) if (now - v.t > WINDOW) seen.delete(k);
  const v = seen.get(ip);
  if (!v || now - v.t > WINDOW) { seen.set(ip, { t: now, n: 1 }); return false; }
  return ++v.n > LIMIT;
}

const int = (v, max) => Math.max(0, Math.min(max, parseInt(v, 10) || 0));

// The beacon body -> the log_visit() arguments, or null when it is not a visit from our pages.
export function visitRow(b) {
  if (!b || typeof b !== "object") return null;
  const sid = String(b.s || "").toLowerCase();
  if (!UUID.test(sid)) return null;
  let entry = String(b.e || "").split(/[?#]/)[0].replace(/[^\w\/\-.~%]/g, "").slice(0, 120);
  if (!entry.startsWith("/")) entry = "";
  return {
    p_sid: sid, p_active: int(b.a, 14400), p_pages: Math.max(1, int(b.p, 500)), p_finds: int(b.f, 500),
    p_find_s: int(b.fs, 14400), p_find_n: int(b.fn, 500), p_buys: int(b.b, 200), p_entry: entry,
    p_returning: b.r === 1 || b.r === true || b.r === "1",
    p_source: String(b.src || "").toLowerCase().replace(/[^a-z0-9_.-]/g, "").slice(0, 23),
  };
}

async function readSmall(request) {
  const len = +request.headers.get("content-length") || 0;
  if (len > MAX_BODY) return null;
  const t = await request.text();
  return t.length > MAX_BODY ? null : t;
}

// phone, tablet or desktop from the user agent (iPads that report a Mac browser count as desktop)
export function deviceOf(ua) {
  if (/iPad|Tablet|PlayBook|Silk|Kindle/i.test(ua) || (/Android/i.test(ua) && !/Mobi/i.test(ua))) return "tablet";
  if (/Mobi|iPhone|iPod|Android|Windows Phone/i.test(ua)) return "phone";
  return "desktop";
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const done = new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
  try {
    if (!env || !env.SUPABASE_SERVICE_KEY) return done;
    const ua = request.headers.get("user-agent") || "";
    if (ua.length < 20 || !/mozilla\/|opera\//i.test(ua) || BOT.test(ua)) return done;
    const origin = request.headers.get("origin");
    if (!origin || !ORIGIN.test(origin)) return done;
    if (limited(request.headers.get("cf-connecting-ip") || "")) return done;
    const text = await readSmall(request);
    if (text == null) return done;
    const row = visitRow(JSON.parse(text || "{}"));
    if (!row) return done;
    // 26 Nov 2026 (owner: "show me the % that is on phone vs on a computer"): the device from the user agent. Until
    // scripts/email_v2.sql section 8 has run, log_visit has no p_device, so a refused call is sent again without it.
    const send = body => fetch(`${SUPA}/rest/v1/rpc/log_visit`, {
      method: "POST",
      headers: { apikey: env.SUPABASE_SERVICE_KEY, Authorization: "Bearer " + env.SUPABASE_SERVICE_KEY, "Content-Type": "application/json", Prefer: "return=minimal" },
      body: JSON.stringify(body),
    });
    const withDevice = { ...row, p_device: deviceOf(ua) };
    context.waitUntil(send(withDevice).then(r => { if (!r.ok && r.status < 500) return send(row); }).then(() => {}, () => {}));
  } catch (e) {}
  return done;
}
