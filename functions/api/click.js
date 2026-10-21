/**
 * Cloudflare Pages Function: one "Buy" click on an agent link (sent by /track.js).
 * Route: POST /api/click  { a: agent, i: item id, pl: platform, pg: page path, r: source }  ->  204
 * Stores agent, item, platform, page, the visitor's country (Cloudflare's CF-IPCountry) and, in the ref column, the
 * member referral code cookie (pc_ref) or else "~" + the visit's source from track.js ("~google", "~tiktok", "~email.news")
 * in Supabase table buy_clicks. No IP address, no user id, nothing else about the visitor.
 * Env: SUPABASE_SERVICE_KEY (already set for /r/<code>).
 */
const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";
const AGENTS = new Set(["mycnbox", "kakobuy", "oopbuy", "lovegobuy", "sugargoo"]);

export async function onRequestPost(context) {
  const { request, env } = context;
  const done = new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
  try {
    if (!env || !env.SUPABASE_SERVICE_KEY) return done;
    const b = JSON.parse((await request.text()).slice(0, 1000) || "{}");
    const agent = String(b.a || "");
    if (!AGENTS.has(agent)) return done;
    const ua = request.headers.get("user-agent") || "";
    if (/bot|crawl|spider|preview|headless/i.test(ua)) return done;
    const cookie = request.headers.get("cookie") || "";
    const src = String(b.r || "").toLowerCase().replace(/[^a-z0-9_.-]/g, "").slice(0, 23);
    const ref = (cookie.match(/(?:^|;\s*)pc_ref=([a-z0-9_-]{3,24})/) || [])[1] || (src ? "~" + src : null);
    const row = {
      agent,
      item_id: /^\d{5,20}$/.test(String(b.i || "")) ? String(b.i) : null,
      platform: ["weidian", "taobao", "1688"].includes(b.pl) ? b.pl : null,
      page: String(b.pg || "").replace(/[^\w\/\-.]/g, "").slice(0, 120) || null,
      country: (request.headers.get("cf-ipcountry") || (request.cf && request.cf.country) || "").slice(0, 2) || null,
      ref,
    };
    context.waitUntil(fetch(`${SUPA}/rest/v1/buy_clicks`, {
      method: "POST",
      headers: { apikey: env.SUPABASE_SERVICE_KEY, Authorization: "Bearer " + env.SUPABASE_SERVICE_KEY, "Content-Type": "application/json", Prefer: "return=minimal" },
      body: JSON.stringify(row),
    }).catch(() => {}));
  } catch (e) {}
  return done;
}
