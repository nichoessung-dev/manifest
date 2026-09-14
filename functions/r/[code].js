// Referral link: /r/<code> -> sets a 30-day pc_ref cookie, counts the click, redirects home.
// Env (Cloudflare Pages > Settings > Environment variables): SUPABASE_SERVICE_KEY
const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";
export async function onRequestGet(context){
  const { params, request, env } = context;
  const raw = (params.code || "").toString().toLowerCase();
  const code = raw.replace(/[^a-z0-9_-]/g, "").slice(0, 24);
  const origin = new URL(request.url).origin;
  const headers = new Headers({ "Location": origin + "/?ref=" + encodeURIComponent(code) });
  if (code && code.length >= 3) {
    headers.append("Set-Cookie",
      `pc_ref=${code}; Path=/; Max-Age=2592000; SameSite=Lax; Secure`);
    // best-effort click count (never blocks the redirect)
    try {
      if (env && env.SUPABASE_SERVICE_KEY) {
        context.waitUntil(fetch(`${SUPA}/rest/v1/rpc/bump_referral_click`, {
          method: "POST",
          headers: { apikey: env.SUPABASE_SERVICE_KEY, Authorization: "Bearer " + env.SUPABASE_SERVICE_KEY, "Content-Type": "application/json" },
          body: JSON.stringify({ p_code: code })
        }).catch(()=>{}));
      }
    } catch(e){}
  }
  return new Response(null, { status: 302, headers });
}
