// /go/<agent>: the one address every link to MyCNBox (app, server-rendered pages, emails, social) goes through.
// It counts the click per placement, then redirects. The MyCNBox link format and the invite codes live here only.
//   /go/mycnbox?k=invite&p=<placement>                     -> the MyCNBox sign-up (invite) link
//   /go/mycnbox?k=item&m=<mall>&i=<itemId>&p=<placement>   -> the MyCNBox product page for that item
// The target is built from the fixed templates below. Nothing from the query string is used as a host or a path:
// the only values that reach it are a mall name from MALLS and a digits-only item id.
// Env (Cloudflare Pages > Settings > Environment variables): SUPABASE_SERVICE_KEY
// Table: public.link_clicks (link_clicks.sql). The redirect works without the key and before the table exists.
const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";

// Invite code per channel. "" = not set yet: email and social then use the site code, and item links carry no invite code.
// The site code never goes on item links: that would mix a counting change into the only sign-up series there is.
const CODES = { site: "AACPYA", product: "", email: "", social: "" };
const REFER_ID = "LHYDVW";
// The mallType values the site's own builders emit (the catalogue's "platform": AGENTS.mycnbox in index.html and _lib/site.js).
const MALLS = ["weidian", "taobao", "1688"];
// A new placement must be added here in the same deploy as the link that uses it, or it is stored as "other".
const PLACEMENTS = ["app-buy", "app-buy-hint", "app-header", "app-popup", "app-tutorial", "app-bonus", "app-guide",
  "ssr-header", "ssr-buy", "ssr-buy-hint", "ssr-guide", "ssr-agent", "how-to-order", "start",
  "email-welcome", "email-guide", "email-nudge", "email-news", "email-saved", "social", "other"];

// Not people: crawlers, link-preview fetchers, scripts, automated browsers, and the mail scanners that name themselves.
// (?<!cu)bot: CUBOT is a phone brand. "compatible;" is in nearly every crawler's string and in no current browser's.
// Most mail scanners pose as a normal browser, so email clicks stay upper limits.
const BOT = new RegExp("(?<!cu)bot|crawl|spider|slurp|preview|fetch|scan|check|monitor|proxy|compatible;|-user/" +
  "|headless|phantomjs|puppeteer|playwright|selenium|lighthouse|facebookexternalhit|meta-external" +
  "|mimecast|proofpoint|barracuda|symantec|sophos|fireeye|trendmicro|zscaler|safelinks|virustotal", "i");
// In-app browsers, first match wins. Threads calls itself "Barcelona". bytedancewebview also covers TikTok builds that drop the app name.
const INAPP = [
  ["tiktok", /tiktok|musical_ly|musically|trill_|bytedancewebview/i],
  ["threads", /barcelona/i],
  ["instagram", /instagram/i],
  ["facebook", /FB_IAB|FBAN|FBAV/],
  ["snapchat", /snapchat/i],
  ["pinterest", /pinterest/i],
  ["discord", /discord/i],
  ["telegram", /telegram/i],
];

// Where a click goes and how it is logged. k, m, i and p each count only when given exactly once.
// "amp;m" is what "&m" turns into when a link was HTML-escaped once too often (&amp;m=... arrives as text).
// It is read as the same parameter, so such a link still reaches its item and keeps its placement.
function resolve(q) {
  const one = name => { const all = q.getAll(name).concat(q.getAll("amp;" + name)); return all.length === 1 ? all[0] : null; };
  const p = one("p"), m = one("m"), i = one("i");
  const placement = PLACEMENTS.includes(p) ? p : "other";
  if (one("k") === "item" && MALLS.includes(m) && /^[0-9]{5,20}$/.test(i || "")) {
    const code = CODES.product && CODES.product !== CODES.site ? CODES.product : "";
    return { kind: "item", placement,
      location: `https://mycnbox.com/goodsDetail?mallType=${m}&itemId=${i}&referId=${REFER_ID}` + (code ? `&inviteCode=${code}` : "") };
  }
  // Everything else, a broken item link included, lands on the sign-up page: a click never gets an error page.
  // The channel comes from the stored placement, so the table alone tells which code a click carried.
  const channel = placement.startsWith("email-") ? "email" : placement === "social" || placement === "start" ? "social" : "site";
  return { kind: "invite", placement, location: "https://mycnbox.com/login/main-login?inviteCode=" + (CODES[channel] || CODES.site) };
}

// One row per human click. Best effort: nothing in here may delay or break the redirect.
// Stored: agent, kind, placement, phone or desktop, in-app browser name. The database adds the time, rounded to the hour.
// Not stored: IP address, user agent, user id, item id, referrer.
function count(context, kind, placement) {
  try {
    const key = context.env && context.env.SUPABASE_SERVICE_KEY;
    if (!key) return;
    const h = context.request.headers, ua = (h.get("user-agent") || "").trim();
    if (!/^(Mozilla|Opera)\/[0-9.]+ \(/.test(ua) || BOT.test(ua)) return;   // every browser's string starts "Mozilla/5.0 ("; an empty one stops here too
    if (/prefetch|prerender|preview/i.test([h.get("purpose"), h.get("sec-purpose"), h.get("x-purpose"), h.get("x-moz")].join(" "))) return;   // the browser loading ahead, not a click
    // An image, script, XHR or frame on someone's page that points here is not a click either: count page loads only.
    // Older browsers and some in-app browsers do not send this header; those are still counted.
    const dest = h.get("sec-fetch-dest");
    if (dest && dest !== "document") return;
    const app = INAPP.find(([, re]) => re.test(ua));
    const row = { agent: "mycnbox", kind, placement, device: /Mobi|Android|iPhone|iPod|iPad/i.test(ua) ? "phone" : "desktop", inapp: app ? app[0] : null };
    const job = (async () => {
      try {
        await fetch(`${SUPA}/rest/v1/link_clicks`, {
          method: "POST",
          headers: { apikey: key, Authorization: "Bearer " + key, "Content-Type": "application/json", Prefer: "return=minimal" },
          body: JSON.stringify(row)
        });
      } catch (e) {}
    })();
    context.waitUntil(job);
  } catch (e) {}
}

function go(context, counted) {
  const agent = String((context.params && context.params.agent) || "").toLowerCase();
  if (agent !== "mycnbox") {
    return new Response(context.request.method === "HEAD" ? null : "Not found", { status: 404,
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow" } });
  }
  const t = resolve(new URL(context.request.url).searchParams);
  if (counted) count(context, t.kind, t.placement);
  // no-store: a cached redirect would hide later clicks and keep an old code alive after CODES changes.
  return new Response(null, { status: 302, headers: { "Location": t.location, "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow" } });
}

export async function onRequestGet(context) {
  return go(context, true);
}

// HEAD (link previews, mail scanners, crawlers): same redirect, never counted. Pages does not send HEAD to onRequestGet.
export async function onRequestHead(context) {
  return go(context, false);
}

// Pages calls this for every method without its own export above (POST, PUT, DELETE, PATCH, OPTIONS).
export async function onRequest() {
  return new Response("Method not allowed", { status: 405,
    headers: { "Allow": "GET, HEAD", "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
}
