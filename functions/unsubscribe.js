// Cloudflare Pages Function: unsubscribe.  Deployed at repo path functions/unsubscribe.js -> /unsubscribe?u=<profile id>&t=<token>
// Env vars (set in Cloudflare Pages > Settings > Environment variables): SUPABASE_SERVICE_KEY, UNSUB_SECRET
// Email v2 (26 Nov 2026):
//   POST  one-click (RFC 8058: Gmail, Apple and Yahoo POST "List-Unsubscribe=One-Click" to the List-Unsubscribe URL):
//         unsubscribes at once and answers plain text. unsub_source "header".
//   POST  with via=page (the button on the page below): unsubscribes and shows the result. unsub_source "link".
//   GET   never unsubscribes (mail scanners and link previews open every link in an email): a small page with an
//         "Unsubscribe" button and a link to the email settings.
//   HEAD  answers 200 without doing anything (link scanners).
// Status: 200 done, 400 a bad or incomplete link, 500 our side failed (missing settings or Supabase), so the daily health
// check (scripts/health_check.py POSTs a deliberately bad token and expects no redirect and no 5xx) stays green.
// Each unsubscribe also writes an email_events row (type unsubscribe) after the answer: see unsubscribeMember().
import { checkToken, readProfile, unsubscribeMember, emailPage, maskEmail, linkFor, msg, back, esc, DISCORD } from "./_lib/email.js";

const STATUS = { ok: 200, invalid: 400, error: 500 };

const invalidPage = () => emailPage({ path: "/unsubscribe", status: 400, title: "Link expired or invalid", body:
  `<h1>Link expired or invalid</h1><p>We couldn't read that unsubscribe link. Message us on ${DISCORD} and we will take you off the list by hand.</p>${back}` });
const errorPage = () => emailPage({ path: "/unsubscribe", status: 500, title: "Something went wrong", body:
  `<h1>Something went wrong</h1><p>That didn't work on our side, and you are not unsubscribed yet. Try again in a few minutes, or message us on ${DISCORD} and we will take you off the list by hand.</p>${back}` });

function donePage(uid, token, email) {
  const who = email ? `<p class="sub">For <b>${esc(email)}</b></p>` : "";
  return emailPage({ path: "/unsubscribe", title: "You're unsubscribed", body:
    `<h1>You're unsubscribed</h1>${who}<div class="em-card"><p>You won't get our weekly picks, saved-find alerts or other emails any more.</p>` +
    `<p>Changed your mind? You can turn them back on in <a href="${esc(linkFor("/email-settings", uid, token))}">email settings</a>.</p></div>${back}` });
}

function askPage(uid, token, email) {
  const who = email ? `<p class="sub">For <b>${esc(email)}</b></p>` : `<p class="sub">From Puro Classico emails</p>`;
  const settings = esc(linkFor("/email-settings", uid, token));
  return emailPage({ path: "/unsubscribe", title: "Unsubscribe", body:
    `<h1>Unsubscribe from our emails?</h1>${who}<div class="em-card">` +
    `<p>You will stop getting our weekly picks, saved-find alerts and other emails.</p>` +
    `<form method="post" action="${esc(linkFor("/unsubscribe", uid, token))}"><input type="hidden" name="via" value="page">` +
    `<div class="em-act"><button class="btn primary" type="submit">Unsubscribe</button></div></form>` +
    `<p class="em-fine">Want fewer emails instead? In <a href="${settings}">email settings</a> you can get only saved-find alerts or pause them for 30 days.</p>` +
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

// RFC 8058 one-click, and the page's button (via=page)
export async function onRequestPost(context) {
  const u = new URL(context.request.url), uid = u.searchParams.get("u"), token = u.searchParams.get("t");
  let via = u.searchParams.get("via") || "";
  try { const f = await context.request.formData(); via = String(f.get("via") || via); } catch (e) {}   // the one-click body is "List-Unsubscribe=One-Click"
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
