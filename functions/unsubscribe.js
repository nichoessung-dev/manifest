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
  return `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;max-width:460px;margin:12vh auto;padding:0 24px;text-align:center;color:#111">
  <div style="font-size:20px;letter-spacing:3px;font-weight:700;margin-bottom:22px;">PURO&nbsp;CLASSICO</div>
  <h1 style="font-size:22px;margin:0 0 10px;">${msg}</h1>
  <p style="color:#666;font-size:15px;line-height:1.6;margin:0 0 24px;">${sub}</p>
  <a href="https://puroclassico.com" style="display:inline-block;padding:12px 28px;background:#111;color:#fff;text-decoration:none;border-radius:10px;font-weight:600;font-size:14px;">Back to Puro Classico</a></div>`;
}

async function unsubscribe(env, uid, token){
  if(!uid || !token) return false;
  const good = await hmacHex(env.UNSUB_SECRET, uid);
  // constant-time-ish compare
  if(token.length !== good.length) return false;
  let diff = 0; for(let i=0;i<good.length;i++) diff |= token.charCodeAt(i) ^ good.charCodeAt(i);
  if(diff !== 0) return false;
  const r = await fetch(`${SUPA}/rest/v1/profiles?id=eq.${encodeURIComponent(uid)}`, {
    method:"PATCH",
    headers:{ apikey: env.SUPABASE_SERVICE_KEY, Authorization:"Bearer "+env.SUPABASE_SERVICE_KEY,
      "Content-Type":"application/json", Prefer:"return=minimal" },
    body: JSON.stringify({ marketing_opt_in:false })
  });
  return r.ok;
}

export async function onRequestGet(context){
  const u = new URL(context.request.url);
  const ok = await unsubscribe(context.env, u.searchParams.get("u"), u.searchParams.get("t"));
  const html = ok ? page("You're unsubscribed", "You won't receive marketing emails from Puro Classico anymore. You can re-enable them any time from your account.")
                  : page("Link expired or invalid", "We couldn't process that unsubscribe link. Please contact us or manage email settings from your account.");
  return new Response(html, { status: ok?200:400, headers:{ "content-type":"text/html; charset=utf-8" }});
}

// RFC 8058 one-click (Gmail/Apple send POST to the List-Unsubscribe URL)
export async function onRequestPost(context){
  const u = new URL(context.request.url);
  await unsubscribe(context.env, u.searchParams.get("u"), u.searchParams.get("t"));
  return new Response("OK", { status: 200 });
}
