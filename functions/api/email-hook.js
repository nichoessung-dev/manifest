// Plunk webhooks (Email v2, 26 Nov 2026): POST /api/email-hook, bounces, spam complaints and deliveries into Supabase.
// Plunk has no project webhooks: each event is its own Plunk workflow (trigger email.bounce, email.complaint or
// email.delivery, "allow re-entry" on), whose Webhook step POSTs here. The step sends a shared secret (Plunk does not sign
// requests) as "Authorization: Bearer <EMAIL_HOOK_SECRET>", an "X-Hook-Secret" header, or ?k=<secret>.
// Body: the custom JSON set on the step (BODY below; Plunk fills in every {{...}} as a string), or Plunk's default body
// ({ contact: { email }, workflow, execution, event: {...} }) as a fallback. The event type comes from the body's "type",
// else ?type=, else the workflow name or the fields the event carries.
// Plunk waits at most 10 s, never retries and can send the same event twice or out of order, so this answers 200 at once
// and writes after the answer (waitUntil), each event once (email_events.dedupe = type and Plunk's emailId):
//   every event      email_events row: send_id = the email_sends row whose provider_id is the event's emailId (or messageId)
//   hard bounce      email_suppression (reason hard_bounce): the engine never mails the address again
//   spam complaint   email_suppression (reason complaint), and profiles.marketing_opt_in false, unsubscribed_at, unsub_source "complaint"
//   provider block   (suppressedByProvider: the address is on Amazon SES's list, the email was not sent) suppressed as well,
//                    but the member's consent is left alone: the block may come from another sender's complaint
// Soft bounces (mailbox full, out of office) and deliveries are only recorded.
// The recipient's address is used for the suppression list and to find the member; the event row keeps only its mailbox
// group (meta.mbox: gmail, outlook, yahoo, icloud or other), so /stats can show delivery and complaints per mailbox provider.
// Env (Cloudflare Pages): EMAIL_HOOK_SECRET, SUPABASE_SERVICE_KEY. Tables: scripts/email_v2.sql.
//
// BODY to paste into each workflow's Webhook step (one type per workflow; values are Plunk variables):
//   email.bounce    {"type":"email.bounce","email":"{{email}}","emailId":"{{event.emailId}}","messageId":"{{event.messageId}}","bounceType":"{{event.bounceType}}","bounceSubType":"{{event.bounceSubType}}","suppressed":"{{event.suppressedByProvider}}","diagnosticCode":"{{event.diagnosticCode}}","at":"{{event.bouncedAt}}"}
//   email.complaint {"type":"email.complaint","email":"{{email}}","emailId":"{{event.emailId}}","messageId":"{{event.messageId}}","feedbackType":"{{event.complaintFeedbackType}}","suppressed":"{{event.suppressedByProvider}}","at":"{{event.complainedAt}}"}
//   email.delivery  {"type":"email.delivery","email":"{{email}}","emailId":"{{event.emailId}}","messageId":"{{event.messageId}}","at":"{{event.deliveredAt}}"}
import { sb, mailbox } from "../_lib/email.js";

const MAX_BODY = 65536;
const TYPES = { "email.bounce": "bounce", bounce: "bounce", "email.complaint": "complaint", complaint: "complaint",
  "email.delivery": "delivered", delivery: "delivered", delivered: "delivered", "email.sent": "sent", sent: "sent",
  "email.open": "open", "email.click": "click" };
const KEEP = new Set(["bounce", "complaint", "delivered"]);   // what is stored; anything else is answered and ignored
const ID = /^[A-Za-z0-9._@+=:-]{1,128}$/;
const EMAIL = /^[^\s@"<>(),;:\\]{1,64}@[^\s@"<>(),;:\\]{1,253}\.[^\s@"<>(),;:\\]{1,63}$/;

const json = (o, status = 200, extra = {}) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...extra } });

// A value Plunk could not fill in arrives as "", "undefined", "null" or the placeholder itself.
const val = v => v == null || typeof v === "object" ? "" : (s => /^(undefined|null)$/i.test(s) || s.includes("{{") ? "" : s)(String(v).trim());
const yes = v => v === true || /^(true|1|yes)$/i.test(val(v));
const iso = v => { const s = val(v); const t = Date.parse(s); return s && !isNaN(t) ? new Date(t).toISOString() : null; };

// Shared-secret check that takes the same time whatever the guess: both sides are hashed to 32 bytes first.
async function secretOk(given, secret) {
  if (!given || !secret) return false;
  const h = async s => new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(s))));
  const [a, b] = await Promise.all([h(given), h(secret)]);
  let d = 0; for (let i = 0; i < a.length; i++) d |= a[i] ^ b[i];
  return d === 0;
}
function givenSecret(request, url) {
  const auth = request.headers.get("authorization") || "";
  const m = /^Bearer\s+(.+)$/i.exec(auth.trim());
  return (m && m[1].trim()) || (request.headers.get("x-hook-secret") || "").trim() || url.searchParams.get("k") || "";
}

// One event in a fixed shape, from the custom body or Plunk's default one. null when the body is not an object.
export function normalize(body, qType = "") {
  if (typeof body === "string") { try { body = JSON.parse(body); } catch (e) { return null; } }   // a body sent as a JSON string
  if (!body || typeof body !== "object" || Array.isArray(body)) return null;
  const ev = body.event && typeof body.event === "object" && !Array.isArray(body.event) ? body.event : {};
  const f = { ...ev, ...body };
  const wf = val(body.workflow && body.workflow.name).toLowerCase();
  let type = TYPES[val(f.type).toLowerCase()] || TYPES[val(qType).toLowerCase()] || null;
  if (!type && wf) type = /complain|spam/.test(wf) ? "complaint" : /bounce/.test(wf) ? "bounce" : /deliver/.test(wf) ? "delivered" : null;
  if (!type) type = "bounceType" in f || "transientBounce" in f || "bouncedAt" in f || "bounceSubType" in f ? "bounce"
    : "complainedAt" in f || "complaintFeedbackType" in f || "complaintSubType" in f || "feedbackType" in f ? "complaint"
    : "deliveredAt" in f ? "delivered" : "sentAt" in f ? "sent" : null;
  const emailId = ID.test(val(f.emailId)) ? val(f.emailId) : "", messageId = ID.test(val(f.messageId)) ? val(f.messageId) : "";
  let email = val(f.email) || val(body.contact && body.contact.email);
  email = EMAIL.test(email) && email.length <= 254 ? email.toLowerCase() : "";
  const sub = val(f.bounceSubType || f.complaintSubType).replace(/[^A-Za-z]/g, "").slice(0, 40);
  const suppressed = yes(f.suppressed) || yes(f.suppressedByProvider) || sub === "OnAccountSuppressionList";
  const bt = val(f.bounceType).toLowerCase();
  // Permanent is a hard bounce; Transient a soft one; anything else (Undetermined, missing) is treated as hard, as Plunk does.
  const kind = suppressed ? "suppressed" : type === "bounce" ? (bt === "transient" || yes(f.transientBounce) ? "soft" : "hard") : null;
  // The SMTP reply's codes only ("550 5.1.1"), not its text, which often repeats the address.
  const diag = val(f.diagnosticCode), code = [(/\b[245]\d\d\b/.exec(diag) || [])[0], (/\b[245]\.\d{1,3}\.\d{1,3}\b/.exec(diag) || [])[0]].filter(Boolean).join(" ");
  const feedback = val(f.feedbackType || f.complaintFeedbackType).replace(/[^A-Za-z-]/g, "").slice(0, 30);
  const at = iso(f.at) || iso(f.bouncedAt) || iso(f.complainedAt) || iso(f.deliveredAt) || iso(f.sentAt);
  const meta = { src: "plunk" };
  if (email) meta.mbox = mailbox(email);
  if (kind) meta.kind = kind;
  if (sub) meta.subtype = sub;
  if (code) meta.code = code;
  if (feedback) meta.feedback = feedback;
  if (at) meta.at = at;
  const ref = emailId || messageId;
  const dedupe = type && ref ? `plunk:${type}${kind ? "-" + kind : ""}:${ref}` : null;
  return { type, kind, email, emailId, messageId, meta, dedupe };
}

const one = async r => { try { const a = await r.json(); return Array.isArray(a) ? a[0] || null : null; } catch (e) { return null; } };

// The writes for one event, after the answer. Returns what it did (for the tests and the logs).
export async function apply(env, ev) {
  const done = { send: null, duplicate: false, stored: false, suppressed: false, optedOut: false };
  const ids = [ev.emailId, ev.messageId].filter(Boolean);
  let send = null;
  if (ids.length) {
    const r = await sb(env, `email_sends?provider_id=in.(${ids.map(i => encodeURIComponent(`"${i}"`)).join(",")})&select=id,member_id,template&limit=1`);
    if (r.ok) send = await one(r);
  }
  done.send = send ? send.id : null;
  const personal = ev.type === "bounce" || ev.type === "complaint";
  let member = send && send.member_id || null, email = ev.email;
  if (personal && !member && email) {
    const r = await sb(env, `profiles?email=eq.${encodeURIComponent(email)}&select=id&limit=1`);
    if (r.ok) member = ((await one(r)) || {}).id || null;
  }
  if (personal && !email && member) {
    const r = await sb(env, `profiles?id=eq.${encodeURIComponent(member)}&select=email`);
    if (r.ok) email = String(((await one(r)) || {}).email || "").toLowerCase();
  }
  const meta = { ...ev.meta };
  if (!meta.mbox && email) meta.mbox = mailbox(email);   // the address came from the profile
  if (!send && ids.length) meta.pid = ids[0];   // no send matched: keep Plunk's id, so the event can still be matched later
  const row = { send_id: send ? send.id : null, member_id: personal ? member : null, type: ev.type, meta, dedupe: ev.dedupe };
  const ins = await sb(env, "email_events?on_conflict=dedupe&select=id", { method: "POST", body: row, prefer: "resolution=ignore-duplicates,return=representation" });
  if (ins.ok) {
    let a = null; try { a = await ins.json(); } catch (e) {}
    if (Array.isArray(a) && a.length === 0) { done.duplicate = true; return done; }   // seen before: everything below already ran
    done.stored = true;
  } else console.error("email-hook: event not stored", ins.status);
  // Never mail this address again: a hard bounce, a block at Amazon SES, or a spam report.
  if (email && (ev.type === "complaint" || (ev.type === "bounce" && ev.kind !== "soft"))) {
    const detail = [ev.kind === "suppressed" ? "provider suppression list" : "", meta.subtype, meta.code, meta.feedback].filter(Boolean).join(" ").slice(0, 200) || null;
    const r = await sb(env, "email_suppression?on_conflict=email", { method: "POST",
      body: { email, reason: ev.type === "complaint" ? "complaint" : "hard_bounce", source: "plunk", detail }, prefer: "resolution=ignore-duplicates,return=minimal" });
    done.suppressed = r.ok;
    if (!r.ok) console.error("email-hook: suppression not stored", r.status);
  }
  // A spam report is an unsubscribe: marketing off, with when and why (not for a provider block, see the top).
  if (ev.type === "complaint" && ev.kind !== "suppressed" && (member || email)) {
    const where = member ? `id=eq.${encodeURIComponent(member)}` : `email=eq.${encodeURIComponent(email)}`;
    let r = await sb(env, `profiles?${where}`, { method: "PATCH", body: { marketing_opt_in: false, unsubscribed_at: new Date().toISOString(), unsub_source: "complaint" }, prefer: "return=minimal" });
    if (r.status === 400) r = await sb(env, `profiles?${where}`, { method: "PATCH", body: { marketing_opt_in: false }, prefer: "return=minimal" });   // email_v2.sql not run yet
    done.optedOut = r.ok;
    if (!r.ok) console.error("email-hook: profile not updated", r.status);
  }
  return done;
}

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== "POST") return json({ error: "POST only" }, 405, { allow: "POST" });
  if (!env.EMAIL_HOOK_SECRET || !env.SUPABASE_SERVICE_KEY) return json({ error: "not configured" }, 503);
  const url = new URL(request.url);
  if (!(await secretOk(givenSecret(request, url), env.EMAIL_HOOK_SECRET))) return json({ error: "unauthorized" }, 401);
  if (Number(request.headers.get("content-length") || 0) > MAX_BODY) return json({ error: "too large" }, 413);
  let text = "";
  try { text = await request.text(); } catch (e) {}
  if (text.length > MAX_BODY) return json({ error: "too large" }, 413);
  let body;
  try { body = JSON.parse(text); } catch (e) { return json({ error: "body is not JSON" }, 400); }
  const ev = normalize(body, url.searchParams.get("type") || "");
  if (!ev) return json({ error: "body is not a JSON object" }, 400);
  if (!KEEP.has(ev.type)) return json({ ok: true, ignored: ev.type || "unknown event" });
  context.waitUntil(apply(env, ev).catch(e => console.error("email-hook:", e && e.message)));
  return json({ ok: true, type: ev.type });
}
