// Tests for the Email v2 website side (no network): functions/api/email-hook.js, functions/unsubscribe.js,
// functions/email-settings.js and the middleware's route list. Supabase is a small in-memory PostgREST.
// Run: node scripts/test_email_web.mjs
import assert from "node:assert/strict";
import fs from "node:fs";
import * as hook from "../functions/api/email-hook.js";
import * as unsub from "../functions/unsubscribe.js";
import * as settings from "../functions/email-settings.js";
import { hmacHex, mailbox } from "../functions/_lib/email.js";

const SECRET = "unsub-test-secret", HOOK = "hook-test-secret-0123456789";
const ENV = { UNSUB_SECRET: SECRET, SUPABASE_SERVICE_KEY: "service-key", EMAIL_HOOK_SECRET: HOOK };
const UID = "11111111-2222-4333-8444-555555555555", UID2 = "66666666-7777-4888-9999-000000000000";
const SEND = "019ac0de-0000-7000-8000-000000000001", SEND_OLD = "019ac0de-0000-7000-8000-000000000000";
const PLUNK_ID = "ac32f08e-c6b9-45d3-9824-a73dff1e3bbf";

// ------------------------------------------------------------------ a tiny PostgREST
const UNIQUE = { email_events: "dedupe", email_suppression: "email", profiles: "id", email_sends: "id" };
function makeDb({ profiles = [], sends = [], missing = [] } = {}) {
  const db = { profiles: structuredClone(profiles), email_sends: structuredClone(sends), email_events: [], email_suppression: [], calls: [], down: false, missing: new Set(missing) };
  const cond = (r, col, expr) => {
    const neg = expr.startsWith("not."); if (neg) expr = expr.slice(4);
    const dot = expr.indexOf("."), op = expr.slice(0, dot), v = expr.slice(dot + 1), x = r[col];
    let ok;
    if (op === "eq") ok = x != null && String(x) === v;
    else if (op === "neq") ok = x == null || String(x) !== v;
    else if (op === "is") ok = v === "null" ? x == null : v === "true" ? x === true : x === false;
    else if (op === "in") ok = v.replace(/^\(|\)$/g, "").split(",").map(s => s.replace(/^"|"$/g, "")).includes(String(x));
    else if (op === "gt") ok = x != null && String(x) > v;
    else if (op === "gte") ok = x != null && String(x) >= v;
    else throw new Error("op " + op);
    return neg ? !ok : ok;
  };
  const cols = (k, v) => k === "or" ? v.replace(/^\(|\)$/g, "").split(",").map(c => c.split(".")[0]) : [k];
  const pick = (r, sel) => sel && sel !== "*" ? Object.fromEntries(sel.split(",").map(c => [c, r[c] === undefined ? null : r[c]])) : { ...r };
  globalThis.fetch = async (url, init = {}) => {
    const u = new URL(url), table = u.pathname.replace(/^\/rest\/v1\//, ""), method = init.method || "GET";
    const body = init.body ? JSON.parse(init.body) : undefined, prefer = (init.headers && init.headers.Prefer) || "";
    db.calls.push({ method, table, query: decodeURIComponent(u.search), body, prefer });
    assert.equal(init.headers.apikey, ENV.SUPABASE_SERVICE_KEY);
    if (db.down) return new Response("unavailable", { status: 503 });
    const rows = db[table];
    if (!rows) return new Response(JSON.stringify({ message: "relation does not exist" }), { status: 404 });
    const filters = [...u.searchParams].filter(([k]) => !["select", "limit", "order", "on_conflict"].includes(k));
    const used = filters.flatMap(([k, v]) => cols(k, v)).concat(body && !Array.isArray(body) ? Object.keys(body) : []).concat((u.searchParams.get("select") || "").split(",").filter(Boolean));
    if (table === "profiles" && used.some(c => db.missing.has(c))) return new Response(JSON.stringify({ code: "PGRST204", message: "column missing" }), { status: 400 });
    const match = r => filters.every(([k, v]) => k === "or" ? v.replace(/^\(|\)$/g, "").split(",").some(c => { const i = c.indexOf("."); return cond(r, c.slice(0, i), c.slice(i + 1)); }) : cond(r, k, v));
    const rep = /return=representation/.test(prefer), sel = u.searchParams.get("select");
    const out = (status, list) => new Response(rep || method === "GET" ? JSON.stringify(list.map(r => pick(r, sel))) : null, { status });
    if (method === "GET") {
      let list = rows.filter(match);
      const order = u.searchParams.get("order");
      if (order) { const [c, dir] = order.split("."); list.sort((a, b) => (String(a[c]) < String(b[c]) ? -1 : 1) * (dir === "desc" ? -1 : 1)); }
      if (u.searchParams.get("limit")) list = list.slice(0, +u.searchParams.get("limit"));
      return out(200, list);
    }
    if (method === "PATCH") {
      const list = rows.filter(match); list.forEach(r => Object.assign(r, body));
      return out(rep ? 200 : 204, list);
    }
    if (method === "POST") {
      const key = u.searchParams.get("on_conflict") || UNIQUE[table];
      const row = { id: rows.length + 1, created_at: new Date().toISOString(), ...body };
      if (row[key] != null && rows.some(r => r[key] === row[key])) {
        if (/ignore-duplicates/.test(prefer)) return out(201, []);
        return new Response(JSON.stringify({ code: "23505" }), { status: 409 });
      }
      rows.push(row);
      return out(201, [row]);
    }
    throw new Error("method " + method);
  };
  return db;
}
const writes = db => db.calls.filter(c => c.method !== "GET");

async function call(fn, url, { method = "GET", body, headers = {}, env = ENV } = {}) {
  const waits = [];
  const request = new Request(url, { method, body, headers });
  const res = await fn({ request, env, waitUntil: p => waits.push(p) });
  await Promise.all(waits);
  return res;
}
const SITE = "https://www.puroclassico.com";
const TOKEN = await hmacHex(SECRET, UID), TOKEN2 = await hmacHex(SECRET, UID2);
const q = (uid = UID, t = TOKEN) => `u=${uid}&t=${t}`;
const PROFILE = { id: UID, email: "Nina.Test@example.com", marketing_opt_in: true, email_freq: "weekly", email_paused_until: null, email_sunset_at: null, unsubscribed_at: null, unsub_source: null,
  email_track: false, email_personal: false, email_consents: [] };
const BROWSER = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const SENDS = [
  { id: SEND_OLD, batch_id: "b0", member_id: UID, template: "w0", status: "sent", provider_id: "older-email-id", created_at: "2026-11-20T10:00:00Z" },
  { id: SEND, batch_id: "b1", member_id: UID, template: "picks", status: "sent", provider_id: PLUNK_ID, created_at: "2026-11-26T16:00:00Z" },
];

// ------------------------------------------------------------------ middleware routes
{
  const src = fs.readFileSync(new URL("../functions/_middleware.js", import.meta.url), "utf8");
  const PASS = new Function("return " + /const PASS = (\/.*\/);/.exec(src)[1])();
  for (const p of ["/api/email-hook", "/email-settings", "/unsubscribe"]) assert.ok(PASS.test(p), p);
  for (const p of ["/api/email-hook/x", "/email-settings/x", "/email-settingsx", "/api/email-hooks"]) assert.ok(!PASS.test(p), p);
}

// ------------------------------------------------------------------ webhook
const hookUrl = SITE + "/api/email-hook";
const bounce = (extra = {}) => JSON.stringify({ type: "email.bounce", email: "nina.test@example.com", emailId: PLUNK_ID, messageId: "0100018c-ses-id",
  bounceType: "Permanent", bounceSubType: "General", suppressed: "false", diagnosticCode: "smtp; 550 5.1.1 <nina.test@example.com>: user unknown", at: "2026-11-26T16:01:00.000Z", ...extra });
const post = (body, headers = { authorization: "Bearer " + HOOK }, url = hookUrl, env = ENV) =>
  call(hook.onRequest, url, { method: "POST", body, headers: { "content-type": "application/json", ...headers }, env });
{
  // a hard bounce: answered at once, stored once, address suppressed, consent untouched
  let db = makeDb({ profiles: [PROFILE], sends: SENDS });
  let res = await post(bounce());
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true, type: "bounce" });
  assert.equal(db.email_events.length, 1);
  const e = db.email_events[0];
  assert.equal(e.type, "bounce"); assert.equal(e.send_id, SEND); assert.equal(e.member_id, UID);
  assert.equal(e.dedupe, "plunk:bounce-hard:" + PLUNK_ID);
  assert.deepEqual(e.meta, { src: "plunk", mbox: "other", kind: "hard", subtype: "General", code: "550 5.1.1", at: "2026-11-26T16:01:00.000Z" });
  assert.ok(!JSON.stringify(e).includes("nina"), "no address in the event row");
  assert.deepEqual(db.email_suppression.map(s => [s.email, s.reason, s.source]), [["nina.test@example.com", "hard_bounce", "plunk"]]);
  assert.equal(db.profiles[0].marketing_opt_in, true);
  // the same webhook again (Plunk can send an event twice): no second row, nothing else written
  const before = writes(db).length;
  res = await post(bounce());
  assert.equal(res.status, 200);
  assert.equal(db.email_events.length, 1);
  assert.equal(writes(db).length, before + 1, "only the ignored insert");
  assert.equal(db.email_suppression.length, 1);
  assert.equal((await hook.apply(ENV, hook.normalize(JSON.parse(bounce())))).duplicate, true);

  // bad, missing and alternative secrets
  db = makeDb({ profiles: [PROFILE], sends: SENDS });
  assert.equal((await post(bounce(), { authorization: "Bearer wrong" })).status, 401);
  assert.equal((await post(bounce(), {})).status, 401);
  assert.equal((await post(bounce(), { authorization: "Bearer " + HOOK + "x" })).status, 401);
  assert.equal(db.calls.length, 0, "nothing read or written without the secret");
  assert.equal((await post(bounce(), { "x-hook-secret": HOOK })).status, 200);
  assert.equal((await post(bounce({ emailId: "another-id" }), {}, hookUrl + "?k=" + HOOK)).status, 200);
  assert.equal(db.email_events.length, 2);
  // not set up, wrong method, bad bodies
  assert.equal((await post(bounce(), undefined, hookUrl, { ...ENV, EMAIL_HOOK_SECRET: "" })).status, 503);
  assert.equal((await call(hook.onRequest, hookUrl, { env: ENV })).status, 405);
  assert.equal((await post("not json")).status, 400);
  assert.equal((await post("[1,2]")).status, 400);
  assert.equal((await post("x".repeat(70000))).status, 413);
  res = await post(JSON.stringify({ type: "email.open", emailId: PLUNK_ID }));
  assert.equal(res.status, 200); assert.equal((await res.json()).ignored, "open");

  // a spam complaint: suppressed and unsubscribed (unsub_source complaint)
  db = makeDb({ profiles: [PROFILE], sends: SENDS });
  res = await post(JSON.stringify({ type: "email.complaint", email: "nina.test@example.com", emailId: PLUNK_ID, messageId: "m1", feedbackType: "abuse", suppressed: "{{event.suppressedByProvider}}", at: "2026-11-26T17:00:00Z" }));
  assert.equal(res.status, 200);
  assert.equal(db.email_events[0].type, "complaint"); assert.equal(db.email_events[0].dedupe, "plunk:complaint:" + PLUNK_ID);
  assert.equal(db.email_events[0].meta.feedback, "abuse");
  assert.equal(db.email_suppression[0].reason, "complaint");
  assert.equal(db.profiles[0].marketing_opt_in, false); assert.equal(db.profiles[0].unsub_source, "complaint"); assert.ok(db.profiles[0].unsubscribed_at);

  // a provider block (Amazon SES suppression list): suppressed, but consent left alone
  db = makeDb({ profiles: [PROFILE], sends: SENDS });
  await post(JSON.stringify({ type: "email.complaint", email: "nina.test@example.com", emailId: PLUNK_ID, suppressed: "true", feedbackType: "" }));
  assert.equal(db.email_events[0].meta.kind, "suppressed");
  assert.equal(db.email_suppression[0].detail, "provider suppression list");
  assert.equal(db.profiles[0].marketing_opt_in, true);

  // a soft bounce and a delivery: recorded only, no address and no member on the delivery
  db = makeDb({ profiles: [PROFILE], sends: SENDS });
  await post(bounce({ bounceType: "Transient", bounceSubType: "MailboxFull", at: "{{event.bouncedAt}}" }));
  await post(JSON.stringify({ type: "email.delivery", email: "Someone@Gmail.com", emailId: PLUNK_ID, messageId: "m1", at: "2026-11-26T16:00:03.000Z" }));
  assert.deepEqual(db.email_events.map(e => [e.type, e.meta.kind || null, e.send_id, e.member_id]), [["bounce", "soft", SEND, UID], ["delivered", null, SEND, null]]);
  assert.equal(db.email_events[0].meta.at, undefined, "an unfilled placeholder is no value");
  assert.equal(db.email_events[1].meta.mbox, "gmail", "only the mailbox group is kept");
  assert.ok(!JSON.stringify(db.email_events).toLowerCase().includes("someone"), "no address in event rows");
  assert.equal(db.email_suppression.length, 0);
  // mailbox groups
  assert.deepEqual(["a@gmail.com", "a@googlemail.com", "a@hotmail.no", "a@outlook.com", "a@live.co.uk", "a@yahoo.co.uk", "a@aol.com", "a@icloud.com", "a@me.com", "a@firma.no", "nope", ""].map(mailbox),
    ["gmail", "gmail", "outlook", "outlook", "outlook", "yahoo", "yahoo", "icloud", "icloud", "other", null, null]);

  // Plunk's default body (no custom body set): type from the fields, address from contact
  db = makeDb({ profiles: [PROFILE], sends: SENDS });
  res = await post(JSON.stringify({ contact: { email: "Nina.Test@Example.com", subscribed: true, data: {} }, workflow: { id: "wf", name: "Bounces" }, execution: { id: "x" },
    event: { subject: "s", messageId: "ses-1", emailId: PLUNK_ID, bounceType: "Permanent", bouncedAt: "2026-11-26T16:01:00.000Z" } }));
  assert.equal(res.status, 200);
  assert.equal(db.email_events[0].type, "bounce"); assert.equal(db.email_suppression[0].email, "nina.test@example.com");
  // a body sent as a JSON string, and ?type= when the body does not say
  db = makeDb({ profiles: [PROFILE], sends: SENDS });
  assert.equal((await post(JSON.stringify(JSON.stringify({ emailId: PLUNK_ID, deliveredAt: "2026-11-26T16:00:03Z" })))).status, 200);
  assert.equal(db.email_events[0].type, "delivered");
  assert.equal((await post(JSON.stringify({ emailId: "id-2", email: "nina.test@example.com" }), undefined, hookUrl + "?type=complaint")).status, 200);
  assert.equal(db.email_events[1].type, "complaint");

  // no send matches the ids: the member is found by address, Plunk's id is kept for later
  db = makeDb({ profiles: [PROFILE, { ...PROFILE, id: UID2, email: "other@example.com" }], sends: SENDS });
  await post(JSON.stringify({ type: "email.complaint", email: "other@example.com", emailId: "unknown-id" }));
  assert.equal(db.email_events[0].send_id, null); assert.equal(db.email_events[0].member_id, UID2); assert.equal(db.email_events[0].meta.pid, "unknown-id");
  assert.equal(db.profiles[1].marketing_opt_in, false); assert.equal(db.profiles[0].marketing_opt_in, true);

  // Supabase down: still a fast 200 (Plunk does not retry), nothing thrown
  db = makeDb({ profiles: [PROFILE], sends: SENDS }); db.down = true;
  assert.equal((await post(bounce())).status, 200);
}

// ------------------------------------------------------------------ unsubscribe
const unsubUrl = (s = q()) => SITE + "/unsubscribe?" + s;
const oneClick = (s = q(), env = ENV) => call(unsub.onRequestPost, unsubUrl(s), { method: "POST", body: "List-Unsubscribe=One-Click", headers: { "content-type": "application/x-www-form-urlencoded" }, env });
{
  // GET never unsubscribes: a page with the button and a settings link
  let db = makeDb({ profiles: [PROFILE], sends: SENDS });
  let res = await call(unsub.onRequestGet, unsubUrl());
  let html = await res.text();
  assert.equal(res.status, 200);
  assert.equal(writes(db).length, 0);
  assert.match(html, /<form method="post" action="\/unsubscribe\?u=[^"]+"><input type="hidden" name="via" value="page">/);
  assert.match(html, /href="\/email-settings\?u=11111111-2222-4333-8444-555555555555&amp;t=[0-9a-f]{64}"/);
  assert.match(html, /Ni•••@example\.com/);
  assert.match(html, /noindex/); assert.match(html, /no-referrer/);
  assert.equal(res.headers.get("cache-control"), "no-store");
  assert.ok(!/[\u2013\u2014]/.test(html), "no en or em dashes");
  // bad token, missing settings
  res = await call(unsub.onRequestGet, unsubUrl(q(UID, "0".repeat(64))));
  assert.equal(res.status, 400); assert.match(await res.text(), /Link expired or invalid/);
  assert.equal((await call(unsub.onRequestGet, unsubUrl(), { env: {} })).status, 500);
  // HEAD as before
  res = await unsub.onRequestHead();
  assert.equal(res.status, 200); assert.equal(await res.text(), "");

  // one-click POST: unsubscribed at once, with when and how, and one unsubscribe event linked to the last email
  res = await oneClick();
  assert.equal(res.status, 200); assert.equal(await res.text(), "OK");
  assert.equal(db.profiles[0].marketing_opt_in, false); assert.equal(db.profiles[0].unsub_source, "header");
  const at = db.profiles[0].unsubscribed_at; assert.ok(at);
  assert.deepEqual(db.email_events.map(e => [e.type, e.send_id, e.member_id, e.meta.source, e.meta.template, e.meta.mbox]), [["unsubscribe", SEND, UID, "header", "picks", "other"]]);
  // again (Gmail and the member both): still 200, first record kept, no second event
  res = await oneClick();
  assert.equal(res.status, 200);
  assert.equal(db.profiles[0].unsubscribed_at, at); assert.equal(db.email_events.length, 1);
  // now GET says so
  html = await (await call(unsub.onRequestGet, unsubUrl())).text();
  assert.match(html, /You're unsubscribed/);

  // the page's button: unsub_source "link" and a result page
  db = makeDb({ profiles: [PROFILE], sends: SENDS });
  res = await call(unsub.onRequestPost, unsubUrl(), { method: "POST", body: "via=page", headers: { "content-type": "application/x-www-form-urlencoded" } });
  assert.equal(res.status, 200); assert.match(await res.text(), /You're unsubscribed/);
  assert.equal(db.profiles[0].unsub_source, "link"); assert.equal(db.email_events[0].meta.source, "link");

  // the health check's deliberately bad token: 400, no redirect, nothing written
  db = makeDb({ profiles: [PROFILE], sends: SENDS });
  res = await oneClick("u=health-check&t=0");
  assert.equal(res.status, 400); assert.equal(await res.text(), "Invalid unsubscribe link");
  assert.equal(db.calls.length, 0);
  // our side failing: 500 (and the page version says so)
  db.down = true;
  assert.equal((await oneClick()).status, 500);
  assert.equal((await oneClick(q(), {})).status, 500);
  res = await call(unsub.onRequestPost, unsubUrl(), { method: "POST", body: "via=page", headers: { "content-type": "application/x-www-form-urlencoded" } });
  assert.equal(res.status, 500); assert.match(await res.text(), /not unsubscribed yet/);
  // before scripts/email_v2.sql (no unsubscribed_at column): the opt-out alone still works
  db = makeDb({ profiles: [{ id: UID, email: "a@b.co", marketing_opt_in: true }], missing: ["unsubscribed_at", "unsub_source", "email_freq", "email_paused_until", "email_sunset_at", "email_track", "email_personal", "email_consents"] });
  assert.equal((await oneClick()).status, 200);
  assert.equal(db.profiles[0].marketing_opt_in, false);
  assert.equal((await call(unsub.onRequestGet, unsubUrl())).status, 200, "the page still shows its button");
}

// ------------------------------------------------------------------ email settings
const setUrl = (s = q()) => SITE + "/email-settings?" + s;
const save = (choice, s = q()) => call(settings.onRequestPost, setUrl(s), { method: "POST", body: "choice=" + choice, headers: { "content-type": "application/x-www-form-urlencoded" } });
const checked = html => (/value="(\w+)" checked/.exec(html) || [])[1];
{
  let db = makeDb({ profiles: [PROFILE, { ...PROFILE, id: UID2, email: "x@example.com", marketing_opt_in: false, unsubscribed_at: "2026-11-01T00:00:00Z", unsub_source: "link" }], sends: SENDS });
  let res = await call(settings.onRequestGet, setUrl());
  let html = await res.text();
  assert.equal(res.status, 200); assert.equal(writes(db).length, 0);
  assert.equal(checked(html), "weekly");
  for (const t of ["Weekly picks and saved-find alerts", "Only saved-find alerts", "Pause for 30 days", "Unsubscribe from everything"]) assert.ok(html.includes(t), t);
  assert.match(html, /<form class="em-card" method="post" action="\/email-settings\?u=/);
  assert.ok(!/[\u2013\u2014]/.test(html), "no en or em dashes");
  assert.equal(checked(await (await call(settings.onRequestGet, setUrl(q() + "&pick=stop"))).text()), "stop");
  assert.equal(checked(await (await call(settings.onRequestGet, setUrl(q() + "&pick=nonsense"))).text()), "weekly");

  res = await save("alerts"); html = await res.text();
  assert.equal(res.status, 200); assert.equal(db.profiles[0].email_freq, "alerts"); assert.equal(checked(html), "alerts");
  assert.match(html, /Saved\. You'll only get saved-find alerts\./);
  res = await save("pause"); html = await res.text();
  const until = Date.parse(db.profiles[0].email_paused_until);
  assert.ok(Math.abs(until - (Date.now() + 30 * 864e5)) < 60000);
  assert.equal(db.profiles[0].email_freq, "alerts", "the frequency stays for after the pause");
  assert.equal(checked(html), "pause"); assert.match(html, /Saved\. No emails until \d{1,2} [A-Z][a-z]{2} 20\d\d\./);
  db.profiles[0].email_sunset_at = "2026-10-01T00:00:00Z";
  res = await save("weekly");
  assert.equal(db.profiles[0].email_freq, "weekly"); assert.equal(db.profiles[0].email_paused_until, null); assert.equal(db.profiles[0].email_sunset_at, null);
  assert.equal((await save("sometimes")).status, 400);

  res = await save("stop"); html = await res.text();
  assert.equal(db.profiles[0].marketing_opt_in, false); assert.equal(db.profiles[0].unsub_source, "settings");
  assert.equal(db.email_events.at(-1).type, "unsubscribe"); assert.equal(db.email_events.at(-1).meta.source, "settings");
  assert.match(html, /You're unsubscribed\./); assert.match(html, /Turn emails back on/); assert.ok(!html.includes('name="choice" value="weekly"'));
  assert.equal((await save("weekly")).status, 200); assert.equal(db.profiles[0].marketing_opt_in, false, "options do nothing while unsubscribed");
  res = await save("on"); html = await res.text();
  assert.equal(db.profiles[0].marketing_opt_in, true); assert.equal(db.profiles[0].unsubscribed_at, null); assert.equal(db.profiles[0].unsub_source, null);
  assert.equal(db.email_events.at(-1).type, "resubscribe"); assert.equal(db.email_events.at(-1).member_id, UID);
  assert.match(html, /Emails are back on/); assert.equal(checked(html), "weekly");

  // another member who unsubscribed: "Turn emails back on"; with a suppressed address no button, and why
  html = await (await call(settings.onRequestGet, setUrl(q(UID2, TOKEN2)))).text();
  assert.match(html, /Your emails are off/); assert.match(html, /Turn emails back on/);
  db.email_suppression.push({ email: "x@example.com", reason: "hard_bounce" });
  html = await (await call(settings.onRequestGet, setUrl(q(UID2, TOKEN2)))).text();
  assert.match(html, /bounced/); assert.ok(!html.includes("Turn emails back on"));
  await save("on", q(UID2, TOKEN2)); assert.equal(db.profiles[1].marketing_opt_in, false);

  // the two consent switches: off unless turned on, each change kept with time, wording version and where
  const sw = html => Object.fromEntries([...html.matchAll(/role="switch" name="(\w+)" value="1"( checked)?/g)].map(m => [m[1], !!m[2]]));
  html = await (await call(settings.onRequestGet, setUrl())).text();
  assert.deepEqual(sw(html), { personal: false, track: false });
  assert.ok(html.includes("Personalise my emails from finds I view") && html.includes("Measure my email clicks"));
  const form = (s, extra = "") => call(settings.onRequestPost, setUrl(), { method: "POST", body: s + extra, headers: { "content-type": "application/x-www-form-urlencoded" } });
  res = await form("choice=weekly&switches=1&personal=1"); html = await res.text();
  assert.equal(db.profiles[0].email_personal, true); assert.equal(db.profiles[0].email_track, false);
  assert.deepEqual(db.profiles[0].email_consents.map(c => [c.what, c.value, c.text_version, c.via]), [["personal", true, settings.TEXT_VERSION, "settings"]]);
  assert.ok(Date.parse(db.profiles[0].email_consents[0].at) > Date.now() - 60000);
  assert.deepEqual(sw(html), { personal: true, track: false }); assert.match(html, /Saved\./);
  await form("choice=weekly&switches=1&personal=1&track=1");
  assert.equal(db.profiles[0].email_track, true); assert.equal(db.profiles[0].email_consents.length, 2, "only the switch that changed is added");
  await form("choice=weekly&switches=1&personal=1&track=1");
  assert.equal(db.profiles[0].email_consents.length, 2, "saving again without a change adds nothing");
  // the footer's one-tap "stop measuring my clicks": a GET that only ever turns tracking off
  res = await call(settings.onRequestGet, setUrl(q() + "&track=off"), { headers: { "user-agent": "Mozilla/5.0 (compatible; SafeLinks/1.0)" } });
  assert.equal(db.profiles[0].email_track, true, "a scanner following the link changes nothing");
  res = await call(settings.onRequestGet, setUrl(q() + "&track=off"), { headers: { "user-agent": BROWSER, "sec-purpose": "prefetch" } });
  assert.equal(db.profiles[0].email_track, true, "nor does a prefetch");
  res = await call(settings.onRequestGet, setUrl(q() + "&track=off"), { headers: { "user-agent": BROWSER } }); html = await res.text();
  assert.equal(res.status, 200); assert.equal(db.profiles[0].email_track, false); assert.equal(db.profiles[0].email_personal, true);
  assert.deepEqual(db.profiles[0].email_consents.at(-1).what + ":" + db.profiles[0].email_consents.at(-1).value + ":" + db.profiles[0].email_consents.at(-1).via, "track:false:footer");
  assert.match(html, /We no longer measure which links you click\. You still get your emails\./); assert.deepEqual(sw(html), { personal: true, track: false });
  const n = db.profiles[0].email_consents.length, w = writes(db).length;
  res = await call(settings.onRequestGet, setUrl(q() + "&track=off"), { headers: { "user-agent": BROWSER } });
  assert.equal(db.profiles[0].email_consents.length, n); assert.equal(writes(db).length, w, "already off: nothing written");
  assert.match(await res.text(), /We no longer measure/);
  assert.equal((await call(settings.onRequestGet, setUrl(q(UID, TOKEN2) + "&track=off"), { headers: { "user-agent": BROWSER } })).status, 400);
  // "Turn emails back on" never touches the switches
  await save("stop"); await save("on");
  assert.equal(db.profiles[0].email_personal, true); assert.equal(db.profiles[0].email_consents.length, n);

  // bad links, gone accounts, our side failing
  assert.equal((await call(settings.onRequestGet, setUrl(q(UID, TOKEN2)))).status, 400);
  assert.equal((await save("stop", q(UID, "abc"))).status, 400);
  assert.equal(db.profiles[0].marketing_opt_in, true);
  const ghost = "99999999-9999-4999-8999-999999999999";
  assert.equal((await call(settings.onRequestGet, setUrl(q(ghost, await hmacHex(SECRET, ghost))))).status, 404);
  db.down = true;
  assert.equal((await call(settings.onRequestGet, setUrl())).status, 500);
  assert.equal((await settings.onRequestHead()).status, 200);
}

console.log("email web: all tests passed");
