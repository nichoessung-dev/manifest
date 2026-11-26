// Email tracking (Email v2, 26 Nov 2026). Every link in our emails points here first.
//   /e/<send>/<campaign>/<link>?u=<destination>&h=<signature>   click: logs it, then 302 to the destination
//   /e/o/<send>/<campaign>.gif                                   open pixel (only in emails whose stream uses it)
// <send> is a UUIDv7 in 22 base64url characters, made by scripts/mailer.py: by default the batch id that every recipient
// of the same email, version and day shares (email_sends.batch_id), so clicks are counted per email and link, not per
// person (EDPB Guidelines 2/2023 and ekomloven § 3-15 treat per-person tracking links like pixels, which need consent).
// With per-member tracking switched on (only with consent) it is the send's own id. Its first 48 bits are the send time
// in milliseconds, so a click's age is known without a database read. <campaign> and <link> are short slugs
// (the utm_campaign on our own links and the block in the email, such as coupon, card-3 or footer).
// The signature (HMAC-SHA256 with the key "e1:" + UNSUB_SECRET, first 16 base64url characters) covers send, campaign,
// link and destination, so this cannot be used as an open redirect; the destination must also be one of our own hosts
// or an agent we link to. A bad link still lands somewhere useful: our homepage. The redirect never waits for logging.
// Raw facts are stored (user agent, network number, country, age of the email, a daily-salted network hash); whether
// a click was a person or a mail scanner is decided later, by scripts/email_stats.py, which sees every click of a send.
// Env (Cloudflare Pages): UNSUB_SECRET, SUPABASE_SERVICE_KEY. Table: public.email_events (scripts/email_v2.sql).
const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";
const HOME = "https://www.puroclassico.com/";
const OWN = /^(www\.|fb\.)?puroclassico\.com$/i;
const ALLOW = /^(www\.|fb\.)?puroclassico\.com$|^(m\.)?mycnbox\.com$|^ikako\.vip$|^(www\.)?(kakobuy|oopbuy|lovegobuy|sugargoo|litbuy|hipobuy|boonbuy|joyagoo|usfans|gtbuy|itaobuy|cssbuy|hubbuy|bbdbuy|bbdbuyeu|superbuy|fishgoo)\.com$/i;   // bbdbuyeu: BBDBuy's sign-up link
const SLUG = /^[a-z0-9][a-z0-9-]{0,31}$/;
const GIF = Uint8Array.from(atob("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"), c => c.charCodeAt(0));

const b64u = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64u = s => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "==".slice(0, (4 - s.length % 4) % 4)), c => c.charCodeAt(0));

async function hmac(secret, msg) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode("e1:" + secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64u(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(msg))).slice(0, 16);
}

// The send id as a UUID string and its send time (ms), or null when it is not a 22-character base64url UUID.
function sendOf(sid) {
  if (!/^[A-Za-z0-9_-]{22}$/.test(sid || "")) return null;
  let b; try { b = unb64u(sid); } catch (e) { return null; }
  if (b.length !== 16) return null;
  const hex = [...b].map(x => x.toString(16).padStart(2, "0")).join("");
  const uuid = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  const at = (b[0] * 2 ** 40) + (b[1] * 2 ** 32) + (b[2] * 2 ** 24) + (b[3] << 16 >>> 0) + (b[4] << 8) + b[5];
  return { uuid, at: (b[6] >> 4) === 7 ? at : null };   // only a version-7 id carries a time
}

const same = (a, b) => { if (a.length !== b.length) return false; let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i); return d === 0; };

// Our own pages get the campaign tags (unless the link already has its own), so site visits and buy clicks count per email.
function tagged(dest, campaign, link) {
  const u = new URL(dest);
  if (OWN.test(u.hostname) && !u.searchParams.has("utm_source")) {
    u.searchParams.set("utm_source", "email"); u.searchParams.set("utm_medium", "email");
    u.searchParams.set("utm_campaign", campaign); u.searchParams.set("utm_content", link);
  }
  return u.toString();
}

async function netHash(request, secret) {
  // the first three parts of an IPv4 address (or four of IPv6), salted per day: enough to see a scanner hitting every
  // link of an email at once, not enough to identify a person, and it changes every day
  const ip = request.headers.get("cf-connecting-ip") || "";
  const net = ip.includes(":") ? ip.split(":").slice(0, 4).join(":") : ip.split(".").slice(0, 3).join(".");
  const day = new Date().toISOString().slice(0, 10);
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(day + "|" + net + "|" + secret));
  return b64u(d).slice(0, 12);
}

function log(ctx, env, row) {
  if (!env.SUPABASE_SERVICE_KEY) return;
  ctx.waitUntil(fetch(`${SUPA}/rest/v1/email_events`, {
    method: "POST",
    headers: { apikey: env.SUPABASE_SERVICE_KEY, Authorization: "Bearer " + env.SUPABASE_SERVICE_KEY,
      "Content-Type": "application/json", Prefer: "return=minimal" },
    body: JSON.stringify(row),
  }).catch(() => {}));
}

function facts(request) {
  const cf = request.cf || {};
  return { ua: (request.headers.get("user-agent") || "").slice(0, 300), asn: Number(cf.asn) || null, country: cf.country || null };
}

const go = (to, extra) => new Response(null, { status: 302, headers: { location: to, "cache-control": "no-store", "x-robots-tag": "noindex", ...(extra || {}) } });

export async function onRequest(ctx) {
  const { request, env } = ctx;
  const url = new URL(request.url);
  const parts = url.pathname.split("/").filter(Boolean);   // ["e", ...]
  const secret = env.UNSUB_SECRET || "";

  // open pixel: /e/o/<send>/<campaign>.gif
  if (parts[1] === "o") {
    const send = sendOf(parts[2]); const campaign = (parts[3] || "").replace(/\.gif$/, "");
    if (send && SLUG.test(campaign) && request.method === "GET") {
      const f = facts(request);
      log(ctx, env, { send_id: send.uuid, type: "open", link: campaign, ...f,
        meta: { age_ms: send.at ? Date.now() - send.at : null, net: secret ? await netHash(request, secret) : null } });
    }
    return new Response(GIF, { headers: { "content-type": "image/gif", "cache-control": "no-store, max-age=0", "x-robots-tag": "noindex" } });
  }

  // click: /e/<send>/<campaign>/<link>?u=...&h=...
  const [, sid, campaign, link] = parts;
  const send = sendOf(sid);
  const dest = url.searchParams.get("u") || "";
  let target = null;
  try { const d = new URL(dest); if (d.protocol === "https:" && ALLOW.test(d.hostname)) target = d.toString(); } catch (e) {}
  if (!send || !SLUG.test(campaign || "") || !SLUG.test(link || "") || !target) return go(HOME);
  // A wrong signature means the link was changed: no logging, and only a destination on the allow list is honoured.
  const good = secret ? same(url.searchParams.get("h") || "", await hmac(secret, `${sid}|${campaign}|${link}|${dest}`)) : false;
  const to = tagged(target, campaign, link);
  if (!good) return go(to);
  if (request.method === "GET") {
    const f = facts(request);
    log(ctx, env, { send_id: send.uuid, type: "click", link, ...f,
      meta: { campaign, dest: new URL(target).hostname + new URL(target).pathname.slice(0, 80),
        age_ms: send.at ? Date.now() - send.at : null, net: await netHash(request, secret),
        purpose: request.headers.get("sec-purpose") || request.headers.get("purpose") || null } });
  }
  return go(to);
}
