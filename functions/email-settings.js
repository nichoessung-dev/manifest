// Email settings (Email v2, 26 Nov 2026): /email-settings?u=<profile id>&t=<token>, linked from the footer of every email
// (the same token as the unsubscribe link: hex HMAC-SHA256(UNSUB_SECRET, profile id)). Phone first, light and dark, noindex.
//   GET   shows the member's choices and changes nothing (mail scanners open every link), with two extras:
//         &pick=weekly|alerts|pause|stop preselects an option, for buttons in an email (win-back: weekly, alerts only, stop);
//         &track=off is the footer's one-tap "stop measuring my clicks": it turns email_track off at once, with no form
//         (CNIL and Garante: withdrawing must take one tap), the only GET that changes anything, because it only ever
//         reduces tracking. A request that names itself a crawler or a prefetch does not count as that tap.
//   POST  saves the form: choice=weekly | alerts | pause | stop | on, and the two consent switches (track, personal).
//         weekly  profiles.email_freq "weekly": weekly picks and saved-find alerts
//         alerts  profiles.email_freq "alerts": only saved-find alerts
//         pause   profiles.email_paused_until = now + 30 days (the frequency stays for when the pause ends)
//         stop    marketing_opt_in false, unsubscribed_at, unsub_source "settings" (and an unsubscribe event)
//         on      marketing_opt_in true again: only on the member's own button press, shown when they are unsubscribed
//         track     profiles.email_track: "Measure my email clicks" (links with the member's own id; scripts/mailer.py)
//         personal  profiles.email_personal: "Personalise my emails from finds I view"
//         Both switches are off unless the member turns them on (no answer means no). Every change of either is added to
//         profiles.email_consents as { what, value, at, text_version, via } (via "settings", or "footer" for track=off).
// Picking weekly, alerts or on also ends a pause and the inactivity stop (email_sunset_at): the member just asked for email.
// Env: UNSUB_SECRET, SUPABASE_SERVICE_KEY. Columns: scripts/email_v2.sql.
import { checkToken, readProfile, unsubscribeMember, sb, logEvent, later, notPerson, emailPage, maskEmail, dayText, linkFor, msg, back, esc, DISCORD, PROFILE_COLS } from "./_lib/email.js";

const PAUSE_DAYS = 30;
// The wording of the two switches. Change TEXT_VERSION whenever their words change: each yes and no is stored with it.
export const TEXT_VERSION = "2026-11-26";
export const SWITCHES = [
  ["personal", "email_personal", "Personalise my emails from finds I view",
    "Weekly picks also use the finds you open on the site. Off: picks use only your saved finds and the style and size you chose."],
  ["track", "email_track", "Measure my email clicks",
    "We see which links you click in our emails, linked to your account, so we can send fewer and better emails. Kept 13 months. Off: clicks are only counted per email, not per person."],
];
const OPTIONS = [
  ["weekly", "Weekly picks and saved-find alerts", () => "One email a week with finds picked for you, and an alert when a find you saved changes."],
  ["alerts", "Only saved-find alerts", () => "Only when a find you saved drops in price, is back in stock or gets new QC photos."],
  ["pause", "Pause for 30 days", p => paused(p) ? `Paused until ${dayText(p.email_paused_until)}. After that your emails start again.`
    : `No emails until ${dayText(Date.now() + PAUSE_DAYS * 864e5)}. After that they start again.`],
  ["stop", "Unsubscribe from everything", () => "No more emails from us."],
];
const DONE = {
  weekly: "Saved. You'll get weekly picks and saved-find alerts.",
  alerts: "Saved. You'll only get saved-find alerts.",
  pause: p => `Saved. No emails until ${dayText(p.email_paused_until)}.`,
  stop: "You're unsubscribed. You won't get our emails any more.",
  on: "Emails are back on. Pick how many you want below.",
  same: "Saved.",
};
const TRACK_OFF = "Done. We no longer measure which links you click. You still get your emails.";
const SUPPRESSED = {
  complaint: `One of our emails to this address was marked as spam, so we stopped sending to it. To get emails again, tell us on ${DISCORD}.`,
  manual: `We stopped sending to this address. To get emails again, tell us on ${DISCORD}.`,
  bounce: `Our emails to this address bounced, so we stopped sending to it. If it works again, tell us on ${DISCORD}.`,
};
const SAVE_ERR = "That didn't save. Try again in a few minutes.";

const paused = p => !!(p && p.email_paused_until && Date.parse(p.email_paused_until) > Date.now());
const current = p => paused(p) ? "pause" : p.email_freq === "alerts" ? "alerts" : "weekly";

const page = (body, status = 200) => emailPage({ title: "Email settings", body, status });
const invalidPage = () => page(`<h1>Link expired or invalid</h1><p>We couldn't open your email settings from that link. Use the link at the bottom of one of our emails, or message us on ${DISCORD} and we will change your settings by hand.</p>${back}`, 400);
const errorPage = () => page(`<h1>Something went wrong</h1><p>We couldn't load your email settings. Try again in a few minutes, or message us on ${DISCORD}.</p>${back}`, 500);
const gonePage = () => page(`<h1>Account not found</h1><p>We couldn't find the account for this link. If you deleted it, you won't get any more emails from us.</p>${back}`, 404);

export function render(uid, token, p, { note = "", pick = "", status = 200 } = {}) {
  const action = esc(linkFor("/email-settings", uid, token)), email = maskEmail(p.email);
  const sup = p.suppressed ? `<p class="em-fine" style="margin:0 0 16px">${SUPPRESSED[p.suppressed] || SUPPRESSED[/bounce/.test(p.suppressed) ? "bounce" : "manual"]}</p>` : "";
  let card;
  if (p.marketing_opt_in !== true) {
    // Unsubscribed, or never asked for marketing email: only the member's own press turns it on.
    card = `<div class="em-card"><h2>Your emails are off</h2>` +
      `<p>You don't get our weekly picks, saved-find alerts or other emails.</p>${sup}` +
      (p.suppressed ? "" : `<form method="post" action="${action}"><input type="hidden" name="choice" value="on">` +
        `<div class="em-act"><button class="btn primary" type="submit">${p.marketing_opt_in === false ? "Turn emails back on" : "Turn emails on"}</button></div></form>`) +
      `</div>`;
  } else {
    const on = OPTIONS.some(o => o[0] === pick) ? pick : current(p);
    const sunset = p.email_sunset_at && !paused(p) ? `<p class="em-fine" style="margin:0 0 16px">We stopped sending because you haven't visited the site for a while. Save a choice to start your emails again.</p>` : "";
    card = `<form class="em-card" method="post" action="${action}">${sup}${sunset}<input type="hidden" name="switches" value="1"><fieldset class="em-opts"><legend>How often</legend>` +
      OPTIONS.map(([v, title, desc]) => `<label class="em-opt${v === "stop" ? " stop" : ""}"><input type="radio" name="choice" value="${v}"${v === on ? " checked" : ""}>` +
        `<span><b>${title}</b><small>${desc(p)}</small></span></label>`).join("") +
      `</fieldset><fieldset class="em-opts" id="choices"><legend>Your choices, off unless you turn them on</legend>` +
      SWITCHES.map(([name, col, title, desc]) => `<label class="em-sw"><span><b>${title}</b><small>${desc}</small></span>` +
        `<input type="checkbox" role="switch" name="${name}" value="1"${p[col] === true ? " checked" : ""}></label>`).join("") +
      `</fieldset><div class="em-act"><button class="btn primary" type="submit">Save</button></div>` +
      `<p class="em-fine">Saved-find alerts are only about finds you saved. Weekly picks use your saved finds and the style and size you chose, and the finds you view only if you turn that on. <a href="/privacy">Privacy</a></p></form>`;
  }
  return page(`<h1>Email settings</h1>` + (email ? `<p class="sub">For <b>${esc(email)}</b></p>` : `<p class="sub">Your Puro Classico emails</p>`) +
    note + card + back, status);
}

// The consent switches that change, as a profile update plus the entries for email_consents (kept to the newest 100).
function consentChange(p, wanted, via) {
  const now = new Date().toISOString(), add = [], body = {};
  for (const [name, col] of SWITCHES) {
    if (!(name in wanted) || (p[col] === true) === wanted[name]) continue;
    body[col] = wanted[name];
    add.push({ what: name, value: wanted[name], at: now, text_version: TEXT_VERSION, via });
  }
  if (add.length) body.email_consents = (Array.isArray(p.email_consents) ? p.email_consents : []).concat(add).slice(-100);
  return body;
}

async function patch(env, uid, body) {
  const r = await sb(env, `profiles?id=eq.${encodeURIComponent(uid)}&select=${PROFILE_COLS}`, { method: "PATCH", body, prefer: "return=representation" });
  if (!r.ok) return null;
  try { return ((await r.json()) || [])[0] || null; } catch (e) { return null; }
}

export async function onRequestGet(context) {
  const u = new URL(context.request.url), uid = u.searchParams.get("u"), token = u.searchParams.get("t");
  const v = await checkToken(context.env, uid, token);
  if (v !== "ok") return v === "invalid" ? invalidPage() : errorPage();
  const p = await readProfile(context.env, uid);
  if (!p.ok) return errorPage();
  if (!p.row) return gonePage();
  let row = p.row, note = "";
  if (u.searchParams.get("track") === "off" && !notPerson(context.request)) {
    const body = consentChange(row, { track: false }, "footer");
    if (Object.keys(body).length) {
      const after = await patch(context.env, uid, body);
      if (!after) return render(uid, token, row, { note: msg(SAVE_ERR, true), status: 500 });
      row = { ...after, suppressed: row.suppressed };
    }
    note = msg(TRACK_OFF);
  }
  return render(uid, token, row, { note, pick: u.searchParams.get("pick") || "" });
}

// The change for each choice. weekly/alerts/pause only apply while the member gets marketing email at all.
function change(choice, p) {
  const now = Date.now();
  if (choice === "weekly" || choice === "alerts") {
    if (choice === current(p) && !p.email_sunset_at) return {};
    return { email_freq: choice, email_paused_until: null, email_sunset_at: null };
  }
  if (choice === "pause") return { email_paused_until: new Date(now + PAUSE_DAYS * 864e5).toISOString() };
  if (choice === "on") return { marketing_opt_in: true, unsubscribed_at: null, unsub_source: null, email_paused_until: null, email_sunset_at: null,
    email_freq: p.email_freq === "alerts" ? "alerts" : "weekly" };
  return {};
}

export async function onRequestPost(context) {
  const { env } = context;
  const u = new URL(context.request.url), uid = u.searchParams.get("u"), token = u.searchParams.get("t");
  const v = await checkToken(env, uid, token);
  if (v !== "ok") return v === "invalid" ? invalidPage() : errorPage();
  let form = null;
  try { form = await context.request.formData(); } catch (e) {}
  const choice = String((form && form.get("choice")) || "");
  const p = await readProfile(env, uid);
  if (!p.ok) return errorPage();
  if (!p.row) return gonePage();
  const row = p.row, opted = row.marketing_opt_in === true;
  if (!["weekly", "alerts", "pause", "stop", "on"].includes(choice)) return render(uid, token, row, { note: msg("Pick one of the options, then save.", true), status: 400 });
  // Nothing to do (already unsubscribed and pressed again, or a stale form): show where things stand.
  if ((choice === "on" && (opted || row.suppressed)) || (choice !== "on" && !opted)) return render(uid, token, row);
  if (choice === "stop") {
    if ((await unsubscribeMember(context, uid, "settings")) !== "ok") return render(uid, token, row, { note: msg(SAVE_ERR, true), status: 500 });
    return render(uid, token, { ...row, marketing_opt_in: false, unsubscribed_at: new Date().toISOString() }, { note: msg(DONE.stop) });
  }
  // The switches are read only from the full form (it carries switches=1), so the "Turn emails back on" button never sets them.
  const wanted = form && form.get("switches") === "1" ? Object.fromEntries(SWITCHES.map(([name]) => [name, form.get(name) === "1"])) : {};
  const body = { ...change(choice, row), ...consentChange(row, wanted, "settings") };
  let after = row;
  if (Object.keys(body).length) {
    after = await patch(env, uid, body);
    if (!after) return render(uid, token, row, { note: msg(SAVE_ERR, true), status: 500 });
    after.suppressed = row.suppressed;
  }
  // Consent to marketing email given again: kept as an event (member, time, where), like the unsubscribes.
  if (choice === "on") later(context, logEvent(env, { member_id: uid, type: "resubscribe", meta: { source: "settings" } }));
  const done = Object.keys(change(choice, row)).length ? DONE[choice] : DONE.same;
  return render(uid, token, after, { note: msg(typeof done === "function" ? done(after) : done) });
}

// HEAD (link scanners): nothing to read, nothing changes.
export async function onRequestHead() {
  return new Response(null, { status: 200, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
}
