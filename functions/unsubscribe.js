// Cloudflare Pages Function: one-click unsubscribe.  Deployed at repo path functions/unsubscribe.js -> /unsubscribe
// Env vars (set in Cloudflare Pages > Settings > Environment variables): SUPABASE_SERVICE_KEY, UNSUB_SECRET
const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";

async function hmacHex(secret, msg){
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret),
    {name:"HMAC", hash:"SHA-256"}, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(msg));
  return [...new Uint8Array(sig)].map(b=>b.toString(16).padStart(2,"0")).join("");
}

function page(msg, sub){
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Email settings · Puro Classico</title><meta name="robots" content="noindex">
  <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;max-width:460px;margin:12vh auto;padding:0 24px;text-align:center;color:#111">
  <div style="font-size:20px;letter-spacing:3px;font-weight:700;margin-bottom:22px;">PURO&nbsp;CLASSICO</div>
  <h1 style="font-size:22px;margin:0 0 10px;">${msg}</h1>
  <p style="color:#666;font-size:15px;line-height:1.6;margin:0 0 24px;">${sub}</p>
  <a href="https://www.puroclassico.com/" style="display:inline-block;padding:13px 28px;min-height:44px;box-sizing:border-box;background:#111;color:#fff;text-decoration:none;border-radius:999px;font-weight:600;font-size:14px;">Back to Puro Classico</a></div>`;
}

// "ok", "invalid" (a bad or incomplete link: the visitor's side) or "error" (missing settings or Supabase failed: ours).
// Only "error" answers 5xx, so the daily health check (a deliberately bad token) stays green while a real failure shows.
async function unsubscribe(env, uid, token){
 try{
  if(!env || !env.UNSUB_SECRET || !env.SUPABASE_SERVICE_KEY) return "error";
  if(!uid || !token) return "invalid";
  const good = await hmacHex(env.UNSUB_SECRET, uid);
  // constant-time-ish compare
  if(token.length !== good.length) return "invalid";
  let diff = 0; for(let i=0;i<good.length;i++) diff |= token.charCodeAt(i) ^ good.charCodeAt(i);
  if(diff !== 0) return "invalid";
  const r = await fetch(`${SUPA}/rest/v1/profiles?id=eq.${encodeURIComponent(uid)}`, {
    method:"PATCH",
    headers:{ apikey: env.SUPABASE_SERVICE_KEY, Authorization:"Bearer "+env.SUPABASE_SERVICE_KEY,
      "Content-Type":"application/json", Prefer:"return=minimal" },
    body: JSON.stringify({ marketing_opt_in:false })
  });
  return r.ok ? "ok" : "error";
 }catch(e){ return "error"; }
}
const STATUS = { ok: 200, invalid: 400, error: 500 };
const DISCORD = '<a href="https://www.puroclassico.com/discord" style="color:#111;">our Discord</a>';

export async function onRequestGet(context){
  const u = new URL(context.request.url);
  const r = await unsubscribe(context.env, u.searchParams.get("u"), u.searchParams.get("t"));
  const html = r === "ok" ? page("You're unsubscribed", `You won't get the newsletter or other marketing emails from Puro Classico any more. Still getting them, or changed your mind? Tell us on ${DISCORD}.`)
    : r === "invalid" ? page("Link expired or invalid", `We couldn't process that unsubscribe link. Message us on ${DISCORD} and we will take you off the list by hand.`)
    : page("Something went wrong", `That didn't work on our side, and you are not unsubscribed yet. Try the link again in a few minutes, or message us on ${DISCORD} and we will take you off the list by hand.`);
  return new Response(html, { status: STATUS[r], headers:{ "content-type":"text/html; charset=utf-8", "cache-control":"no-store" }});
}

// RFC 8058 one-click (Gmail/Apple send POST to the List-Unsubscribe URL)
export async function onRequestPost(context){
  const u = new URL(context.request.url);
  const r = await unsubscribe(context.env, u.searchParams.get("u"), u.searchParams.get("t"));
  return new Response(r === "ok" ? "OK" : r === "invalid" ? "Invalid unsubscribe link" : "Unsubscribe failed", { status: STATUS[r], headers:{ "cache-control":"no-store" } });
}

// HEAD (link scanners/prefetchers): answer without unsubscribing anyone.
export async function onRequestHead(){
  return new Response(null, { status: 200, headers:{ "content-type":"text/html; charset=utf-8" }});
}
