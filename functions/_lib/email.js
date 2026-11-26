// Email v2 (26 Nov 2026): the parts shared by the member-facing email page and the provider webhook.
//   functions/unsubscribe.js       /unsubscribe?u=<profile id>&t=<token>   one-click POST (RFC 8058), the confirm page and its undo
//   functions/api/email-hook.js    /api/email-hook                         Plunk bounces, complaints and deliveries
// No email settings page (owner, 26 Nov 2026): emails carry Unsubscribe only.
// <token> = hex HMAC-SHA256(UNSUB_SECRET, profile id): the token scripts/mailer.py (and the old newsletter.py) put in every
// unsubscribe link. Env (Cloudflare Pages): UNSUB_SECRET, SUPABASE_SERVICE_KEY. Tables: scripts/email_v2.sql.
// The page changes nothing on a GET (mail scanners open every link in an email); only a POST (a button) does.
import { header, THEME_HEAD, PAGE_JS, DS_VER, esc, ic } from "./site.js";

export const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";
export { esc };

export async function hmacHex(secret, msg) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(msg));
  return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, "0")).join("");
}

// Equal-length strings compared without an early exit.
export function sameText(a, b) {
  a = String(a); b = String(b);
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

// "ok", "invalid" (a bad or incomplete link: the visitor's side) or "error" (missing settings: ours). Only "error" may
// answer 5xx, so the daily health check (a deliberately bad token on /unsubscribe) stays green while a real failure shows.
export async function checkToken(env, uid, token) {
  if (!env || !env.UNSUB_SECRET || !env.SUPABASE_SERVICE_KEY) return "error";
  if (!uid || !token || uid.length > 64 || token.length > 128) return "invalid";
  return sameText(String(token).toLowerCase(), await hmacHex(env.UNSUB_SECRET, uid)) ? "ok" : "invalid";
}

export function sb(env, path, { method = "GET", body, prefer } = {}) {
  const headers = { apikey: env.SUPABASE_SERVICE_KEY, Authorization: "Bearer " + env.SUPABASE_SERVICE_KEY };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (prefer) headers.Prefer = prefer;
  return fetch(`${SUPA}/rest/v1/${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
}
const rows = async r => { try { const a = await r.json(); return Array.isArray(a) ? a : []; } catch (e) { return []; } };

// The member's email state. { ok: false } when Supabase did not answer; row is null when the account is gone.
export const PROFILE_COLS = "email,marketing_opt_in,unsubscribed_at";
export async function readProfile(env, uid) {
  try {
    const r = await sb(env, `profiles?id=eq.${encodeURIComponent(uid)}&select=${PROFILE_COLS}`);
    if (!r.ok) return { ok: false };
    const row = (await rows(r))[0] || null;
    if (row && row.email) {   // an address we must not send to any more (hard bounce, spam report): the page says so
      const s = await sb(env, `email_suppression?email=eq.${encodeURIComponent(String(row.email).toLowerCase())}&select=reason`);
      row.suppressed = s.ok ? ((await rows(s))[0] || {}).reason || null : null;
    }
    return { ok: true, row };
  } catch (e) { return { ok: false }; }
}

// Turns marketing email off and records when and how (unsubscribed_at, unsub_source: header | link), once:
// a member who already unsubscribed keeps the first record. The filter lets the update through when they are opted in,
// never chose, or have no unsubscribe on record yet (the app's own toggle can switch opt-in back on without clearing it).
// When the update changed the profile, an email_events row (type unsubscribe) is written after the answer, linked to the
// last email the member got, so unsubscribes count per email on /stats. Returns "ok" or "error".
export async function unsubscribeMember(ctx, uid, source) {
  const env = ctx.env, id = encodeURIComponent(uid);
  try {
    let r = await sb(env, `profiles?id=eq.${id}&or=(marketing_opt_in.is.true,marketing_opt_in.is.null,unsubscribed_at.is.null)&select=id,email`,
      { method: "PATCH", body: { marketing_opt_in: false, unsubscribed_at: new Date().toISOString(), unsub_source: source }, prefer: "return=representation" });
    if (r.status === 400) {
      // scripts/email_v2.sql not run yet (no unsubscribed_at column): the opt-out alone, as before Email v2
      r = await sb(env, `profiles?id=eq.${id}`, { method: "PATCH", body: { marketing_opt_in: false }, prefer: "return=minimal" });
      return r.ok ? "ok" : "error";
    }
    if (!r.ok) return "error";
    const changed = (await rows(r))[0];
    if (changed) later(ctx, logUnsubscribe(env, uid, source, changed.email));
    return "ok";
  } catch (e) { return "error"; }
}

async function logUnsubscribe(env, uid, source, email) {
  let send = null;
  try {
    const r = await sb(env, `email_sends?member_id=eq.${encodeURIComponent(uid)}&status=neq.failed&select=id,template&order=created_at.desc&limit=1`);
    if (r.ok) send = (await rows(r))[0] || null;
  } catch (e) {}
  await logEvent(env, { send_id: send ? send.id : null, member_id: uid, type: "unsubscribe", meta: { source, template: send ? send.template : null, mbox: mailbox(email) } });
}

// The mailbox group of an address (gmail, outlook, yahoo, icloud or other), so /stats can show delivery, bounces, complaints
// and unsubscribes per mailbox provider. Only the group is stored with an event, never the address.
export function mailbox(email) {
  const d = String(email || "").toLowerCase().split("@")[1] || "";
  if (!d) return null;
  if (/^(gmail|googlemail)\.com$/.test(d)) return "gmail";
  if (/^(outlook|hotmail|live|msn|passport)\.[a-z.]{2,12}$/.test(d)) return "outlook";
  if (/^(yahoo|ymail|rocketmail|aol)\.[a-z.]{2,12}$/.test(d)) return "yahoo";
  if (/^(icloud|me|mac)\.com$/.test(d)) return "icloud";
  return "other";
}

export async function logEvent(env, row) {
  try { await sb(env, "email_events", { method: "POST", body: row, prefer: "return=minimal" }); } catch (e) {}
}

// Work that must not hold up the answer (the database write behind an unsubscribe, a webhook's writes).
export function later(ctx, p) {
  const job = Promise.resolve(p).catch(() => {});
  if (ctx && typeof ctx.waitUntil === "function") ctx.waitUntil(job);
  return job;
}

export function maskEmail(e) {
  const m = /^([^@\s]+)@([^@\s]+)$/.exec(String(e || ""));
  if (!m) return "";
  return (m[1].length <= 2 ? m[1].slice(0, 1) : m[1].slice(0, 2)) + "•••@" + m[2];
}

export const linkFor = (path, uid, token) => `${path}?u=${encodeURIComponent(uid)}&t=${encodeURIComponent(token)}`;
export const DISCORD = '<a href="/discord">our Discord</a>';

// ------------------------------------------------------------------ page shell
// The site's header and the legal pages' slim footer around one narrow column, in the ds.css look (light and dark).
// No search script, chat or visit timer: these pages carry a personal token in the address, which must not travel
// anywhere (no-referrer as well). Never cached, never indexed.
const CSS = `
main.em{max-width:600px;margin:0 auto;padding:40px 16px 88px}
@media(min-width:641px){main.em{padding:64px 32px 112px}}
main.em h1{font-size:clamp(30px,7vw,44px);line-height:1.08;letter-spacing:-.035em;font-weight:650;margin:0 0 10px;text-wrap:balance}
main.em h2{font-size:18px;line-height:1.3;letter-spacing:-.01em;font-weight:600;margin:0 0 6px}
main.em p{color:var(--ink-2);font-size:15.5px;line-height:1.6;margin:0 0 14px;text-wrap:pretty}
main.em a{color:var(--ink);text-underline-offset:3px;text-decoration-color:color-mix(in srgb,var(--ink) 35%,transparent)}
main.em .sub{color:var(--muted);font-size:15px;margin:0 0 28px}
main.em .sub b{color:var(--ink);font-weight:600}
.em-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);padding:20px;box-shadow:var(--sh-sm)}
@media(min-width:641px){.em-card{padding:24px}}
.em-card p:last-child{margin-bottom:0}
.em-act{display:flex;flex-wrap:wrap;align-items:center;gap:12px 20px;margin-top:20px}
main.em .btn{min-height:44px;padding:0 24px;font-size:15px}
main.em .btn.primary{flex:none;width:auto}
@media(max-width:480px){main.em .em-act .btn.primary{flex:1 1 100%}}
.em-msg{display:flex;gap:10px;align-items:flex-start;margin:0 0 20px;padding:14px 16px;border-radius:var(--r-lg);background:var(--surface-2);color:var(--ink);font-size:15px;line-height:1.5}
.em-msg .ic{flex:none;width:18px;height:18px;margin-top:2px}
.em-msg.err{background:transparent;border:1px solid var(--ink)}
main.em .em-fine{margin:20px 0 0;font-size:13.5px;line-height:1.55;color:var(--muted)}
.em-fine a{color:var(--muted)!important}
.em-back{display:inline-flex;align-items:center;min-height:44px;font-size:14px;font-weight:500;color:var(--muted)!important;text-decoration:none}
@media(hover:hover){.em-back:hover{color:var(--ink)!important}}
`;

const FOOT = `<footer class="f"><div class="w"><div class="fbar"><a class="logo" href="/" aria-label="Puro Classico home"></a>` +
  `<nav class="flinks" aria-label="Puro Classico"><a href="/discord">${ic("message", "sm")}Discord</a><a href="/about">About</a>` +
  `<a href="/terms">Terms</a><a href="/privacy">Privacy</a></nav></div><p class="legal">© Puro Classico</p></div></footer>`;

export function emailPage({ title, body, path = "/unsubscribe", status = 200 }) {
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>${esc(title)} | Puro Classico</title>
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
<meta name="theme-color" content="#FFFFFF"><link rel="icon" type="image/png" href="/favicon.png?v=4">
${THEME_HEAD}
<link rel="preload" href="/fonts/inter-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/ds.css?v=${DS_VER}">
<style>${CSS}</style>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
${header(path)}
<main class="em" id="main">
${body}
</main>
${FOOT}
${PAGE_JS}
</body>
</html>`;
  return new Response(html, { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-robots-tag": "noindex" } });
}

export const msg = (text, err = false) => `<p class="em-msg${err ? " err" : ""}" role="${err ? "alert" : "status"}">${ic(err ? "alert" : "check")}<span>${text}</span></p>`;
export const back = `<a class="em-back" href="/">Back to Puro Classico</a>`;
