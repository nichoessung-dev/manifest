// Product page view counter (29 Oct 2026), used by functions/product/[id].js.
// One server-rendered /product/<id> page load by a person adds 1 to a DAILY counter row in Supabase
// (table product_page_views, function bump_product_view, both in OWNER_SQL.sql): day, product id, a source bucket worked
// out from the Referer host (or the link's utm_source), and the link's utm_campaign. Nothing else is stored: no IP address,
// no user agent, no cookie, no country, no user id, no full referrer. Nothing is set on or read from the visitor's device.
// Counted before the edge cache answers, so cached pages count too. Crawlers, link previews, headless browsers, HEAD
// requests and prefetches are skipped. The write runs in context.waitUntil after the page has been sent, and every error is
// swallowed: the page never waits for it and never breaks because of it. Without SUPABASE_SERVICE_KEY, or before the owner
// has run the SQL, nothing is counted and nothing else changes.
const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";

// Not people. The first part is the same filter as functions/go/[agent].js and functions/api/search.js; the second adds
// named crawlers, AI fetchers, chat-app link previews and HTTP libraries that do not say "bot".
// (?<!cu)bot: CUBOT is a phone brand. "compatible;" is in nearly every crawler's string and in no current browser's.
export const BOT = new RegExp("(?<!cu)bot|crawl|spider|slurp|preview|fetch|scan|check|monitor|proxy|compatible;|-user/" +
  "|headless|phantomjs|puppeteer|playwright|selenium|lighthouse|facebookexternalhit|meta-external" +
  "|mimecast|proofpoint|barracuda|symantec|sophos|fireeye|trendmicro|zscaler|safelinks|virustotal" +
  "|googleother|google-inspectiontool|google-pagerenderer|googleproducer|google-structureddatatestingtool|mediapartners-google|adsbot|apis-google|feedfetcher|google-read-aloud|storebot" +
  "|bingpreview|yandex|baiduspider|petalbot|bytespider|gptbot|chatgpt-user|oai-searchbot|claude|anthropic|perplexity" +
  "|ccbot|amazonbot|applebot|duckassist|whatsapp|skypeuripreview|embedly|quora link|vkshare|w3c_validator|outbrain" +
  "|curl/|wget/|python-|aiohttp|httpx|go-http-client|okhttp|java/|libwww|httpclient|axios/|node-fetch|undici|got \\(" +
  "|postman|insomnia|ahrefs|semrush|mj12|dotbot|screaming frog|sitebulb|uptime|pingdom|statuscake|datadog|newrelic" +
  "|cloudflare-|wappalyzer|electron/|puroclassico", "i");   // last: our own health check, IndexNow and posting scripts

// The buckets a row can carry. Unknown sources become "other", so a visitor cannot invent new rows through utm_source.
export const SOURCES = ["google", "bing", "direct", "tiktok", "discord", "email", "telegram", "youtube", "pinterest", "instagram", "threads", "site", "other"];
// utm_source / src / channel ?ref= values from our own links (see scripts/*_drops.py, post_short.py, pins.py, newsletter.py).
const TAGS = { google: "google", bing: "bing", tiktok: "tiktok", tt: "tiktok", discord: "discord", dc: "discord", email: "email",
  newsletter: "email", brevo: "email", telegram: "telegram", tg: "telegram", youtube: "youtube", yt: "youtube", pinterest: "pinterest",
  pin: "pinterest", instagram: "instagram", ig: "instagram", threads: "threads" };
// Referer host -> bucket, first match wins. android-app:// referrers name the app (Gmail, the Google app, YouTube ...).
const HOSTS = [
  [/^(mail\.google\.com|com\.google\.android\.gm|outlook\.(live|office|office365)\.com|mail\.yahoo\.com|mail\.proton\.me|mail\.aol\.com|mail\.yandex\.[a-z]+|webmail\..+|.*\.mail\.[a-z.]+)$/, "email"],
  [/(^|\.)google\.[a-z.]+$|^com\.google\.android\.googlequicksearchbox$/, "google"],
  [/(^|\.)bing\.com$/, "bing"],
  [/(^|\.)tiktok\.com$|^com\.zhiliaoapp\.musically$|^com\.ss\.android\.ugc\.trill$/, "tiktok"],
  [/(^|\.)(discord\.com|discordapp\.com|discord\.gg)$/, "discord"],
  [/(^|\.)(t\.me|telegram\.org|telegram\.me)$|^org\.telegram\.messenger$/, "telegram"],
  [/(^|\.)(youtube\.com|youtu\.be)$|^com\.google\.android\.youtube$/, "youtube"],
  [/(^|\.)pinterest\.[a-z.]+$|^pin\.it$/, "pinterest"],
  [/(^|\.)instagram\.com$/, "instagram"],
  [/(^|\.)threads\.(net|com)$/, "threads"],
  [/(^|\.)puroclassico\.com$|(^|\.)manifest-bq9\.pages\.dev$/, "site"],
];
const clean = v => String(v || "").toLowerCase().replace(/[^a-z0-9_.-]/g, "");

// Our own campaign tags only (the same list as CAMPAIGN_KNOWN in scripts/bake_stats.py and the check in
// bump_product_view in OWNER_SQL.sql). Anything else is stored as "", so a visitor cannot add rows by inventing tags.
export const CAMPAIGNS = /^(drop|pin|short-[a-z0-9-]{1,20}|welcome|ordering|mycnbox|newsletter|saved|(welcome|ordering|mycnbox)-test)$/;

// The link's campaign tag (lowercase) when it is one of ours; "" otherwise or when there is none.
export function campaignOf(url) {
  const c = clean(url.searchParams.get("utm_campaign")).replace(/^[._-]+/, "").slice(0, 40);
  return CAMPAIGNS.test(c) ? c : "";
}

// Which kind of place sent this page view. Our own tags first (in-app browsers often drop the Referer), then the Referer
// host, then the in-app browser's name, else "direct".
export function sourceOf(request, url) {
  const q = url.searchParams;
  const tag = clean(q.get("utm_source") || q.get("src")), medium = clean(q.get("utm_medium")), ref = clean(q.get("ref"));
  if (tag) return TAGS[tag] || (medium === "email" ? "email" : "other");
  if (medium === "email") return "email";
  if (ref && TAGS[ref]) return TAGS[ref];
  const referer = request.headers.get("referer") || "";
  if (referer) {
    let host = "";
    try { host = new URL(referer).hostname.toLowerCase().replace(/^www\./, ""); } catch (e) {}
    if (!host) return "other";
    for (const [re, name] of HOSTS) if (re.test(host)) return name;
    return "other";
  }
  const ua = request.headers.get("user-agent") || "";
  if (/tiktok|musical_ly|musically|trill_|bytedancewebview/i.test(ua)) return "tiktok";
  if (/instagram/i.test(ua)) return "instagram";
  if (/discord/i.test(ua)) return "discord";
  if (/telegram/i.test(ua)) return "telegram";
  if (/pinterest/i.test(ua)) return "pinterest";
  if (ref) return "other";                                         // a member's ?ref= code: a referral, not a direct visit
  return "direct";
}

// Is this request a person loading the page? GET only (HEAD is how monitors and link checkers look), no prefetch or
// prerender (Sec-Purpose, Purpose, X-Purpose, X-Moz), a top-level page load when the browser says what it is fetching,
// and a user agent that is not a crawler, preview fetcher, script or headless browser.
export function isCountable(request) {
  if (request.method !== "GET") return false;
  const h = request.headers;
  const purpose = [h.get("sec-purpose"), h.get("purpose"), h.get("x-purpose"), h.get("x-moz")].filter(Boolean).join(" ");
  if (/prefetch|prerender|preview/i.test(purpose)) return false;
  const dest = h.get("sec-fetch-dest");
  if (dest && dest !== "document") return false;                   // fetch(), <link rel=prefetch>, images, iframes
  const ua = h.get("user-agent") || "";
  if (ua.length < 20 || !/mozilla\/|opera\//i.test(ua) || BOT.test(ua)) return false;
  const cf = request.cf || {};
  if (cf.verifiedBotCategory || (cf.botManagement && cf.botManagement.verifiedBot)) return false;
  return true;
}

// At most LIMIT counted views per IP per minute, per isolate. The IP is only a key in this isolate's memory, never written
// anywhere (IPv6 by its /64); it stops one script from inflating the counts or filling the table with campaign rows.
const LIMIT = 30, WINDOW = 60000, seen = new Map();
// The first 64 bits of an IPv6 address, written out in full, so "2001:db8::1" and "2001:db8:0:0:5::9" share a key.
export function v6prefix(ip) {
  const [head, tail] = String(ip).toLowerCase().split("%")[0].split("::");
  const h = head ? head.split(":") : [], t = tail === undefined ? [] : (tail ? tail.split(":") : []);
  const groups = tail === undefined ? h : h.concat(Array(Math.max(0, 8 - h.length - t.length)).fill("0"), t);
  return groups.slice(0, 4).map(g => (parseInt(g, 16) || 0).toString(16)).join(":");
}
function limited(ip) {
  if (!ip) return false;
  if (ip.includes(":")) ip = v6prefix(ip);                          // IPv6: one key per /64, the block one user can rotate through
  const now = Date.now();
  if (seen.size > 5000) for (const [k, v] of seen) if (now - v.t > WINDOW) seen.delete(k);
  const v = seen.get(ip);
  if (!v || now - v.t > WINDOW) { seen.set(ip, { t: now, n: 1 }); return false; }
  return ++v.n > LIMIT;
}

// Count one view of product `id` (already validated by the caller). Never throws, never waits.
export function countView(context, id) {
  try {
    const { request, env } = context;
    if (!env || !env.SUPABASE_SERVICE_KEY || !isCountable(request)) return false;
    if (limited(request.headers.get("cf-connecting-ip") || "")) return false;
    const url = new URL(request.url);
    const body = { p_product_id: String(id).slice(0, 40), p_source: sourceOf(request, url), p_campaign: campaignOf(url) };
    context.waitUntil(fetch(`${SUPA}/rest/v1/rpc/bump_product_view`, {
      method: "POST",
      headers: { apikey: env.SUPABASE_SERVICE_KEY, Authorization: "Bearer " + env.SUPABASE_SERVICE_KEY, "Content-Type": "application/json", Prefer: "return=minimal" },
      body: JSON.stringify(body),
    }).then(() => {}, () => {}));
    return true;
  } catch (e) { return false; }
}
