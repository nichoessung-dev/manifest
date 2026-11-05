/**
 * Cloudflare Pages Function: one "Report this find" from the product drawer (index.html, reportFind()).
 * Route: POST /api/report  { id: product id, r: dead | wrong | scam | other, k: this browser's random report token }
 *        optional header Authorization: Bearer <the member's Supabase access token>
 *   -> 200 {"ok":true} always (also when the report is dropped, so a spammer learns nothing about the limits).
 * Stores one row in Supabase table product_reports (SQL.md): product, reason, member id (when signed in), when the member
 * account was made and whether its email is confirmed, and three hashes: of the IP, of its /24 network (/48 for IPv6) and of
 * the browser token. No raw IP, no user agent, no free text. Visitors cannot read or write the table (RLS on, no policies);
 * only this function and scripts/bake_reports.py (service key) can.
 * Anti-abuse, here: same-origin POST only, obvious bots dropped, body <= 1 KB, the id must be a real find, a burst limit per
 * IP, one report per find per member / per browser / per IP (anonymous), at most 10 anonymous reports per IP per day, 30 per
 * member per day and 40 per IP per day in all. Whether reports hide a find is decided later, in scripts/bake_reports.py
 * (weights, distinct people and networks, view-scaled threshold), never here.
 * Before the table exists every lookup fails and the report is dropped: the endpoint still answers 200.
 * POST is passed through by _middleware.js (only GET/HEAD are routed), so no PASS entry is needed; GET /api/report is a 404.
 * Env: SUPABASE_SERVICE_KEY (already set). Optional REPORT_SALT: a private salt for the hashes (without it a fixed salt is
 * used, as in functions/api/chat.js; set it once, changing it later resets the per-IP dedupe for 30 days).
 */
import { P } from "../_lib/site.js";

const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";
const REASONS = new Set(["dead", "wrong", "scam", "other"]);
export const LIMITS = { anonPerIpDay: 10, memberPerDay: 30, ipPerDay: 40, burst: 6, burstWindow: 10 * 60 * 1000 };
const DAY = 864e5, WINDOW_DAYS = 30;
// Same people-vs-machines filter as functions/api/search.js and functions/go/[agent].js.
const BOT = new RegExp("(?<!cu)bot|crawl|spider|slurp|preview|fetch|scan|check|monitor|proxy|compatible;|-user/" +
  "|headless|phantomjs|puppeteer|playwright|selenium|lighthouse|facebookexternalhit|meta-external" +
  "|mimecast|proofpoint|barracuda|symantec|sophos|fireeye|trendmicro|zscaler|safelinks|virustotal", "i");
const ORIGIN = /^https:\/\/([a-z0-9-]+\.)*(puroclassico\.com|manifest-bq9\.pages\.dev)$|^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/;
const MAX_BODY = 1024;
const OK = () => new Response('{"ok":true}', { status: 200, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

let _ids = null;
const knownId = id => { if (!_ids) _ids = new Set(P.map(p => String(p.id))); return _ids.has(id); };

// The network an IP belongs to: IPv4 /24 ("1.2.3"), IPv6 /48 (first three groups, written out in full).
export function netPrefix(ip) {
  ip = String(ip || "").trim().toLowerCase();
  const v4 = ip.match(/^(?:::ffff:)?(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.\d{1,3}$/);
  if (v4) return v4.slice(1, 4).join(".");
  if (!ip.includes(":")) return "";
  const [head, tail] = ip.split("::");
  const h = head ? head.split(":") : [], t = tail != null && tail !== "" ? tail.split(":") : [];
  const full = tail == null ? h : h.concat(Array(Math.max(0, 8 - h.length - t.length)).fill("0"), t);
  return full.slice(0, 3).map(x => (x || "0").replace(/^0+(?=.)/, "")).join(":");
}

// The request body, checked: a real-looking id and reason and a 16-64 character token. null = drop.
export function cleanBody(text) {
  let b; try { b = JSON.parse(text || "{}"); } catch (e) { return null; }
  if (!b || typeof b !== "object") return null;
  const id = String(b.id == null ? "" : b.id), r = String(b.r || ""), k = String(b.k || "");
  if (!/^[0-9A-Za-z_-]{1,40}$/.test(id) || !REASONS.has(r)) return null;
  return { id, r, k: /^[A-Za-z0-9_-]{16,64}$/.test(k) ? k : "" };
}

// May this report be stored? `recent` = this member's, browser's or IP's rows from the last 30 days
// ({product_id, user_id, ip_hash, tok_hash, created_at}). Pure, so it can be tested without a network.
export function decide(me, recent, now) {
  if (!me.user_id && !me.tok_hash) return "no-token";                 // anonymous reports need this browser's token
  const day = now - DAY;
  let anonIpDay = 0, ipDay = 0, memberDay = 0;
  for (const x of recent) {
    const t = Date.parse(x.created_at) || 0, sameIp = x.ip_hash === me.ip_hash;
    const mine = me.user_id ? x.user_id === me.user_id : (!x.user_id && (x.tok_hash === me.tok_hash || sameIp));
    if (x.product_id === me.product_id && mine) return "duplicate";   // one report per find per member, or per browser and IP
    if (t < day) continue;
    if (sameIp) { ipDay++; if (!x.user_id) anonIpDay++; }
    if (me.user_id && x.user_id === me.user_id) memberDay++;
  }
  if (ipDay >= LIMITS.ipPerDay) return "ip-day";
  if (me.user_id ? memberDay >= LIMITS.memberPerDay : anonIpDay >= LIMITS.anonPerIpDay) return me.user_id ? "member-day" : "anon-day";
  return "ok";
}

async function hash(salt, s) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(salt + ":" + s));
  return [...new Uint8Array(d)].slice(0, 16).map(b => b.toString(16).padStart(2, "0")).join("");
}

// Burst limit per IP hash, in this isolate's memory only (the daily limits are counted in the table).
const seen = new Map();
function burst(h) {
  const now = Date.now();
  if (seen.size > 5000) for (const [k, v] of seen) if (now - v.t > LIMITS.burstWindow) seen.delete(k);
  const v = seen.get(h);
  if (!v || now - v.t > LIMITS.burstWindow) { seen.set(h, { t: now, n: 1 }); return false; }
  return ++v.n > LIMITS.burst;
}

async function readSmall(request) {
  if ((+request.headers.get("content-length") || 0) > MAX_BODY) return null;
  if (!request.body || !request.body.getReader) { const t = await request.text(); return t.length > MAX_BODY ? null : t; }
  const reader = request.body.getReader(), parts = []; let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY) { try { await reader.cancel(); } catch (e) {} return null; }
    parts.push(value);
  }
  const buf = new Uint8Array(size); let off = 0;
  for (const p of parts) { buf.set(p, off); off += p.byteLength; }
  return new TextDecoder().decode(buf);
}

const timed = (url, init, ms = 4000) => {
  const c = new AbortController(), t = setTimeout(() => c.abort(), ms);
  return fetch(url, { ...init, signal: c.signal }).finally(() => clearTimeout(t));
};

// The signed-in member behind a Supabase access token, checked by Supabase itself. null = anonymous or not valid.
async function member(env, auth) {
  const m = /^Bearer ([A-Za-z0-9._-]{20,4096})$/.exec(auth || "");
  if (!m) return null;
  try {
    const r = await timed(`${SUPA}/auth/v1/user`, { headers: { apikey: env.SUPABASE_SERVICE_KEY, Authorization: "Bearer " + m[1] } });
    if (!r.ok) return null;
    const u = await r.json();
    if (!u || !/^[0-9a-f-]{36}$/.test(u.id || "")) return null;
    return { id: u.id, created_at: u.created_at || null, verified: !!(u.email_confirmed_at || u.confirmed_at || u.phone_confirmed_at) };
  } catch (e) { return null; }
}

async function save(env, me) {
  const H = { apikey: env.SUPABASE_SERVICE_KEY, Authorization: "Bearer " + env.SUPABASE_SERVICE_KEY };
  const since = new Date(Date.now() - WINDOW_DAYS * DAY).toISOString();
  const who = [`ip_hash.eq.${me.ip_hash}`];
  if (me.user_id) who.push(`user_id.eq.${me.user_id}`);
  if (me.tok_hash) who.push(`tok_hash.eq.${me.tok_hash}`);
  const q = `${SUPA}/rest/v1/product_reports?select=product_id,user_id,ip_hash,tok_hash,created_at&or=(${who.join(",")})` +
    `&created_at=gte.${encodeURIComponent(since)}&order=created_at.desc&limit=1000`;
  const r = await timed(q, { headers: H });
  if (!r.ok) return "lookup-" + r.status;                             // 404 until the table exists: drop, answer 200 anyway
  const verdict = decide(me, await r.json(), Date.now());
  if (verdict !== "ok") return verdict;
  const row = { product_id: me.product_id, reason: me.reason, user_id: me.user_id, account_created: me.account_created,
    verified: me.verified, ip_hash: me.ip_hash, net_hash: me.net_hash, tok_hash: me.tok_hash, country: me.country };
  // The unique indexes (SQL.md) catch two reports racing past the lookup; a 409 is simply dropped.
  const w = await timed(`${SUPA}/rest/v1/product_reports`, { method: "POST",
    headers: { ...H, "Content-Type": "application/json", Prefer: "return=minimal" }, body: JSON.stringify(row) });
  return w.ok ? "stored" : "insert-" + w.status;
}

export async function onRequestPost(context) {
  const { request, env } = context;
  try {
    if (!env || !env.SUPABASE_SERVICE_KEY) return OK();
    const ua = request.headers.get("user-agent") || "";
    if (!/^(Mozilla|Opera)\/[0-9.]+ \(/.test(ua) || BOT.test(ua)) return OK();
    const origin = request.headers.get("origin");
    if (!origin || !ORIGIN.test(origin)) return OK();
    const ip = request.headers.get("cf-connecting-ip") || "";
    if (!ip) return OK();
    const salt = "pc-report:" + (env.REPORT_SALT || "v1");
    const ip_hash = await hash(salt, ip);
    if (burst(ip_hash)) return OK();
    const text = await readSmall(request);
    if (text == null) return OK();
    const b = cleanBody(text);
    if (!b || !knownId(b.id)) return OK();
    const u = await member(env, request.headers.get("authorization"));
    const me = {
      product_id: b.id, reason: b.r, user_id: u ? u.id : null, account_created: u ? u.created_at : null, verified: u ? u.verified : false,
      ip_hash, net_hash: await hash(salt + ":net", netPrefix(ip) || ip), tok_hash: b.k ? await hash(salt + ":tok", b.k) : null,
      country: (request.headers.get("cf-ipcountry") || (request.cf && request.cf.country) || "").slice(0, 2) || null,
    };
    context.waitUntil(save(env, me).catch(() => {}));
  } catch (e) {}
  return OK();
}
