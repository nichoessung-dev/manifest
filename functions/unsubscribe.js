// Cloudflare Pages Function: unsubscribe.  Deployed at repo path functions/unsubscribe.js -> /unsubscribe?u=<profile id>&t=<token>
// Env vars (set in Cloudflare Pages > Settings > Environment variables): SUPABASE_SERVICE_KEY, UNSUB_SECRET
// Email v2 (26 Nov 2026). There is no email settings page (owner, 26 Nov 2026), so this is the one email page members see.
//   POST  one-click (RFC 8058: Gmail, Apple and Yahoo POST "List-Unsubscribe=One-Click" to the List-Unsubscribe URL):
//         unsubscribes at once and answers plain text. unsub_source "header".
//   POST  with via=page (the button on the page below): unsubscribes and shows the result. unsub_source "link".
//   POST  with via=undo (the button on the result page): marketing email on again, only on the member's own press, and
//         kept as an email_events row (type resubscribe). An address on the suppression list stays off.
//   GET   never changes anything (mail scanners and link previews open every link in an email): a small page with an
//         "Unsubscribe" button, or the result page (with its undo button) when they already unsubscribed.
//   HEAD  answers 200 without doing anything (link scanners).
// Status: 200 done, 400 a bad or incomplete link, 500 our side failed (missing settings or Supabase), so the daily health
// check (scripts/health_check.py POSTs a deliberately bad token and expects no redirect and no 5xx) stays green.
// Each unsubscribe also writes an email_events row (type unsubscribe) after the answer: see unsubscribeMember().
import { checkToken, readProfile, unsubscribeMember, sb, logEvent, later, emailPage, maskEmail, linkFor, msg, back, esc, DISCORD } from "./_lib/email.js";

const STATUS = { ok: 200, invalid: 400, error: 500 };
const SUPPRESSED = `Our emails to this address bounced or were reported as spam, so we stopped sending to it and can't turn them back on here. Message us on ${DISCORD} and we will look at it.`;

const invalidPage = () => emailPage({ path: "/unsubscribe", status: 400, title: "Link expired or invalid", body:
  `<h1>Link expired or invalid</h1><p>We couldn't read that unsubscribe link. Message us on ${DISCORD} and we will take you off the list by hand.</p>${back}` });
const errorPage = (undo = false) => emailPage({ path: "/unsubscribe", status: 500, title: "Something went wrong", body:
  `<h1>Something went wrong</h1><p>That didn't work on our side, and ${undo ? "your emails are still off" : "you are not unsubscribed yet"}. Try again in a few minutes, or message us on ${DISCORD} and we will ${undo ? "turn them back on" : "take you off the list"} by hand.</p>${back}` });
const who = email => email ? `<p class="sub">For <b>${esc(email)}</b></p>` : "";

function donePage(uid, token, email, note = "") {
  return emailPage({ path: "/unsubscribe", title: "You're unsubscribed", body:
    `<h1>You're unsubscribed</h1>${who(email)}${note}<div class="em-card"><p>You won't get our weekly picks, saved-find alerts or other emails any more.</p>` +
    `<form method="post" action="${esc(linkFor("/unsubscribe", uid, token))}"><input type="hidden" name="via" value="undo">` +
    `<p class="em-fine">Unsubscribed by mistake?</p><div class="em-act" style="margin-top:12px"><button class="btn" type="submit">Turn emails back on</button></div></form>` +
    `</div>${back}` });
}

const onPage = email => emailPage({ path: "/unsubscribe", title: "Emails are back on", body:
  `<h1>Emails are back on</h1>${who(email)}<div class="em-card"><p>You'll get our weekly picks and saved-find alerts again. Every email has an unsubscribe link at the bottom.</p></div>${back}` });

function askPage(uid, token, email) {
  return emailPage({ path: "/unsubscribe", title: "Unsubscribe", body:
    `<h1>Unsubscribe from our emails?</h1>${email ? who(email) : `<p class="sub">From Puro Classico emails</p>`}<div class="em-card">` +
    `<p>You will stop getting our weekly picks, saved-find alerts and other emails.</p>` +
    `<form method="post" action="${esc(linkFor("/unsubscribe", uid, token))}"><input type="hidden" name="via" value="page">` +
    `<div class="em-act"><button class="btn primary" type="submit">Unsubscribe</button></div></form>` +
    `</div>${back}` });
}

export async function onRequestGet(context) {
  const u = new URL(context.request.url), uid = u.searchParams.get("u"), token = u.searchParams.get("t");
  const v = await checkToken(context.env, uid, token);
  if (v !== "ok") return v === "invalid" ? invalidPage() : errorPage();
  // Nothing changes here. The profile is read only to say which address this is and whether it is already unsubscribed;
  // if that read fails, the button still works.
  const p = await readProfile(context.env, uid);
  const row = p.ok && p.row, email = row ? maskEmail(row.email) : "";
  if (row && row.marketing_opt_in === false && row.unsubscribed_at) return donePage(uid, token, email);
  return askPage(uid, token, email);
}

// "Turn emails back on": the member's own press on the result page. Clears the unsubscribe record, so a later
// unsubscribe is recorded again.
async function undo(context, uid, token) {
  const env = context.env;
  const v = await checkToken(env, uid, token);
  if (v !== "ok") return v === "invalid" ? invalidPage() : errorPage(true);
  const p = await readProfile(env, uid);
  if (!p.ok) return errorPage(true);
  if (!p.row) return invalidPage();
  const email = maskEmail(p.row.email);
  if (p.row.suppressed) return donePage(uid, token, email, msg(SUPPRESSED, true));
  if (p.row.marketing_opt_in !== true) {
    const path = `profiles?id=eq.${encodeURIComponent(uid)}`;
    let r = await sb(env, path, { method: "PATCH", body: { marketing_opt_in: true, unsubscribed_at: null, unsub_source: null }, prefer: "return=minimal" });
    if (r.status === 400) r = await sb(env, path, { method: "PATCH", body: { marketing_opt_in: true }, prefer: "return=minimal" });   // before scripts/email_v2.sql
    if (!r.ok) return errorPage(true);
    later(context, logEvent(env, { member_id: uid, type: "resubscribe", meta: { source: "unsubscribe-page" } }));
  }
  return onPage(email);
}

// RFC 8058 one-click, the page's button (via=page) and its undo (via=undo)
export async function onRequestPost(context) {
  const u = new URL(context.request.url), uid = u.searchParams.get("u"), token = u.searchParams.get("t");
  let via = u.searchParams.get("via") || "";
  try { const f = await context.request.formData(); via = String(f.get("via") || via); } catch (e) {}   // the one-click body is "List-Unsubscribe=One-Click"
  try {
    if (via === "undo") return await undo(context, uid, token);
  } catch (e) { return errorPage(true); }
  const page = via === "page";
  let r = await checkToken(context.env, uid, token);
  if (r === "ok") r = await unsubscribeMember(context, uid, page ? "link" : "header");
  if (page) {
    if (r === "invalid") return invalidPage();
    if (r === "error") return errorPage();
    const p = await readProfile(context.env, uid);
    return donePage(uid, token, p.ok && p.row ? maskEmail(p.row.email) : "");
  }
  return new Response(r === "ok" ? "OK" : r === "invalid" ? "Invalid unsubscribe link" : "Unsubscribe failed", { status: STATUS[r], headers: { "cache-control": "no-store" } });
}

// HEAD (link scanners/prefetchers): answer without unsubscribing anyone.
export async function onRequestHead() {
  return new Response(null, { status: 200, headers: { "content-type": "text/html; charset=utf-8" } });
}
